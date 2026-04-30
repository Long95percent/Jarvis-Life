"""Lightweight daily rhythm triggers for proactive Jarvis messages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Callable

import structlog

from app.jarvis.agents import JARVIS_AGENTS
from app.jarvis.models import LifeContext, ProactiveMessage

logger = structlog.get_logger("jarvis.proactive_routines")

ACTIVE_SOURCE_AGENTS = {"user", "user_chat", "user_ui"}
ACTIVE_WINDOW_MINUTES = 120
QUIET_START = time(0, 0)
QUIET_END = time(6, 30)


@dataclass(frozen=True)
class RoutineRule:
    routine_id: str
    agent_id: str
    start: time
    end: time
    build_content: Callable[[LifeContext, bool], str]
    weekdays: set[int] | None = None

    @property
    def trigger(self) -> str:
        return f"routine:{self.routine_id}"

    def is_due(self, now: datetime) -> bool:
        current = now.time()
        if self.weekdays is not None and now.weekday() not in self.weekdays:
            return False
        return self.start <= current <= self.end


def _is_quiet_hour(now: datetime) -> bool:
    current = now.time()
    return QUIET_START <= current < QUIET_END


def _is_user_recently_active(ctx: LifeContext, now_utc: datetime) -> bool:
    if ctx.source_agent not in ACTIVE_SOURCE_AGENTS:
        return False
    elapsed = now_utc - ctx.last_updated.replace(tzinfo=None)
    return timedelta(0) <= elapsed <= timedelta(minutes=ACTIVE_WINDOW_MINUTES)


def _morning_content(ctx: LifeContext, active: bool) -> str:
    if ctx.sleep_quality <= 4.0:
        return "早上好。昨晚恢复看起来不太理想，我可以先帮你把今天压强最高的事排出来，剩下的尽量放轻一点。"
    if ctx.schedule_density >= 7.0:
        return "早上好。今天日程有点密，我可以先帮你检查提醒、会议和缓冲时间，把最容易撞车的地方挑出来。"
    return "早上好。要不要我先帮你过一遍今天的提醒和安排，把需要提前处理的事拎出来？"


def _midday_content(ctx: LifeContext, active: bool) -> str:
    if ctx.stress_level >= 7.0 or ctx.schedule_density >= 7.0:
        return "到饭点了。今天消耗偏高，先别硬扛，我可以按你现在的时间和胃口给你选一个省事但稳的午餐。"
    return "差不多该吃点东西了。你现在胃口怎么样？我可以按清淡、快速、补能量三个方向给你挑。"


def _evening_content(ctx: LifeContext, active: bool) -> str:
    if ctx.stress_level >= 8.0 or ctx.mood_trend == "negative":
        return "今晚我想轻轻确认一下你的状态。压力好像还没完全降下来，我们可以先把明天最压人的部分挪轻一点。"
    if ctx.sleep_quality <= 4.0:
        return "晚上了。昨晚睡眠不太好，今晚先别把自己推太满，我可以帮你收一个低刺激的睡前节奏。"
    return "晚上了。要不要做一个很短的收尾？我可以帮你把明天要记得的事和今晚该放下的事分开。"


def _weekly_content(ctx: LifeContext, active: bool) -> str:
    return "这周快收尾了。我可以帮你做一个很短的周复盘：哪些事推进了、哪些要挪到下周、哪些该直接放掉。"


def _should_attach_local_life_hint(rule: RoutineRule, ctx: LifeContext, active: bool) -> bool:
    if not active:
        return False
    if rule.routine_id == "midday_appetite":
        return ctx.stress_level >= 6.5 or ctx.schedule_density >= 6.5
    if rule.routine_id == "evening_checkin":
        return ctx.stress_level >= 8.0 or ctx.sleep_quality <= 4.0 or ctx.mood_trend == "negative"
    return False


async def build_local_life_opportunity_hint(
    agent_id: str,
    *,
    now: datetime | None = None,
    radius_m: int = 3000,
    window_days: int = 14,
) -> str:
    """Return one cached local-life opportunity for proactive copy.

    This intentionally reads cache only. Proactive routines must stay quick and
    should not perform live web search.
    """
    from app.jarvis.local_life_search import list_cached_local_life_opportunities

    category_by_agent = {
        "nora": "food",
        "mira": "recovery",
        "leo": "activity",
        "maxwell": "activity",
        "alfred": None,
    }
    items = await list_cached_local_life_opportunities(
        now=now,
        category=category_by_agent.get(agent_id),
        radius_m=radius_m,
        window_days=window_days,
        limit=1,
    )
    if not items:
        return ""
    item = items[0].to_dict()
    distance = item.get("distance_m")
    distance_text = f"{distance}m" if distance is not None else "距离不明"
    venue = item.get("venue") or item.get("address") or "附近"
    return f" 我这边还看到一个可选的附近机会：{item.get('title')}，{venue}，约 {distance_text}。"


class ProactiveRoutineScheduler:
    """Creates lightweight daily rhythm messages without a separate scheduler."""

    def __init__(self) -> None:
        self.rules = [
            RoutineRule(
                routine_id="morning_brief",
                agent_id="maxwell",
                start=time(8, 0),
                end=time(10, 30),
                build_content=_morning_content,
            ),
            RoutineRule(
                routine_id="midday_appetite",
                agent_id="nora",
                start=time(11, 30),
                end=time(13, 30),
                build_content=_midday_content,
            ),
            RoutineRule(
                routine_id="evening_checkin",
                agent_id="mira",
                start=time(21, 30),
                end=time(23, 30),
                build_content=_evening_content,
            ),
            RoutineRule(
                routine_id="weekly_review",
                agent_id="alfred",
                start=time(19, 0),
                end=time(21, 30),
                build_content=_weekly_content,
                weekdays={6},
            ),
        ]

    async def check_routines(
        self,
        ctx: LifeContext,
        *,
        now: datetime | None = None,
        now_utc: datetime | None = None,
    ) -> list[dict]:
        now_utc = (now_utc or now or datetime.utcnow()).replace(tzinfo=None)
        local_now = (now or (now_utc + timedelta(hours=8))).replace(tzinfo=None)
        maintenance_created: list[dict] = []
        if local_now.time() >= time(1, 0):
            from app.core.dependencies import get_resource
            from app.jarvis.mood_snapshot_maintenance import ensure_mood_snapshots
            from app.jarvis.planner_maintenance import run_planner_daily_maintenance_once

            mood_maintenance = await ensure_mood_snapshots(today=local_now.date().isoformat(), backfill_days=3, include_today=True)
            if not mood_maintenance.get("skipped"):
                maintenance_created.append({"routine_id": "mood_snapshot_maintenance", "result": mood_maintenance})

            maintenance = await run_planner_daily_maintenance_once(
                today=local_now.date().isoformat(),
                llm_client=get_resource("llm_client"),
                auto_reschedule=True,
                push_today=True,
            )
            if not maintenance.get("skipped"):
                maintenance_created.append({"routine_id": "planner_daily_maintenance", "result": maintenance})
        if _is_quiet_hour(local_now):
            return maintenance_created
        from app.jarvis.care_triggers import evaluate_care_triggers

        care_results = await evaluate_care_triggers(local_now.date().isoformat())
        for result in care_results:
            maintenance_created.append({"routine_id": "care_trigger", "result": result})

        from app.jarvis.persistence import (
            has_proactive_routine_run,
            save_proactive_message,
            save_proactive_routine_run,
        )
        from app.jarvis.user_settings import get_enabled_agents

        active = _is_user_recently_active(ctx, now_utc)
        run_date = local_now.date().isoformat()
        created: list[dict] = [*maintenance_created]

        for rule in self.rules:
            if not rule.is_due(local_now):
                continue
            if await has_proactive_routine_run(rule.routine_id, run_date):
                continue
            if not get_enabled_agents([rule.agent_id]):
                continue

            priority = self._priority_for(rule, ctx, active)
            agent_def = JARVIS_AGENTS.get(rule.agent_id, {})
            content = rule.build_content(ctx, active)
            if _should_attach_local_life_hint(rule, ctx, active):
                try:
                    content += await build_local_life_opportunity_hint(rule.agent_id, now=local_now)
                except Exception as exc:
                    logger.warning("jarvis.routine.local_life_hint_failed", routine_id=rule.routine_id, error=str(exc))
            msg = ProactiveMessage(
                agent_id=rule.agent_id,
                agent_name=agent_def.get("name", rule.agent_id),
                content=content,
                trigger=rule.trigger,
                priority=priority,
            )
            saved = await save_proactive_message(msg)
            await save_proactive_routine_run(
                routine_id=rule.routine_id,
                run_date=run_date,
                message_id=saved.get("id") or msg.id,
            )
            logger.info(
                "jarvis.routine.message_persisted",
                routine_id=rule.routine_id,
                agent_id=rule.agent_id,
                priority=priority,
                active=active,
            )
            created.append(saved)

        return created

    @staticmethod
    def _priority_for(rule: RoutineRule, ctx: LifeContext, active: bool) -> str:
        if rule.routine_id == "evening_checkin" and (ctx.stress_level >= 8.0 or ctx.mood_trend == "negative"):
            return "high"
        if rule.routine_id == "morning_brief" and (ctx.schedule_density >= 7.0 or ctx.sleep_quality <= 4.0):
            return "high" if active else "normal"
        return "normal" if active else "low"
