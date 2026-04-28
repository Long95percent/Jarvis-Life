"""Psychological-care trend aggregation and day-detail explanations."""

from __future__ import annotations

from datetime import date as Date, datetime, timedelta
from typing import Any


def _range_days(range_name: str, end: str | None = None) -> tuple[str, str, int]:
    today = Date.fromisoformat(end[:10]) if end else datetime.utcnow().date()
    normalized = range_name.lower().strip()
    if normalized == "week":
        days = 7
    elif normalized == "month":
        days = 30
    elif normalized == "year":
        days = 365
    else:
        raise ValueError("range must be one of week, month, year")
    start = today - timedelta(days=days - 1)
    return start.isoformat(), today.isoformat(), days


def _empty_point(day: str) -> dict[str, Any]:
    return {
        "date": day,
        "mood_score": None,
        "stress_score": None,
        "energy_score": None,
        "sleep_risk_score": None,
        "schedule_pressure_score": None,
        "dominant_emotions": [],
        "risk_flags": [],
        "summary": "暂无当日心理快照。",
        "confidence": 0.0,
    }


def empty_care_trends(range_name: str = "week", end: str | None = None, *, tracking_enabled: bool = False) -> dict[str, Any]:
    start, end_day, days = _range_days(range_name, end=end)
    start_date = Date.fromisoformat(start)
    series = [_empty_point((start_date + timedelta(days=offset)).isoformat()) for offset in range(days)]
    message = "心理趋势追踪已关闭。" if not tracking_enabled else "暂无当日心理快照。"
    return {
        "range": range_name,
        "start": start,
        "end": end_day,
        "tracking_enabled": tracking_enabled,
        "series": series,
        "details": {
            point["date"]: {
                "date": point["date"],
                "snapshot": point,
                "emotion_observations": [],
                "stress_signals": [],
                "behavior_observations": [],
                "care_triggers": [],
                "positive_events": [],
                "negative_events": [],
                "explanations": [message],
            }
            for point in series
        },
    }


def _explanations(
    snapshot: dict[str, Any],
    emotion_observations: list[dict[str, Any]],
    stress_signals: list[dict[str, Any]],
    behavior_observations: list[dict[str, Any]],
    care_triggers: list[dict[str, Any]],
) -> list[str]:
    result: list[str] = []
    if not snapshot or snapshot.get("mood_score") is None:
        result.append("当天还没有形成心理快照；有聊天情绪、行为或压力信号后会自动补齐。")

    schedule_signals = [
        item for item in stress_signals
        if item.get("signal_type") in {
            "schedule_density_high",
            "task_load_high",
            "workbench_backlog",
            "rest_window_insufficient",
            "overdue_task",
            "planner_missed",
            "schedule_pressure",
        }
    ]
    if schedule_signals:
        strongest = max(schedule_signals, key=lambda item: float(item.get("score") or 0))
        result.append(f"任务/日程压力：{strongest.get('reason') or strongest.get('signal_type')}（强度 {float(strongest.get('score') or 0):.1f}/10）。")

    for signal in stress_signals[:5]:
        reason = str(signal.get("reason") or "").strip()
        if reason and not any(reason in item for item in result):
            result.append(reason)

    late_behaviors = [item for item in behavior_observations if item.get("observation_type") in {"late_night_usage", "beyond_bedtime"}]
    if late_behaviors:
        deviations = [int(item.get("deviation_minutes") or 0) for item in late_behaviors if item.get("deviation_minutes") is not None]
        suffix = f"，最晚偏离约 {max(deviations)} 分钟" if deviations else ""
        result.append(f"作息信号：当天有 {len(late_behaviors)} 条晚睡/超过 bedtime 活跃记录{suffix}，作为疲劳风险输入。")

    low_energy = [
        item for item in emotion_observations
        if float(item.get("fatigue_score") or 0) >= 7 or str(item.get("primary_emotion") or "") in {"tired", "exhausted", "burnout"}
    ]
    if low_energy:
        result.append(f"低能量表达：当天有 {len(low_energy)} 条疲劳或低能量情绪 observation。")

    high_stress = [item for item in emotion_observations if float(item.get("stress_score") or 0) >= 7]
    if high_stress:
        result.append(f"高压表达：当天有 {len(high_stress)} 条聊天情绪 observation 的压力分不低于 7。")

    if snapshot.get("positive_events"):
        result.append("正向来源：" + "；".join(str(item) for item in (snapshot.get("positive_events") or [])[:3]) + "。")
    if snapshot.get("negative_events"):
        result.append("负向来源：" + "；".join(str(item) for item in (snapshot.get("negative_events") or [])[:3]) + "。")

    if care_triggers:
        result.append("关怀触发：" + "；".join(f"{item.get('trigger_type')}（{item.get('severity')}）" for item in care_triggers[:3]) + "。")

    if float(snapshot.get("stress_score") or 0) >= 7 or "stress_high" in set(snapshot.get("risk_flags") or []):
        result.append("连续高压会结合最近多天快照判断，并由关怀触发层做降频处理。")

    summary = str(snapshot.get("summary") or "").strip()
    if summary and summary != "暂无当日心理快照。":
        result.append(summary)

    deduped: list[str] = []
    for item in result:
        if item and item not in deduped:
            deduped.append(item)
    return deduped[:10]


