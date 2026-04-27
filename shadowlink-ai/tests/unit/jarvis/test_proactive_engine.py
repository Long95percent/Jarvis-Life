import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from app.jarvis import persistence
from app.jarvis.proactive_engine import ProactiveTriggerEngine, TriggerRule
from app.jarvis.models import LifeContext, RoundtableDecision


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    tmp = Path(tempfile.mkdtemp()) / "jarvis.db"
    monkeypatch.setattr(persistence, "_DB_PATH", tmp)
    persistence._initialized = False
    yield tmp
    persistence._initialized = False


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


@pytest.mark.asyncio
async def test_check_triggers_persists_proactive_messages(engine):
    engine.roundtable.convene = AsyncMock(
        return_value=MagicMock(
            decisions=[
                RoundtableDecision(
                    agent_id="alfred",
                    action="send_message",
                    payload={"content": "我注意到你的压力偏高，先帮你稳住今天的安排。"},
                )
            ]
        )
    )

    await engine.check_triggers()

    messages = await persistence.list_proactive_messages(include_read=False)
    assert len(messages) == 1
    assert messages[0]["agent_id"] == "alfred"
    assert messages[0]["trigger"] == "stress_spike"
    assert messages[0]["status"] == "pending"
