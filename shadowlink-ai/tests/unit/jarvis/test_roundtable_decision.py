import asyncio
import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.v1 import jarvis_router
from app.api.v1.jarvis_router import RoundtableAcceptRequest, RoundtableReturnRequest, accept_roundtable_decision, return_roundtable_to_private_chat
from app.jarvis import persistence
from app.jarvis.roundtable_graph import RoundtableAgentTurnResult, RoundtableGraphState


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    db_dir = Path("data") / "test_dbs"
    db_dir.mkdir(parents=True, exist_ok=True)
    tmp = db_dir / f"jarvis-{uuid4().hex}.db"
    monkeypatch.setattr(persistence, "_DB_PATH", tmp)
    persistence._initialized = False
    yield tmp
    persistence._initialized = False


def test_roundtable_session_stores_decision_metadata_and_result():
    session_id = "rt-session-1"
    asyncio.run(persistence.save_session(
        session_id=session_id,
        scenario_id="study_energy_decision",
        scenario_name="疲惫学习决策",
        participants=["mira", "maxwell", "athena"],
        agent_roster="jarvis",
        round_count=1,
        mode="decision",
        source_session_id="private-1",
        source_agent_id="mira",
    ))
    saved = asyncio.run(persistence.save_roundtable_result(
        result_id="rt-result-1",
        session_id=session_id,
        mode="decision",
        status="draft",
        summary="先恢复，再做最小学习块。",
        options=[{"id": "light", "title": "降强度"}],
        recommended_option="缩小学习任务 + 安排恢复窗口",
        tradeoffs=[{"option": "降强度", "pros": ["可完成"], "cons": ["产出少"]}],
        actions=[{"title": "生成待确认日程调整卡", "owner": "maxwell"}],
        handoff_target="maxwell",
        context={"date": "2026-04-28"},
    ))
    sessions = asyncio.run(persistence.list_sessions(limit=5))

    assert sessions[0]["mode"] == "decision"
    assert sessions[0]["source_session_id"] == "private-1"
    assert saved["recommended_option"] == "缩小学习任务 + 安排恢复窗口"
    assert saved["options"][0]["id"] == "light"


def test_accept_decision_creates_pending_action_without_calendar_mutation():
    session_id = "rt-session-2"
    asyncio.run(persistence.save_session(
        session_id=session_id,
        scenario_id="study_energy_decision",
        scenario_name="疲惫学习决策",
        participants=["mira", "maxwell", "athena"],
        agent_roster="jarvis",
        round_count=1,
        mode="decision",
    ))
    asyncio.run(persistence.save_roundtable_result(
        result_id="rt-result-2",
        session_id=session_id,
        mode="decision",
        status="draft",
        summary="生成待确认卡。",
        options=[],
        recommended_option="继续但降强度",
        tradeoffs=[],
        actions=[{"title": "低强度学习"}],
        handoff_target="maxwell",
        context={"date": "2026-04-28"},
    ))

    response = asyncio.run(accept_roundtable_decision(session_id, RoundtableAcceptRequest(result_id="rt-result-2")))

    assert response["direct_calendar_mutation"] is False
    assert response["pending_action"]["status"] == "pending"
    assert response["pending_action"]["action_type"] == "calendar.add"
    assert response["result"]["status"] == "accepted"
    assert response["result"]["pending_action_id"] == response["pending_action"]["id"]


def test_roundtable_result_schema_exposes_normalized_fields():
    session_id = "rt-session-schema"
    asyncio.run(persistence.save_session(
        session_id=session_id,
        scenario_id="study_energy_decision",
        scenario_name="schema test",
        participants=["mira", "maxwell"],
        agent_roster="jarvis",
        round_count=1,
        mode="decision",
    ))
    saved = asyncio.run(persistence.save_roundtable_result(
        result_id="rt-result-schema",
        session_id=session_id,
        mode="decision",
        status="draft",
        summary="schema summary",
        options=[{"id": "one"}],
        recommended_option="one",
        tradeoffs=[],
        actions=[],
        handoff_target="maxwell",
        context={"date": "2026-04-28"},
    ))

    assert saved["result_json"]["summary"] == "schema summary"
    assert saved["user_choice"] is None
    assert saved["handoff_status"] == "none"


