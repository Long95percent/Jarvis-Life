"""Escalation rules — decide whether a private chat should be auto-escalated
to a group roundtable.

Rule-based for determinism (an LLM classifier would be more accurate but
adds latency + cost per message). Each rule inspects the user's message
plus the current LifeContext and may emit an EscalationHint.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.jarvis.models import LifeContext

Severity = Literal["info", "suggest", "urgent"]


@dataclass(frozen=True)
class EscalationHint:
    scenario_id: str
    severity: Severity
    reason: str
    countdown_seconds: int = 3  # UI auto-launches after this; 0 = no auto


# Keyword groups (Chinese + English) by theme
_STRESS_WORDS = [
    "压力", "焦虑", "撑不住", "崩溃", "累", "疲惫", "烦", "累死",
    "stressed", "anxious", "overwhelmed", "burnout", "exhausted",
]
_SCHEDULE_WORDS = [
    "日程", "会议", "安排", "开会", "忙死", "赶", "deadline", "ddl",
    "meeting", "schedule", "busy",
]
_MOOD_WORDS = [
    "难过", "低落", "不开心", "伤心", "失落", "无助",
    "sad", "down", "depressed", "hopeless",
]
_RELAX_WORDS = [
    "周末", "休息", "放松", "度假", "恢复",
    "weekend", "relax", "rest", "recharge",
]
_LIFESTYLE_WORDS = [
    "吃什么", "吃啥", "去哪玩", "活动", "运动", "散步", "推荐一下",
    "where to eat", "what to do", "activity",
]


def _contains_any(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(kw.lower() in lowered for kw in keywords)


def evaluate_escalation(
    *, user_message: str, agent_id: str, context: LifeContext
) -> EscalationHint | None:
    """Return an EscalationHint if the message warrants escalation, else None.

    Prioritization (first match wins):
      1. urgent stress cues + high stress context -> emotional_care
      2. mood decline cues + negative mood -> emotional_care
      3. schedule strain cues + high schedule density -> schedule_coord
      4. relax/weekend cues -> weekend_recharge
      5. lifestyle/activity cues -> local_lifestyle
    """
    msg = user_message.strip()

    # Rule 1: stress — strong signal combined with context
    if _contains_any(msg, _STRESS_WORDS):
        if context.stress_level >= 7.0:
            return EscalationHint(
                scenario_id="emotional_care",
                severity="urgent",
                reason=f"你提到压力,当前压力指数 {context.stress_level:.1f}/10 已偏高",
                countdown_seconds=3,
            )
        if context.stress_level >= 4.0:
            return EscalationHint(
                scenario_id="emotional_care",
                severity="suggest",
                reason="检测到压力相关话题,建议拉个圆桌一起帮你梳理",
                countdown_seconds=5,
            )

    # Rule 2: mood decline
    if _contains_any(msg, _MOOD_WORDS):
        if context.mood_trend == "negative":
            return EscalationHint(
                scenario_id="emotional_care",
                severity="urgent",
                reason="心情提示 + 当前情绪基调偏负面",
                countdown_seconds=3,
            )
        return EscalationHint(
            scenario_id="emotional_care",
            severity="suggest",
            reason="提到情绪话题,Mira 建议联合专家团队",
            countdown_seconds=5,
        )

    # Rule 3: schedule strain
    if _contains_any(msg, _SCHEDULE_WORDS):
        if context.schedule_density >= 7.0:
            return EscalationHint(
                scenario_id="schedule_coord",
                severity="urgent",
                reason=f"日程密度 {context.schedule_density:.1f}/10,需要多方协调",
                countdown_seconds=3,
            )
        if context.schedule_density >= 4.0:
            return EscalationHint(
                scenario_id="schedule_coord",
                severity="suggest",
                reason="日程话题,建议让 Maxwell 带队一起规划",
                countdown_seconds=5,
            )

    # Rule 4: weekend/relax
    if _contains_any(msg, _RELAX_WORDS):
        return EscalationHint(
            scenario_id="weekend_recharge",
            severity="suggest",
            reason="周末恢复话题,Leo 建议拉圆桌一起规划",
            countdown_seconds=5,
        )

    # Rule 5: lifestyle/activity
    if _contains_any(msg, _LIFESTYLE_WORDS):
        return EscalationHint(
            scenario_id="local_lifestyle",
            severity="info",
            reason="活动/生活话题,拉 Leo 带队给你建议",
            countdown_seconds=6,
        )

    return None
