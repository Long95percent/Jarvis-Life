import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

import pytest

from app.jarvis import persistence
from app.jarvis.models import LifeContext
from app.jarvis.proactive_routines import ProactiveRoutineScheduler


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    db_dir = Path("data") / "test_dbs"
    db_dir.mkdir(parents=True, exist_ok=True)
    tmp = db_dir / f"jarvis-{uuid4().hex}.db"
    monkeypatch.setattr(persistence, "_DB_PATH", tmp)
    persistence._initialized = False
    yield tmp
    persistence._initialized = False


def test_morning_brief_fires_once_when_user_recently_active():
    scheduler = ProactiveRoutineScheduler()
    now = datetime(2026, 4, 27, 8, 30)
    ctx = LifeContext(
        stress_level=4.0,
        schedule_density=5.0,
        sleep_quality=6.0,
        last_updated=now - timedelta(minutes=20),
        source_agent="user_chat",
    )

    with patch("app.jarvis.user_settings.get_enabled_agents", return_value=["maxwell"]), patch(
        "app.jarvis.mood_snapshot_maintenance.ensure_mood_snapshots",
        return_value={"skipped": True},
    ), patch("app.jarvis.planner_maintenance.run_planner_daily_maintenance_once", return_value={"skipped": True}):
        first = asyncio.run(scheduler.check_routines(ctx, now=now))
        second = asyncio.run(scheduler.check_routines(ctx, now=now))

    assert len(first) == 1
    assert second == []
    assert first[0]["agent_id"] == "maxwell"
    assert first[0]["trigger"] == "routine:morning_brief"
    assert first[0]["priority"] == "normal"
    assert "今天" in first[0]["content"]


def test_midday_appetite_inactive_user_is_low_priority_but_persisted():
    scheduler = ProactiveRoutineScheduler()
    now = datetime(2026, 4, 27, 12, 10)
    ctx = LifeContext(
        stress_level=3.0,
        schedule_density=4.0,
        sleep_quality=7.0,
        last_updated=now - timedelta(hours=6),
        source_agent="system",
    )

    with patch("app.jarvis.user_settings.get_enabled_agents", return_value=["nora"]), patch(
        "app.jarvis.mood_snapshot_maintenance.ensure_mood_snapshots",
        return_value={"skipped": True},
    ), patch("app.jarvis.planner_maintenance.run_planner_daily_maintenance_once", return_value={"skipped": True}):
        messages = asyncio.run(scheduler.check_routines(ctx, now=now))

    assert len(messages) == 1
    assert messages[0]["agent_id"] == "nora"
    assert messages[0]["trigger"] == "routine:midday_appetite"
    assert messages[0]["priority"] == "low"
    assert messages[0]["status"] == "pending"


def test_evening_checkin_becomes_high_priority_when_stress_is_high():
    scheduler = ProactiveRoutineScheduler()
    now = datetime(2026, 4, 27, 22, 5)
    ctx = LifeContext(
        stress_level=8.5,
        schedule_density=6.0,
        sleep_quality=5.0,
        mood_trend="negative",
        last_updated=now - timedelta(minutes=15),
        source_agent="user_ui",
    )

    with patch("app.jarvis.user_settings.get_enabled_agents", return_value=["mira"]), patch(
        "app.jarvis.mood_snapshot_maintenance.ensure_mood_snapshots",
        return_value={"skipped": True},
    ), patch("app.jarvis.planner_maintenance.run_planner_daily_maintenance_once", return_value={"skipped": True}):
        messages = asyncio.run(scheduler.check_routines(ctx, now=now))

    assert len(messages) == 1
    assert messages[0]["agent_id"] == "mira"
    assert messages[0]["trigger"] == "routine:evening_checkin"
    assert messages[0]["priority"] == "high"
    assert "压力" in messages[0]["content"]


def test_routines_do_not_fire_during_quiet_hours():
    scheduler = ProactiveRoutineScheduler()
    now = datetime(2026, 4, 27, 2, 30)
    ctx = LifeContext(last_updated=now - timedelta(minutes=10), source_agent="user_chat")

    with patch(
        "app.jarvis.mood_snapshot_maintenance.ensure_mood_snapshots",
        return_value={"skipped": True},
    ), patch("app.jarvis.planner_maintenance.run_planner_daily_maintenance_once", return_value={"skipped": True}):
        messages = asyncio.run(scheduler.check_routines(ctx, now=now))

    assert messages == []


def test_mood_snapshot_maintenance_runs_after_one_am():
    scheduler = ProactiveRoutineScheduler()
    now = datetime(2026, 5, 4, 1, 10)
    ctx = LifeContext(last_updated=now - timedelta(minutes=10), source_agent="user_chat")
    asyncio.run(persistence.save_emotion_observation(
        session_id="s-routine-mood",
        agent_id="mira",
        primary_emotion="stressed",
        secondary_emotions=[],
        valence=-0.4,
        arousal=0.7,
        stress_score=7,
        fatigue_score=6,
        risk_level="medium",
        confidence=0.7,
        evidence_summary="今天压力偏高",
        signals=["stress_signal"],
        source="test",
        created_at=datetime(2026, 5, 4, 0, 30).timestamp(),
    ))

    with patch("app.jarvis.user_settings.is_psychological_tracking_enabled", return_value=True), patch(
        "app.jarvis.planner_maintenance.run_planner_daily_maintenance_once",
        return_value={"skipped": True},
    ):
        messages = asyncio.run(scheduler.check_routines(ctx, now=now))

    mood_item = next(item for item in messages if item.get("routine_id") == "mood_snapshot_maintenance")
    assert mood_item["result"]["skipped"] is False
    assert "2026-05-04" in mood_item["result"]["checked"]
    snapshots = asyncio.run(persistence.list_mood_snapshots(start="2026-05-04", end="2026-05-04"))
    assert len(snapshots) == 1
