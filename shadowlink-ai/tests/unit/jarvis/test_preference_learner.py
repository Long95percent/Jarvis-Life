import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from app.api.v1 import jarvis_router
from app.api.v1.jarvis_router import AgentChatRequest
from app.jarvis import persistence
from app.jarvis.preference_learner import PreferenceLearner, build_preference_profile_prefix


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    tmp = Path(tempfile.mkdtemp()) / "jarvis.db"
    monkeypatch.setattr(persistence, "_DB_PATH", tmp)
    persistence._initialized = False
    yield tmp
    persistence._initialized = False


@pytest.fixture
def learner():
    mock_llm = MagicMock()
    mock_llm.chat = AsyncMock(
        return_value='{"key": "prefers_morning_suggestions", "value": true}'
    )
    return PreferenceLearner(llm_client=mock_llm)


@pytest.mark.asyncio
async def test_observe_updates_profile(learner):
    await learner.observe(
        agent_id="leo",
        user_message="I'm too tired for that.",
        agent_response="How about a 10-minute walk instead?",
    )
    profile = learner.get_profile()
    assert profile.interaction_count == 1


@pytest.mark.asyncio
async def test_observe_extracts_preference(learner):
    # LLM extraction runs every 5 observations (_OBSERVE_EVERY_N = 5)
    for _ in range(5):
        await learner.observe(
            agent_id="leo",
            user_message="No, evenings don't work for me.",
            agent_response="Noted! I'll suggest morning activities instead.",
        )
    profile = learner.get_profile()
    assert "prefers_morning_suggestions" in profile.preferences


@pytest.mark.asyncio
async def test_agent_preference_profile_upsert_accumulates_evidence():
    first = await persistence.upsert_agent_preference_profile(
        agent_id="mira",
        preference_key="low_interrupt",
        preference_value="用户不喜欢频繁提醒，需要低打扰关心。",
        confidence=0.62,
        source_agent="mira",
        source_excerpt="别太频繁提醒我",
    )
    second = await persistence.upsert_agent_preference_profile(
        agent_id="mira",
        preference_key="low_interrupt",
        preference_value="用户明确要求减少提醒频率。",
        confidence=0.81,
        source_agent="maxwell",
        source_excerpt="少提醒一点",
    )

    assert first["id"] == second["id"]
    assert second["evidence_count"] == 2
    assert second["confidence"] == 0.81
    assert second["preference_value"] == "用户明确要求减少提醒频率。"


@pytest.mark.asyncio
async def test_preference_learner_persists_global_and_agent_profiles():
    mock_llm = MagicMock()
    mock_llm.chat = AsyncMock(
        return_value=(
            '{"preferences":['
            '{"key":"low_interrupt","value":"用户偏好低打扰，不喜欢频繁提醒。","scope":"global","target_agents":["mira","maxwell"],"confidence":0.82,"evidence":"别太频繁提醒我"},'
            '{"key":"nutrition_under_stress","value":"压力大时适合温热、低刺激、简单食物。","scope":"agent","target_agents":["nora"],"confidence":0.76,"evidence":"压力大时不知道吃什么"}'
            ']}'
        )
    )
    learner = PreferenceLearner(llm_client=mock_llm)

    for _ in range(5):
        await learner.observe(
            agent_id="nora",
            user_message="我压力大的时候别太频繁提醒我，先共情再建议，吃东西最好简单温热。",
            agent_response="我会温和一点。",
        )

    global_rows = await persistence.list_agent_preference_profiles(agent_id="global")
    mira_rows = await persistence.list_agent_preference_profiles(agent_id="mira")
    maxwell_rows = await persistence.list_agent_preference_profiles(agent_id="maxwell")
    nora_rows = await persistence.list_agent_preference_profiles(agent_id="nora")

    assert [item["preference_key"] for item in global_rows] == ["low_interrupt"]
    assert [item["preference_key"] for item in mira_rows] == ["low_interrupt"]
    assert [item["preference_key"] for item in maxwell_rows] == ["low_interrupt"]
    assert [item["preference_key"] for item in nora_rows] == ["nutrition_under_stress"]


@pytest.mark.asyncio
async def test_build_preference_profile_prefix_includes_global_and_agent_specific():
    await persistence.upsert_agent_preference_profile(
        agent_id="global",
        preference_key="low_interrupt",
        preference_value="用户偏好低打扰。",
        confidence=0.8,
        source_agent="mira",
        source_excerpt="别太频繁提醒我",
    )
    await persistence.upsert_agent_preference_profile(
        agent_id="nora",
        preference_key="nutrition_under_stress",
        preference_value="压力大时适合温热、低刺激、简单食物。",
        confidence=0.74,
        source_agent="nora",
        source_excerpt="压力大时不知道吃什么",
    )

    nora_prefix = await build_preference_profile_prefix("nora")
    maxwell_prefix = await build_preference_profile_prefix("maxwell")

    assert "偏好学习画像" in nora_prefix
    assert "用户偏好低打扰" in nora_prefix
    assert "温热、低刺激" in nora_prefix
    assert "用户偏好低打扰" in maxwell_prefix
    assert "温热、低刺激" not in maxwell_prefix


@pytest.mark.asyncio
async def test_chat_pipeline_injects_preference_profile_prefix(monkeypatch):
    class CapturingLLM:
        def __init__(self):
            self.calls = []

        async def chat(self, **kwargs):
            self.calls.append(kwargs)
            if "严格只输出 JSON" in kwargs.get("message", ""):
                return '{"memories":[]}'
            return "我会按你的低打扰偏好来回答。"

    async def no_memory_extract(**kwargs):
        return []

    await persistence.upsert_agent_preference_profile(
        agent_id="nora",
        preference_key="nutrition_under_stress",
        preference_value="压力大时适合温热、低刺激、简单食物。",
        confidence=0.8,
        source_agent="nora",
        source_excerpt="压力大时不知道吃什么",
    )
    monkeypatch.setattr(jarvis_router, "extract_and_save_chat_memories", no_memory_extract)
    llm = CapturingLLM()

    await jarvis_router.chat_with_agent(
        AgentChatRequest(
            agent_id="nora",
            session_id="session-preference-prefix",
            message="今天吃什么？",
        ),
        llm_client=llm,
    )

    assert "## 偏好学习画像" in llm.calls[-1]["message"]
    assert "温热、低刺激" in llm.calls[-1]["message"]
