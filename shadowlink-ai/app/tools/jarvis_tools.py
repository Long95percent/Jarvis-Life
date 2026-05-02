"""Jarvis-specific tools registered into the unified ToolRegistry.

These tools expose life-domain data through the same MCP/registry surface
used elsewhere in the project, so Jarvis agents can be connected via
role-based whitelists instead of ad-hoc prompt injection.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from app.config import settings as app_settings
from app.core.dependencies import get_resource
from app.jarvis.agents import get_agent
from app.jarvis.collaboration_memory import remember_coordination_summary
from app.jarvis.context_bus import get_life_context_bus
from app.jarvis.user_settings import build_profile_prefix, get_settings
from app.mcp.adapters.activities_adapter import fetch_nearby_activities
from app.mcp.adapters.activities_adapter import Activity
from app.mcp.adapters.calendar_adapter import (
    add_event,
    compute_schedule_density,
    delete_event,
    get_upcoming_events,
    update_event,
)
from app.mcp.adapters.news_adapter import fetch_news
from app.mcp.adapters.weather_adapter import get_current_weather
from app.models.mcp import ToolCategory
from app.tools.base import ShadowLinkTool


def _get_llm_client():
    return get_resource("llm_client")


async def _collect_life_snapshot(
    *,
    hours_ahead: int = 48,
    include_weather: bool = True,
    include_activities: bool = True,
    include_news: bool = True,
) -> dict:
    profile = get_settings().profile
    ctx = await get_life_context_bus().get_context()
    events = get_upcoming_events(hours_ahead=hours_ahead)

    weather = None
    if include_weather:
        weather = await get_current_weather(
            latitude=profile.location.lat,
            longitude=profile.location.lng,
        )

    activities: list[dict] = []
    if include_activities:
        nearby = await fetch_nearby_activities(
            lat=profile.location.lat,
            lng=profile.location.lng,
            radius_m=2000,
            limit=5,
        )
        activities = [
            {
                "name": item.name,
                "category": item.category,
                "distance_m": item.distance_m,
                "address": item.address,
            }
            for item in nearby
        ]

    news: list[dict] = []
    if include_news:
        items = await fetch_news(limit=5)
        news = [
            {
                "title": item.title,
                "source": item.source,
                "published": item.published,
                "summary": item.summary,
            }
            for item in items
        ]

    return {
        "profile": {
            "name": profile.name,
            "location_label": profile.location.label,
            "sleep_schedule": profile.sleep_schedule.model_dump(),
        },
        "context": ctx.model_dump(),
        "events": [
            {
                "id": event.id,
                "title": event.title,
                "start": event.start.isoformat(),
                "end": event.end.isoformat(),
                "stress_weight": event.stress_weight,
            }
            for event in events
        ],
        "weather": weather,
        "activities": activities,
        "news": news,
    }


def _build_briefing_heuristics(snapshot: dict) -> tuple[list[str], list[str], list[str]]:
    context = snapshot["context"]
    events = snapshot["events"]
    weather = snapshot.get("weather") or {}

    risks: list[str] = []
    priorities: list[str] = []
    suggested_actions: list[str] = []

    if context.get("stress_level", 0) >= 7:
        risks.append("当前压力较高，决策与沟通成本会上升。")
        suggested_actions.append("优先保留最关键的一项任务，避免继续堆叠新承诺。")
    if context.get("schedule_density", 0) >= 7:
        risks.append("日程密度偏高，容易出现切换损耗与延迟。")
        suggested_actions.append("为接下来的关键事项预留缓冲时间。")
    if context.get("sleep_quality", 10) <= 4:
        risks.append("睡眠质量偏低，注意力与情绪稳定性可能受影响。")
        suggested_actions.append("降低高强度任务密度，并补充休息/饮水。")
    if weather and weather.get("is_good_weather") is False:
        risks.append("当前天气一般，户外安排需要准备备选方案。")

    if events:
        first_event = events[0]
        priorities.append(f"优先关注最近一项安排：{first_event['title']}。")
        if len(events) > 1:
            priorities.append(f"今天未来 {len(events)} 项安排需要节奏管理。")
    else:
        priorities.append("当前没有近期待办日程，可主动安排恢复或准备性任务。")

    if snapshot.get("news"):
        priorities.append("留意外部新闻变化是否影响今天的判断与沟通。")

    if not suggested_actions:
        suggested_actions.append("维持当前节奏，按优先级逐项推进。")

    return risks, priorities, suggested_actions


def _format_snapshot_for_prompt(snapshot: dict, *, include_activities: bool = True, include_news: bool = True) -> str:
    context = snapshot["context"]
    lines = [
        build_profile_prefix().strip() or "[用户画像] 暂无补充画像",
        (
            f"[Life context] stress={context.get('stress_level')}/10, "
            f"schedule_density={context.get('schedule_density')}/10, "
            f"sleep={context.get('sleep_quality')}/10, mood={context.get('mood_trend')}"
        ),
        "## Upcoming events",
    ]
    events = snapshot["events"]
    if events:
        lines.extend(
            f"- {event['title']} | {event['start']} -> {event['end']}"
            for event in events[:8]
        )
    else:
        lines.append("- (none)")

    weather = snapshot.get("weather")
    if weather:
        lines.extend([
            "## Weather",
            f"- temperature_c={weather.get('temperature_c')}, code={weather.get('weather_code')}, good={weather.get('is_good_weather')}",
        ])

    if include_activities:
        lines.append("## Nearby activities")
        activities = snapshot.get("activities") or []
        if activities:
            lines.extend(
                f"- {item['name']} ({item['category']}, {item['distance_m']}m)"
                for item in activities[:5]
            )
        else:
            lines.append("- (none)")

    if include_news:
        lines.append("## News")
        news = snapshot.get("news") or []
        if news:
            lines.extend(
                f"- {item['title']} ({item['source']})"
                for item in news[:5]
            )
        else:
            lines.append("- (none)")

    return "\n".join(lines)


def _parse_json_object(raw: str) -> dict:
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end <= start:
        return {"raw": raw.strip()}
    try:
        data = json.loads(raw[start:end])
    except json.JSONDecodeError:
        return {"raw": raw.strip()}
    return data if isinstance(data, dict) else {"raw": raw.strip()}


def _parse_iso_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None


def _to_timestamp(value: datetime | None) -> float:
    if value is None:
        return 0.0
    return value.timestamp()


def _event_lookup(event_id: str | None = None, title_query: str | None = None, hours_ahead: int = 168) -> dict | None:
    query = (title_query or "").strip().lower()
    for event in [
        {
            "id": item.id,
            "title": item.title,
            "start": item.start,
            "end": item.end,
            "stress_weight": item.stress_weight,
        }
        for item in get_upcoming_events(hours_ahead=hours_ahead)
    ]:
        if event_id and event["id"] == event_id:
            return event
        if query and query in event["title"].lower():
            return event
    return None


def _serialize_event(event: dict) -> dict:
    return {
        "id": event["id"],
        "title": event["title"],
        "start": event["start"].isoformat(),
        "end": event["end"].isoformat(),
        "stress_weight": event["stress_weight"],
    }


def _parse_plan_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None


def _infer_plan_days(text: str, target_start: str | None, target_end: str | None) -> int:
    lowered = text.lower()
    if target_start and target_end:
        start = _parse_plan_date(target_start)
        end = _parse_plan_date(target_end)
        if start is not None and end is not None:
            return max(1, min(60, (end.date() - start.date()).days + 1))
    if any(marker in text for marker in ["一个月", "30天", "30 天"]) or "30 days" in lowered:
        return 30
    if any(marker in text for marker in ["两周", "2周", "14天", "14 天"]) or "two weeks" in lowered:
        return 14
    if any(marker in text for marker in ["一周", "7天", "7 天"]) or "week" in lowered:
        return 7
    if any(marker in text for marker in ["长期", "雅思", "旅行", "旅游", "备考", "考试"]):
        return 14
    return 3


def _build_daily_plan(
    *,
    title: str,
    user_request: str,
    classification: str,
    target_start: str | None,
    target_end: str | None,
) -> list[dict]:
    start_dt = _parse_plan_date(target_start)
    start_date = start_dt.date() if start_dt is not None else datetime.now(ZoneInfo("Asia/Shanghai")).date()
    total_days = _infer_plan_days(user_request, target_start, target_end)
    lowered = user_request.lower()

    if "雅思" in user_request or "ielts" in lowered:
        templates = [
            ("雅思听力精听与错题记录", "完成 1 组听力精听，记录生词、定位词和错因。", 60),
            ("雅思阅读限时训练", "完成 1 篇阅读限时训练，复盘题型和定位策略。", 60),
            ("雅思口语素材与跟读", "整理 1 个口语话题素材并完成跟读录音。", 45),
            ("雅思写作结构训练", "完成 1 个小作文/大作文提纲或段落练习。", 75),
            ("雅思单词与复盘", "复习高频词与本周错题，更新薄弱点清单。", 45),
        ]
    elif "旅游" in user_request or "旅行" in user_request or "玩" in user_request:
        templates = [
            ("确认旅行约束", "确认目的地、预算、同行人、出发日期和不可接受条件。", 30),
            ("交通与住宿初筛", "筛选交通方案和住宿区域，记录价格与通勤风险。", 60),
            ("路线与活动草案", "列出每日路线、核心活动和备选方案。", 60),
            ("预订与证件检查", "检查证件、签证、预订状态和付款风险。", 45),
            ("行李与天气清单", "根据天气、活动强度和行程生成行李清单。", 30),
        ]
    else:
        templates = [
            (f"{title}：明确目标", "明确完成标准、约束和下一步动作。", 30),
            (f"{title}：推进执行", "完成一个可交付的小步骤，并记录阻塞。", 45),
            (f"{title}：复盘调整", "复盘进展，调整剩余安排和优先级。", 30),
        ]

    daily_plan: list[dict] = []
    for index in range(total_days):
        day = start_date + timedelta(days=index)
        task_title, description, minutes = templates[index % len(templates)]
        daily_plan.append({
            "date": day.isoformat(),
            "title": task_title,
            "description": description,
            "start_time": "20:00",
            "end_time": f"{21 + (minutes > 60):02d}:00" if minutes >= 60 else "20:45",
            "estimated_minutes": minutes,
            "status": "pending",
            "sort_order": index,
            "classification": classification,
        })
    return daily_plan


def _get_window_events(window_start: datetime, window_end: datetime) -> list[dict]:
    horizon_hours = max(24, int((_to_timestamp(window_end) - datetime.utcnow().timestamp()) / 3600) + 24)
    events = [
        {
            "id": item.id,
            "title": item.title,
            "start": item.start,
            "end": item.end,
            "stress_weight": item.stress_weight,
        }
        for item in get_upcoming_events(hours_ahead=horizon_hours)
    ]
    return [
        event
        for event in events
        if _to_timestamp(event["end"]) > _to_timestamp(window_start)
        and _to_timestamp(event["start"]) < _to_timestamp(window_end)
    ]


def _normalized_restrictions(restrictions: list[str] | None) -> set[str]:
    return {item.strip().lower() for item in (restrictions or []) if item and item.strip()}


def _meal_allowed(tags: set[str], restrictions: set[str]) -> bool:
    if not restrictions:
        return True
    blocked_pairs = {
        "vegan": {"meat", "fish", "egg", "dairy"},
        "vegetarian": {"meat", "fish"},
        "dairy_free": {"dairy"},
        "lactose_intolerant": {"dairy"},
        "gluten_free": {"gluten"},
        "nut_free": {"nuts"},
    }
    blocked: set[str] = set()
    for restriction in restrictions:
        blocked |= blocked_pairs.get(restriction, set())
    return tags.isdisjoint(blocked)


def _append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _distance_to_minutes(distance_m: int, mode: str) -> int:
    speed_m_per_min = {
        "walking": 80,
        "cycling": 220,
        "transit": 250,
        "driving": 450,
    }.get(mode, 80)
    return max(3, int(distance_m / speed_m_per_min))


async def _fetch_rankable_activities(
    *,
    limit: int = 8,
    categories: list[str] | None = None,
) -> list[dict]:
    profile = get_settings().profile.location
    acts = await fetch_nearby_activities(
        lat=profile.lat,
        lng=profile.lng,
        categories=categories or None,
        limit=limit,
    )
    return [
        {
            "name": item.name,
            "category": item.category,
            "distance_m": item.distance_m,
            "lat": item.lat,
            "lng": item.lng,
            "address": item.address,
        }
        for item in acts
    ]


def _find_activity_candidate(activities: list[dict], activity_name: str) -> dict | None:
    query = activity_name.strip().lower()
    for item in activities:
        if query == item["name"].strip().lower():
            return item
    for item in activities:
        if query in item["name"].strip().lower():
            return item
    return None


def _build_free_slots(
    *,
    window_start: datetime,
    window_end: datetime,
    duration_minutes: int,
    preferred_period: str = "any",
    buffer_minutes: int = 10,
) -> list[dict]:
    if _to_timestamp(window_end) <= _to_timestamp(window_start):
        return []

    events = sorted(
        _get_window_events(window_start, window_end),
        key=lambda event: _to_timestamp(event["start"]),
    )
    slots: list[dict] = []
    cursor = window_start
    required_seconds = duration_minutes * 60
    buffer_seconds = buffer_minutes * 60

    def _period_match(slot_start: datetime) -> bool:
        hour = slot_start.hour
        if preferred_period == "morning":
            return 6 <= hour < 12
        if preferred_period == "afternoon":
            return 12 <= hour < 18
        if preferred_period == "evening":
            return 18 <= hour < 23
        return True

    def _align_to_preferred_period(slot_start: datetime, slot_end: datetime) -> datetime | None:
        if preferred_period == "any":
            return slot_start

        period_start_hour = {"morning": 6, "afternoon": 12, "evening": 18}[preferred_period]
        period_end_hour = {"morning": 12, "afternoon": 18, "evening": 23}[preferred_period]

        candidate = slot_start
        if candidate.hour < period_start_hour:
            candidate = candidate.replace(hour=period_start_hour, minute=0, second=0, microsecond=0)

        if candidate.hour >= period_end_hour:
            return None

        latest_start = datetime.utcfromtimestamp(_to_timestamp(slot_end) - required_seconds)
        if _to_timestamp(candidate) > _to_timestamp(latest_start):
            return None
        return candidate

    for event in events:
        gap_end_ts = _to_timestamp(event["start"]) - buffer_seconds
        gap_end = datetime.utcfromtimestamp(gap_end_ts)
        if gap_end_ts - _to_timestamp(cursor) >= required_seconds:
            candidate_start = _align_to_preferred_period(cursor, gap_end)
            if candidate_start is not None and _period_match(candidate_start):
                slots.append({
                    "start": candidate_start,
                    "end": gap_end,
                })
        cursor = max(
            cursor,
            datetime.utcfromtimestamp(_to_timestamp(event["end"]) + buffer_seconds),
        )

    if _to_timestamp(window_end) - _to_timestamp(cursor) >= required_seconds:
        candidate_start = _align_to_preferred_period(cursor, window_end)
        if candidate_start is not None and _period_match(candidate_start):
            slots.append({"start": candidate_start, "end": window_end})

    return slots


def _parse_clock_time(raw: str | None, fallback: str) -> datetime:
    clock = raw or fallback
    hour, minute = [int(part) for part in clock.split(":")]
    now = datetime.utcnow()
    return now.replace(hour=hour, minute=minute, second=0, microsecond=0)


def _clock_on_reference_day(clock_raw: str | None, fallback: str, reference: datetime) -> datetime:
    clock = clock_raw or fallback
    hour, minute = [int(part) for part in clock.split(":")]
    return reference.replace(hour=hour, minute=minute, second=0, microsecond=0)


_NUTRITION_REFERENCE: dict[str, dict] = {
    "coffee": {
        "aliases": {"coffee", "americano", "latte", "espresso"},
        "highlights": ["提神快", "几乎不含热量（不额外加糖时）"],
        "caffeine_mg": 95,
        "best_for": ["晨间启动", "午前专注"],
        "cautions": ["下午晚些时候饮用可能影响入睡", "空腹大量饮用可能刺激胃部"],
        "tags": {"drink", "caffeine"},
    },
    "green tea": {
        "aliases": {"green tea", "matcha", "tea"},
        "highlights": ["咖啡因较咖啡温和", "含茶多酚"],
        "caffeine_mg": 35,
        "best_for": ["午前轻提神", "餐后清爽补水"],
        "cautions": ["晚上饮用仍可能影响睡眠"],
        "tags": {"drink", "caffeine"},
    },
    "oatmeal": {
        "aliases": {"oatmeal", "oats", "燕麦"},
        "highlights": ["富含可溶性膳食纤维", "释放能量更平稳"],
        "cautions": ["若对麸质非常敏感需选择认证无麸质燕麦"],
        "best_for": ["早餐", "稳定能量"],
        "tags": {"gluten_optional", "vegan"},
    },
    "greek yogurt": {
        "aliases": {"greek yogurt", "yogurt", "酸奶"},
        "highlights": ["蛋白质较高", "适合作为早餐或加餐"],
        "cautions": ["乳糖不耐受或 dairy-free 人群需替换"],
        "best_for": ["早餐", "训练后加餐"],
        "tags": {"dairy", "vegetarian"},
    },
    "salmon": {
        "aliases": {"salmon", "三文鱼"},
        "highlights": ["优质蛋白", "富含 omega-3"],
        "cautions": ["不适合素食或 vegan 人群"],
        "best_for": ["高压日修复", "晚餐蛋白来源"],
        "tags": {"fish"},
    },
    "banana": {
        "aliases": {"banana", "香蕉"},
        "highlights": ["补充碳水与钾", "容易消化"],
        "cautions": ["单独食用饱腹感有限，建议搭配蛋白"],
        "best_for": ["会前快速补能", "下午加餐"],
        "tags": {"vegan"},
    },
    "tofu": {
        "aliases": {"tofu", "豆腐"},
        "highlights": ["植物蛋白友好", "烹饪适配度高"],
        "cautions": ["若对大豆敏感需避免"],
        "best_for": ["素食正餐", "清淡晚餐"],
        "tags": {"vegan", "vegetarian"},
    },
    "eggs": {
        "aliases": {"eggs", "egg", "鸡蛋"},
        "highlights": ["高蛋白", "早餐准备方便"],
        "cautions": ["vegan 人群需避免"],
        "best_for": ["早餐", "快速补蛋白"],
        "tags": {"egg", "vegetarian"},
    },
    "nuts": {
        "aliases": {"nuts", "almonds", "walnuts", "坚果"},
        "highlights": ["健康脂肪", "便携加餐"],
        "cautions": ["坚果过敏人群需避免", "热量密度高需控制份量"],
        "best_for": ["下午加餐", "延长饱腹感"],
        "tags": {"nuts", "vegan"},
    },
}


_MEAL_TEMPLATES: list[dict] = [
    {
        "name": "早餐：燕麦 + 香蕉 + 无糖酸奶/豆乳",
        "meal_type": "breakfast",
        "tags": {"vegetarian"},
        "benefits": ["稳定上午能量", "准备快", "适合高压日"],
    },
    {
        "name": "早餐：鸡蛋全麦三明治 + 一份水果",
        "meal_type": "breakfast",
        "tags": {"egg", "gluten"},
        "benefits": ["蛋白充足", "会议日前更耐饿"],
    },
    {
        "name": "午餐：三文鱼/豆腐 + 米饭 + 绿叶菜",
        "meal_type": "lunch",
        "tags": {"fish"},
        "benefits": ["兼顾蛋白与恢复", "适合高压力工作日"],
    },
    {
        "name": "午餐：鸡胸/豆腐能量碗 + 藜麦 + 蔬菜",
        "meal_type": "lunch",
        "tags": {"meat"},
        "benefits": ["饱腹稳定", "不容易午后犯困"],
    },
    {
        "name": "晚餐：清炒豆腐蔬菜 + 杂粮饭",
        "meal_type": "dinner",
        "tags": {"vegan"},
        "benefits": ["清淡收尾", "降低夜间负担"],
    },
    {
        "name": "晚餐：味噌汤 + 烤鱼/豆腐 + 时蔬",
        "meal_type": "dinner",
        "tags": {"fish"},
        "benefits": ["补充蛋白", "适合恢复型晚餐"],
    },
    {
        "name": "加餐：坚果 + 水果",
        "meal_type": "snack",
        "tags": {"nuts", "vegan"},
        "benefits": ["防止下午能量塌陷", "便携"],
    },
    {
        "name": "加餐：酸奶/豆乳 + 一根香蕉",
        "meal_type": "snack",
        "tags": {"dairy", "vegan_option"},
        "benefits": ["快速补能", "适合任务切换间隙"],
    },
]


class JarvisContextSnapshotInput(BaseModel):
    include_events: bool = Field(default=True, description="Whether to include upcoming events in the response")


class JarvisContextSnapshotTool(ShadowLinkTool):
    name: str = "jarvis_context_snapshot"
    description: str = "Read the user's latest life context: stress, schedule density, sleep, mood, and active events."
    args_schema: type[BaseModel] = JarvisContextSnapshotInput
    category: ToolCategory = ToolCategory.SYSTEM

    def _run(self, include_events: bool = True) -> dict:
        raise NotImplementedError("Use async version")

    async def _arun(self, include_events: bool = True) -> dict:
        ctx = await get_life_context_bus().get_context()
        data = ctx.model_dump()
        if not include_events:
            data["active_events"] = []
        return data


class JarvisCalendarUpcomingInput(BaseModel):
    hours_ahead: int = Field(default=48, ge=1, le=168, description="How many hours ahead to inspect")
    limit: int = Field(default=10, ge=1, le=20, description="Maximum events to return")
    start: str | None = Field(default=None, description="Optional ISO8601 window start")
    end: str | None = Field(default=None, description="Optional ISO8601 window end")


class JarvisCalendarUpcomingTool(ShadowLinkTool):
    name: str = "jarvis_calendar_upcoming"
    description: str = "List upcoming calendar events with ids, titles, and times."
    args_schema: type[BaseModel] = JarvisCalendarUpcomingInput
    category: ToolCategory = ToolCategory.SYSTEM

    def _run(self, hours_ahead: int = 48, limit: int = 10, start: str | None = None, end: str | None = None) -> list[dict]:
        raise NotImplementedError("Use async version")

    async def _arun(self, hours_ahead: int = 48, limit: int = 10, start: str | None = None, end: str | None = None) -> list[dict]:
        if start and end:
            from app.mcp.adapters.calendar_adapter import get_events_between

            events = get_events_between(datetime.fromisoformat(start), datetime.fromisoformat(end))
        else:
            events = get_upcoming_events(hours_ahead=hours_ahead)
        return [
            {
                "id": event.id,
                "title": event.title,
                "start": event.start.isoformat(),
                "end": event.end.isoformat(),
                "stress_weight": event.stress_weight,
            }
            for event in events[:limit]
        ]


class JarvisWeatherInput(BaseModel):
    latitude: float | None = Field(default=None, description="Optional latitude override")
    longitude: float | None = Field(default=None, description="Optional longitude override")


class JarvisWeatherTool(ShadowLinkTool):
    name: str = "jarvis_weather_snapshot"
    description: str = "Fetch the latest local weather near the user's configured location."
    args_schema: type[BaseModel] = JarvisWeatherInput
    category: ToolCategory = ToolCategory.SEARCH

    def _run(self, latitude: float | None = None, longitude: float | None = None) -> dict:
        raise NotImplementedError("Use async version")

    async def _arun(self, latitude: float | None = None, longitude: float | None = None) -> dict:
        profile = get_settings().profile.location
        lat = latitude if latitude is not None else profile.lat
        lng = longitude if longitude is not None else profile.lng
        weather = await get_current_weather(latitude=lat, longitude=lng)
        return {
            "location_label": profile.label,
            "latitude": lat,
            "longitude": lng,
            **weather,
        }


class JarvisActivitiesInput(BaseModel):
    radius_m: int = Field(default=2000, ge=200, le=10000, description="Search radius in meters")
    limit: int = Field(default=5, ge=1, le=20, description="Maximum activities to return")
    categories: list[str] = Field(default_factory=list, description="Optional category filters")


class JarvisActivitiesTool(ShadowLinkTool):
    name: str = "jarvis_local_activities"
    description: str = "Find nearby activities and places that fit the user's current location."
    args_schema: type[BaseModel] = JarvisActivitiesInput
    category: ToolCategory = ToolCategory.SEARCH

    def _run(self, radius_m: int = 2000, limit: int = 5, categories: list[str] | None = None) -> list[dict]:
        raise NotImplementedError("Use async version")

    async def _arun(self, radius_m: int = 2000, limit: int = 5, categories: list[str] | None = None) -> list[dict]:
        profile = get_settings().profile.location
        activities = await fetch_nearby_activities(
            lat=profile.lat,
            lng=profile.lng,
            radius_m=radius_m,
            categories=categories or None,
            limit=limit,
        )
        return [
            {
                "name": item.name,
                "category": item.category,
                "lat": item.lat,
                "lng": item.lng,
                "distance_m": item.distance_m,
                "address": item.address,
            }
            for item in activities
        ]


class JarvisLocalLifeSearchInput(BaseModel):
    query: str = Field(description="User-facing local-life search query")
    category: str | None = Field(default=None, description="Optional category such as food, recovery, activity, market")
    radius_m: int = Field(default=3000, ge=200, le=20000, description="Maximum distance from configured user location")
    window_days: int = Field(default=14, ge=1, le=60, description="Future search window in days")
    limit: int = Field(default=5, ge=1, le=10, description="Maximum local-life items to return")
    min_date: str | None = Field(default=None, description="Earliest valid date in YYYY-MM-DD; defaults to today")


class JarvisLocalLifeSearchTool(ShadowLinkTool):
    name: str = "jarvis_local_life_search"
    description: str = (
        "Find nearby, recent local activities or local-life opportunities. "
        "Results are filtered to items whose deadline/end date is today or later and are cached for roundtable/proactive use."
    )
    args_schema: type[BaseModel] = JarvisLocalLifeSearchInput
    category: ToolCategory = ToolCategory.SEARCH

    def _run(
        self,
        query: str,
        category: str | None = None,
        radius_m: int = 3000,
        window_days: int = 14,
        limit: int = 5,
        min_date: str | None = None,
    ) -> list[dict]:
        raise NotImplementedError("Use async version")

    async def _arun(
        self,
        query: str,
        category: str | None = None,
        radius_m: int = 3000,
        window_days: int = 14,
        limit: int = 5,
        min_date: str | None = None,
    ) -> list[dict]:
        from app.jarvis.local_life_search import LocalLifeSearchQuery, LocalLifeSearchService

        service = LocalLifeSearchService()
        items = await service.search(
            LocalLifeSearchQuery(
                query=query,
                category=category,
                radius_m=radius_m,
                window_days=window_days,
                limit=limit,
                min_date=min_date,
            )
        )
        return [item.to_dict() if hasattr(item, "to_dict") else dict(item) for item in items]


class JarvisNewsDigestInput(BaseModel):
    limit: int = Field(default=5, ge=1, le=10, description="Maximum headlines to return")


class JarvisNewsDigestTool(ShadowLinkTool):
    name: str = "jarvis_news_digest"
    description: str = "Fetch a short digest of recent news headlines."
    args_schema: type[BaseModel] = JarvisNewsDigestInput
    category: ToolCategory = ToolCategory.SEARCH

    def _run(self, limit: int = 5) -> list[dict]:
        raise NotImplementedError("Use async version")

    async def _arun(self, limit: int = 5) -> list[dict]:
        items = await fetch_news(limit=limit)
        return [
            {
                "title": item.title,
                "source": item.source,
                "published": item.published,
                "summary": item.summary,
                "link": item.link,
            }
            for item in items
        ]


class JarvisCalendarAddInput(BaseModel):
    title: str = Field(description="Event title")
    start: str = Field(description="Start time in ISO8601 format")
    end: str = Field(description="End time in ISO8601 format")
    stress_weight: float = Field(default=1.0, description="Stress impact weight for schedule density")
    location: str | None = Field(default=None, description="Optional event location")
    notes: str | None = Field(default=None, description="Optional event notes")
    created_reason: str | None = Field(default=None, description="Why this event is suggested")
    route_required: bool = Field(default=False, description="Whether route planning may be needed")


class JarvisCalendarAddTool(ShadowLinkTool):
    name: str = "jarvis_calendar_add"
    description: str = "Create a new calendar event and refresh life context schedule density."
    args_schema: type[BaseModel] = JarvisCalendarAddInput
    category: ToolCategory = ToolCategory.SYSTEM
    requires_confirmation: bool = True

    def _run(
        self,
        title: str,
        start: str,
        end: str,
        stress_weight: float = 1.0,
        location: str | None = None,
        notes: str | None = None,
        created_reason: str | None = None,
        route_required: bool = False,
    ) -> dict:
        raise NotImplementedError("Use async version")

    async def _arun(
        self,
        title: str,
        start: str,
        end: str,
        stress_weight: float = 1.0,
        location: str | None = None,
        notes: str | None = None,
        created_reason: str | None = None,
        route_required: bool = False,
    ) -> dict:
        from datetime import datetime

        if not title.strip():
            return {"type": "calendar.add", "ok": False, "error": "missing title"}

        try:
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
        except ValueError as exc:
            return {"type": "calendar.add", "ok": False, "error": f"invalid datetime: {exc}"}

        event = add_event(
            title.strip(),
            start_dt,
            end_dt,
            stress_weight,
            location=location,
            notes=notes,
            source="agent_tool",
            created_reason=created_reason,
            route_required=route_required,
        )
        density = compute_schedule_density()
        active_events = get_upcoming_events(hours_ahead=24)
        await get_life_context_bus().update_fields(
            {"schedule_density": density, "active_events": active_events},
            source="agent_tool",
        )
        return {
            "type": "calendar.add",
            "ok": True,
            "event_id": event.id,
            "title": event.title,
            "start": event.start.isoformat(),
            "end": event.end.isoformat(),
            "new_schedule_density": density,
        }


class JarvisCalendarDeleteInput(BaseModel):
    event_id: str = Field(description="Existing calendar event id")


class JarvisCalendarDeleteTool(ShadowLinkTool):
    name: str = "jarvis_calendar_delete"
    description: str = "Delete a calendar event by id and refresh life context schedule density."
    args_schema: type[BaseModel] = JarvisCalendarDeleteInput
    category: ToolCategory = ToolCategory.SYSTEM
    requires_confirmation: bool = True

    def _run(self, event_id: str) -> dict:
        raise NotImplementedError("Use async version")

    async def _arun(self, event_id: str) -> dict:
        clean_id = event_id.strip()
        if not clean_id:
            return {"type": "calendar.delete", "ok": False, "error": "missing event_id"}

        ok = delete_event(clean_id)
        if not ok:
            return {"type": "calendar.delete", "ok": False, "error": f"event {clean_id} not found"}

        density = compute_schedule_density()
        active_events = get_upcoming_events(hours_ahead=24)
        await get_life_context_bus().update_fields(
            {"schedule_density": density, "active_events": active_events},
            source="agent_tool",
        )
        return {
            "type": "calendar.delete",
            "ok": True,
            "event_id": clean_id,
            "new_schedule_density": density,
        }


class JarvisCalendarUpdateInput(BaseModel):
    event_id: str = Field(description="Existing calendar event id")
    title: str | None = Field(default=None, description="Optional new title")
    start: str | None = Field(default=None, description="Optional new start time in ISO8601 format")
    end: str | None = Field(default=None, description="Optional new end time in ISO8601 format")
    stress_weight: float | None = Field(default=None, description="Optional updated stress impact weight")
    location: str | None = Field(default=None, description="Optional new location")
    notes: str | None = Field(default=None, description="Optional new notes")
    status: str | None = Field(default=None, description="Optional status: confirmed, completed, postponed, conflict")
    route_required: bool | None = Field(default=None, description="Whether route planning may be needed")


class JarvisCalendarUpdateTool(ShadowLinkTool):
    name: str = "jarvis_calendar_update"
    description: str = "Update an existing calendar event and refresh life context schedule density."
    args_schema: type[BaseModel] = JarvisCalendarUpdateInput
    category: ToolCategory = ToolCategory.SYSTEM
    requires_confirmation: bool = True

    def _run(
        self,
        event_id: str,
        title: str | None = None,
        start: str | None = None,
        end: str | None = None,
        stress_weight: float | None = None,
        location: str | None = None,
        notes: str | None = None,
        status: str | None = None,
        route_required: bool | None = None,
    ) -> dict:
        raise NotImplementedError("Use async version")

    async def _arun(
        self,
        event_id: str,
        title: str | None = None,
        start: str | None = None,
        end: str | None = None,
        stress_weight: float | None = None,
        location: str | None = None,
        notes: str | None = None,
        status: str | None = None,
        route_required: bool | None = None,
    ) -> dict:
        from datetime import datetime

        clean_id = event_id.strip()
        if not clean_id:
            return {"type": "calendar.update", "ok": False, "error": "missing event_id"}

        kwargs: dict[str, object] = {}
        if title is not None:
            kwargs["title"] = title
        if start:
            try:
                kwargs["start"] = datetime.fromisoformat(start.replace("Z", "+00:00"))
            except ValueError as exc:
                return {"type": "calendar.update", "ok": False, "error": f"invalid start: {exc}"}
        if end:
            try:
                kwargs["end"] = datetime.fromisoformat(end.replace("Z", "+00:00"))
            except ValueError as exc:
                return {"type": "calendar.update", "ok": False, "error": f"invalid end: {exc}"}
        if stress_weight is not None:
            kwargs["stress_weight"] = stress_weight
        if location is not None:
            kwargs["location"] = location
        if notes is not None:
            kwargs["notes"] = notes
        if status is not None:
            kwargs["status"] = status
        if route_required is not None:
            kwargs["route_required"] = route_required

        event = update_event(clean_id, **kwargs)
        if event is None:
            return {"type": "calendar.update", "ok": False, "error": f"event {clean_id} not found"}

        density = compute_schedule_density()
        active_events = get_upcoming_events(hours_ahead=24)
        await get_life_context_bus().update_fields(
            {"schedule_density": density, "active_events": active_events},
            source="agent_tool",
        )
        return {
            "type": "calendar.update",
            "ok": True,
            "event_id": event.id,
            "title": event.title,
            "start": event.start.isoformat(),
            "end": event.end.isoformat(),
            "new_schedule_density": density,
        }


class JarvisContextUpdateInput(BaseModel):
    stress_level: float | None = Field(default=None, description="Updated stress level from 0 to 10")
    schedule_density: float | None = Field(default=None, description="Updated schedule density from 0 to 10")
    sleep_quality: float | None = Field(default=None, description="Updated sleep quality from 0 to 10")
    mood_trend: str | None = Field(default=None, description="Updated mood trend")


class JarvisContextUpdateTool(ShadowLinkTool):
    name: str = "jarvis_context_update"
    description: str = "Update the user's life context fields such as stress, sleep, schedule density, or mood."
    args_schema: type[BaseModel] = JarvisContextUpdateInput
    category: ToolCategory = ToolCategory.SYSTEM
    requires_confirmation: bool = True

    def _run(
        self,
        stress_level: float | None = None,
        schedule_density: float | None = None,
        sleep_quality: float | None = None,
        mood_trend: str | None = None,
    ) -> dict:
        raise NotImplementedError("Use async version")

    async def _arun(
        self,
        stress_level: float | None = None,
        schedule_density: float | None = None,
        sleep_quality: float | None = None,
        mood_trend: str | None = None,
    ) -> dict:
        fields = {
            key: value
            for key, value in {
                "stress_level": stress_level,
                "schedule_density": schedule_density,
                "sleep_quality": sleep_quality,
                "mood_trend": mood_trend,
            }.items()
            if value is not None
        }
        if not fields:
            return {"type": "context.set", "ok": False, "error": "no valid fields"}

        await get_life_context_bus().update_fields(fields, source="agent_tool")
        return {"type": "context.set", "ok": True, "fields": fields}


class MaxwellTaskCandidate(BaseModel):
    title: str = Field(description="Task title")
    deadline: str | None = Field(default=None, description="Optional deadline in ISO8601 format")
    importance: int = Field(default=3, ge=1, le=5, description="Importance from 1 to 5")
    estimated_minutes: int = Field(default=30, ge=5, le=480, description="Estimated effort in minutes")
    energy_level: str = Field(default="medium", description="Required energy: low, medium, or high")
    must_do: bool = Field(default=False, description="Whether this task is mandatory today")


class MaxwellDeadlineItem(BaseModel):
    title: str = Field(description="Deadline item title")
    due_at: str = Field(description="Deadline timestamp in ISO8601 format")
    estimated_minutes: int = Field(default=30, ge=5, le=480, description="Estimated effort to complete")
    importance: int = Field(default=3, ge=1, le=5, description="Importance from 1 to 5")


class JarvisMeetingBriefInput(BaseModel):
    event_id: str | None = Field(default=None, description="Target calendar event id")
    title_query: str | None = Field(default=None, description="Fallback title match when event_id is unknown")
    objective: str | None = Field(default=None, description="Optional meeting objective")
    agenda: list[str] = Field(default_factory=list, description="Optional agenda bullets")


class JarvisMeetingBriefTool(ShadowLinkTool):
    name: str = "jarvis_meeting_brief"
    description: str = "Prepare a concise meeting brief with timing, checklist, and schedule risks."
    args_schema: type[BaseModel] = JarvisMeetingBriefInput
    category: ToolCategory = ToolCategory.SYSTEM

    def _run(
        self,
        event_id: str | None = None,
        title_query: str | None = None,
        objective: str | None = None,
        agenda: list[str] | None = None,
    ) -> dict:
        raise NotImplementedError("Use async version")

    async def _arun(
        self,
        event_id: str | None = None,
        title_query: str | None = None,
        objective: str | None = None,
        agenda: list[str] | None = None,
    ) -> dict:
        event = _event_lookup(event_id=event_id, title_query=title_query)
        if event is None:
            return {"type": "meeting.brief", "ok": False, "error": "meeting not found"}

        now = datetime.utcnow()
        start_ts = _to_timestamp(event["start"])
        now_ts = now.timestamp()
        minutes_until = max(0, int((start_ts - now_ts) / 60))
        duration_minutes = max(1, int((_to_timestamp(event["end"]) - start_ts) / 60))
        ctx = await get_life_context_bus().get_context()

        all_events = [
            {
                "id": item.id,
                "title": item.title,
                "start": item.start,
                "end": item.end,
            }
            for item in get_upcoming_events(hours_ahead=168)
        ]
        previous_event = None
        next_event = None
        for candidate in all_events:
            if candidate["id"] == event["id"]:
                continue
            if _to_timestamp(candidate["end"]) <= start_ts:
                if previous_event is None or _to_timestamp(candidate["end"]) > _to_timestamp(previous_event["end"]):
                    previous_event = candidate
            elif _to_timestamp(candidate["start"]) >= _to_timestamp(event["end"]):
                if next_event is None or _to_timestamp(candidate["start"]) < _to_timestamp(next_event["start"]):
                    next_event = candidate

        risks: list[str] = []
        if minutes_until < 30:
            risks.append("距离会议开始不足 30 分钟，准备时间偏紧。")
        if ctx.schedule_density >= 7:
            risks.append("今天整体日程密度较高，会议前后容易被打断。")
        if previous_event and int((start_ts - _to_timestamp(previous_event["end"])) / 60) < 15:
            risks.append("会议前缓冲少于 15 分钟，建议提前收尾上一项安排。")
        if next_event and int((_to_timestamp(next_event["start"]) - _to_timestamp(event["end"])) / 60) < 15:
            risks.append("会议结束后衔接过紧，结论要在会内当场收束。")

        checklist = [
            "确认会议目标与需要达成的结论。",
            "准备 2-3 个关键讨论点，避免会上发散。",
            "提前打开相关材料或链接，减少临场切换成本。",
        ]
        if agenda:
            checklist.insert(0, "本次议程重点：" + "；".join(agenda[:4]))
        if objective:
            checklist.insert(0, f"本次会议目标：{objective}")

        summary = (
            f"{event['title']} 将在 {minutes_until} 分钟后开始，预计持续 {duration_minutes} 分钟。"
            if minutes_until > 0
            else f"{event['title']} 已进入会前窗口，建议立刻进入准备状态。"
        )

        return {
            "type": "meeting.brief",
            "ok": True,
            "event": _serialize_event(event),
            "minutes_until_start": minutes_until,
            "duration_minutes": duration_minutes,
            "objective": objective or "",
            "agenda": agenda or [],
            "risks": risks,
            "checklist": checklist,
            "summary": summary,
        }


class JarvisTaskPlanDecomposeInput(BaseModel):
    user_request: str = Field(description="Original user request or routed task intent")
    source_agent: str = Field(default="maxwell", description="Agent that detected or owns this task")
    target_start: str | None = Field(default=None, description="Optional preferred project start date/time in ISO8601")
    target_end: str | None = Field(default=None, description="Optional preferred project end/deadline in ISO8601")
    user_constraints: list[str] = Field(default_factory=list, description="Known constraints and preferences")


class JarvisTaskPlanDecomposeTool(ShadowLinkTool):
    name: str = "jarvis_task_plan_decompose"
    description: str = (
        "Maxwell-only skill: classify and decompose short/long/future user goals into a background task plan. "
        "For long-term, recurring, exam-prep, travel-prep, or future projects, the returned plan includes daily_plan "
        "items that are automatically persisted as editable daily execution items when the user explicitly asks for scheduling."
    )
    args_schema: type[BaseModel] = JarvisTaskPlanDecomposeInput
    category: ToolCategory = ToolCategory.SYSTEM
    requires_confirmation: bool = False

    @staticmethod
    def _should_write_to_calendar(text: str) -> bool:
        return any(marker in text for marker in ["写入日程", "加入日程", "放进日程", "排进日程", "安排学习计划", "帮我安排", "写进日程"])

    @staticmethod
    def _secretary_intent(text: str) -> str:
        if any(marker in text for marker in ["重排", "重新安排", "延期", "没完成", "未完成"]):
            return "reschedule_plan"
        if any(marker in text for marker in ["未来", "30天", "30 天", "一个月", "长期", "雅思", "ielts", "考研", "考试"]):
            return "long_plan"
        return "short_schedule"

    def _run(
        self,
        user_request: str,
        source_agent: str = "maxwell",
        target_start: str | None = None,
        target_end: str | None = None,
        user_constraints: list[str] | None = None,
    ) -> dict:
        raise NotImplementedError("Use async version")

    async def _arun(
        self,
        user_request: str,
        source_agent: str = "maxwell",
        target_start: str | None = None,
        target_end: str | None = None,
        user_constraints: list[str] | None = None,
    ) -> dict:
        text = user_request.strip()
        if not text:
            return {"type": "task.plan", "ok": False, "error": "missing user_request"}

        if self._should_write_to_calendar(text):
            llm_client = _get_llm_client()
            if llm_client is not None:
                from app.jarvis.secretary_planning_service import run_secretary_plan_request

                today = (target_start or datetime.utcnow().isoformat())[:10]
                result = await run_secretary_plan_request(
                    intent=self._secretary_intent(text),
                    message=text,
                    today=today,
                    llm_client=llm_client,
                    timezone=None,
                    auto_project_calendar=True,
                )
                return {
                    "type": "task.plan",
                    "ok": True,
                    "pending_background_task": False,
                    "source": "secretary_planning_service",
                    "intent": result.get("intent"),
                    "summary": result.get("summary"),
                    "plan": result.get("plan"),
                    "plan_days": result.get("plan_days", []),
                    "calendar_events": result.get("calendar_events", []),
                    "daily_plan_count": len(result.get("plan_days", [])),
                }

        lowered = text.lower()
        long_markers = ["雅思", "ielts", "考研", "考试", "一个月", "暑假", "长期", "今年", "旅行", "旅游", "搬家", "作品集"]
        recurring_markers = ["每天", "每周", "每月", "长期", "一直", "坚持"]
        future_markers = ["暑假", "之后", "以后", "一个月后", "放假", "明年", "下个月"]
        if any(marker in lowered for marker in ["ielts"]):
            classification = "long_project"
        elif any(marker in text for marker in future_markers):
            classification = "future_project"
        elif any(marker in text for marker in recurring_markers):
            classification = "recurring_plan"
        elif any(marker in text for marker in long_markers):
            classification = "long_project"
        else:
            classification = "short_project"

        now = datetime.utcnow()
        start_hint = target_start or now.isoformat()
        end_hint = target_end
        title = text[:32]
        if "雅思" in text or "ielts" in lowered:
            title = "雅思备考计划"
            milestones = [
                {"title": "确认目标分数与考试日期", "target_date": target_start or "待用户确认"},
                {"title": "完成词汇与听力第一轮", "target_date": target_end or "开始后第 4 周"},
                {"title": "完成一次全真模拟与复盘", "target_date": target_end or "开始后第 6 周"},
            ]
            subtasks = [
                {"title": "听力/阅读训练", "schedule_policy": "每周 3 次，每次 60 分钟", "estimated_minutes": 60},
                {"title": "口语素材与跟读", "schedule_policy": "每周 2 次，每次 45 分钟", "estimated_minutes": 45},
                {"title": "写作批改与复盘", "schedule_policy": "每周 1 次，每次 90 分钟", "estimated_minutes": 90},
            ]
            calendar_candidates = [
                {"title": "雅思听力/阅读训练", "preferred_period": "evening", "duration_minutes": 60, "repeat": "weekly:3", "editable": True},
                {"title": "雅思写作训练", "preferred_period": "weekend_morning", "duration_minutes": 90, "repeat": "weekly:1", "editable": True},
            ]
            questions = ["目标分数是多少？", "预计什么时候考试？", "每周能稳定投入几天、每天多久？"]
        elif "旅游" in text or "旅行" in text or "玩" in text:
            title = "旅行筹备计划"
            milestones = [
                {"title": "确认目的地、预算和同行人", "target_date": target_start or "待用户确认"},
                {"title": "查询交通与住宿", "target_date": "出行前 4-6 周"},
                {"title": "预订酒店与核心交通", "target_date": "出行前 3-4 周"},
                {"title": "整理证件、天气、路线和行李", "target_date": "出行前 1 周"},
            ]
            subtasks = [
                {"title": "确认旅行偏好与预算", "schedule_policy": "启动计划当天", "estimated_minutes": 30},
                {"title": "查酒店和路线", "schedule_policy": "启动后 1 周内", "estimated_minutes": 60},
                {"title": "出发前检查清单", "schedule_policy": "出发前 3 天", "estimated_minutes": 30},
            ]
            calendar_candidates = [
                {"title": "启动旅行计划：确认目的地/预算/时间", "preferred_period": "evening", "duration_minutes": 30, "editable": True},
                {"title": "查询酒店与路线", "preferred_period": "weekend_afternoon", "duration_minutes": 60, "editable": True},
            ]
            questions = ["目的地是哪里？", "预计几号出发、几号回来？", "预算和同行人有要求吗？"]
        else:
            milestones = [
                {"title": "明确目标和完成标准", "target_date": target_start or "待用户确认"},
                {"title": "完成第一轮推进", "target_date": target_end or "开始后 1 周"},
            ]
            subtasks = [
                {"title": f"推进：{title}", "schedule_policy": "近期找空档", "estimated_minutes": 45},
            ]
            calendar_candidates = [
                {"title": title, "preferred_period": "any", "duration_minutes": 45, "editable": True},
            ]
            questions = ["这个任务最晚希望什么时候完成？", "每次适合投入多长时间？"]

        task_id = f"task_{uuid4().hex}"
        daily_plan = _build_daily_plan(
            title=title,
            user_request=text,
            classification=classification,
            target_start=target_start,
            target_end=target_end,
        )
        plan = {
            "id": task_id,
            "title": title,
            "type": classification,
            "status": "draft",
            "source_agent": source_agent,
            "original_user_request": text,
            "goal": title,
            "time_horizon": {"start_after": start_hint, "target_date": end_hint, "deadline": target_end},
            "milestones": milestones,
            "subtasks": subtasks,
            "calendar_candidates": calendar_candidates,
            "daily_plan": daily_plan,
            "clarifying_questions": questions,
            "user_constraints": user_constraints or [],
        }
        return {
            "type": "task.plan",
            "ok": True,
            "pending_background_task": True,
            "task_id": task_id,
            "classification": classification,
            "title": title,
            "need_clarification": classification in {"long_project", "future_project", "recurring_plan"},
            "clarifying_questions": questions,
            "daily_plan_count": len(daily_plan),
            "plan": plan,
        }

class JarvisTaskPrioritizeInput(BaseModel):
    tasks: list[MaxwellTaskCandidate] = Field(description="Candidate tasks to prioritize")


class JarvisTaskPrioritizeTool(ShadowLinkTool):
    name: str = "jarvis_task_prioritize"
    description: str = "Re-rank tasks by deadline pressure, importance, and current context load."
    args_schema: type[BaseModel] = JarvisTaskPrioritizeInput
    category: ToolCategory = ToolCategory.SYSTEM

    def _run(self, tasks: list[dict]) -> dict:
        raise NotImplementedError("Use async version")

    async def _arun(self, tasks: list[dict]) -> dict:
        if not tasks:
            return {"type": "task.prioritize", "ok": False, "error": "no tasks provided"}

        ctx = await get_life_context_bus().get_context()
        now = datetime.utcnow()
        ranked: list[dict] = []
        for index, task in enumerate(tasks, start=1):
            deadline = _parse_iso_datetime(task.get("deadline"))
            hours_left = None
            if deadline is not None:
                hours_left = (_to_timestamp(deadline) - now.timestamp()) / 3600

            importance = int(task.get("importance", 3))
            estimated_minutes = int(task.get("estimated_minutes", 30))
            must_do = bool(task.get("must_do", False))
            energy_level = str(task.get("energy_level", "medium")).lower()

            score = importance * 12 + (15 if must_do else 0)
            reasons: list[str] = []

            if hours_left is not None:
                if hours_left <= 0:
                    score += 30
                    reasons.append("已到或已过 deadline")
                elif hours_left <= 6:
                    score += 22
                    reasons.append("deadline 非常近")
                elif hours_left <= 24:
                    score += 16
                    reasons.append("deadline 在 24 小时内")
                elif hours_left <= 72:
                    score += 8
                    reasons.append("deadline 在 3 天内")

            if estimated_minutes <= 30 and ctx.schedule_density >= 7:
                score += 6
                reasons.append("当前节奏紧，短任务更容易落地")
            elif estimated_minutes >= 120 and ctx.schedule_density >= 7:
                score -= 4
                reasons.append("长任务在高密度日程下更难完整推进")

            if ctx.sleep_quality <= 4 and energy_level == "high":
                score -= 5
                reasons.append("睡眠偏低，高耗能任务可稍后安排")
            elif energy_level == "low":
                score += 3
                reasons.append("低能耗任务更适合当前状态")

            ranked.append({
                "title": task.get("title", f"Task {index}"),
                "score": score,
                "importance": importance,
                "deadline": deadline.isoformat() if deadline else None,
                "estimated_minutes": estimated_minutes,
                "must_do": must_do,
                "reason": "；".join(reasons) or "综合重要性与执行成本排序",
            })

        ranked.sort(key=lambda item: item["score"], reverse=True)
        top = ranked[0]
        return {
            "type": "task.prioritize",
            "ok": True,
            "ordered_tasks": ranked,
            "top_recommendation": f"现在先做：{top['title']}",
            "summary": f"已完成 {len(ranked)} 个任务的优先级重排，首项建议是 {top['title']}。",
        }


class JarvisDeadlineCheckInput(BaseModel):
    items: list[MaxwellDeadlineItem] = Field(description="Tasks or deliverables with deadlines")


class JarvisDeadlineCheckTool(ShadowLinkTool):
    name: str = "jarvis_deadline_check"
    description: str = "Scan upcoming deadlines, flag overdue risks, and surface calendar conflicts."
    args_schema: type[BaseModel] = JarvisDeadlineCheckInput
    category: ToolCategory = ToolCategory.SYSTEM

    def _run(self, items: list[dict]) -> dict:
        raise NotImplementedError("Use async version")

    async def _arun(self, items: list[dict]) -> dict:
        if not items:
            return {"type": "deadline.check", "ok": False, "error": "no deadline items provided"}

        now = datetime.utcnow()
        risks: list[dict] = []
        healthy: list[dict] = []

        for item in items:
            due_at = _parse_iso_datetime(item.get("due_at"))
            if due_at is None:
                risks.append({
                    "title": item.get("title", "Untitled"),
                    "severity": "high",
                    "reason": "deadline 时间格式无效",
                })
                continue

            hours_left = (_to_timestamp(due_at) - now.timestamp()) / 3600
            estimated_minutes = int(item.get("estimated_minutes", 30))
            importance = int(item.get("importance", 3))
            window_start = now
            window_end = due_at
            blocking_events = _get_window_events(window_start, window_end) if hours_left > 0 else []
            busy_minutes = sum(
                max(0, int((_to_timestamp(event["end"]) - _to_timestamp(event["start"])) / 60))
                for event in blocking_events
            )
            available_minutes = max(0, int((_to_timestamp(due_at) - now.timestamp()) / 60) - busy_minutes)

            if hours_left <= 0:
                risks.append({
                    "title": item.get("title", "Untitled"),
                    "severity": "critical",
                    "reason": "deadline 已经过期",
                    "due_at": due_at.isoformat(),
                })
            elif available_minutes < estimated_minutes:
                risks.append({
                    "title": item.get("title", "Untitled"),
                    "severity": "high" if importance >= 4 else "medium",
                    "reason": "在当前日程下，可用时间不足以完成任务",
                    "due_at": due_at.isoformat(),
                    "available_minutes": available_minutes,
                    "estimated_minutes": estimated_minutes,
                    "blocking_events": [_serialize_event(event) for event in blocking_events[:4]],
                })
            elif hours_left <= 24:
                risks.append({
                    "title": item.get("title", "Untitled"),
                    "severity": "medium",
                    "reason": "deadline 在 24 小时内，建议尽快推进",
                    "due_at": due_at.isoformat(),
                    "available_minutes": available_minutes,
                })
            else:
                healthy.append({
                    "title": item.get("title", "Untitled"),
                    "due_at": due_at.isoformat(),
                    "available_minutes": available_minutes,
                })

        return {
            "type": "deadline.check",
            "ok": True,
            "risks": risks,
            "healthy_items": healthy,
            "summary": f"检查了 {len(items)} 个 deadline，发现 {len(risks)} 个需要重点关注。",
        }


class JarvisCalendarFindFreeSlotInput(BaseModel):
    duration_minutes: int = Field(ge=15, le=480, description="Required slot duration in minutes")
    window_start: str | None = Field(default=None, description="Optional search window start in ISO8601")
    window_end: str | None = Field(default=None, description="Optional search window end in ISO8601")
    horizon_hours: int = Field(default=72, ge=1, le=168, description="Fallback search horizon in hours")
    preferred_period: str = Field(default="any", description="morning, afternoon, evening, or any")
    buffer_minutes: int = Field(default=15, ge=0, le=120, description="Required buffer between meetings")


class JarvisCalendarFindFreeSlotTool(ShadowLinkTool):
    name: str = "jarvis_calendar_find_free_slot"
    description: str = "Find free calendar slots that satisfy duration, buffer, and preferred time-of-day."
    args_schema: type[BaseModel] = JarvisCalendarFindFreeSlotInput
    category: ToolCategory = ToolCategory.SYSTEM

    def _run(
        self,
        duration_minutes: int,
        window_start: str | None = None,
        window_end: str | None = None,
        horizon_hours: int = 72,
        preferred_period: str = "any",
        buffer_minutes: int = 15,
    ) -> dict:
        raise NotImplementedError("Use async version")

    async def _arun(
        self,
        duration_minutes: int,
        window_start: str | None = None,
        window_end: str | None = None,
        horizon_hours: int = 72,
        preferred_period: str = "any",
        buffer_minutes: int = 15,
    ) -> dict:
        now = datetime.utcnow()
        search_start = _parse_iso_datetime(window_start) or now
        search_end = _parse_iso_datetime(window_end) or datetime.utcfromtimestamp(now.timestamp() + horizon_hours * 3600)
        if _to_timestamp(search_end) <= _to_timestamp(search_start):
            return {"type": "calendar.find_free_slot", "ok": False, "error": "invalid search window"}

        events = sorted(
            _get_window_events(search_start, search_end),
            key=lambda event: _to_timestamp(event["start"]),
        )

        slots: list[dict] = []
        cursor = search_start
        padded_duration = duration_minutes * 60
        buffer_seconds = buffer_minutes * 60

        def _period_match(slot_start: datetime) -> bool:
            hour = slot_start.hour
            if preferred_period == "morning":
                return 6 <= hour < 12
            if preferred_period == "afternoon":
                return 12 <= hour < 18
            if preferred_period == "evening":
                return 18 <= hour < 23
            return True

        for event in events:
            gap_end_ts = _to_timestamp(event["start"]) - buffer_seconds
            if gap_end_ts - _to_timestamp(cursor) >= padded_duration and _period_match(cursor):
                slots.append({
                    "start": cursor.isoformat(),
                    "end": datetime.utcfromtimestamp(gap_end_ts).isoformat(),
                    "duration_minutes": int((gap_end_ts - _to_timestamp(cursor)) / 60),
                })
            cursor = max(
                cursor,
                datetime.utcfromtimestamp(_to_timestamp(event["end"]) + buffer_seconds),
            )

        if _to_timestamp(search_end) - _to_timestamp(cursor) >= padded_duration and _period_match(cursor):
            slots.append({
                "start": cursor.isoformat(),
                "end": search_end.isoformat(),
                "duration_minutes": int((_to_timestamp(search_end) - _to_timestamp(cursor)) / 60),
            })

        return {
            "type": "calendar.find_free_slot",
            "ok": True,
            "requested_duration_minutes": duration_minutes,
            "preferred_period": preferred_period,
            "slots": slots[:5],
            "summary": (
                f"找到 {len(slots)} 个可用空档。"
                if slots
                else "在当前窗口内没有找到满足条件的空档。"
            ),
        }


class JarvisActivityRankByEnergyInput(BaseModel):
    energy_level: str = Field(default="medium", description="low, medium, or high")
    categories: list[str] = Field(default_factory=list, description="Optional activity categories")
    limit: int = Field(default=5, ge=1, le=10, description="Maximum ranked activities to return")


class JarvisActivityRankByEnergyTool(ShadowLinkTool):
    name: str = "jarvis_activity_rank_by_energy"
    description: str = "Rank nearby activities by current energy level, distance, and user interests."
    args_schema: type[BaseModel] = JarvisActivityRankByEnergyInput
    category: ToolCategory = ToolCategory.SYSTEM

    def _run(self, energy_level: str = "medium", categories: list[str] | None = None, limit: int = 5) -> dict:
        raise NotImplementedError("Use async version")

    async def _arun(self, energy_level: str = "medium", categories: list[str] | None = None, limit: int = 5) -> dict:
        activities = await _fetch_rankable_activities(limit=max(limit * 2, 6), categories=categories)
        if not activities:
            return {"type": "activity.rank_by_energy", "ok": False, "error": "no activities available"}

        profile = get_settings().profile
        ctx = await get_life_context_bus().get_context()
        interests = {item.lower() for item in profile.interests}
        ranked: list[dict] = []

        for item in activities:
            category = item["category"]
            score = 50
            reasons: list[str] = []

            if energy_level == "low":
                if category in {"cafe", "museum", "park"}:
                    score += 16
                    reasons.append("更适合低能量状态")
                if item["distance_m"] <= 1200:
                    score += 10
                    reasons.append("距离较近，执行阻力低")
            elif energy_level == "high":
                if category in {"gym", "park"}:
                    score += 16
                    reasons.append("适合高能量释放")
                if item["distance_m"] <= 2500:
                    score += 6
            else:
                if item["distance_m"] <= 1800:
                    score += 8
                    reasons.append("距离适中")

            if ctx.stress_level >= 7 and category in {"park", "museum", "cafe"}:
                score += 8
                reasons.append("高压力时更偏恢复型活动")

            if any(keyword in item["name"].lower() or keyword == category for keyword in interests):
                score += 12
                reasons.append("和用户兴趣更贴近")

            ranked.append({
                **item,
                "score": score,
                "reason": "；".join(reasons) or "综合距离与当前状态排序",
            })

        ranked.sort(key=lambda entry: entry["score"], reverse=True)
        return {
            "type": "activity.rank_by_energy",
            "ok": True,
            "energy_level": energy_level,
            "activities": ranked[:limit],
            "summary": f"已按 {energy_level} 能量状态筛出 {min(limit, len(ranked))} 个更合适的活动。",
        }


class JarvisRouteEstimateInput(BaseModel):
    activity_name: str = Field(description="Chosen activity name")
    travel_mode: str = Field(default="walking", description="walking, cycling, transit, or driving")


class JarvisRouteEstimateTool(ShadowLinkTool):
    name: str = "jarvis_route_estimate"
    description: str = "Estimate rough travel time to a candidate activity."
    args_schema: type[BaseModel] = JarvisRouteEstimateInput
    category: ToolCategory = ToolCategory.SYSTEM

    def _run(self, activity_name: str, travel_mode: str = "walking") -> dict:
        raise NotImplementedError("Use async version")

    async def _arun(self, activity_name: str, travel_mode: str = "walking") -> dict:
        activities = await _fetch_rankable_activities(limit=12)
        activity = _find_activity_candidate(activities, activity_name)
        if activity is None:
            return {"type": "route.estimate", "ok": False, "error": "activity not found"}

        minutes = _distance_to_minutes(activity["distance_m"], travel_mode)
        return {
            "type": "route.estimate",
            "ok": True,
            "activity_name": activity["name"],
            "travel_mode": travel_mode,
            "distance_m": activity["distance_m"],
            "estimated_minutes": minutes,
            "summary": f"从当前位置到 {activity['name']} 约 {minutes} 分钟（{travel_mode}）。",
        }


class JarvisPlanActivitySlotInput(BaseModel):
    activity_name: str = Field(description="Activity to place on the calendar")
    duration_minutes: int = Field(default=60, ge=15, le=240, description="Planned activity duration")
    preferred_period: str = Field(default="afternoon", description="morning, afternoon, evening, or any")
    travel_mode: str = Field(default="walking", description="walking, cycling, transit, or driving")
    horizon_hours: int = Field(default=72, ge=1, le=168, description="Search horizon for placing the activity")
    buffer_minutes: int = Field(default=10, ge=0, le=60, description="Buffer around surrounding events")


class JarvisPlanActivitySlotTool(ShadowLinkTool):
    name: str = "jarvis_plan_activity_slot"
    description: str = "Pick a suitable free slot for an activity and add it to the calendar."
    args_schema: type[BaseModel] = JarvisPlanActivitySlotInput
    category: ToolCategory = ToolCategory.SYSTEM
    requires_confirmation: bool = True

    def _run(
        self,
        activity_name: str,
        duration_minutes: int = 60,
        preferred_period: str = "afternoon",
        travel_mode: str = "walking",
        horizon_hours: int = 72,
        buffer_minutes: int = 10,
    ) -> dict:
        raise NotImplementedError("Use async version")

    async def _arun(
        self,
        activity_name: str,
        duration_minutes: int = 60,
        preferred_period: str = "afternoon",
        travel_mode: str = "walking",
        horizon_hours: int = 72,
        buffer_minutes: int = 10,
    ) -> dict:
        activities = await _fetch_rankable_activities(limit=12)
        activity = _find_activity_candidate(activities, activity_name)
        if activity is None:
            return {"type": "calendar.add", "ok": False, "error": "activity not found"}

        route_minutes = _distance_to_minutes(activity["distance_m"], travel_mode)
        now = datetime.utcnow()
        search_end = now + timedelta(hours=horizon_hours)
        slots = _build_free_slots(
            window_start=now,
            window_end=search_end,
            duration_minutes=duration_minutes + route_minutes * 2,
            preferred_period=preferred_period,
            buffer_minutes=buffer_minutes,
        )
        if not slots:
            return {"type": "calendar.add", "ok": False, "error": "no free slot available"}

        chosen = slots[0]
        start = chosen["start"]
        end = start + timedelta(minutes=duration_minutes)
        title = f"Leo 活动：{activity['name']}"
        event = add_event(title, start, end, stress_weight=0.4 if activity["category"] in {"park", "cafe", "museum"} else 0.7)
        density = compute_schedule_density()
        active_events = get_upcoming_events(hours_ahead=24)
        await get_life_context_bus().update_fields(
            {"schedule_density": density, "active_events": active_events},
            source="agent_tool",
        )
        return {
            "type": "calendar.add",
            "ok": True,
            "event_id": event.id,
            "title": event.title,
            "start": event.start.isoformat(),
            "end": event.end.isoformat(),
            "activity_name": activity["name"],
            "travel_mode": travel_mode,
            "estimated_route_minutes": route_minutes,
            "new_schedule_density": density,
        }


class JarvisMealPlanInput(BaseModel):
    meals: list[str] = Field(default_factory=lambda: ["breakfast", "lunch", "dinner"], description="Meals to plan")
    include_snack: bool = Field(default=True, description="Whether to include a snack recommendation")
    dietary_restrictions: list[str] = Field(default_factory=list, description="Optional explicit dietary restrictions")
    goal: str = Field(default="steady_energy", description="steady_energy, stress_recovery, or light_digest")


class JarvisMealPlanTool(ShadowLinkTool):
    name: str = "jarvis_meal_plan"
    description: str = "Generate a practical daily meal plan aligned with context, weather, and dietary restrictions."
    args_schema: type[BaseModel] = JarvisMealPlanInput
    category: ToolCategory = ToolCategory.SYSTEM

    def _run(
        self,
        meals: list[str] | None = None,
        include_snack: bool = True,
        dietary_restrictions: list[str] | None = None,
        goal: str = "steady_energy",
    ) -> dict:
        raise NotImplementedError("Use async version")

    async def _arun(
        self,
        meals: list[str] | None = None,
        include_snack: bool = True,
        dietary_restrictions: list[str] | None = None,
        goal: str = "steady_energy",
    ) -> dict:
        profile = get_settings().profile
        snapshot = await _collect_life_snapshot(
            hours_ahead=24,
            include_weather=True,
            include_activities=False,
            include_news=False,
        )
        restrictions = _normalized_restrictions(dietary_restrictions or profile.diet_restrictions)
        desired_meals = list(meals or ["breakfast", "lunch", "dinner"])
        if include_snack and "snack" not in desired_meals:
            desired_meals.append("snack")

        selected: list[dict] = []
        for meal_type in desired_meals:
            candidates = [
                template for template in _MEAL_TEMPLATES
                if template["meal_type"] == meal_type and _meal_allowed(template["tags"], restrictions)
            ]
            if not candidates:
                selected.append({
                    "meal": meal_type,
                    "suggestion": f"{meal_type}：按你的饮食限制，建议选择清淡高蛋白组合并避开禁忌食材。",
                    "benefits": ["需按个人禁忌手动替换"],
                })
                continue

            pick = candidates[0]
            if goal == "stress_recovery" and meal_type in {"lunch", "dinner"}:
                fish_or_tofu = [item for item in candidates if "fish" in item["tags"] or "vegan" in item["tags"]]
                if fish_or_tofu:
                    pick = fish_or_tofu[0]
            if snapshot["context"].get("sleep_quality", 7) <= 4 and meal_type == "dinner":
                lighter = [item for item in candidates if "清淡" in "".join(item["benefits"]) or "vegan" in item["tags"]]
                if lighter:
                    pick = lighter[0]

            selected.append({
                "meal": meal_type,
                "suggestion": pick["name"],
                "benefits": pick["benefits"],
            })

        hydration_note = "天气偏热，餐间注意补水。" if (snapshot.get("weather") or {}).get("temperature_c", 20) >= 28 else "保持规律饮水即可。"
        return {
            "type": "meal.plan",
            "ok": True,
            "goal": goal,
            "dietary_restrictions": sorted(restrictions),
            "meals": selected,
            "notes": [
                "高压力日优先保证蛋白质与稳定碳水。",
                hydration_note,
            ],
            "summary": f"已生成 {len(selected)} 段饮食建议，重点目标是 {goal}。",
        }


class JarvisNutritionLookupInput(BaseModel):
    food_name: str = Field(description="Food or drink to inspect")
    goal: str = Field(default="general", description="general, stress_recovery, energy, or sleep_friendly")


class JarvisNutritionLookupTool(ShadowLinkTool):
    name: str = "jarvis_nutrition_lookup"
    description: str = "Explain the nutrition profile and suitability of a given food or drink."
    args_schema: type[BaseModel] = JarvisNutritionLookupInput
    category: ToolCategory = ToolCategory.SYSTEM

    def _run(self, food_name: str, goal: str = "general") -> dict:
        raise NotImplementedError("Use async version")

    async def _arun(self, food_name: str, goal: str = "general") -> dict:
        query = food_name.strip().lower()
        profile = None
        canonical_name = food_name.strip()
        for name, item in _NUTRITION_REFERENCE.items():
            if query == name or query in item["aliases"]:
                profile = item
                canonical_name = name
                break

        if profile is None:
            return {
                "type": "nutrition.lookup",
                "ok": False,
                "error": f"暂时没有 {food_name} 的营养参考卡片",
            }

        restrictions = _normalized_restrictions(get_settings().profile.diet_restrictions)
        compatible = _meal_allowed(set(profile.get("tags", set())), restrictions)
        advice = list(profile.get("best_for", []))
        if goal == "sleep_friendly" and profile.get("caffeine_mg", 0) > 0:
            advice.append("如果是睡眠友好目标，建议放到更早时间或换无咖啡因替代。")
        if goal == "stress_recovery":
            advice.append("高压力阶段建议搭配稳定碳水或蛋白，不要只单吃。")

        return {
            "type": "nutrition.lookup",
            "ok": True,
            "food_name": canonical_name,
            "highlights": profile.get("highlights", []),
            "best_for": profile.get("best_for", []),
            "cautions": profile.get("cautions", []),
            "caffeine_mg": profile.get("caffeine_mg", 0),
            "compatible_with_profile": compatible,
            "dietary_restrictions": sorted(restrictions),
            "advice": advice,
        }


class JarvisHydrationPlanInput(BaseModel):
    activity_level: str = Field(default="medium", description="low, medium, or high")
    target_ml: int | None = Field(default=None, description="Optional explicit hydration target")


class JarvisHydrationPlanTool(ShadowLinkTool):
    name: str = "jarvis_hydration_plan"
    description: str = "Create a hydration target and drinking rhythm for today."
    args_schema: type[BaseModel] = JarvisHydrationPlanInput
    category: ToolCategory = ToolCategory.SYSTEM

    def _run(self, activity_level: str = "medium", target_ml: int | None = None) -> dict:
        raise NotImplementedError("Use async version")

    async def _arun(self, activity_level: str = "medium", target_ml: int | None = None) -> dict:
        profile = get_settings().profile
        snapshot = await _collect_life_snapshot(
            hours_ahead=24,
            include_weather=True,
            include_activities=False,
            include_news=False,
        )
        weather = snapshot.get("weather") or {}
        base = target_ml or 2000
        if activity_level == "high":
            base += 600
        elif activity_level == "low":
            base -= 200
        if (weather.get("temperature_c") or 0) >= 28:
            base += 400
        if snapshot["context"].get("schedule_density", 0) >= 7:
            base += 200

        wake = _parse_clock_time(profile.sleep_schedule.wake, "07:00")
        bedtime = _parse_clock_time(profile.sleep_schedule.bedtime, "23:00")
        schedule = [
            {"time": wake.isoformat(), "amount_ml": 350, "note": "起床后先补一杯水"},
            {"time": wake.replace(hour=min(11, wake.hour + 3)).isoformat(), "amount_ml": 400, "note": "上午工作段中补水"},
            {"time": wake.replace(hour=13, minute=0).isoformat(), "amount_ml": 450, "note": "午餐前后分次喝"},
            {"time": wake.replace(hour=16, minute=0).isoformat(), "amount_ml": 400, "note": "下午避免靠咖啡替代补水"},
            {"time": bedtime.replace(hour=max(19, bedtime.hour - 3)).isoformat(), "amount_ml": 300, "note": "晚餐后少量补水，避免临睡前集中喝"},
        ]

        return {
            "type": "hydration.plan",
            "ok": True,
            "target_ml": base,
            "activity_level": activity_level,
            "schedule": schedule,
            "summary": f"今天建议目标饮水量约 {base} ml，分 5 次完成会更稳。",
        }


class JarvisCaffeineCutoffGuardInput(BaseModel):
    beverage_name: str = Field(default="coffee", description="coffee, tea, energy drink, or custom label")
    proposed_time: str | None = Field(default=None, description="When the user plans to drink it, in ISO8601")
    caffeine_mg: int | None = Field(default=None, description="Optional caffeine amount override")


class JarvisCaffeineCutoffGuardTool(ShadowLinkTool):
    name: str = "jarvis_caffeine_cutoff_guard"
    description: str = "Judge whether a caffeinated drink is still safe for today and suggest alternatives."
    args_schema: type[BaseModel] = JarvisCaffeineCutoffGuardInput
    category: ToolCategory = ToolCategory.SYSTEM

    def _run(
        self,
        beverage_name: str = "coffee",
        proposed_time: str | None = None,
        caffeine_mg: int | None = None,
    ) -> dict:
        raise NotImplementedError("Use async version")

    async def _arun(
        self,
        beverage_name: str = "coffee",
        proposed_time: str | None = None,
        caffeine_mg: int | None = None,
    ) -> dict:
        profile = get_settings().profile
        ctx = await get_life_context_bus().get_context()
        proposed_dt = _parse_iso_datetime(proposed_time) or datetime.utcnow()
        bedtime = _clock_on_reference_day(profile.sleep_schedule.bedtime, "23:00", proposed_dt)
        if _to_timestamp(bedtime) <= _to_timestamp(proposed_dt):
            bedtime = bedtime + timedelta(days=1)

        default_caffeine = 95
        query = beverage_name.strip().lower()
        for item in _NUTRITION_REFERENCE.values():
            if query in item["aliases"] or query == next(iter(item["aliases"])):
                default_caffeine = item.get("caffeine_mg", default_caffeine)
                break
        caffeine_value = caffeine_mg if caffeine_mg is not None else default_caffeine

        cutoff_hours = 9 if ctx.sleep_quality <= 5 else 8
        cutoff_dt = datetime.utcfromtimestamp(_to_timestamp(bedtime) - cutoff_hours * 3600)
        allowed = _to_timestamp(proposed_dt) <= _to_timestamp(cutoff_dt)

        recommendation = (
            "可以喝，但建议搭配水并控制总量。"
            if allowed
            else "不建议现在再喝含咖啡因饮品，改成无咖啡因饮料或只补水更稳。"
        )
        if ctx.sleep_quality <= 5 and beverage_name.lower() == "coffee":
            recommendation += " 你最近睡眠一般，今天更应提前截止。"

        return {
            "type": "caffeine.cutoff.guard",
            "ok": True,
            "beverage_name": beverage_name,
            "proposed_time": proposed_dt.isoformat(),
            "cutoff_time": cutoff_dt.isoformat(),
            "caffeine_mg": caffeine_value,
            "allowed": allowed,
            "recommendation": recommendation,
        }


class JarvisCheckinScheduleInput(BaseModel):
    delay_hours: int = Field(default=12, ge=1, le=72, description="How many hours later to schedule the check-in")
    duration_minutes: int = Field(default=10, ge=5, le=60, description="Check-in slot length")
    note: str = Field(default="情绪状态轻回访", description="Short follow-up note")


class JarvisCheckinScheduleTool(ShadowLinkTool):
    name: str = "jarvis_checkin_schedule"
    description: str = "Schedule a lightweight emotional follow-up as a concrete future check-in action."
    args_schema: type[BaseModel] = JarvisCheckinScheduleInput
    category: ToolCategory = ToolCategory.SYSTEM
    requires_confirmation: bool = True

    def _run(self, delay_hours: int = 12, duration_minutes: int = 10, note: str = "情绪状态轻回访") -> dict:
        raise NotImplementedError("Use async version")

    async def _arun(self, delay_hours: int = 12, duration_minutes: int = 10, note: str = "情绪状态轻回访") -> dict:
        start = datetime.utcnow() + timedelta(hours=delay_hours)
        end = start + timedelta(minutes=duration_minutes)
        event = add_event(f"Mira 回访：{note}", start, end, stress_weight=0.2)
        density = compute_schedule_density()
        active_events = get_upcoming_events(hours_ahead=24)
        await get_life_context_bus().update_fields(
            {"schedule_density": density, "active_events": active_events},
            source="agent_tool",
        )
        return {
            "type": "checkin.schedule",
            "ok": True,
            "event_id": event.id,
            "title": event.title,
            "start": event.start.isoformat(),
            "end": event.end.isoformat(),
            "note": note,
        }


class JarvisBreathingProtocolInput(BaseModel):
    goal: str = Field(default="calm_down", description="calm_down, reset_focus, or sleep_transition")
    duration_minutes: int = Field(default=3, ge=1, le=10, description="Protocol duration in minutes")
    intensity: str = Field(default="gentle", description="gentle, standard, or grounding")


class JarvisBreathingProtocolTool(ShadowLinkTool):
    name: str = "jarvis_breathing_protocol"
    description: str = "Provide a structured short breathing protocol the user can follow immediately."
    args_schema: type[BaseModel] = JarvisBreathingProtocolInput
    category: ToolCategory = ToolCategory.SYSTEM

    def _run(self, goal: str = "calm_down", duration_minutes: int = 3, intensity: str = "gentle") -> dict:
        raise NotImplementedError("Use async version")

    async def _arun(self, goal: str = "calm_down", duration_minutes: int = 3, intensity: str = "gentle") -> dict:
        cycles = max(3, duration_minutes * 4)
        if goal == "sleep_transition":
            inhale, hold, exhale = 4, 0, 6
            intro = "把节奏放慢，重点放在更长的呼气。"
        elif goal == "reset_focus":
            inhale, hold, exhale = 4, 2, 4
            intro = "先把注意力从杂念拉回呼吸，再回到手头任务。"
        else:
            inhale, hold, exhale = 4, 2, 6
            intro = "先把肩膀放松，呼气时有意识地卸掉紧张。"

        if intensity == "grounding":
            intro += " 同时感受双脚踩地和椅背支撑。"

        steps = [
            "坐稳或站稳，肩膀下沉，视线轻落。",
            f"吸气 {inhale} 秒，停 {hold} 秒，呼气 {exhale} 秒。",
            f"重复 {cycles} 个循环；如果走神，只把注意力带回呼气。",
            "结束前观察一下胸口、下颌和肩膀有没有放松一点。",
        ]
        return {
            "type": "breathing.protocol",
            "ok": True,
            "goal": goal,
            "duration_minutes": duration_minutes,
            "intensity": intensity,
            "intro": intro,
            "steps": steps,
            "summary": f"这是一个约 {duration_minutes} 分钟的呼吸流程，适合现在立刻做。",
        }


class JarvisMoodJournalInput(BaseModel):
    mood: str = Field(description="Current mood label")
    intensity: int = Field(default=5, ge=1, le=10, description="Mood intensity from 1 to 10")
    triggers: list[str] = Field(default_factory=list, description="What triggered this feeling")
    body_signals: list[str] = Field(default_factory=list, description="Body sensations or stress signals")
    note: str = Field(default="", description="Optional free-form journal note")


class JarvisMoodJournalTool(ShadowLinkTool):
    name: str = "jarvis_mood_journal"
    description: str = "Record a structured mood journal entry for later follow-up and pattern tracking."
    args_schema: type[BaseModel] = JarvisMoodJournalInput
    category: ToolCategory = ToolCategory.SYSTEM
    requires_confirmation: bool = True

    def _run(
        self,
        mood: str,
        intensity: int = 5,
        triggers: list[str] | None = None,
        body_signals: list[str] | None = None,
        note: str = "",
    ) -> dict:
        raise NotImplementedError("Use async version")

    async def _arun(
        self,
        mood: str,
        intensity: int = 5,
        triggers: list[str] | None = None,
        body_signals: list[str] | None = None,
        note: str = "",
    ) -> dict:
        created_at = datetime.utcnow()
        entry = {
            "entry_id": f"mood-{int(created_at.timestamp())}",
            "created_at": created_at.isoformat(),
            "mood": mood,
            "intensity": intensity,
            "triggers": triggers or [],
            "body_signals": body_signals or [],
            "note": note,
        }
        journal_path = Path(app_settings.data_dir) / "mira_mood_journal.jsonl"
        _append_jsonl(journal_path, entry)
        return {
            "type": "mood.journal",
            "ok": True,
            "entry_id": entry["entry_id"],
            "created_at": entry["created_at"],
            "mood": mood,
            "intensity": intensity,
        }


class JarvisBurnoutRiskAssessInput(BaseModel):
    user_message: str = Field(default="", description="Latest user statement to include in the assessment")
    recent_signals: list[str] = Field(default_factory=list, description="Observed stress or overload signals")


class JarvisBurnoutRiskAssessTool(ShadowLinkTool):
    name: str = "jarvis_burnout_risk_assess"
    description: str = "Assess current burnout risk from stress, sleep, schedule density, and recent signals."
    args_schema: type[BaseModel] = JarvisBurnoutRiskAssessInput
    category: ToolCategory = ToolCategory.SYSTEM

    def _run(self, user_message: str = "", recent_signals: list[str] | None = None) -> dict:
        raise NotImplementedError("Use async version")

    async def _arun(self, user_message: str = "", recent_signals: list[str] | None = None) -> dict:
        ctx = await get_life_context_bus().get_context()
        signals = [signal.strip() for signal in (recent_signals or []) if signal.strip()]
        score = 0
        reasons: list[str] = []

        if ctx.stress_level >= 8:
            score += 3
            reasons.append("当前压力评分很高")
        elif ctx.stress_level >= 6:
            score += 2
            reasons.append("压力处在偏高区间")

        if ctx.sleep_quality <= 4:
            score += 3
            reasons.append("睡眠质量较差")
        elif ctx.sleep_quality <= 6:
            score += 1
            reasons.append("睡眠恢复一般")

        if ctx.schedule_density >= 7:
            score += 2
            reasons.append("日程密度偏高")

        overload_keywords = ("累", "扛不住", "崩", "burnout", "撑不住", "烦", "透不过气")
        if any(keyword in user_message.lower() for keyword in overload_keywords):
            score += 2
            reasons.append("用户表述里出现明显疲惫/压垮信号")

        if signals:
            score += min(2, len(signals))
            reasons.append(f"最近还观察到 {len(signals)} 个额外风险信号")

        if score >= 7:
            level = "high"
        elif score >= 4:
            level = "medium"
        else:
            level = "low"

        recommendations = {
            "high": [
                "今天应立即压缩非关键安排，优先保留必要事项。",
                "安排一次短呼吸练习，并在 12-24 小时内做一次回访。",
            ],
            "medium": [
                "给接下来任务之间留缓冲，避免连续高压切换。",
                "今天尽量减少刺激物，优先恢复睡眠。",
            ],
            "low": [
                "当前风险可控，维持节奏并继续观察睡眠与压力变化。",
            ],
        }[level]

        return {
            "type": "burnout.risk_assess",
            "ok": True,
            "risk_level": level,
            "score": score,
            "reasons": reasons,
            "recommendations": recommendations,
            "signals": signals,
        }


class JarvisDailyBriefingInput(BaseModel):
    hours_ahead: int = Field(default=24, ge=1, le=72, description="How many upcoming hours to summarize")
    include_weather: bool = Field(default=True, description="Whether to include local weather in the briefing")
    include_news: bool = Field(default=True, description="Whether to include headline signals in the briefing")


class JarvisDailyBriefingTool(ShadowLinkTool):
    name: str = "jarvis_daily_briefing"
    description: str = "Generate a cross-domain daily briefing with risks, priorities, and suggested actions."
    args_schema: type[BaseModel] = JarvisDailyBriefingInput
    category: ToolCategory = ToolCategory.SYSTEM

    def _run(self, hours_ahead: int = 24, include_weather: bool = True, include_news: bool = True) -> dict:
        raise NotImplementedError("Use async version")

    async def _arun(self, hours_ahead: int = 24, include_weather: bool = True, include_news: bool = True) -> dict:
        snapshot = await _collect_life_snapshot(
            hours_ahead=hours_ahead,
            include_weather=include_weather,
            include_activities=False,
            include_news=include_news,
        )
        risks, priorities, suggested_actions = _build_briefing_heuristics(snapshot)

        summary_parts: list[str] = []
        if risks:
            summary_parts.append("主要风险：" + "；".join(risks[:2]))
        if priorities:
            summary_parts.append("当前优先级：" + "；".join(priorities[:2]))
        if suggested_actions:
            summary_parts.append("建议动作：" + "；".join(suggested_actions[:2]))

        return {
            "type": "daily_briefing",
            "ok": True,
            "generated_at": datetime.utcnow().isoformat(),
            "context": snapshot["context"],
            "upcoming_events": snapshot["events"][:6],
            "weather": snapshot.get("weather"),
            "news_headlines": snapshot.get("news", [])[:3],
            "risks": risks,
            "priorities": priorities,
            "suggested_actions": suggested_actions,
            "briefing": "\n".join(summary_parts),
        }


class JarvisSpecialistOrchestrateInput(BaseModel):
    goal: str = Field(description="Coordination goal Alfred wants to solve")
    user_message: str = Field(default="", description="Optional latest user request")
    agents: list[str] = Field(
        default_factory=lambda: ["maxwell", "nora", "mira", "leo"],
        description="Specialist agents to consult",
    )


class JarvisSpecialistOrchestrateTool(ShadowLinkTool):
    name: str = "jarvis_specialist_orchestrate"
    description: str = "Consult Jarvis specialists and return an aligned cross-domain recommendation plan."
    args_schema: type[BaseModel] = JarvisSpecialistOrchestrateInput
    category: ToolCategory = ToolCategory.SYSTEM

    def _run(self, goal: str, user_message: str = "", agents: list[str] | None = None) -> dict:
        raise NotImplementedError("Use async version")

    async def _arun(self, goal: str, user_message: str = "", agents: list[str] | None = None) -> dict:
        llm_client = _get_llm_client()
        if llm_client is None:
            return {"type": "specialist_orchestrate", "ok": False, "error": "llm_client not initialized"}

        selected_agents = [
            agent_id for agent_id in (agents or ["maxwell", "nora", "mira", "leo"])
            if agent_id in {"maxwell", "nora", "mira", "leo"}
        ]
        if not selected_agents:
            return {"type": "specialist_orchestrate", "ok": False, "error": "no valid specialist agents"}

        snapshot = await _collect_life_snapshot(
            hours_ahead=48,
            include_weather=True,
            include_activities=True,
            include_news=True,
        )
        shared_prompt = _format_snapshot_for_prompt(snapshot)
        specialist_outputs: list[dict] = []

        for agent_id in selected_agents:
            agent = get_agent(agent_id)
            prompt = (
                f"{shared_prompt}\n\n"
                f"## Coordination goal\n{goal}\n\n"
                f"## Latest user message\n{user_message or '(none)'}\n\n"
                f"## Your task\n"
                f"As {agent['name']} ({agent['role']}), give Alfred a concise professional recommendation.\n"
                f"Return JSON only:\n"
                f'{{"agent_id":"{agent_id}","focus":"...","priority":"low|medium|high","advice":["..."],"risk":"..."}}\n'
            )
            raw = await llm_client.chat(
                message=prompt,
                system_prompt=agent["system_prompt"],
                temperature=0.3,
            )
            parsed = _parse_json_object(raw or "")
            parsed.setdefault("agent_id", agent_id)
            parsed.setdefault("agent_name", agent["name"])
            parsed.setdefault("agent_role", agent["role"])
            specialist_outputs.append(parsed)

        synthesis_prompt = (
            f"{shared_prompt}\n\n"
            f"## Coordination goal\n{goal}\n\n"
            f"## Specialist recommendations\n"
            f"{json.dumps(specialist_outputs, ensure_ascii=False, indent=2)}\n\n"
            f"Return JSON only:\n"
            f'{{"summary":"...","aligned_actions":["..."],"conflicts":["..."],"followups":["..."]}}\n'
        )
        synthesis_raw = await llm_client.chat(
            message=synthesis_prompt,
            system_prompt=get_agent("alfred")["system_prompt"],
            temperature=0.2,
        )
        synthesis = _parse_json_object(synthesis_raw or "")

        await remember_coordination_summary(
            source_agent="alfred",
            participant_agents=["alfred", *selected_agents],
            goal=goal,
            summary=str(synthesis.get("summary", "")),
            payload={
                "specialists": specialist_outputs,
                "aligned_actions": synthesis.get("aligned_actions", []),
                "conflicts": synthesis.get("conflicts", []),
                "followups": synthesis.get("followups", []),
                "user_message": user_message,
            },
        )

        return {
            "type": "specialist_orchestrate",
            "ok": True,
            "goal": goal,
            "specialists": specialist_outputs,
            "summary": synthesis.get("summary", ""),
            "aligned_actions": synthesis.get("aligned_actions", []),
            "conflicts": synthesis.get("conflicts", []),
            "followups": synthesis.get("followups", []),
        }
