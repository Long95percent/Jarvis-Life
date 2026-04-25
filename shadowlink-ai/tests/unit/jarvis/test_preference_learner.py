import pytest
from unittest.mock import AsyncMock, MagicMock
from app.jarvis.preference_learner import PreferenceLearner
from app.jarvis.models import UserProfile


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
