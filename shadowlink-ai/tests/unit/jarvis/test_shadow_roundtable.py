import pytest
from unittest.mock import AsyncMock, MagicMock
from app.jarvis.shadow_roundtable import ShadowRoundtable
from app.jarvis.models import LifeContext, RoundtableResult


@pytest.fixture
def mock_llm():
    client = MagicMock()
    client.chat = AsyncMock(return_value='{"action": "send_message", "payload": {"content": "Stay hydrated!"}}')
    return client


@pytest.fixture
def roundtable(mock_llm):
    return ShadowRoundtable(llm_client=mock_llm)


@pytest.mark.asyncio
async def test_convene_returns_roundtable_result(roundtable):
    ctx = LifeContext(stress_level=8.0, schedule_density=9.0)
    result = await roundtable.convene(
        trigger="stress_spike",
        context=ctx,
        participating_agents=["nora", "mira"],
    )
    assert isinstance(result, RoundtableResult)
    assert result.trigger == "stress_spike"
    assert len(result.decisions) > 0


@pytest.mark.asyncio
async def test_shadow_agent_excluded_from_roundtable(roundtable):
    ctx = LifeContext()
    result = await roundtable.convene(
        trigger="daily_morning",
        context=ctx,
        participating_agents=["alfred", "shadow"],  # shadow should be filtered out
    )
    agent_ids = [d.agent_id for d in result.decisions]
    assert "shadow" not in agent_ids
