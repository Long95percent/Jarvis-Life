"""Daily mood snapshot aggregation for the psychological-care MVP."""

from __future__ import annotations

from collections import Counter
from datetime import date as Date, datetime, time as Time, timedelta
from statistics import mean
from typing import Any


def _day_bounds(day: str) -> tuple[float, float]:
    parsed = Date.fromisoformat(day)
    start = datetime.combine(parsed, Time.min)
    end = start + timedelta(days=1)
    return start.timestamp(), end.timestamp()


def _clamp(value: float, lower: float = 0.0, upper: float = 10.0) -> float:
    return max(lower, min(upper, value))


def _mood_from_valence(valence: float) -> float:
    return _clamp((valence + 1.0) * 5.0)


def build_snapshot_payload(
    day: str,
    observations: list[dict[str, Any]],
    behavior_observations: list[dict[str, Any]] | None = None,
    stress_signals: list[dict[str, Any]] | None = None,
    positive_events: list[str] | None = None,
) -> dict[str, Any] | None:
    behavior_observations = behavior_observations or []
    stress_signals = stress_signals or []
    positive_events = positive_events or []
    if not observations and not behavior_observations and not stress_signals and not positive_events:
        return None

    behavior_types = [str(item.get("observation_type") or "") for item in behavior_observations]
    has_sleep_behavior = any(item in behavior_types for item in ["late_night_usage", "beyond_bedtime"])
    stress_values = [float(item.get("stress_score") or 0.0) for item in observations] or [0.0]
    fatigue_values = [float(item.get("fatigue_score") or 0.0) for item in observations] or ([6.0] if has_sleep_behavior else [0.0])
    valence_values = [float(item.get("valence") or 0.0) for item in observations] or [0.0]
    confidence_values = [float(item.get("confidence") or 0.0) for item in observations]
    emotions = [str(item.get("primary_emotion") or "unknown") for item in observations]
    risk_levels = [str(item.get("risk_level") or "low") for item in observations]

    dominant_emotions = [name for name, _count in Counter(emotions).most_common(3)] or ["behavior_signal"]
    risk_flags: list[str] = []
    if "high" in risk_levels:
        risk_flags.append("high_risk_observation")
    if risk_levels.count("medium") >= 2:
        risk_flags.append("repeated_medium_risk")
    if max(fatigue_values or [0.0]) >= 7:
        risk_flags.append("fatigue_high")
    if max(stress_values or [0.0]) >= 7:
        risk_flags.append("stress_high")
    if "late_night_usage" in behavior_types:
        risk_flags.append("late_night_usage")
    if "beyond_bedtime" in behavior_types:
        risk_flags.append("beyond_bedtime")
    if "heartbeat" in behavior_types and len([item for item in behavior_types if item == "heartbeat"]) >= 3:
        risk_flags.append("continuous_online_signal")
    for signal in stress_signals:
        signal_type = str(signal.get("signal_type") or "schedule_pressure")
        if signal.get("severity") in {"medium", "high"} or float(signal.get("score") or 0.0) >= 5:
            risk_flags.append(signal_type)

    mood_score = round(mean(_mood_from_valence(value) for value in valence_values), 2)
    stress_score = round(mean(stress_values), 2)
    fatigue_score = round(mean(fatigue_values), 2)
    energy_score = round(_clamp(10.0 - fatigue_score), 2)
    behavior_sleep_risk = 8.0 if has_sleep_behavior else 2.0
    emotion_sleep_risk = 8.0 if any("sleep_signal" in (item.get("signals_json") or []) for item in observations) else 2.0
    sleep_risk_score = round(max(behavior_sleep_risk, emotion_sleep_risk), 2)
    schedule_pressure_score = round(min(10.0, max([float(item.get("score") or 0.0) for item in stress_signals] or [0.0])), 2)
    if confidence_values:
        confidence = mean(confidence_values) + min(0.2, len(observations) * 0.03)
    else:
        confidence = 0.35
    if behavior_observations:
        confidence += min(0.15, len(behavior_observations) * 0.02)
    if stress_signals:
        confidence += min(0.15, len(stress_signals) * 0.03)
    confidence = round(min(1.0, confidence), 2)

    negative_events = [str(item.get("evidence_summary") or "") for item in observations if str(item.get("risk_level") or "low") in {"medium", "high"}]
    negative_events.extend(str(item.get("reason") or "") for item in stress_signals if item.get("reason"))
    summary = (
        f"{day} 聚合了 {len(observations)} 条情绪 observation、{len(behavior_observations)} 条行为 observation、{len(stress_signals)} 条压力 signal；"
        f"主要情绪：{'、'.join(dominant_emotions)}；"
        f"压力均值 {stress_score}/10，日程压力 {schedule_pressure_score}/10，能量 {energy_score}/10。"
    )
    if positive_events:
        summary += f" 正向事件：{'、'.join(positive_events[:3])}。"
    if risk_flags:
        summary += f" 风险标记：{'、'.join(risk_flags)}。"

    return {
        "date": day,
        "mood_score": mood_score,
        "stress_score": stress_score,
        "energy_score": energy_score,
        "sleep_risk_score": sleep_risk_score,
        "schedule_pressure_score": schedule_pressure_score,
        "dominant_emotions": dominant_emotions,
        "positive_events": positive_events,
        "negative_events": negative_events[:5],
        "risk_flags": risk_flags,
        "summary": summary,
        "confidence": confidence,
    }


