import tempfile
import sqlite3
from pathlib import Path

import pytest

from app.api.v1.jarvis_router import PendingActionConfirmRequest, confirm_pending_action_item
from app.jarvis import persistence
from app.jarvis.models import ProactiveMessage


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
async def test_proactive_messages_are_persistent_and_non_destructive():
    saved = await persistence.save_proactive_message(
        ProactiveMessage(
            agent_id="alfred",
            agent_name="Alfred",
            content="你的压力偏高，我先帮你看一下今天的安排。",
            trigger="stress_spike",
        )
    )

    first_read = await persistence.list_proactive_messages(include_read=False)
    second_read = await persistence.list_proactive_messages(include_read=False)

    assert [msg["id"] for msg in first_read] == [saved["id"]]
    assert [msg["id"] for msg in second_read] == [saved["id"]]
    assert first_read[0]["status"] == "pending"
    assert first_read[0]["read"] is False


@pytest.mark.asyncio
async def test_proactive_message_status_flow_read_and_dismissed():
    saved = await persistence.save_proactive_message(
        ProactiveMessage(
            agent_id="mira",
            agent_name="Mira",
            content="我注意到你最近情绪在下降。",
            trigger="mood_declining",
        )
    )

    delivered = await persistence.mark_proactive_messages_delivered([saved["id"]])
    assert delivered == 1
    after_delivery = await persistence.list_proactive_messages(include_read=False)
    assert after_delivery[0]["status"] == "delivered"
    assert after_delivery[0]["delivered_at"] is not None

    read = await persistence.mark_proactive_message_read(saved["id"])
    assert read is not None
    assert read["status"] == "read"
    assert read["read"] is True
    assert read["read_at"] is not None
    assert await persistence.list_proactive_messages(include_read=False) == []

    dismissed_msg = await persistence.save_proactive_message(
        ProactiveMessage(
            agent_id="nora",
            agent_name="Nora",
            content="睡眠不足时先别安排高强度训练。",
            trigger="sleep_poor",
        )
    )
    dismissed = await persistence.dismiss_proactive_message(dismissed_msg["id"])
    assert dismissed is not None
    assert dismissed["status"] == "dismissed"
    assert dismissed["dismissed_at"] is not None
    assert await persistence.list_proactive_messages(include_read=True) == [read]


@pytest.mark.asyncio
async def test_proactive_routine_runs_are_recorded_once_per_day():
    assert await persistence.has_proactive_routine_run("morning_brief", "2026-04-27") is False

    saved = await persistence.save_proactive_routine_run(
        routine_id="morning_brief",
        run_date="2026-04-27",
        message_id="msg-morning",
    )
    repeated = await persistence.save_proactive_routine_run(
        routine_id="morning_brief",
        run_date="2026-04-27",
        message_id="msg-duplicate",
    )

    assert saved["routine_id"] == "morning_brief"
    assert saved["run_date"] == "2026-04-27"
    assert saved["message_id"] == "msg-morning"
    assert repeated["message_id"] == "msg-morning"
    assert await persistence.has_proactive_routine_run("morning_brief", "2026-04-27") is True
    assert await persistence.has_proactive_routine_run("morning_brief", "2026-04-28") is False


