import asyncio
from pathlib import Path
from uuid import uuid4

import pytest

from app.api.v1.jarvis_router import RoundtableAcceptRequest, RoundtableReturnRequest, accept_roundtable_decision, return_roundtable_to_private_chat
from app.jarvis import persistence


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
