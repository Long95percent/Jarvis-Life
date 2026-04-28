import asyncio
from pathlib import Path
from uuid import uuid4

import pytest

from app.api.v1.jarvis_router import (
    RoundtablePlanRequest,
    RoundtableSaveRequest,
    convert_roundtable_brainstorm_to_plan,
    save_roundtable_brainstorm_memory,
)
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


def _seed_brainstorm_result(session_id: str = "bs-session") -> dict:
    asyncio.run(persistence.save_session(
        session_id=session_id,
        scenario_id="work_brainstorm",
        scenario_name="工作难题头脑风暴",
        participants=["moderator", "explorer", "critic", "synthesizer"],
        agent_roster="brainstorm",
        round_count=1,
        mode="brainstorm",
    ))
    return asyncio.run(persistence.save_roundtable_result(
        result_id="bs-result",
        session_id=session_id,
        mode="brainstorm",
        status="draft",
        summary="可以从三个方向发散：产品体验、技术验证、演示叙事。",
        options=[{"title": "产品体验", "summary": "先做可感知 demo"}],
        recommended_option="",
        tradeoffs=[{"title": "发散与收敛", "description": "需要用户选择优先方向"}],
        actions=[{"type": "save_as_memory", "enabled": False}],
        handoff_target="maxwell",
        context={
            "topic": "如何做一个 Jarvis demo",
            "themes": [{"title": "产品体验", "summary": "先做可感知 demo"}],
            "ideas": [{"id": "i1", "title": "做一条从疲惫到计划的完整演示", "source_agent": "explorer"}],
            "tensions": [{"title": "范围", "description": "demo 不能太散"}],
            "followup_questions": ["先演示哪条主线？"],
            "save_as_memory": False,
        },
    ))


def test_save_brainstorm_requires_user_action_and_writes_memory_only_after_click():
    session_id = "bs-session-save"
    _seed_brainstorm_result(session_id)

    before = asyncio.run(persistence.list_jarvis_memories(memory_kind="brainstorm_inspiration", limit=10))
    response = asyncio.run(save_roundtable_brainstorm_memory(session_id, RoundtableSaveRequest(result_id="bs-result")))
    after = asyncio.run(persistence.list_jarvis_memories(memory_kind="brainstorm_inspiration", limit=10))

    assert before == []
    assert len(after) == 1
    assert response["direct_calendar_mutation"] is False
    assert response["direct_plan_mutation"] is False
    assert response["result"]["save_as_memory"] is True
    assert response["memory"]["memory_kind"] == "brainstorm_inspiration"


def test_convert_brainstorm_to_plan_creates_pending_action_without_direct_plan_write():
    session_id = "bs-session-plan"
    _seed_brainstorm_result(session_id)

    response = asyncio.run(convert_roundtable_brainstorm_to_plan(session_id, RoundtablePlanRequest(result_id="bs-result")))

    assert response["direct_calendar_mutation"] is False
    assert response["direct_plan_mutation"] is False
    assert response["pending_action"]["status"] == "pending"
    assert response["pending_action"]["action_type"] == "task.plan"
    assert response["pending_action"]["agent_id"] == "maxwell"
    assert response["result"]["status"] == "handoff_pending"
    assert response["result"]["pending_action_id"] == response["pending_action"]["id"]