@pytest.mark.asyncio
async def test_existing_conversation_and_collaboration_tables_get_session_columns(temp_db):
    with sqlite3.connect(temp_db) as con:
        con.execute(
            """
            CREATE TABLE conversation_history (
                id TEXT PRIMARY KEY,
                conversation_type TEXT NOT NULL,
                title TEXT NOT NULL,
                agent_id TEXT,
                scenario_id TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        con.execute(
            """
            CREATE TABLE collaboration_memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_agent TEXT NOT NULL,
                participant_agents TEXT NOT NULL,
                memory_kind TEXT NOT NULL,
                content TEXT NOT NULL,
                structured_payload TEXT NOT NULL,
                importance REAL NOT NULL DEFAULT 1.0,
                created_at REAL NOT NULL
            )
            """
        )
        con.commit()
    persistence._initialized = False

    saved = await persistence.save_conversation(
        conversation_id="private:s1:maxwell",
        conversation_type="private_chat",
        title="Maxwell 私聊",
        agent_id="maxwell",
        scenario_id=None,
        session_id="s1",
        route_payload={"mode": "private_chat"},
    )
    await persistence.save_collaboration_memory(
        session_id="s1",
        source_agent="maxwell",
        participant_agents=["maxwell", "alfred"],
        memory_kind="coordination_summary",
        content="Maxwell asked Alfred for schedule context.",
    )

    assert saved["session_id"] == "s1"
    memories = await persistence.get_relevant_collaboration_memories("alfred")
    assert memories[0]["session_id"] == "s1"


@pytest.mark.asyncio
async def test_private_chat_history_can_be_scoped_by_session():
    await persistence.save_chat_turn(
        session_id="private-maxwell-a",
        agent_id="maxwell",
        role="user",
        content="A 会话的问题",
    )
    await persistence.save_chat_turn(
        session_id="private-maxwell-a",
        agent_id="maxwell",
        role="agent",
        content="A 会话的回复",
    )
    await persistence.save_chat_turn(
        session_id="private-maxwell-b",
        agent_id="maxwell",
        role="user",
        content="B 会话的问题",
    )

    session_a = await persistence.get_chat_history("maxwell", session_id="private-maxwell-a")
    session_b = await persistence.get_chat_history("maxwell", session_id="private-maxwell-b")
    all_maxwell = await persistence.get_chat_history("maxwell")

    assert [turn["content"] for turn in session_a] == ["A 会话的问题", "A 会话的回复"]
    assert [turn["content"] for turn in session_b] == ["B 会话的问题"]
    assert len(all_maxwell) == 3


@pytest.mark.asyncio
async def test_clearing_private_chat_history_is_session_scoped():
    await persistence.save_chat_turn(
        session_id="private-mira-a",
        agent_id="mira",
        role="user",
        content="A 会话里说压力大",
    )
    await persistence.save_chat_turn(
        session_id="private-mira-b",
        agent_id="mira",
        role="user",
        content="B 会话里说睡不好",
    )

    cleared = await persistence.clear_chat_history("mira", session_id="private-mira-a")
    session_a = await persistence.get_chat_history("mira", session_id="private-mira-a")
    session_b = await persistence.get_chat_history("mira", session_id="private-mira-b")
    all_mira = await persistence.get_chat_history("mira")

    assert cleared == 1
    assert session_a == []
    assert [turn["content"] for turn in session_b] == ["B 会话里说睡不好"]
    assert [turn["content"] for turn in all_mira] == ["B 会话里说睡不好"]


@pytest.mark.asyncio
async def test_background_task_days_are_persisted_and_completable():
    task = await persistence.save_background_task(
        task_id="task-ielts",
        title="雅思备考计划",
        task_type="long_project",
        source_agent="maxwell",
        original_user_request="帮我安排 7 天游雅思学习计划",
        goal="雅思备考",
        time_horizon={"start_after": "2026-05-01", "target_date": "2026-05-07"},
        milestones=[],
        subtasks=[],
        calendar_candidates=[],
    )
    assert task["id"] == "task-ielts"

    days = await persistence.save_background_task_days(
        task_id="task-ielts",
        daily_plan=[
            {
                "date": "2026-05-01",
                "title": "雅思听力精听",
                "description": "完成一组听力精听并记录错因。",
                "start_time": "20:00",
                "end_time": "21:00",
                "estimated_minutes": 60,
            },
            {
                "date": "2026-05-02",
                "title": "雅思阅读限时训练",
                "description": "完成一篇阅读并复盘题型。",
                "estimated_minutes": 60,
            },
        ],
    )

    assert len(days) == 2
    assert [day["title"] for day in days] == ["雅思听力精听", "雅思阅读限时训练"]
    assert all(day["status"] == "pending" for day in days)

    completed = await persistence.update_background_task_day_status(days[0]["id"], "completed")
    assert completed is not None
    assert completed["status"] == "completed"

    pending_days = await persistence.list_background_task_days(task_id="task-ielts", status="pending")
    assert [day["title"] for day in pending_days] == ["雅思阅读限时训练"]


@pytest.mark.asyncio
async def test_push_background_task_days_to_workbench_is_idempotent():
    await persistence.save_background_task(
        task_id="task-workbench",
        title="雅思备考计划",
        task_type="long_project",
        source_agent="maxwell",
        original_user_request="帮我安排雅思学习计划",
        goal="雅思备考",
        time_horizon={"start_after": "2026-05-01", "target_date": "2026-05-02"},
        milestones=[],
        subtasks=[],
        calendar_candidates=[],
    )
    await persistence.save_background_task_days(
        task_id="task-workbench",
        daily_plan=[
            {
                "date": "2026-05-01",
                "title": "雅思听力精听",
                "description": "完成一组听力精听。",
                "start_time": "20:00",
                "end_time": "21:00",
            },
            {
                "date": "2026-05-02",
                "title": "雅思阅读训练",
                "description": "完成一篇阅读。",
            },
        ],
    )

    first_push = await persistence.push_background_task_days_to_workbench(plan_date="2026-05-01")
    second_push = await persistence.push_background_task_days_to_workbench(plan_date="2026-05-01")
    workbench_items = await persistence.list_maxwell_workbench_items()
    pushed_days = await persistence.list_background_task_days(status="pushed")

    assert len(first_push) == 1
    assert second_push == []
    assert len(workbench_items) == 1
    assert workbench_items[0]["title"] == "雅思听力精听"
    assert workbench_items[0]["status"] == "todo"
    assert [day["title"] for day in pushed_days] == ["雅思听力精听"]
    assert pushed_days[0]["workbench_item_id"] == workbench_items[0]["id"]


@pytest.mark.asyncio
async def test_mark_overdue_background_task_days_as_missed():
    await persistence.save_background_task(
        task_id="task-overdue",
        title="7 天游雅思学习计划",
        task_type="long_project",
        source_agent="maxwell",
        original_user_request="帮我安排 7 天游雅思学习计划",
        goal="雅思备考",
        time_horizon={"start_after": "2026-05-01", "target_date": "2026-05-03"},
        milestones=[],
        subtasks=[],
        calendar_candidates=[],
    )
    await persistence.save_background_task_days(
        task_id="task-overdue",
        daily_plan=[
            {"date": "2026-05-01", "title": "未完成的昨日任务", "status": "pending"},
            {"date": "2026-05-02", "title": "已推送但未完成任务", "status": "pushed"},
            {"date": "2026-05-03", "title": "今天任务", "status": "pending"},
            {"date": "2026-05-01", "title": "已完成旧任务", "status": "completed"},
        ],
    )

    missed = await persistence.mark_overdue_background_task_days_missed(today="2026-05-03")
    pending_days = await persistence.list_background_task_days(status="pending")
    completed_days = await persistence.list_background_task_days(status="completed")

    assert [day["title"] for day in missed] == ["未完成的昨日任务", "已推送但未完成任务"]
    assert all(day["status"] == "missed" for day in missed)
    assert [day["title"] for day in pending_days] == ["今天任务"]
    assert [day["title"] for day in completed_days] == ["已完成旧任务"]


@pytest.mark.asyncio
async def test_confirming_task_plan_persists_daily_plan_days():
    await persistence.save_pending_action(
        pending_id="pending-ielts-plan",
        action_type="task.plan",
        tool_name="jarvis_task_plan_decompose",
        agent_id="maxwell",
        session_id="session-maxwell",
        title="7 天游雅思学习计划",
        arguments={
            "plan": {
                "id": "task-confirm-ielts",
                "title": "7 天游雅思学习计划",
                "type": "long_project",
                "source_agent": "maxwell",
                "original_user_request": "帮我安排 7 天雅思学习计划，每天晚上学习 1 小时",
                "goal": "建立连续 7 天雅思学习节奏",
                "time_horizon": {"start_after": "2026-05-01", "target_date": "2026-05-07"},
                "milestones": [],
                "subtasks": [],
                "calendar_candidates": [],
                "daily_plan": [
                    {
                        "date": "2026-05-01",
                        "title": "雅思听力精听",
                        "description": "完成 1 组听力精听并记录错因。",
                        "start_time": "20:00",
                        "end_time": "21:00",
                        "estimated_minutes": 60,
                    },
                    {
                        "date": "2026-05-02",
                        "title": "雅思阅读限时训练",
                        "description": "完成 1 篇阅读并复盘题型。",
                        "start_time": "20:00",
                        "end_time": "21:00",
                        "estimated_minutes": 60,
                    },
                ],
            }
        },
    )

    response = await confirm_pending_action_item(
        "pending-ielts-plan",
        PendingActionConfirmRequest(),
    )

    assert response["fallback"] is False
    assert response["pending_action"]["status"] == "confirmed"
    assert response["result"]["persisted"] is True
    assert response["result"]["task"]["id"] == "task-confirm-ielts"
    assert response["result"]["task_day_count"] == 2

    days = await persistence.list_background_task_days(task_id="task-confirm-ielts")
    assert [day["plan_date"] for day in days] == ["2026-05-01", "2026-05-02"]
    assert [day["status"] for day in days] == ["pending", "pending"]

    completed = await persistence.update_background_task_day_status(days[0]["id"], "completed")
    assert completed is not None
    assert completed["status"] == "completed"


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
