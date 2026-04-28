"""Schedule pressure signal aggregation for psychological-care MVP."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as Date, datetime, time as Time, timedelta
from typing import Any

from app.jarvis.persistence import (
    list_background_task_days,
    list_agent_events,
    list_jarvis_plan_days,
    list_maxwell_workbench_items,
    list_mood_snapshots,
    replace_stress_signals,
)


@dataclass(frozen=True)
class StressSignalPayload:
    signal_type: str
    severity: str
    score: float
    reason: str
    source_refs: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_type": self.signal_type,
            "severity": self.severity,
            "score": self.score,
            "reason": self.reason,
            "source_refs": self.source_refs,
        }


def _severity(score: float) -> str:
    if score >= 8:
        return "high"
    if score >= 5:
        return "medium"
    return "low"


def _day_bounds(day: str) -> tuple[datetime, datetime]:
    parsed = Date.fromisoformat(day[:10])
    start = datetime.combine(parsed, Time.min)
    return start, start + timedelta(days=1)


def _event_minutes(event: Any) -> float:
    return max(0.0, (event.end - event.start).total_seconds() / 60.0) * float(getattr(event, "stress_weight", 1.0) or 1.0)


def _event_ref(event: Any) -> dict[str, Any]:
    return {
        "source": "calendar_events",
        "id": getattr(event, "id", None),
        "title": getattr(event, "title", "日程"),
        "start": getattr(event, "start", None).isoformat() if getattr(event, "start", None) else None,
        "end": getattr(event, "end", None).isoformat() if getattr(event, "end", None) else None,
    }


def _task_ref(day: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": day.get("source") or "background_task_days",
        "id": day.get("id"),
        "task_id": day.get("task_id") or day.get("plan_id"),
        "title": day.get("title"),
        "status": day.get("status"),
    }


def _workbench_ref(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": "maxwell_workbench_items",
        "id": item.get("id"),
        "task_day_id": item.get("task_day_id"),
        "title": item.get("title"),
        "status": item.get("status"),
    }


def _event_ref_from_agent_event(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": "jarvis_agent_events",
        "id": item.get("id"),
        "event_type": item.get("event_type"),
        "plan_id": item.get("plan_id"),
        "plan_day_id": item.get("plan_day_id"),
        "payload": item.get("payload") or {},
    }


def _event_mentions_day(item: dict[str, Any], day: str) -> bool:
    day_key = day[:10]
    payload = item.get("payload") or {}
    text = str(payload)
    return day_key in text or any(
        str(value or "")[:10] == day_key
        for value in [payload.get("today"), payload.get("plan_date"), payload.get("date")]
    )


async def _continuous_high_pressure_streak(day: str) -> tuple[int, list[dict[str, Any]]]:
    target = Date.fromisoformat(day[:10])
    start = (target - timedelta(days=6)).isoformat()
    snapshots = await list_mood_snapshots(start=start, end=day[:10], limit=10)
    by_date = {item.get("date"): item for item in snapshots}
    streak_items: list[dict[str, Any]] = []
    for offset in range(0, 7):
        key = (target - timedelta(days=offset)).isoformat()
        snapshot = by_date.get(key)
        if not snapshot:
            break
        if float(snapshot.get("stress_score") or 0) >= 7 or float(snapshot.get("schedule_pressure_score") or 0) >= 7:
            streak_items.append(snapshot)
            continue
        break
    return len(streak_items), list(reversed(streak_items))


async def build_schedule_pressure_signals(day: str) -> list[dict[str, Any]]:
    from app.jarvis.user_settings import is_psychological_tracking_enabled

    if not is_psychological_tracking_enabled():
        return []

    start, end = _day_bounds(day)
    signals: list[StressSignalPayload] = []

    try:
        from app.mcp.adapters.calendar_adapter import get_events_between

        events = get_events_between(start, end)
    except Exception:
        events = []

    weighted_minutes = sum(_event_minutes(event) for event in events)
    if weighted_minutes >= 240 or len(events) >= 4:
        score = min(10.0, max(weighted_minutes / 60.0, len(events) * 1.5))
        signals.append(StressSignalPayload(
            signal_type="schedule_density_high",
            severity=_severity(score),
            score=round(score, 2),
            reason=f"当天有 {len(events)} 个日程，加权占用约 {round(weighted_minutes / 60, 1)} 小时，日程密度偏高。",
            source_refs=[_event_ref(event) for event in events[:5]],
        ))

    evening_events = [event for event in events if event.start.hour >= 20 or event.end.hour >= 21]
    evening_minutes = sum(_event_minutes(event) for event in evening_events)
    if evening_minutes >= 90:
        score = min(10.0, evening_minutes / 30.0)
        signals.append(StressSignalPayload(
            signal_type="evening_load_high",
            severity=_severity(score),
            score=round(score, 2),
            reason=f"晚间仍有 {len(evening_events)} 个任务/日程，加权占用约 {round(evening_minutes)} 分钟，可能挤压恢复时间。",
            source_refs=[_event_ref(event) for event in evening_events[:5]],
        ))

    task_days = await list_background_task_days(plan_date=day, limit=200)
    plan_days = await list_jarvis_plan_days(start=day, end=day, limit=200)
    for item in task_days:
        item.setdefault("source", "background_task_days")
    for item in plan_days:
        item.setdefault("source", "jarvis_plan_days")
    unified_days = [*task_days, *plan_days]
    active_days = [item for item in unified_days if item.get("status") in {"pending", "pushed", "missed", "scheduled", "rescheduled"}]
    estimated_minutes = sum(int(item.get("estimated_minutes") or 0) for item in active_days)
    if len(active_days) >= 5 or estimated_minutes >= 240:
        score = min(10.0, max(len(active_days) * 1.4, estimated_minutes / 45.0))
        signals.append(StressSignalPayload(
            signal_type="task_load_high",
            severity=_severity(score),
            score=round(score, 2),
            reason=f"当天有 {len(active_days)} 个未完成/待处理计划项，预估约 {estimated_minutes} 分钟，任务负载偏高。",
            source_refs=[_task_ref(item) for item in active_days[:8]],
        ))

    missed_days = [item for item in unified_days if item.get("status") == "missed"]
    if missed_days:
        score = min(10.0, len(missed_days) * 2.0)
        signals.append(StressSignalPayload(
            signal_type="missed_tasks",
            severity=_severity(score),
            score=round(score, 2),
            reason=f"当天已有 {len(missed_days)} 个 missed 计划项，可能形成补偿压力。",
            source_refs=[_task_ref(item) for item in missed_days[:8]],
        ))

    reschedule_events = [
        item for item in await list_agent_events(event_type="plan.rescheduled", limit=100)
        if _event_mentions_day(item, day)
    ]
    skipped_reschedule_events = [
        item for item in await list_agent_events(event_type="plan.reschedule.skipped", limit=100)
        if _event_mentions_day(item, day)
    ]
    if reschedule_events or skipped_reschedule_events:
        count = len(reschedule_events) + len(skipped_reschedule_events)
        score = min(10.0, 3.0 + count * 2.0)
        signals.append(StressSignalPayload(
            signal_type="plan_reschedule_pressure",
            severity=_severity(score),
            score=round(score, 2),
            reason=f"当天关联 {count} 条计划重排/重排失败日志，说明计划负载已经触发调整。",
            source_refs=[_event_ref_from_agent_event(item) for item in [*reschedule_events, *skipped_reschedule_events][:8]],
        ))

    workbench_items = await list_maxwell_workbench_items(plan_date=day, limit=200)
    unfinished_workbench = [item for item in workbench_items if item.get("status") in {"todo", "doing"}]
    if len(unfinished_workbench) >= 4:
        score = min(10.0, len(unfinished_workbench) * 1.5)
        signals.append(StressSignalPayload(
            signal_type="workbench_backlog",
            severity=_severity(score),
            score=round(score, 2),
            reason=f"Maxwell 工作台仍有 {len(unfinished_workbench)} 个 todo/doing 项，执行队列偏满。",
            source_refs=[_workbench_ref(item) for item in unfinished_workbench[:8]],
        ))

    free_minutes = max(0.0, 16 * 60 - weighted_minutes - estimated_minutes)
    if weighted_minutes + estimated_minutes >= 8 * 60 or free_minutes < 180:
        score = min(10.0, (weighted_minutes + estimated_minutes) / 60.0)
        signals.append(StressSignalPayload(
            signal_type="rest_window_insufficient",
            severity=_severity(score),
            score=round(score, 2),
            reason=f"日程与计划合计约 {round((weighted_minutes + estimated_minutes) / 60, 1)} 小时，休息窗口可能不足。",
            source_refs=[
                *[_event_ref(event) for event in events[:4]],
                *[_task_ref(item) for item in active_days[:4]],
            ],
        ))

    streak_count, streak_items = await _continuous_high_pressure_streak(day)
    if streak_count >= 3:
        score = min(10.0, 4.0 + streak_count * 1.5)
        signals.append(StressSignalPayload(
            signal_type="continuous_high_pressure",
            severity=_severity(score),
            score=round(score, 2),
            reason=f"截至当天已连续 {streak_count} 天 stress_score 或 schedule_pressure_score 不低于 7。",
            source_refs=[{"source": "jarvis_mood_snapshots", "date": item.get("date")} for item in streak_items],
        ))

    return [signal.to_dict() for signal in signals]


async def aggregate_schedule_pressure_signals(day: str) -> list[dict[str, Any]]:
    from app.jarvis.user_settings import is_psychological_tracking_enabled

    if not is_psychological_tracking_enabled():
        return []

    signals = await build_schedule_pressure_signals(day)
    return await replace_stress_signals(date=day[:10], signals=signals)