async def aggregate_mood_snapshot(day: str | None = None) -> dict[str, Any] | None:
    from app.jarvis.persistence import (
        list_background_task_days,
        list_behavior_observations,
        list_emotion_observations,
        list_jarvis_plan_days,
        list_maxwell_workbench_items,
        list_stress_signals,
        upsert_mood_snapshot,
    )
    from app.jarvis.stress_observation import aggregate_schedule_pressure_signals

    target_day = day or datetime.utcnow().date().isoformat()
    start_ts, end_ts = _day_bounds(target_day)
    observations = await list_emotion_observations(created_from=start_ts, created_to=end_ts, limit=500)
    behavior_observations = await list_behavior_observations(date=target_day, limit=500)
    stress_signals = await aggregate_schedule_pressure_signals(target_day)
    if not stress_signals:
        stress_signals = await list_stress_signals(date=target_day, limit=500)
    completed_task_days = await list_background_task_days(status="completed", plan_date=target_day, limit=50)
    completed_plan_days = await list_jarvis_plan_days(status="completed", start=target_day, end=target_day, limit=50)
    completed_workbench = await list_maxwell_workbench_items(status="done", plan_date=target_day, limit=50)
    positive_events = []
    positive_events.extend(f"完成任务：{item.get('title') or item.get('id')}" for item in completed_task_days[:5])
    positive_events.extend(f"完成计划：{item.get('title') or item.get('id')}" for item in completed_plan_days[:5])
    positive_events.extend(f"完成工作台事项：{item.get('title') or item.get('id')}" for item in completed_workbench[:5])
    positive_events.extend(
        f"表达积极情绪：{item.get('evidence_summary') or item.get('primary_emotion')}"
        for item in observations
        if str(item.get("primary_emotion") or "").lower() in {"happy", "relaxed", "calm", "joy", "positive"}
        or float(item.get("valence") or 0.0) >= 0.45
    )
    positive_events.extend(
        f"按时休息：{item.get('observation_type')}"
        for item in behavior_observations
        if str(item.get("observation_type") or "") in {"on_time_rest", "early_bedtime", "healthy_rest"}
    )
    positive_events.extend(
        f"减少任务负载：{signal.get('reason') or signal.get('signal_type')}"
        for signal in stress_signals
        if str(signal.get("signal_type") or "") in {"workload_reduced", "schedule_pressure_reduced"}
    )
    payload = build_snapshot_payload(target_day, observations, behavior_observations, stress_signals, positive_events=positive_events)
    if payload is None:
        return None
    snapshot = await upsert_mood_snapshot(**payload)
    try:
        from app.jarvis.care_triggers import evaluate_care_triggers

        await evaluate_care_triggers(target_day)
    except Exception:
        pass
    return snapshot