def _snapshot_point(day: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "date": day,
        "mood_score": snapshot.get("mood_score"),
        "stress_score": snapshot.get("stress_score"),
        "energy_score": snapshot.get("energy_score"),
        "sleep_risk_score": snapshot.get("sleep_risk_score"),
        "schedule_pressure_score": snapshot.get("schedule_pressure_score"),
        "dominant_emotions": snapshot.get("dominant_emotions") or [],
        "risk_flags": snapshot.get("risk_flags") or [],
        "summary": snapshot.get("summary"),
        "confidence": snapshot.get("confidence", 0.0),
    }


async def build_care_day_detail(day: str) -> dict[str, Any]:
    from app.jarvis.mood_snapshot import _day_bounds
    from app.jarvis.persistence import (
        list_behavior_observations,
        list_care_triggers_for_day,
        list_emotion_observations,
        list_mood_snapshots,
        list_stress_signals,
    )

    target_day = Date.fromisoformat(day[:10]).isoformat()
    start_ts, end_ts = _day_bounds(target_day)
    snapshots = await list_mood_snapshots(start=target_day, end=target_day, limit=1)
    snapshot = snapshots[0] if snapshots else _empty_point(target_day)
    point = _snapshot_point(target_day, snapshot)
    emotion_observations = await list_emotion_observations(created_from=start_ts, created_to=end_ts, limit=80)
    stress_signals = await list_stress_signals(date=target_day, limit=50)
    behavior_observations = await list_behavior_observations(date=target_day, limit=80)
    care_triggers = await list_care_triggers_for_day(target_day, limit=50)
    return {
        "date": target_day,
        "snapshot": point,
        "emotion_observations": emotion_observations,
        "stress_signals": stress_signals,
        "behavior_observations": behavior_observations,
        "care_triggers": care_triggers,
        "positive_events": snapshot.get("positive_events") or [],
        "negative_events": snapshot.get("negative_events") or [],
        "explanations": _explanations(snapshot, emotion_observations, stress_signals, behavior_observations, care_triggers),
    }


async def build_care_trends(range_name: str = "week", end: str | None = None) -> dict[str, Any]:
    from app.jarvis.persistence import list_mood_snapshots

    start, end_day, days = _range_days(range_name, end=end)
    snapshots = await list_mood_snapshots(start=start, end=end_day, limit=days + 5)
    snapshot_by_date = {item["date"]: item for item in snapshots}

    series: list[dict[str, Any]] = []
    details: dict[str, Any] = {}
    start_date = Date.fromisoformat(start)
    for offset in range(days):
        day = (start_date + timedelta(days=offset)).isoformat()
        snapshot = snapshot_by_date.get(day) or _empty_point(day)
        point = _snapshot_point(day, snapshot)
        series.append(point)
        details[day] = await build_care_day_detail(day)

    return {
        "range": range_name,
        "start": start,
        "end": end_day,
        "tracking_enabled": True,
        "series": series,
        "details": details,
    }
