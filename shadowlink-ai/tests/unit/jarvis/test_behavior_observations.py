import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from app.jarvis import persistence
from app.jarvis.behavior_observation import record_chat_activity_observations
from app.api.v1.jarvis_router import BehaviorEventRequest, list_care_behavior_observations, record_care_behavior_event
from app.jarvis.user_settings import JarvisSettings, SleepSchedule, UserProfile


CN_TZ = timezone(timedelta(hours=8))


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    db_dir = Path("data") / "test_dbs"
    db_dir.mkdir(parents=True, exist_ok=True)
    tmp = db_dir / f"jarvis-{uuid4().hex}.db"
    monkeypatch.setattr(persistence, "_DB_PATH", tmp)
    persistence._initialized = False
    yield tmp
    persistence._initialized = False


@pytest.fixture(autouse=True)
def sleep_profile(monkeypatch):
    settings = JarvisSettings(
        profile=UserProfile(sleep_schedule=SleepSchedule(bedtime="23:00", wake="07:00"))
    )
    monkeypatch.setattr("app.jarvis.behavior_observation.get_settings", lambda: settings)


def test_first_chat_records_first_and_last_active():
    now = datetime(2026, 4, 28, 9, 0, tzinfo=CN_TZ)

    saved = asyncio.run(record_chat_activity_observations(
        session_id="s-behavior-1",
        agent_id="mira",
        occurred_at=now,
    ))

    types = {item["observation_type"] for item in saved}
    assert types == {"first_active", "last_active"}
    observations = asyncio.run(persistence.list_behavior_observations(date="2026-04-28"))
    assert len(observations) == 2
    assert observations[0]["expected_bedtime"] == "23:00"
    assert observations[0]["expected_wake"] == "07:00"


def test_second_chat_only_updates_last_active_with_duration():
    first = datetime(2026, 4, 28, 9, 0, tzinfo=CN_TZ)
    second = datetime(2026, 4, 28, 9, 45, tzinfo=CN_TZ)

    asyncio.run(record_chat_activity_observations(session_id="s-behavior-2", agent_id="mira", occurred_at=first))
    saved = asyncio.run(record_chat_activity_observations(session_id="s-behavior-2", agent_id="mira", occurred_at=second))

    assert [item["observation_type"] for item in saved] == ["last_active"]
    assert saved[0]["duration_minutes"] == 45


def test_late_night_chat_records_fatigue_signal_without_diagnosis():
    now = datetime(2026, 4, 28, 23, 45, tzinfo=CN_TZ)

    saved = asyncio.run(record_chat_activity_observations(
        session_id="s-behavior-3",
        agent_id="mira",
        occurred_at=now,
    ))

    types = {item["observation_type"] for item in saved}
    assert "late_night_usage" in types
    assert "beyond_bedtime" in types
    beyond = next(item for item in saved if item["observation_type"] == "beyond_bedtime")
    assert beyond["deviation_minutes"] == 45
    assert "diagnosis" not in beyond


def test_frontend_lifecycle_event_api_records_heartbeat_and_close():
    heartbeat = asyncio.run(record_care_behavior_event(BehaviorEventRequest(
        session_id="s-behavior-api",
        agent_id="mira",
        observation_type="heartbeat",
        duration_minutes=5,
    )))
    closed = asyncio.run(record_care_behavior_event(BehaviorEventRequest(
        session_id="s-behavior-api",
        agent_id="mira",
        observation_type="closed",
        duration_minutes=6,
    )))

    assert heartbeat["observation"]["observation_type"] == "activity_window"
    assert closed["observation"]["observation_type"] == "closed"
    listed = asyncio.run(list_care_behavior_observations(session_id="s-behavior-api"))
    assert [item["observation_type"] for item in listed[:2]] == ["closed", "activity_window"]


def test_heartbeat_events_merge_into_single_activity_window():
    first = datetime(2026, 4, 28, 10, 0, tzinfo=CN_TZ).timestamp()
    second = datetime(2026, 4, 28, 10, 10, tzinfo=CN_TZ).timestamp()

    asyncio.run(record_care_behavior_event(BehaviorEventRequest(
        session_id="s-window",
        agent_id="mira",
        observation_type="heartbeat",
        occurred_at=first,
        session_started_at=first,
    )))
    updated = asyncio.run(record_care_behavior_event(BehaviorEventRequest(
        session_id="s-window",
        agent_id="mira",
        observation_type="heartbeat",
        occurred_at=second,
        session_started_at=first,
    )))

    listed = asyncio.run(list_care_behavior_observations(session_id="s-window"))
    windows = [item for item in listed if item["observation_type"] == "activity_window"]
    assert len(windows) == 1
    assert updated["observation"]["id"] == windows[0]["id"]
    assert windows[0]["duration_minutes"] == 10
    assert windows[0]["actual_first_active_at"] == first
    assert windows[0]["actual_last_active_at"] == second


def test_idle_resume_and_desktop_lifecycle_events_are_recorded():
    idle = asyncio.run(record_care_behavior_event(BehaviorEventRequest(
        session_id="s-lifecycle",
        agent_id="mira",
        observation_type="idle_start",
        duration_minutes=5,
    )))
    resumed = asyncio.run(record_care_behavior_event(BehaviorEventRequest(
        session_id="s-lifecycle",
        agent_id="mira",
        observation_type="resume",
        duration_minutes=8,
    )))
    minimized = asyncio.run(record_care_behavior_event(BehaviorEventRequest(
        session_id="s-lifecycle",
        agent_id="mira",
        observation_type="app_minimized",
        duration_minutes=9,
    )))

    assert idle["observation"]["observation_type"] == "idle_start"
    assert resumed["observation"]["observation_type"] == "activity_window"
    assert minimized["observation"]["observation_type"] == "app_minimized"


def test_behavior_event_stops_when_psychological_tracking_disabled(monkeypatch):
    monkeypatch.setattr("app.jarvis.user_settings.is_psychological_tracking_enabled", lambda: False)

    result = asyncio.run(record_care_behavior_event(BehaviorEventRequest(
        session_id="s-disabled",
        agent_id="mira",
        observation_type="heartbeat",
        duration_minutes=1,
    )))

    assert result == {"observation": None, "tracking_enabled": False}
    assert asyncio.run(list_care_behavior_observations(session_id="s-disabled")) == []
