import tempfile
from pathlib import Path

import pytest

from app.jarvis import persistence


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    """Point persistence at a fresh temp DB for each test."""
    tmp = Path(tempfile.mkdtemp()) / "jarvis.db"
    monkeypatch.setattr(persistence, "_DB_PATH", tmp)
    persistence._initialized = False
    yield tmp
    persistence._initialized = False


@pytest.mark.asyncio
async def test_save_then_list_session():
    await persistence.save_session(
        session_id="s1",
        scenario_id="schedule_coord",
        scenario_name="今日日程协调",
        participants=["alfred", "nora"],
        agent_roster="jarvis",
        round_count=1,
    )
    sessions = await persistence.list_sessions()
    assert len(sessions) == 1
    assert sessions[0]["session_id"] == "s1"
    assert sessions[0]["participants"] == ["alfred", "nora"]


@pytest.mark.asyncio
async def test_append_turn_and_fetch():
    await persistence.save_session(
        session_id="s2",
        scenario_id="emotional_care",
        scenario_name="情绪疏导",
        participants=["mira"],
        agent_roster="jarvis",
        round_count=1,
    )
    await persistence.append_turn(
        session_id="s2", role="user", speaker_name="You", content="压力好大", timestamp=123.0,
    )
    await persistence.append_turn(
        session_id="s2", role="mira", speaker_name="Mira（心理师）", content="深呼吸。", timestamp=124.0,
    )
    turns = await persistence.get_session_turns("s2")
    assert len(turns) == 2
    assert turns[0]["role"] == "user"
    assert turns[1]["speaker_name"].startswith("Mira")


@pytest.mark.asyncio
async def test_snapshot_context_and_latest():
    await persistence.snapshot_context(
        stress_level=7.5,
        schedule_density=8.0,
        sleep_quality=5.5,
        mood_trend="negative",
        source_agent="user",
    )
    latest = await persistence.latest_context()
    assert latest is not None
    assert latest["stress_level"] == 7.5
    assert latest["mood_trend"] == "negative"


@pytest.mark.asyncio
async def test_context_history_ordered_desc():
    for i in range(3):
        await persistence.snapshot_context(
            stress_level=float(i),
            schedule_density=0, sleep_quality=7,
            mood_trend="neutral", source_agent="test",
        )
    history = await persistence.context_history(limit=10)
    assert len(history) == 3
    assert history[0]["stress_level"] == 2  # most recent first
