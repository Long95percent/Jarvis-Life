import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.jarvis.proactive_engine import ProactiveTriggerEngine, TriggerRule
from app.jarvis.models import LifeContext


@pytest.fixture
def engine():
    mock_roundtable = MagicMock()
    mock_roundtable.convene = AsyncMock(return_value=MagicMock(decisions=[]))
    mock_bus = MagicMock()
    mock_bus.get_context = AsyncMock(return_value=LifeContext(stress_level=9.0))
    return ProactiveTriggerEngine(roundtable=mock_roundtable, context_bus=mock_bus)


def test_stress_spike_rule_fires_at_9(engine):
    ctx = LifeContext(stress_level=9.0)
    fired = [r for r in engine.rules if r.evaluate(ctx)]
    names = [r.name for r in fired]
    assert "stress_spike" in names


def test_stress_spike_rule_silent_at_5(engine):
    ctx = LifeContext(stress_level=5.0)
    fired = [r for r in engine.rules if r.evaluate(ctx)]
    names = [r.name for r in fired]
    assert "stress_spike" not in names


@pytest.mark.asyncio
async def test_check_triggers_calls_roundtable_on_fire(engine):
    await engine.check_triggers()
    engine.roundtable.convene.assert_called_once()