def test_return_roundtable_writes_summary_to_source_private_chat():
    session_id = "rt-session-return"
    asyncio.run(persistence.save_session(
        session_id=session_id,
        scenario_id="study_energy_decision",
        scenario_name="疲惫学习决策",
        participants=["mira", "maxwell"],
        agent_roster="jarvis",
        round_count=1,
        mode="decision",
        source_session_id="private-return-1",
        source_agent_id="mira",
    ))
    asyncio.run(persistence.append_turn(session_id=session_id, role="mira", speaker_name="Mira", content="先照顾状态。", timestamp=1.0))
    asyncio.run(persistence.save_roundtable_result(
        result_id="rt-result-return",
        session_id=session_id,
        mode="decision",
        status="draft",
        summary="建议先恢复，再安排低强度学习。",
        options=[],
        recommended_option="先恢复再学习",
        tradeoffs=[],
        actions=[],
        handoff_target="maxwell",
        context={"date": "2026-04-28"},
    ))

    response = asyncio.run(return_roundtable_to_private_chat(
        session_id,
        RoundtableReturnRequest(result_id="rt-result-return", user_choice="先恢复再学习", note="回私聊继续"),
    ))
    history = asyncio.run(persistence.get_chat_history(agent_id="mira", session_id="private-return-1", limit=5))
    result = asyncio.run(persistence.get_roundtable_result("rt-result-return"))

    assert response["source_session_id"] == "private-return-1"
    assert response["return_turn_id"] is not None
    assert history[-1]["role"] == "agent"
    assert "圆桌讨论总结" in history[-1]["content"]
    assert result["status"] == "returned"
    assert result["handoff_status"] == "returned"
    assert result["user_choice"] == "先恢复再学习"


def test_roundtable_sequential_turn_degrades_failed_agent_and_continues(monkeypatch):
    from app.api.v1 import jarvis_router
    from app.jarvis.roundtable_sessions import create_session

    session_id = "rt-session-degrade"
    create_session(
        session_id=session_id,
        scenario_id="study_energy_decision",
        scenario_name="degrade test",
        participants=["mira", "maxwell"],
        agent_roster="jarvis",
    )

    async def fake_run_agent_turn(agent_id, **kwargs):
        if agent_id == "mira":
            raise RuntimeError("provider timeout")
        return "Maxwell continues with a smaller plan.", []

    monkeypatch.setattr(jarvis_router, "run_agent_turn", fake_run_agent_turn)

    async def collect_events():
        events = []
        async for event in jarvis_router._run_roundtable_round(
            llm_client=None,
            session_id=session_id,
            scenario_id="study_energy_decision",
            scenario_name="degrade test",
            scenario_icon="T",
            participants=["mira", "maxwell"],
            opening_prompt="Continue safely.",
            profile_prefix="",
            context_prefix="",
            phase_label="open",
            mode="brainstorm",
            initial_user_input="help me decide",
            decision_context=None,
        ):
            events.append(event)
        return events

    events = asyncio.run(collect_events())
    names = [event["event"] for event in events]
    token_payloads = [event["data"] for event in events if event["event"] == "token"]

    assert "agent_degraded" in names
    assert names.count("token") == 2
    assert any("Maxwell continues" in payload for payload in token_payloads)
    assert any("progress" in payload for payload in token_payloads)


def test_roundtable_session_stores_title_user_prompt_and_context_explanation():
    session_id = "rt-session-meta"
    asyncio.run(persistence.save_session(
        session_id=session_id,
        scenario_id="study_energy_decision",
        scenario_name="Decision Meta",
        participants=["mira", "maxwell"],
        agent_roster="jarvis",
        round_count=1,
        title="Decision Meta: tired study",
        user_prompt="I am tired but want to study.",
        mode="decision",
        source_session_id="private-meta",
        source_agent_id="mira",
    ))
    record = asyncio.run(persistence.get_roundtable_session(session_id))

    assert record["title"] == "Decision Meta: tired study"
    assert record["user_prompt"] == "I am tired but want to study."
    assert record["source_session_id"] == "private-meta"
    assert record["source_agent_id"] == "mira"


