from pathlib import Path
from uuid import uuid4

import pytest

from app.api.v1 import jarvis_router
from app.jarvis import tool_runtime
from app.api.v1.jarvis_router import AgentChatRequest
from app.jarvis import persistence
from app.jarvis.agent_consultation import AgentConsultationResult


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    db_dir = Path("data") / "test_dbs"
    db_dir.mkdir(parents=True, exist_ok=True)
    tmp = db_dir / f"jarvis-{uuid4().hex}.db"
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
        if "strict" in message.lower() and "json" in message.lower():
            return '{"memories":[]}'
        return "OK"


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
                "output": {"type": "meal.plan", "ok": True, "summary": "stable dinner plan"},
            }
        ]

    monkeypatch.setattr(jarvis_router, "execute_tool_calls", fake_execute_tool_calls)
    llm = RecordingLLM(events)

    response = await jarvis_router.chat_with_agent(
        AgentChatRequest(
            agent_id="nora",
            session_id="session-nora-intent",
            message="I am tired tonight, what should I eat?",
        ),
        llm_client=llm,
    )

    assert response.agent_id == "nora"
    assert events[:2] == ["tool:jarvis_meal_plan", "llm"]
    assert "jarvis_meal_plan" in llm.calls[-1]["message"]
    assert "stable dinner plan" in llm.calls[-1]["message"]


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



def test_private_calendar_delete_intent_executes_schedule_editor(monkeypatch):
    import asyncio

    captured: list[dict] = []

    async def fake_execute_tool_calls(agent_id, calls):
        captured.append({"agent_id": agent_id, "calls": calls})
        return [
            {
                "tool_name": "jarvis_schedule_editor",
                "success": True,
                "requires_confirmation": False,
                "description": "Edit schedule",
                "output": {"type": "schedule.editor.delete", "ok": True, "matched_count": 2, "deleted_count": 2},
            }
        ]

    async def scenario():
        monkeypatch.setattr(jarvis_router, "execute_tool_calls", fake_execute_tool_calls)
        llm = RecordingLLM([])
        return await jarvis_router.chat_with_agent(
            AgentChatRequest(
                agent_id="maxwell",
                session_id="session-maxwell-delete-intent",
                message="delete all python calendar events",
            ),
            llm_client=llm,
        )

    response = asyncio.run(scenario())

    assert response.agent_id == "maxwell"
    assert captured[0]["agent_id"] == "maxwell"
    call = captured[0]["calls"][0]
    assert call["tool_name"] == "jarvis_schedule_editor"
    assert call["arguments"]["operation"] == "delete"
    assert call["arguments"]["scope"] == "all"
    assert call["arguments"]["keyword"].lower() == "python"


def test_private_delete_schedule_routes_to_maxwell_from_other_agent(monkeypatch):
    import asyncio

    captured: list[dict] = []

    async def fake_execute_tool_calls(agent_id, calls):
        captured.append({"agent_id": agent_id, "calls": calls})
        return [
            {
                "tool_name": "jarvis_schedule_editor",
                "success": True,
                "requires_confirmation": False,
                "description": "Edit schedule",
                "output": {"type": "schedule.editor.delete", "ok": True, "matched_count": 1, "deleted_count": 1},
            }
        ]

    async def scenario():
        monkeypatch.setattr(jarvis_router, "execute_tool_calls", fake_execute_tool_calls)
        llm = RecordingLLM([])
        return await jarvis_router.chat_with_agent(
            AgentChatRequest(
                agent_id="alfred",
                session_id="session-alfred-delete-routes",
                message="delete Wuxi schedule event",
            ),
            llm_client=llm,
        )

    response = asyncio.run(scenario())

    assert response.agent_id == "maxwell"
    assert response.routing is not None
    assert captured[0]["agent_id"] == "maxwell"
    call = captured[0]["calls"][0]
    assert call["tool_name"] == "jarvis_schedule_editor"
    assert call["arguments"]["operation"] == "delete"
    assert call["arguments"]["keyword"].lower() == "wuxi"


