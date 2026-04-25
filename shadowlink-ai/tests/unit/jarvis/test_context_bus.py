import asyncio
import pytest
from app.jarvis.context_bus import LifeContextBus
from app.jarvis.models import LifeContext


@pytest.fixture
def bus():
    return LifeContextBus()


@pytest.mark.asyncio
async def test_get_context_returns_default(bus):
    ctx = await bus.get_context()
    assert ctx.stress_level == 0.0
    assert ctx.mood_trend == "neutral"


@pytest.mark.asyncio
async def test_update_context_partial(bus):
    await bus.update_fields({"stress_level": 7.5, "mood_trend": "negative"}, source="maxwell")
    ctx = await bus.get_context()
    assert ctx.stress_level == 7.5
    assert ctx.mood_trend == "negative"
    assert ctx.source_agent == "maxwell"


@pytest.mark.asyncio
async def test_subscribe_receives_update(bus):
    queue = await bus.subscribe("test_agent")
    await bus.update_fields({"stress_level": 9.0}, source="nora")
    event = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert event["stress_level"] == 9.0
    assert event["source_agent"] == "nora"
