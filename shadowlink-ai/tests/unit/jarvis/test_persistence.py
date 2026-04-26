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


@pytest.mark.asyncio
async def test_demo_run_trace_and_memory_export():
    await persistence.start_demo_run(
        demo_run_id="demo-ielts-001",
        seed_name="ielts-rhythm-travel",
        profile_seed={"goals": ["IELTS 7.0"], "care_preference": "low_interrupt"},
    )

    memory = await persistence.save_demo_memory_item(
        demo_run_id="demo-ielts-001",
        demo_step_id="step-01",
        memory_kind="care_preference",
        content="用户偏好低打扰、先共情再建议。",
        source_text="最近压力大，别太频繁提醒我。",
        sensitivity="private",
        confidence=0.8,
        importance=0.9,
    )
    trace = await persistence.append_demo_trace_event(
        demo_run_id="demo-ielts-001",
        demo_step_id="step-01",
        event_type="agent_reply",
        agent_id="mira",
        user_input="最近压力大，别太频繁提醒我。",
        agent_reply="我会降低打扰频率。",
        memory_events=[{"memory_id": memory["id"], "action": "created"}],
        confirmation={"required": False},
    )

    exported = await persistence.export_demo_trace("demo-ielts-001")
    assert exported is not None
    assert exported["demo_run"]["profile_seed"]["goals"] == ["IELTS 7.0"]
    assert exported["memory_items"][0]["memory_kind"] == "care_preference"
    assert exported["memory_items"][0]["sensitivity"] == "private"
    assert exported["trace_events"][0]["id"] == trace["id"]
    assert exported["trace_events"][0]["memory_events"][0]["memory_id"] == memory["id"]


@pytest.mark.asyncio
async def test_reset_demo_data_only_clears_demo_tables():
    await persistence.save_session(
        session_id="s-demo-keep",
        scenario_id="schedule_coord",
        scenario_name="日程协调",
        participants=["maxwell"],
        agent_roster="jarvis",
        round_count=1,
    )
    await persistence.start_demo_run(
        demo_run_id="demo-reset-001",
        seed_name="reset-check",
        profile_seed={},
    )
    await persistence.save_demo_memory_item(
        demo_run_id="demo-reset-001",
        demo_step_id="step-01",
        memory_kind="fact",
        content="测试记忆",
    )

    deleted = await persistence.reset_demo_data()

    assert deleted["demo_runs"] == 1
    assert deleted["memory_items"] == 1
    assert await persistence.list_demo_runs() == []
    assert len(await persistence.list_sessions()) == 1


@pytest.mark.asyncio
async def test_jarvis_memory_save_list_dedupe_and_delete():
    first = await persistence.save_jarvis_memory(
        memory_kind="preference",
        content="用户偏好低打扰关心。",
        source_agent="mira",
        session_id="chat-1",
        source_text="不要太频繁提醒我",
        structured_payload={"category": "care_preference"},
        sensitivity="private",
        confidence=0.7,
        importance=0.8,
    )
    second = await persistence.save_jarvis_memory(
        memory_kind="preference",
        content="用户偏好低打扰关心。",
        source_agent="mira",
        session_id="chat-1",
        source_text="别频繁提醒",
        structured_payload={"category": "care_preference"},
        sensitivity="private",
        confidence=0.9,
        importance=0.6,
    )

    memories = await persistence.list_jarvis_memories(limit=10)
    assert first["id"] == second["id"]
    assert len(memories) == 1
    assert memories[0]["confidence"] == 0.9
    assert memories[0]["importance"] == 0.8

    await persistence.mark_jarvis_memories_used([first["id"]])
    assert (await persistence.list_jarvis_memories(limit=1))[0]["last_used_at"] is not None
    assert await persistence.delete_jarvis_memory(first["id"]) is True
    assert await persistence.list_jarvis_memories(limit=10) == []