def test_private_chat_react_repairs_schedule_editor_missing_event_id(monkeypatch):
    import asyncio

    calls_seen: list[dict] = []

    async def fake_execute_tool_calls(agent_id, calls, **kwargs):
        calls_seen.extend(calls)
        call = calls[0]
        arguments = call["arguments"]
        if arguments.get("operation") == "update" and not arguments.get("patches"):
            return [
                {
                    "tool_name": "jarvis_schedule_editor",
                    "success": False,
                    "description": "Edit schedule",
                    "error": "patches[0].event_id: Field required",
                }
            ]
        if arguments.get("operation") == "query":
            return [
                {
                    "tool_name": "jarvis_schedule_editor",
                    "success": True,
                    "requires_confirmation": False,
                    "description": "Edit schedule",
                    "output": {
                        "type": "schedule.editor.query",
                        "ok": True,
                        "matched_count": 1,
                        "events": [
                            {
                                "id": "event_meeting_1",
                                "title": "team meeting",
                                "start": "2026-05-04T09:00:00",
                                "end": "2026-05-04T10:00:00",
                            }
                        ],
                    },
                }
            ]
        if arguments.get("operation") == "update" and arguments.get("patches"):
            return [
                {
                    "tool_name": "jarvis_schedule_editor",
                    "success": True,
                    "requires_confirmation": False,
                    "description": "Edit schedule",
                    "output": {
                        "type": "schedule.editor.update",
                        "ok": True,
                        "updated_count": 1,
                        "updated_events": [{"id": "event_meeting_1", "title": "team meeting updated"}],
                    },
                }
            ]
        raise AssertionError(f"unexpected calls: {calls}")

    class ReactRepairLLM(RecordingLLM):
        async def chat(self, *, message: str, system_prompt: str, temperature: float = 0.7, **kwargs):
            self.events.append("llm")
            self.calls.append({"message": message, "system_prompt": system_prompt})
            if len(self.calls) == 1:
                return '<jarvis-tool>{"tool_name":"jarvis_schedule_editor","arguments":{"operation":"update","scope":"all","keyword":"meeting","title":"team meeting updated"}}</jarvis-tool>'
            return "已更新会议。"

    monkeypatch.setattr(jarvis_router, "execute_tool_calls", fake_execute_tool_calls)
    monkeypatch.setattr(tool_runtime, "execute_tool_calls", fake_execute_tool_calls)
    llm = ReactRepairLLM([])

    async def scenario():
        return await jarvis_router.chat_with_agent(
            AgentChatRequest(
                agent_id="maxwell",
                session_id="session-maxwell-react-repair",
                message="update the meeting title",
            ),
            llm_client=llm,
        )

    response = asyncio.run(scenario())

    assert response.agent_id == "maxwell"
    assert [call["arguments"]["operation"] for call in calls_seen] == ["update", "query", "update"]
    repaired_patch = calls_seen[-1]["arguments"]["patches"][0]
    assert repaired_patch["event_id"] == "event_meeting_1"
    assert repaired_patch["title"] == "team meeting updated"
    assert response.actions is not None
    assert any(action.get("updated_count") == 1 for action in response.actions)


def test_private_chat_formats_schedule_disambiguation_candidates(monkeypatch):
    import asyncio

    async def fake_execute_tool_calls(agent_id, calls, **kwargs):
        return [
            {
                "tool_name": "jarvis_schedule_editor",
                "success": True,
                "requires_confirmation": False,
                "description": "Edit schedule",
                "output": {
                    "type": "schedule.editor.delete",
                    "ok": False,
                    "code": "needs_disambiguation",
                    "candidate_count": 2,
                    "candidates": [
                        {
                            "id": "event_meeting_a",
                            "title": "meeting A",
                            "start": "2026-05-26T09:00:00",
                            "end": "2026-05-26T10:00:00",
                        },
                        {
                            "id": "event_meeting_b",
                            "title": "meeting B",
                            "start": "2026-05-27T09:00:00",
                            "end": "2026-05-27T10:00:00",
                        },
                    ],
                },
            }
        ]

    class DisambiguationLLM(RecordingLLM):
        async def chat(self, *, message: str, system_prompt: str, temperature: float = 0.7, **kwargs):
            self.events.append("llm")
            self.calls.append({"message": message, "system_prompt": system_prompt})
            if len(self.calls) == 1:
                return '<jarvis-tool>{"tool_name":"jarvis_schedule_editor","arguments":{"operation":"delete","scope":"all","keyword":"meeting"}}</jarvis-tool>'
            return "我找到了多个候选：event_meeting_a meeting A；event_meeting_b meeting B。你要删哪一个，还是全部删除？"

    monkeypatch.setattr(tool_runtime, "execute_tool_calls", fake_execute_tool_calls)
    llm = DisambiguationLLM([])

    async def scenario():
        return await jarvis_router.chat_with_agent(
            AgentChatRequest(
                agent_id="maxwell",
                session_id="session-maxwell-disambiguation",
                message="delete meeting",
            ),
            llm_client=llm,
        )

    response = asyncio.run(scenario())

    assert "## 多候选澄清" in llm.calls[-1]["message"]
    assert "event_meeting_a" in llm.calls[-1]["message"]
    assert "meeting A" in llm.calls[-1]["message"]
    assert "event_meeting_b" in llm.calls[-1]["message"]
    assert "不要说已经删除或已经更新" in llm.calls[-1]["message"]
    assert "多个候选" in response.content


def test_private_chat_uses_llm_strategy_router_for_complex_schedule(monkeypatch):
    import asyncio

    class StrategyRouterLLM(RecordingLLM):
        async def chat(self, *, message: str, system_prompt: str, temperature: float = 0.7, **kwargs):
            self.events.append("llm")
            self.calls.append({"message": message, "system_prompt": system_prompt})
            if "## 私聊策略路由" in message:
                return '{"domain":"schedule","strategy":"plan_execute","confidence":0.93,"needs_tool":true,"reason":"用户要求复杂长期日程安排"}'
            return "我会先制定计划再执行。"

    llm = StrategyRouterLLM([])

    async def scenario():
        return await jarvis_router.chat_with_agent(
            AgentChatRequest(
                agent_id="maxwell",
                session_id="session-maxwell-llm-strategy",
                message="帮我安排接下来一个月每天学习和复盘，并且避开已有日程",
            ),
            llm_client=llm,
        )

    response = asyncio.run(scenario())

    final_message = llm.calls[-1]["message"]
    assert response.agent_id == "maxwell"
    assert "## 私聊执行策略" in final_message
    assert "strategy: plan_execute" in final_message
    assert "日程领域必须先查询或调用工具" in final_message
    assert "## 用户可见回复契约" in final_message
    assert "不要把 function_call、tool_name、arguments、JSON 指令" in final_message
    assert "所有带尖括号的协议标签都不是用户可见回复" in final_message
    assert response.metadata["llm_strategy"]["strategy"] == "plan_execute"
