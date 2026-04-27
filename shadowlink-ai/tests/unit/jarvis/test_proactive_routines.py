from datetime import datetime, timedelta
from pathlib import Path
import tempfile
from unittest.mock import patch

import pytest

from app.jarvis import persistence
from app.jarvis.models import LifeContext
from app.jarvis.proactive_routines import ProactiveRoutineScheduler


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    tmp = Path(tempfile.mkdtemp()) / "jarvis.db"
    monkeypatch.setattr(persistence, "_DB_PATH", tmp)
    persistence._initialized = False
    yield tmp
    persistence._initialized = False


@pytest.mark.asyncio
async def test_morning_brief_fires_once_when_user_recently_active():
    scheduler = ProactiveRoutineScheduler()
    now = datetime(2026, 4, 27, 8, 30)
    ctx = LifeContext(
        stress_level=4.0,
        schedule_density=5.0,
        sleep_quality=6.0,
        last_updated=now - timedelta(minutes=20),
        source_agent="user_chat",
    )

    with patch("app.jarvis.user_settings.get_enabled_agents", return_value=["maxwell"]):
        first = await scheduler.check_routines(ctx, now=now)
        second = await scheduler.check_routines(ctx, now=now)

    assert len(first) == 1
    assert second == []
    assert first[0]["agent_id"] == "maxwell"
    assert first[0]["trigger"] == "routine:morning_brief"
    assert first[0]["priority"] == "normal"
    assert "今天" in first[0]["content"]


@pytest.mark.asyncio
async def test_midday_appetite_inactive_user_is_low_priority_but_persisted():
    scheduler = ProactiveRoutineScheduler()
    now = datetime(2026, 4, 27, 12, 10)
    ctx = LifeContext(
        stress_level=3.0,
        schedule_density=4.0,
        sleep_quality=7.0,
        last_updated=now - timedelta(hours=6),
        source_agent="system",
    )

    with patch("app.jarvis.user_settings.get_enabled_agents", return_value=["nora"]):
        messages = await scheduler.check_routines(ctx, now=now)

    assert len(messages) == 1
    assert messages[0]["agent_id"] == "nora"
    assert messages[0]["trigger"] == "routine:midday_appetite"
    assert messages[0]["priority"] == "low"
    assert messages[0]["status"] == "pending"


@pytest.mark.asyncio
async def test_evening_checkin_becomes_high_priority_when_stress_is_high():
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

    with patch("app.jarvis.user_settings.get_enabled_agents", return_value=["mira"]):
        messages = await scheduler.check_routines(ctx, now=now)

    assert len(messages) == 1
    assert messages[0]["agent_id"] == "mira"
    assert messages[0]["trigger"] == "routine:evening_checkin"
    assert messages[0]["priority"] == "high"
    assert "压力" in messages[0]["content"]


@pytest.mark.asyncio
async def test_routines_do_not_fire_during_quiet_hours():
    scheduler = ProactiveRoutineScheduler()
    now = datetime(2026, 4, 27, 2, 30)
    ctx = LifeContext(last_updated=now - timedelta(minutes=10), source_agent="user_chat")

    messages = await scheduler.check_routines(ctx, now=now)

    assert messages == []
