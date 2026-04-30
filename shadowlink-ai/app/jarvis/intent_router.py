"""Lightweight local intent planning for single-agent Jarvis chats.

This module is intentionally small and deterministic. It handles high-signal
private-chat intents before the LLM turn, then lets the role prompt handle
ordinary conversation and ambiguous requests.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Literal

from app.jarvis.tool_runtime import get_allowed_tool_names


NextAction = Literal["chat_only", "ask_missing_slots", "call_tool", "pending_confirmation"]

_CONFIRMATION_TOOLS = {
    "jarvis_calendar_add",
    "jarvis_calendar_delete",
    "jarvis_calendar_update",
    "jarvis_plan_activity_slot",
    "jarvis_context_update",
    "jarvis_checkin_schedule",
    "jarvis_mood_journal",
}


@dataclass(frozen=True)
class AgentIntentDecision:
    agent_id: str
    intent: str
    tool_name: str | None
    confidence: float
    slots: dict[str, Any] = field(default_factory=dict)
    missing_slots: list[str] = field(default_factory=list)
    next_action: NextAction = "chat_only"
    reason: str = ""


def plan_agent_intent(
    agent_id: str,
    message: str,
    local_now: datetime | None = None,
) -> AgentIntentDecision:
    """Plan a role-local tool intent for a private Jarvis chat message."""

    now = local_now or datetime.now()
    text = _normalize(message)
    if not text or _is_small_talk(text):
        return _chat_only(agent_id, "small_talk")

    planner = {
        "maxwell": _plan_maxwell,
        "nora": _plan_nora,
        "mira": _plan_mira,
        "leo": _plan_leo,
    }.get(agent_id)
    if planner is None:
        return _chat_only(agent_id, "no_local_router")

    decision = planner(agent_id, text, now)
    if decision.tool_name is None:
        return decision

    if decision.tool_name not in set(get_allowed_tool_names(agent_id)):
        return _chat_only(agent_id, f"tool_not_allowed:{decision.tool_name}")
    return decision


def _plan_maxwell(agent_id: str, text: str, now: datetime) -> AgentIntentDecision:
    if _has_any(text, ["一个月", "一周", "几周", "长期", "第一轮", "备考", "准备完", "项目", "计划"]) and _has_any(
        text,
        ["准备", "复习", "完成", "做完", "推进", "搞定"],
    ):
        return _decision(
            agent_id,
            intent="task_decompose",
            tool_name="jarvis_task_plan_decompose",
            confidence=0.78,
            slots={"user_request": text, "source_agent": agent_id},
            reason="long_term_goal",
        )

    if _has_any(text, ["安排", "日程", "提醒", "加到", "放进", "排进", "预约"]):
        slots: dict[str, Any] = {
            "title": _extract_calendar_title(text),
            "stress_weight": 1.0,
            "created_reason": "用户在 Maxwell 私聊中要求安排或提醒。",
        }
        start = _extract_datetime(text, now)
        duration = _extract_duration_minutes(text) or 60
        missing: list[str] = []
        if start is None:
            missing.extend(["start", "end"])
        else:
            end = start + timedelta(minutes=duration)
            slots["start"] = start.isoformat()
            slots["end"] = end.isoformat()

        return _decision(
            agent_id,
            intent="calendar_create",
            tool_name="jarvis_calendar_add",
            confidence=0.82 if not missing else 0.68,
            slots=slots,
            missing_slots=missing,
            reason="calendar_request",
        )

    return _chat_only(agent_id, "no_maxwell_intent")


def _plan_nora(agent_id: str, text: str, now: datetime) -> AgentIntentDecision:
    if _has_any(text, ["咖啡", "拿铁", "美式", "茶", "奶茶", "能量饮料"]) and _has_any(text, ["还能喝", "可以喝", "现在喝", "睡", "提神"]):
        return _decision(
            agent_id,
            intent="caffeine_guard",
            tool_name="jarvis_caffeine_cutoff_guard",
            confidence=0.84,
            slots={
                "beverage_name": _extract_beverage(text),
                "proposed_time": now.isoformat(),
            },
            reason="caffeine_timing",
        )

    if _has_any(text, ["营养", "热量", "蛋白", "碳水", "脂肪"]) and _has_any(text, ["查", "看看", "怎么样", "分析"]):
        food_name = _extract_food_name(text)
        missing = [] if food_name else ["food_name"]
        slots = {"goal": "general"}
        if food_name:
            slots["food_name"] = food_name
        return _decision(
            agent_id,
            intent="nutrition_lookup",
            tool_name="jarvis_nutrition_lookup",
            confidence=0.72,
            slots=slots,
            missing_slots=missing,
            reason="nutrition_lookup",
        )

    if _has_any(text, ["吃什么", "吃点什么", "晚饭", "晚餐", "早餐", "午饭", "午餐", "餐", "撑得住"]):
        meals = _extract_meals(text)
        goal = "stress_recovery" if _has_any(text, ["累", "疲惫", "压力", "撑得住", "恢复", "焦虑"]) else "steady_energy"
        return _decision(
            agent_id,
            intent="meal_plan",
            tool_name="jarvis_meal_plan",
            confidence=0.8,
            slots={"meals": meals, "include_snack": True, "goal": goal},
            reason="meal_planning",
        )

    return _chat_only(agent_id, "no_nora_intent")


def _plan_mira(agent_id: str, text: str, now: datetime) -> AgentIntentDecision:
    if _has_any(text, ["回访", "提醒我状态", "看看我的状态", "跟进"]) and _has_any(text, ["明天", "之后", "晚点", "过会"]):
        return _decision(
            agent_id,
            intent="checkin_schedule",
            tool_name="jarvis_checkin_schedule",
            confidence=0.79,
            slots={
                "delay_hours": _extract_delay_hours(text),
                "duration_minutes": 10,
                "note": "情绪状态轻回访",
            },
            reason="emotional_checkin",
        )

    if _has_any(text, ["焦虑", "喘不过气", "慌", " panic", "崩溃", "紧张", "呼吸"]):
        return _decision(
            agent_id,
            intent="breathing_protocol",
            tool_name="jarvis_breathing_protocol",
            confidence=0.86,
            slots={"goal": "calm_down", "duration_minutes": 3, "intensity": "grounding"},
            reason="acute_anxiety",
        )

    return _chat_only(agent_id, "no_mira_intent")


def _plan_leo(agent_id: str, text: str, now: datetime) -> AgentIntentDecision:
    if _has_any(text, ["安排进日程", "排进日程", "放进日程", "加到日程", "安排"]) and _has_any(
        text,
        ["散步", "活动", "运动", "逛", "走走"],
    ):
        slots = {
            "activity_name": _extract_activity_name(text),
            "duration_minutes": _extract_duration_minutes(text) or 60,
            "preferred_period": _extract_period(text) or "afternoon",
        }
        missing: list[str] = []
        if _extract_datetime(text, now) is None:
            missing.append("start")
        return _decision(
            agent_id,
            intent="plan_activity_slot",
            tool_name="jarvis_plan_activity_slot",
            confidence=0.74,
            slots=slots,
            missing_slots=missing,
            reason="activity_scheduling",
        )

    if _has_any(text, ["周末", "附近", "去哪", "活动", "推荐"]) and _has_any(text, ["活动", "推荐", "低负担", "去哪", "玩"]):
        categories = ["low_effort"] if _has_any(text, ["低负担", "轻松", "不累"]) else []
        return _decision(
            agent_id,
            intent="local_activities",
            tool_name="jarvis_local_activities",
            confidence=0.76,
            slots={"radius_m": 2000, "limit": 5, "categories": categories},
            reason="local_activity_search",
        )

    return _chat_only(agent_id, "no_leo_intent")


def _decision(
    agent_id: str,
    *,
    intent: str,
    tool_name: str,
    confidence: float,
    slots: dict[str, Any],
    reason: str,
    missing_slots: list[str] | None = None,
) -> AgentIntentDecision:
    missing = missing_slots or []
    if missing:
        next_action: NextAction = "ask_missing_slots"
    elif tool_name in _CONFIRMATION_TOOLS:
        next_action = "pending_confirmation"
    else:
        next_action = "call_tool"
    return AgentIntentDecision(
        agent_id=agent_id,
        intent=intent,
        tool_name=tool_name,
        confidence=confidence,
        slots=slots,
        missing_slots=missing,
        next_action=next_action,
        reason=reason,
    )


def _chat_only(agent_id: str, reason: str) -> AgentIntentDecision:
    return AgentIntentDecision(
        agent_id=agent_id,
        intent="chat_only",
        tool_name=None,
        confidence=0.0,
        slots={},
        missing_slots=[],
        next_action="chat_only",
        reason=reason,
    )


def _normalize(message: str) -> str:
    return re.sub(r"\s+", " ", message.strip())


def _has_any(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def _is_small_talk(text: str) -> bool:
    small_talk_markers = ["你好", "早上好", "晚上好", "今天还不错", "谢谢", "辛苦了"]
    action_markers = ["安排", "提醒", "吃", "喝", "营养", "焦虑", "活动", "回访", "计划"]
    return _has_any(text, small_talk_markers) and not _has_any(text, action_markers)


def _extract_calendar_title(text: str) -> str:
    title = text
    title = re.sub(r".*?(提醒我|帮我安排|安排|加到日程|放进日程|排进日程)", "", title)
    title = re.sub(r"(明天|今天|后天|今晚|明晚|上午|下午|晚上|早上|中午|\d{1,2}\s*点|半小时|\d+(\.\d+)?\s*(个)?小时|\d+\s*分钟)", " ", title)
    title = re.sub(r"[，。！？,.!?]", " ", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title or "待安排事项"


def _extract_datetime(text: str, now: datetime) -> datetime | None:
    if not _has_any(text, ["今天", "明天", "后天", "今晚", "明晚", "点"]):
        return None

    day_offset = 0
    if "后天" in text:
        day_offset = 2
    elif "明天" in text or "明晚" in text:
        day_offset = 1

    hour_match = re.search(r"(\d{1,2})\s*点", text)
    if hour_match is None:
        if "早上" in text or "上午" in text:
            hour = 9
        elif "中午" in text:
            hour = 12
        elif "今晚" in text or "明晚" in text or "晚上" in text:
            hour = 19
        elif "下午" in text:
            hour = 15
        else:
            return None
    else:
        hour = int(hour_match.group(1))
        if _has_any(text, ["下午", "晚上", "今晚", "明晚"]) and hour < 12:
            hour += 12

    minute = 30 if "半" in text and hour_match is not None and text.find("半", hour_match.end(), hour_match.end() + 2) >= 0 else 0
    target = now + timedelta(days=day_offset)
    return target.replace(hour=hour, minute=minute, second=0, microsecond=0)


def _extract_duration_minutes(text: str) -> int | None:
    if "半小时" in text:
        return 30
    hour_match = re.search(r"(\d+(?:\.\d+)?)\s*(个)?小时", text)
    if hour_match:
        return max(1, int(float(hour_match.group(1)) * 60))
    minute_match = re.search(r"(\d+)\s*分钟", text)
    if minute_match:
        return max(1, int(minute_match.group(1)))
    return None


def _extract_delay_hours(text: str) -> int:
    if "明天" in text:
        return 24
    hour_match = re.search(r"(\d+)\s*(个)?小时", text)
    if hour_match:
        return max(1, min(72, int(hour_match.group(1))))
    if _has_any(text, ["晚点", "过会"]):
        return 3
    return 12


def _extract_meals(text: str) -> list[str]:
    meals: list[str] = []
    if _has_any(text, ["早餐", "早饭", "早上"]):
        meals.append("breakfast")
    if _has_any(text, ["午餐", "午饭", "中午"]):
        meals.append("lunch")
    if _has_any(text, ["晚餐", "晚饭", "晚上", "今晚"]):
        meals.append("dinner")
    return meals or ["breakfast", "lunch", "dinner"]


def _extract_beverage(text: str) -> str:
    if "奶茶" in text:
        return "tea"
    if "茶" in text:
        return "tea"
    if "能量饮料" in text:
        return "energy drink"
    return "coffee"


def _extract_food_name(text: str) -> str | None:
    if _has_any(text, ["这个", "这个东西", "它"]):
        return None
    match = re.search(r"(?:查一下|看看|分析一下)?(.+?)(?:的)?营养", text)
    if match:
        value = re.sub(r"^(帮我|请|想|这个)", "", match.group(1)).strip(" ，。？?")
        return value or None
    return None


def _extract_activity_name(text: str) -> str:
    for name in ["散步", "运动", "走走", "逛街", "看展"]:
        if name in text:
            return name
    return "低负担活动"


def _extract_period(text: str) -> str | None:
    if _has_any(text, ["早上", "上午"]):
        return "morning"
    if "中午" in text or "下午" in text:
        return "afternoon"
    if _has_any(text, ["晚上", "今晚"]):
        return "evening"
    return None
