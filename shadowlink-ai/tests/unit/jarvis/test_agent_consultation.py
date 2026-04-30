import tempfile
from pathlib import Path

import pytest

from app.api.v1 import jarvis_router
from app.api.v1.jarvis_router import AgentChatRequest
from app.jarvis import persistence
from app.jarvis.agent_consultation import parse_consult_edges, plan_consult_edges, run_agent_consultations


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
        if "## Jarvis private agent consultation" in message and "Mira" in system_prompt:
            return '{"summary":"心理状态偏紧绷，建议先降低强度并保留恢复边界。","confidence":0.82,"needs_followup":false}'
        if "## Jarvis private agent consultation" in message and "Maxwell" in system_prompt:
            return '{"summary":"今晚时间紧，只适合一个 45 分钟学习块，不建议强塞 2 小时。","confidence":0.78,"needs_followup":false}'
        if "## Jarvis private agent consultation" in message and "Nora" in system_prompt:
            return '{"summary":"建议温热、低油，搭配一点碳水和蛋白，避免空腹咖啡。","confidence":0.8,"needs_followup":false}'
        if "## Jarvis private agent consultation" in message and "Leo" in system_prompt:
            return '{"summary":"建议低负担散步或短时户外，不要安排高消耗活动。","confidence":0.76,"needs_followup":false}'
        if "## Jarvis private agent consultation" in message and "Athena" in system_prompt:
            return '{"summary":"建议先做诊断题定位薄弱项，再用短循环复习和错题复盘推进。","confidence":0.81,"needs_followup":false}'
        if "Mira" in system_prompt:
            return "我问了 Maxwell 和 Nora。今晚先别硬顶，保留一个 45 分钟学习块，再吃一点温热、低油、有碳水和蛋白的晚饭。"
        if "Nora" in system_prompt:
            return "我问了 Mira。你现在更需要先降强度，再吃温热、简单、低刺激的食物。"
        if "Leo" in system_prompt:
            return "我问了 Maxwell。明天下午可以安排散步，但要避开会议并留出缓冲。"
        return "结合内部咨询，我建议先做一个轻量版本。"


def test_parse_consult_edges_supports_role_aliases():
    edges = parse_consult_edges(
        source_agent="nora",
        message="你先去问问心理师我最近心理状态，再决定今天吃什么。",
    )

    assert [(edge.from_agent, edge.to_agent) for edge in edges] == [("nora", "mira")]


def test_parse_consult_edges_supports_athena_aliases():
    edges = parse_consult_edges(
        source_agent="maxwell",
        message="你先问问学习策略师，我现在雅思应该怎么复习。",
    )

    assert [(edge.from_agent, edge.to_agent) for edge in edges] == [("maxwell", "athena")]


def test_parse_consult_edges_supports_two_hop_chain():
    edges = parse_consult_edges(
        source_agent="alfred",
        message="让营养师问心理师，再让心理师问秘书，然后给我一个建议。",
    )

    assert [(edge.from_agent, edge.to_agent) for edge in edges] == [
        ("nora", "mira"),
        ("mira", "maxwell"),
    ]


def test_plan_consult_edges_routes_emotional_message_to_mira():
    edges = plan_consult_edges(
        source_agent="nora",
        message="我最近压力很大，睡不好，也有点焦虑。",
    )

    assert [(edge.from_agent, edge.to_agent, edge.intent_type) for edge in edges] == [
        ("nora", "mira", "care_intent")
    ]
    assert edges[0].metadata["matched_keywords"]


def test_plan_consult_edges_routes_food_energy_message_to_nora():
    edges = plan_consult_edges(
        source_agent="mira",
        message="我今晚很累，吃什么能补充能量又不刺激？",
    )

    assert [(edge.from_agent, edge.to_agent, edge.intent_type) for edge in edges] == [
        ("mira", "nora", "nutrition_intent")
    ]


def test_plan_consult_edges_routes_schedule_message_to_maxwell_without_handoff():
    edges = plan_consult_edges(
        source_agent="leo",
        message="明天下午帮我安排一次散步，别和会议冲突。",
    )

    assert [(edge.from_agent, edge.to_agent, edge.intent_type) for edge in edges] == [
        ("leo", "maxwell", "schedule_intent")
    ]


def test_plan_consult_edges_routes_learning_strategy_message_to_athena():
    edges = plan_consult_edges(
        source_agent="mira",
        message="我今晚很累但还想复习雅思，怎么学才不浪费时间？",
    )

    assert [(edge.from_agent, edge.to_agent, edge.intent_type) for edge in edges] == [
        ("mira", "athena", "learning_intent")
    ]


def test_plan_consult_edges_routes_maxwell_emotional_message_to_mira():
    edges = plan_consult_edges(
        source_agent="maxwell",
        message="我焦虑到有点撑不住，今晚还要继续学吗？",
    )

    assert [(edge.from_agent, edge.to_agent, edge.intent_type) for edge in edges] == [
        ("maxwell", "mira", "care_intent")
    ]


def test_plan_consult_edges_limits_mixed_message_to_two_specialists():
    edges = plan_consult_edges(
        source_agent="alfred",
        message="我今晚很累还要复习，吃什么比较好，明天也要安排会议，周末还想出去放松。",
    )

    assert len(edges) == 2
    assert {edge.to_agent for edge in edges} <= {"maxwell", "mira", "nora", "leo", "athena"}
    assert all(edge.to_agent != "alfred" for edge in edges)


def test_plan_consult_edges_explicit_request_takes_priority():
    edges = plan_consult_edges(
        source_agent="nora",
        message="你先去问问心理师我最近心理状态，再决定今天吃什么。",
    )

    assert [(edge.from_agent, edge.to_agent, edge.intent_type) for edge in edges] == [
        ("nora", "mira", "explicit_consult")
    ]


def test_plan_consult_edges_never_consults_self_or_shadow():
    edges = plan_consult_edges(
        source_agent="mira",
        message="我压力很大，也有点焦虑。",
    )

    assert edges == []


def test_plan_consult_edges_ignores_vague_small_talk():
    edges = plan_consult_edges(
        source_agent="alfred",
        message="你好呀，今天感觉还行。",
    )

    assert edges == []


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


@pytest.mark.asyncio
async def test_chat_pipeline_schedule_intent_consults_maxwell_without_switching_agent(monkeypatch):
    llm = FakeConsultLLM()

    async def no_memory_extract(**kwargs):
        return []

    monkeypatch.setattr(jarvis_router, "extract_and_save_chat_memories", no_memory_extract)

    response = await jarvis_router.chat_with_agent(
        AgentChatRequest(
            agent_id="mira",
            session_id="session-mira-schedule",
            message="今晚很累但还要学 2 小时，帮我重新安排一下。",
        ),
        llm_client=llm,
    )

    final_call = llm.calls[-1]
    assert response.agent_id == "mira"
    assert response.routing is None
    assert response.actions is None or all(action["type"] != "schedule_intent" for action in response.actions)
    assert "## 私下咨询结果" in final_call["message"]
    assert "Maxwell" in final_call["message"]
    assert "我问了 Maxwell" in response.content
