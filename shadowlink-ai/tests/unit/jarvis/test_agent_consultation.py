import tempfile
from pathlib import Path

import pytest

from app.api.v1 import jarvis_router
from app.api.v1.jarvis_router import AgentChatRequest
from app.jarvis import persistence
from app.jarvis.agent_consultation import parse_consult_edges, run_agent_consultations


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    tmp = Path(tempfile.mkdtemp()) / "jarvis.db"
    monkeypatch.setattr(persistence, "_DB_PATH", tmp)
    persistence._initialized = False
    yield tmp
    persistence._initialized = False


class FakeConsultLLM:
    def __init__(self):
        self.calls: list[dict[str, str]] = []

    async def chat(self, *, message: str, system_prompt: str, temperature: float = 0.7, **kwargs):
        self.calls.append({"message": message, "system_prompt": system_prompt})
        if "严格只输出 JSON" in message:
            return '{"memories":[]}'
        if "Mira" in system_prompt:
            return '{"summary":"心理状态偏紧绷，建议低刺激、温热、稳定血糖。","confidence":0.82,"needs_followup":false}'
        if "Maxwell" in system_prompt:
            return '{"summary":"今晚时间紧，只适合 20 分钟内完成的轻量安排。","confidence":0.78,"needs_followup":false}'
        return "结合内部咨询，我建议今晚吃温热、简单、低刺激的食物。"


def test_parse_consult_edges_supports_role_aliases():
    edges = parse_consult_edges(
        source_agent="nora",
        message="你先去问问心理师我最近心理状态，再决定今天吃什么。",
    )

    assert [(edge.from_agent, edge.to_agent) for edge in edges] == [("nora", "mira")]


def test_parse_consult_edges_supports_two_hop_chain():
    edges = parse_consult_edges(
        source_agent="alfred",
        message="让营养师问心理师，再让心理师问秘书，然后给我一个建议。",
    )

    assert [(edge.from_agent, edge.to_agent) for edge in edges] == [
        ("nora", "mira"),
        ("mira", "maxwell"),
    ]


@pytest.mark.asyncio
async def test_run_agent_consultations_executes_chain_and_saves_memory():
    llm = FakeConsultLLM()

    result = await run_agent_consultations(
        source_agent="nora",
        user_message="让营养师问心理师，再让心理师问秘书，然后决定晚饭。",
        session_id="session-consult-chain",
        llm_client=llm,
        context_summary="stress=8 sleep=4",
    )

    assert result.has_consultations is True
    assert [(item["from_agent"], item["to_agent"]) for item in result.consultations] == [
        ("mira", "maxwell"),
        ("nora", "mira"),
    ]
    assert "Maxwell" in llm.calls[1]["message"]
    assert "心理状态偏紧绷" in result.prompt_prefix
    assert result.actions[0]["type"] == "agent.consult"
    assert result.actions[0]["arguments"]["consultations"][0]["to_agent"] == "maxwell"

    memories = await persistence.get_relevant_collaboration_memories("nora", limit=10)
    assert [item["memory_kind"] for item in memories] == ["agent_consultation", "agent_consultation"]
    assert memories[-1]["structured_payload"]["to_agent"] == "mira"


@pytest.mark.asyncio
async def test_chat_pipeline_injects_consult_context_into_final_agent(monkeypatch):
    llm = FakeConsultLLM()

    async def no_memory_extract(**kwargs):
        return []

    monkeypatch.setattr(jarvis_router, "extract_and_save_chat_memories", no_memory_extract)

    response = await jarvis_router.chat_with_agent(
        AgentChatRequest(
            agent_id="nora",
            session_id="session-nora-mira",
            message="你先去问问心理师我最近心理状态，再决定今天吃什么。",
        ),
        llm_client=llm,
    )

    final_call = llm.calls[-1]
    assert response.agent_id == "nora"
    assert response.actions is not None
    assert response.actions[0]["type"] == "agent.consult"
    assert "## 私下咨询结果" in final_call["message"]
    assert "心理状态偏紧绷" in final_call["message"]
    assert "温热、简单、低刺激" in response.content
