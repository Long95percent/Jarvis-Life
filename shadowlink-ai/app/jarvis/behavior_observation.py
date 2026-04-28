"""Behavior observation MVP for psychological-care signals.

This layer records usage-behavior signals only. Late-night or beyond-bedtime
activity is treated as a fatigue/risk signal, never as a diagnosis.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time as Time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.config import settings as app_settings
from app.jarvis.persistence import list_behavior_observations, save_behavior_observation, upsert_behavior_activity_window
from app.jarvis.user_settings import get_settings


@dataclass(frozen=True)
class BehaviorObservationPayload:
    date: str
    session_id: str | None
    agent_id: str
    observation_type: str
    expected_bedtime: str | None
    expected_wake: str | None
    actual_first_active_at: float | None = None
    actual_last_active_at: float | None = None
    deviation_minutes: int | None = None
    duration_minutes: int | None = None
    source: str = "chat_activity_mvp"
    created_at: float | None = None


def _local_timezone() -> ZoneInfo | timezone:
    try:
        return ZoneInfo(app_settings.default_timezone or "Asia/Shanghai")
    except Exception:
        return timezone(timedelta(hours=8))


def _parse_hhmm(value: str | None) -> Time | None:
    if not value:
        return None
    try:
        hour, minute = value.split(":", 1)
        return Time(hour=int(hour), minute=int(minute))
    except Exception:
        return None


def _minutes_after_bedtime(now: datetime, bedtime: str | None) -> int | None:
    bedtime_value = _parse_hhmm(bedtime)
    if bedtime_value is None:
        return None
    expected = datetime.combine(now.date(), bedtime_value, tzinfo=now.tzinfo)
    wake = _parse_hhmm(get_settings().profile.sleep_schedule.wake)
    if wake is not None and bedtime_value < wake and now.time() < wake:
        expected -= timedelta(days=1)
    if now < expected:
        return None
    return int((now - expected).total_seconds() // 60)


async def build_chat_activity_observations(
    *,
    session_id: str | None,
    agent_id: str,
    occurred_at: datetime | None = None,
) -> list[BehaviorObservationPayload]:
    tz = _local_timezone()
    now = (occurred_at or datetime.now(tz)).astimezone(tz)
    created_at = now.timestamp()
    day = now.date().isoformat()
    sleep_schedule = get_settings().profile.sleep_schedule
    recent = await list_behavior_observations(date=day, session_id=session_id, limit=100)

    payloads: list[BehaviorObservationPayload] = []
    common = {
        "date": day,
        "session_id": session_id,
        "agent_id": agent_id,
        "expected_bedtime": sleep_schedule.bedtime,
        "expected_wake": sleep_schedule.wake,
        "created_at": created_at,
    }

    first_seen = next((item for item in recent if item.get("observation_type") == "first_active"), None)
    if first_seen is None:
        payloads.append(BehaviorObservationPayload(
            **common,
            observation_type="first_active",
            actual_first_active_at=created_at,
        ))

    last_active_items = [item for item in recent if item.get("actual_last_active_at") is not None]
    previous_last = max((float(item["actual_last_active_at"]) for item in last_active_items), default=None)
    duration_minutes = int((created_at - previous_last) // 60) if previous_last is not None and created_at >= previous_last else None
    payloads.append(BehaviorObservationPayload(
        **common,
        observation_type="last_active",
        actual_last_active_at=created_at,
        duration_minutes=duration_minutes,
    ))

    late_night = now.hour >= 23 or now.hour < 5
    if late_night:
        payloads.append(BehaviorObservationPayload(
            **common,
            observation_type="late_night_usage",
            actual_last_active_at=created_at,
            deviation_minutes=_minutes_after_bedtime(now, sleep_schedule.bedtime),
        ))

    bedtime_deviation = _minutes_after_bedtime(now, sleep_schedule.bedtime)
    if bedtime_deviation is not None and bedtime_deviation >= 30:
        payloads.append(BehaviorObservationPayload(
            **common,
            observation_type="beyond_bedtime",
            actual_last_active_at=created_at,
            deviation_minutes=bedtime_deviation,
        ))

    return payloads


async def record_chat_activity_observations(
    *,
    session_id: str | None,
    agent_id: str,
    occurred_at: datetime | None = None,
) -> list[dict[str, object]]:
    from app.jarvis.user_settings import is_psychological_tracking_enabled

    if not is_psychological_tracking_enabled():
        return []

    payloads = await build_chat_activity_observations(
        session_id=session_id,
        agent_id=agent_id,
        occurred_at=occurred_at,
    )
    saved: list[dict[str, object]] = []
    for payload in payloads:
        saved.append(await save_behavior_observation(**payload.__dict__))
    return saved


async def record_behavior_event(
    *,
    session_id: str | None,
    agent_id: str,
    observation_type: str,
    occurred_at: datetime | None = None,
    duration_minutes: int | None = None,
    session_started_at: datetime | None = None,
) -> dict[str, object]:
    from app.jarvis.user_settings import is_psychological_tracking_enabled

    if not is_psychological_tracking_enabled():
        return {}

    tz = _local_timezone()
    now = (occurred_at or datetime.now(tz)).astimezone(tz)
    started = (session_started_at.astimezone(tz) if session_started_at else now)
    sleep_schedule = get_settings().profile.sleep_schedule
    created_at = now.timestamp()
    started_at = started.timestamp()
    if observation_type in {"heartbeat", "visibility_visible", "app_opened", "app_activated", "app_restored", "resume", "idle_end"}:
        return await upsert_behavior_activity_window(
            date=now.date().isoformat(),
            session_id=session_id,
            agent_id=agent_id,
            expected_bedtime=sleep_schedule.bedtime,
            expected_wake=sleep_schedule.wake,
            started_at=started_at,
            last_active_at=created_at,
            deviation_minutes=_minutes_after_bedtime(now, sleep_schedule.bedtime),
            duration_minutes=duration_minutes,
            source="frontend_activity_window",
        )
    return await save_behavior_observation(
        date=now.date().isoformat(),
        session_id=session_id,
        agent_id=agent_id,
        observation_type=observation_type,
        expected_bedtime=sleep_schedule.bedtime,
        expected_wake=sleep_schedule.wake,
        actual_last_active_at=created_at,
        deviation_minutes=_minutes_after_bedtime(now, sleep_schedule.bedtime),
        duration_minutes=duration_minutes,
        source="frontend_lifecycle_mvp",
        created_at=created_at,
    )