def test_roundtable_document_context_reads_text_file_by_filename_keyword(tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    paper = docs_dir / "code-learning-paper-notes.md"
    paper.write_text("Transformer paper notes\nKey idea: attention scales with context.", encoding="utf-8")

    context = asyncio.run(jarvis_router._resolve_roundtable_document_context(
        "帮我读一下 code-learning-paper 文档，然后总结给 Athena",
        search_dirs=[docs_dir],
        max_chars=500,
    ))

    assert context["status"] == "attached"
    assert context["file_name"] == "code-learning-paper-notes.md"
    assert "attention scales with context" in context["content"]


def test_roundtable_document_context_uses_path_tiebreaker_for_same_score(tmp_path):
    docs_dir = tmp_path / "docs"
    short_dir = docs_dir / "a"
    long_dir = docs_dir / "a" / "nested"
    short_dir.mkdir(parents=True)
    long_dir.mkdir(parents=True)
    short_doc = short_dir / "ohmorilog5-2.md"
    long_doc = long_dir / "ohmorilog5-2.md"
    short_doc.write_text("short path log wins", encoding="utf-8")
    long_doc.write_text("long path log should not be selected", encoding="utf-8")

    context = asyncio.run(jarvis_router._resolve_roundtable_document_context(
        "帮我读 ohmorilog5-2",
        search_dirs=[docs_dir],
        max_chars=500,
    ))

    assert context["status"] == "attached"
    assert context["file_path"] == str(short_doc.resolve())
    assert "short path log wins" in context["content"]


def test_roundtable_document_context_is_added_to_continue_prompt(tmp_path):
    docs_dir = tmp_path / "uploads"
    docs_dir.mkdir()
    paper = docs_dir / "research-note.txt"
    paper.write_text("Research note: spaced repetition beats rereading.", encoding="utf-8")

    context = asyncio.run(jarvis_router._resolve_roundtable_document_context(
        "读一下 research-note 科研文档",
        search_dirs=[docs_dir],
        max_chars=500,
    ))
    prefixed = jarvis_router._append_roundtable_document_context("base context\n", context)

    assert "## 临时文档上下文" in prefixed
    assert "research-note.txt" in prefixed
    assert "spaced repetition beats rereading" in prefixed


def test_continue_roundtable_injects_document_context_into_next_round(monkeypatch, tmp_path):
    from app.config import settings as app_settings
    from app.jarvis.roundtable_sessions import create_session

    docs_dir = tmp_path / "uploads"
    docs_dir.mkdir()
    paper = docs_dir / "athena-research.txt"
    paper.write_text("Athena source: interleaving practice improves transfer.", encoding="utf-8")

    session_id = "rt-session-doc-chain"
    create_session(
        session_id=session_id,
        scenario_id="study_energy_decision",
        scenario_name="疲惫学习决策",
        participants=["athena"],
        agent_roster="jarvis",
    )

    class FakeContextBus:
        async def get_context(self):
            return SimpleNamespace(stress_level=2.0, schedule_density=3.0, mood_trend="stable")

    captured: dict = {}

    async def fake_local_life_context_prefix(**kwargs):
        return ""

    async def fake_prepare_decision_context():
        return {"date": "2026-05-02"}

    async def fake_run_graph_or_legacy_round(**kwargs):
        captured.update(kwargs)
        yield {"event": "done", "data": "{}"}

    monkeypatch.setattr(jarvis_router, "get_life_context_bus", lambda: FakeContextBus())
    monkeypatch.setattr(jarvis_router, "_build_local_life_context_prefix", fake_local_life_context_prefix)
    monkeypatch.setattr(jarvis_router, "_prepare_decision_context", fake_prepare_decision_context)
    monkeypatch.setattr(jarvis_router, "_run_graph_or_legacy_round", fake_run_graph_or_legacy_round)
    monkeypatch.setattr(app_settings, "data_dir", str(docs_dir))
    monkeypatch.setattr(app_settings.file_processing, "upload_dir", str(docs_dir))

    response = asyncio.run(jarvis_router.continue_roundtable(
        jarvis_router.RoundtableContinueRequest(
            session_id=session_id,
            user_message="帮我读一下 athena-research 文档再继续讨论",
        ),
        llm_client=None,
    ))

    async def drain_response():
        async for _ in response.body_iterator:
            pass

    asyncio.run(drain_response())

    assert "interleaving practice improves transfer" in captured["context_prefix"]
    assert captured["decision_context"]["document_context"]["file_name"] == "athena-research.txt"


def test_roundtable_intent_executes_private_chat_readonly_tool(monkeypatch):
    captured_calls = []

    async def fake_execute_tool_calls(agent_id, calls):
        captured_calls.append((agent_id, calls))
        return [{
            "tool_name": "jarvis_meal_plan",
            "success": True,
            "requires_confirmation": False,
            "description": "meal planning",
            "output": {"meals": ["dinner"], "summary": "晚餐建议清淡高蛋白"},
        }]

    monkeypatch.setattr(jarvis_router, "execute_tool_calls", fake_execute_tool_calls)

    context = asyncio.run(jarvis_router._resolve_roundtable_intent_context(
        "今晚很累，吃什么比较撑得住？",
        participants=["mira", "nora", "alfred"],
    ))
    prefixed = jarvis_router._append_roundtable_intent_context("base context\n", context)

    assert captured_calls == [("nora", [{"tool_name": "jarvis_meal_plan", "arguments": {"meals": ["dinner"], "include_snack": True, "goal": "stress_recovery"}}])]
    assert context["status"] == "tool_executed"
    assert context["intent"]["agent_id"] == "nora"
    assert "## 圆桌意图识别与工具结果" in prefixed
    assert "晚餐建议清淡高蛋白" in prefixed


def test_roundtable_intent_persists_write_tool_as_pending_action(monkeypatch):
    async def fake_execute_tool_calls(agent_id, calls):
        return [{
            "tool_name": "jarvis_calendar_add",
            "success": True,
            "requires_confirmation": True,
            "confirmation_id": "confirm-calendar-1",
            "description": "add calendar event",
            "arguments": {
                "title": "复习英语",
                "start": "2026-05-03T15:00:00",
                "end": "2026-05-03T16:00:00",
            },
        }]

    monkeypatch.setattr(jarvis_router, "execute_tool_calls", fake_execute_tool_calls)

    context = asyncio.run(jarvis_router._resolve_roundtable_intent_context(
        "明天下午 3 点提醒我复习英语 1 小时",
        participants=["maxwell", "alfred"],
        session_id="rt-pending-intent",
    ))
    pending = [
        item
        for item in asyncio.run(persistence.list_pending_actions())
        if item.get("session_id") == "rt-pending-intent"
    ]

    assert context["status"] == "pending_confirmation"
    assert context["direct_mutation"] is False
    assert context["action_results"][0]["pending_confirmation"] is True
    assert pending[0]["id"] == "confirm-calendar-1"
    assert pending[0]["status"] == "pending"
    assert pending[0]["agent_id"] == "maxwell"


def test_roundtable_intent_defers_task_plan_without_executing_tool(monkeypatch):
    calls = []

    async def fake_execute_tool_calls(agent_id, calls_payload):
        calls.append((agent_id, calls_payload))
        return [{
            "tool_name": "jarvis_task_plan_decompose",
            "success": True,
            "requires_confirmation": False,
            "output": {"type": "task.plan", "ok": True, "plan": {"title": "should not be created"}},
        }]

    monkeypatch.setattr(jarvis_router, "execute_tool_calls", fake_execute_tool_calls)

    context = asyncio.run(jarvis_router._resolve_roundtable_intent_context(
        "帮我准备一个月的雅思复习计划",
        participants=["athena", "maxwell", "alfred"],
        session_id="rt-task-plan-defer",
    ))
    pending = [
        item
        for item in asyncio.run(persistence.list_pending_actions())
        if item.get("session_id") == "rt-task-plan-defer"
    ]

    assert calls == []
    assert context["status"] == "pending_confirmation"
    assert context["direct_mutation"] is False
    assert context["action_results"][0]["pending_confirmation"] is True
    assert context["action_results"][0]["tool_name"] == "jarvis_task_plan_decompose"
    assert pending[0]["action_type"] == "task.plan"
    assert pending[0]["tool_name"] == "jarvis_task_plan_decompose"


def test_roundtable_intent_missing_slots_are_injected_for_discussion():
    context = asyncio.run(jarvis_router._resolve_roundtable_intent_context(
        "帮我安排复习英语",
        participants=["maxwell", "alfred"],
    ))
    prefixed = jarvis_router._append_roundtable_intent_context("base context\n", context)

    assert context["status"] == "missing_slots"
    assert context["intent"]["intent"] == "calendar_create"
    assert context["missing_slots"] == ["start", "end"]
    assert "缺少槽位" in prefixed
    assert "start" in prefixed


def test_roundtable_agent_turn_tool_reasoning_persists_write_tool_as_pending(monkeypatch):
    from app.jarvis import roundtable_graph

    captured_kwargs = {}

    async def fake_run_agent_turn(**kwargs):
        captured_kwargs.update(kwargs)
        return "Maxwell 已生成待确认日程卡片。", [{
            "tool_name": "jarvis_calendar_add",
            "success": True,
            "requires_confirmation": True,
            "confirmation_id": "rt-agent-tool-confirm-1",
            "description": "add calendar event",
            "arguments": {
                "title": "复习英语",
                "start": "2026-05-03T15:00:00",
                "end": "2026-05-03T16:00:00",
            },
        }]

    monkeypatch.setattr(roundtable_graph, "run_agent_turn", fake_run_agent_turn)

    result = asyncio.run(roundtable_graph.run_roundtable_agent_turn(
        agent_id="maxwell",
        llm_client=None,
        message="明天下午 3 点提醒我复习英语",
        system_prompt="system",
        temperature=0.3,
        session_id="rt-agent-tool-session",
    ))
    pending = [
        item
        for item in asyncio.run(persistence.list_pending_actions())
        if item.get("session_id") == "rt-agent-tool-session"
    ]

    assert result.content == "Maxwell 已生成待确认日程卡片。"
    assert "jarvis_task_plan_decompose" in captured_kwargs["defer_confirmation_tools"]
    assert result.tool_results[0]["tool_name"] == "jarvis_calendar_add"
    assert result.action_results[0]["pending_confirmation"] is True
    assert result.action_results[0]["pending_action_id"] == "rt-agent-tool-confirm-1"
    assert pending[0]["id"] == "rt-agent-tool-confirm-1"
    assert pending[0]["agent_id"] == "maxwell"


@pytest.mark.parametrize(
    ("module_name", "executor_name", "agent_id", "scenario_id"),
    [
        ("app.jarvis.schedule_coord_graph", "ScheduleCoordGraphExecutor", "maxwell", "schedule_coord"),
        ("app.jarvis.local_lifestyle_graph", "LocalLifestyleGraphExecutor", "leo", "local_lifestyle"),
        ("app.jarvis.emotional_care_graph", "EmotionalCareGraphExecutor", "mira", "emotional_care"),
        ("app.jarvis.study_energy_decision_graph", "StudyEnergyDecisionGraphExecutor", "athena", "study_energy_decision"),
        ("app.jarvis.weekend_recharge_graph", "WeekendRechargeGraphExecutor", "nora", "weekend_recharge"),
        ("app.jarvis.work_brainstorm_graph", "WorkBrainstormGraphExecutor", "moderator", "work_brainstorm"),
    ],
)
def test_all_preset_roundtable_graphs_use_agent_turn_tool_reasoning(monkeypatch, module_name, executor_name, agent_id, scenario_id):
    module = importlib.import_module(module_name)
    called: list[str] = []

    async def fake_run_roundtable_agent_turn(**kwargs):
        called.append(kwargs["agent_id"])
        return RoundtableAgentTurnResult(
            content=f"{kwargs['agent_id']} used shared agent-turn tool reasoning.",
            tool_results=[{"tool_name": "example_tool", "success": True}],
            action_results=[],
        )

    monkeypatch.setattr(module, "run_roundtable_agent_turn", fake_run_roundtable_agent_turn)
    executor = getattr(module, executor_name)(llm_client=SimpleNamespace())
    state = RoundtableGraphState(
        session_id=f"rt-{scenario_id}",
        scenario_id=scenario_id,
        user_goal="验证圆桌工具决策覆盖",
        participants=[agent_id],
        round_index=1,
        context={},
        user_feedback_history=[],
    )

    async def collect_events():
        events = []
        async for event in executor._run_role(state, agent_id):
            events.append(event)
        return events

    events = asyncio.run(collect_events())
    completed = [event for event in events if event["event"] == "role_completed"]
    payload = json.loads(completed[0]["data"])

    assert called == [agent_id]
    assert payload["agent_id"] == agent_id
    assert payload["tool_results"] == [{"tool_name": "example_tool", "success": True}]
    assert "shared agent-turn tool reasoning" in payload["content"]
