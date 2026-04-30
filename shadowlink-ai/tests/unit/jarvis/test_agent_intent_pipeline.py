import tempfile
from pathlib import Path

import pytest

from app.api.v1 import jarvis_router
from app.api.v1.jarvis_router import AgentChatRequest
from app.jarvis import persistence
from app.jarvis.agent_consultation import AgentConsultationResult


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    tmp = Path(tempfile.mkdtemp()) / "jarvis.db"
    monkeypatch.setattr(persistence, "_DB_PATH", tmp)
    persistence._initialized = False
    persistence._ensure_initialized()
    yield tmp
    persistence._initialized = False


@pytest.fixture(autouse=True)
def quiet_background_work(monkeypatch):
    async def no_memory_extract(**kwargs):
        return []

    async def no_compaction(**kwargs):
        return None

    async def no_consultations(**kwargs):
        return AgentConsultationResult([], "", [])

    monkeypatch.setattr(jarvis_router, "extract_and_save_chat_memories", no_memory_extract)
    monkeypatch.setattr(jarvis_router, "maybe_compact_old_raw_memories", no_compaction)
    monkeypatch.setattr(jarvis_router, "run_agent_consultations", no_consultations)


class RecordingLLM:
    def __init__(self, events: list[str]):
        self.events = events
        self.calls: list[dict[str, str]] = []

    async def chat(self, *, message: str, system_prompt: str, temperature: float = 0.7, **kwargs):
        self.events.append("llm")
        self.calls.append({"message": message, "system_prompt": system_prompt})
        if "严格只输出 JSON" in message:
            return '{"memories":[]}'
        return "我已经结合你的请求处理好了。"


@pytest.mark.asyncio
async def test_private_agent_intent_executes_planned_tool_before_final_response(monkeypatch):
    events: list[str] = []

    async def fake_execute_tool_calls(agent_id, calls):
        events.append(f"tool:{calls[0]['tool_name']}")
        return [
            {
                "tool_name": calls[0]["tool_name"],
                "success": True,
                "requires_confirmation": False,
                "description": "Generate meal plan",
                "output": {"type": "meal.plan", "ok": True, "summary": "晚餐以稳定能量和恢复为主。"},
            }
        ]

    monkeypatch.setattr(jarvis_router, "execute_tool_calls", fake_execute_tool_calls)
    llm = RecordingLLM(events)

    response = await jarvis_router.chat_with_agent(
        AgentChatRequest(
            agent_id="nora",
            session_id="session-nora-intent",
            message="今晚很累，吃什么比较撑得住？",
        ),
        llm_client=llm,
    )

    assert response.agent_id == "nora"
    assert events[:2] == ["tool:jarvis_meal_plan", "llm"]
    assert "## 私聊意图识别" in llm.calls[-1]["message"]
    assert "jarvis_meal_plan" in llm.calls[-1]["message"]
    assert "晚餐以稳定能量和恢复为主" in llm.calls[-1]["message"]


@pytest.mark.asyncio
async def test_private_calendar_intent_creates_pending_action_for_current_agent(monkeypatch):
    async def fake_execute_tool_calls(agent_id, calls):
        assert agent_id == "maxwell"
        assert calls[0]["tool_name"] == "jarvis_calendar_add"
        return [
            {
                "tool_name": "jarvis_calendar_add",
                "success": True,
                "requires_confirmation": True,
                "confirmation_id": "confirm-calendar-1",
                "description": "Create calendar event",
                "arguments": calls[0]["arguments"],
            }
        ]

    monkeypatch.setattr(jarvis_router, "execute_tool_calls", fake_execute_tool_calls)
    llm = RecordingLLM([])

    response = await jarvis_router.chat_with_agent(
        AgentChatRequest(
            agent_id="maxwell",
            session_id="session-maxwell-intent",
            message="明天下午 3 点提醒我复习英语 1 小时",
        ),
        llm_client=llm,
    )

    assert response.agent_id == "maxwell"
    assert response.routing is None
    assert response.actions is not None
    pending = response.actions[0]
    assert pending["type"] == "calendar.add"
    assert pending["pending_confirmation"] is True
    assert pending["tool_name"] == "jarvis_calendar_add"
    assert pending["arguments"]["title"] == "复习英语"

    saved = await persistence.list_pending_actions()
    assert saved[0]["agent_id"] == "maxwell"
    assert saved[0]["session_id"] == "session-maxwell-intent"


@pytest.mark.asyncio
async def test_private_small_talk_does_not_execute_planned_tools(monkeypatch):
    async def fail_execute_tool_calls(agent_id, calls):
        raise AssertionError(f"unexpected planned tool calls: {calls}")

    monkeypatch.setattr(jarvis_router, "execute_tool_calls", fail_execute_tool_calls)
    llm = RecordingLLM([])

    response = await jarvis_router.chat_with_agent(
        AgentChatRequest(
            agent_id="nora",
            session_id="session-nora-small-talk",
            message="你好呀，今天还不错",
        ),
        llm_client=llm,
    )

    assert response.agent_id == "nora"
    assert response.actions is None
    assert "## 私聊意图识别" not in llm.calls[-1]["message"]
