"""Care trigger rules and feedback loop for psychological-care MVP."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from app.jarvis.persistence import (
    count_care_triggers_for_day,
    list_behavior_observations,
    list_mood_snapshots,
    list_stress_signals,
    recent_care_trigger_exists,
    recent_negative_care_feedback_count,
    recent_negative_care_feedback_count_by_type,
    save_care_trigger_and_intervention,
)
from app.jarvis.user_settings import is_psychological_tracking_enabled


@dataclass(frozen=True)
class CareTriggerCandidate:
    trigger_type: str
    severity: str
    reason: str
    content: str
    evidence_ids: list[dict[str, Any]]
    suggested_action: dict[str, Any]
    cooldown_hours: int = 24


def _day_minus(day: str, days: int) -> str:
    return (datetime.fromisoformat(day[:10]) - timedelta(days=days)).date().isoformat()


def _safe_content(trigger_type: str, severity: str, reason: str) -> str:
    if severity == "high" or trigger_type == "high_risk_keyword":
        return (
            "Mira 关心你的安全：我注意到这里可能有比较高的风险信号。"
            "我不会给你做诊断；如果你现在可能伤害自己，请优先联系身边可信任的人或当地紧急求助渠道。"
            "如果可以，先回复我一个字，或者把手机放到离自己更安全的位置。"
        )
    if trigger_type == "late_night_streak":
        return "Mira 轻轻提醒：这几天你都比较晚还在使用 Jarvis。要不要让 Maxwell 帮你明天留出一小段恢复时间？"
    if trigger_type == "task_overload":
        return "Mira 注意到今天任务和日程压力偏高。要不要把一个低优先级任务挪开，先保留一点恢复空间？"
    if trigger_type == "stress_streak":
        return "Mira 看到最近几天压力都偏高。要不要先做一次减负整理，只保留今天最关键的一件事？"
    return f"Mira 看到一个需要温和留意的信号：{reason} 要不要我帮你把接下来安排得轻一点？"


async def build_care_trigger_candidates(day: str | None = None) -> list[CareTriggerCandidate]:
    target_day = day or datetime.utcnow().date().isoformat()
    snapshots = await list_mood_snapshots(start=_day_minus(target_day, 2), end=target_day, limit=5)
    snapshot_by_date = {item["date"]: item for item in snapshots}
    today_snapshot = snapshot_by_date.get(target_day)
    stress_signals = await list_stress_signals(date=target_day, limit=20)
    behavior_today = await list_behavior_observations(date=target_day, limit=100)
    behavior_prev_1 = await list_behavior_observations(date=_day_minus(target_day, 1), limit=100)
    behavior_prev_2 = await list_behavior_observations(date=_day_minus(target_day, 2), limit=100)

    candidates: list[CareTriggerCandidate] = []
    risk_flags = set(today_snapshot.get("risk_flags") or []) if today_snapshot else set()
    if today_snapshot and "high_risk_observation" in risk_flags:
        reason = "当天快照包含 high_risk_observation，高风险只做安全提示和求助建议。"
        candidates.append(CareTriggerCandidate(
            trigger_type="high_risk_keyword",
            severity="high",
            reason=reason,
            content=_safe_content("high_risk_keyword", "high", reason),
            evidence_ids=[{"source": "jarvis_mood_snapshots", "date": target_day}],
            suggested_action={"kind": "safety_check", "requires_confirmation": False},
            cooldown_hours=12,
        ))

    stress_days = [snapshot_by_date.get(_day_minus(target_day, offset)) for offset in [0, 1, 2]]
    if all(item and float(item.get("stress_score") or 0) >= 7 for item in stress_days):
        reason = "最近 3 天 stress_score 均不低于 7，可能存在连续高压力。"
        candidates.append(CareTriggerCandidate(
            trigger_type="stress_streak",
            severity="medium",
            reason=reason,
            content=_safe_content("stress_streak", "medium", reason),
            evidence_ids=[{"source": "jarvis_mood_snapshots", "date": item["date"]} for item in stress_days if item],
            suggested_action={"kind": "reduce_today_scope", "handoff_target": "maxwell"},
            cooldown_hours=36,
        ))

    late_counts = []
    for observations in [behavior_today, behavior_prev_1, behavior_prev_2]:
        late_counts.append(any(item.get("observation_type") in {"late_night_usage", "beyond_bedtime"} for item in observations))
    if all(late_counts):
        reason = "连续 3 天存在晚间/超过 bedtime 活跃信号，只作为疲劳风险输入。"
        candidates.append(CareTriggerCandidate(
            trigger_type="late_night_streak",
            severity="medium",
            reason=reason,
            content=_safe_content("late_night_streak", "medium", reason),
            evidence_ids=[{"source": "jarvis_behavior_observations", "date": _day_minus(target_day, offset)} for offset in [0, 1, 2]],
            suggested_action={"kind": "schedule_recovery_window", "handoff_target": "maxwell"},
            cooldown_hours=36,
        ))

    overload_signals = [item for item in stress_signals if item.get("signal_type") in {"task_load_high", "workbench_backlog", "rest_window_insufficient", "schedule_density_high"} and float(item.get("score") or 0) >= 6]
    if overload_signals:
        reason = overload_signals[0].get("reason") or "今天存在任务或日程过载信号。"
        candidates.append(CareTriggerCandidate(
            trigger_type="task_overload",
            severity="medium" if max(float(item.get("score") or 0) for item in overload_signals) < 8 else "high",
            reason=str(reason),
            content=_safe_content("task_overload", "medium", str(reason)),
            evidence_ids=[{"source": "jarvis_stress_signals", "id": item.get("id"), "signal_type": item.get("signal_type")} for item in overload_signals[:5]],
            suggested_action={"kind": "move_low_priority_task", "handoff_target": "maxwell"},
            cooldown_hours=24,
        ))

    return candidates


async def evaluate_care_triggers(day: str | None = None) -> list[dict[str, Any]]:
    if not is_psychological_tracking_enabled():
        return []
    target_day = day or datetime.utcnow().date().isoformat()
    negative_feedback = await recent_negative_care_feedback_count(time.time() - 7 * 86400)
    daily_budget = 1 if negative_feedback >= 1 else 2
    if await count_care_triggers_for_day(target_day) >= daily_budget:
        return []

    saved: list[dict[str, Any]] = []
    candidates = await build_care_trigger_candidates(target_day)
    for candidate in candidates:
        type_negative_feedback = await recent_negative_care_feedback_count_by_type(candidate.trigger_type, time.time() - 14 * 86400)
        adjusted_cooldown_hours = candidate.cooldown_hours * (3 if type_negative_feedback >= 1 else 1)
        cooldown_after = time.time() - adjusted_cooldown_hours * 3600
        if await recent_care_trigger_exists(candidate.trigger_type, cooldown_after):
            continue
        result = await save_care_trigger_and_intervention(
            trigger_type=candidate.trigger_type,
            severity=candidate.severity,
            reason=candidate.reason,
            evidence_ids=candidate.evidence_ids,
            content=candidate.content,
            suggested_action=candidate.suggested_action,
            cooldown_until=time.time() + adjusted_cooldown_hours * 3600,
        )
        saved.append(result)
        if len(saved) >= daily_budget:
            break
    return saved
