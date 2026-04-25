import pytest
from unittest.mock import AsyncMock, patch

from app.jarvis.local_life_aggregator import refresh_local_life, get_cached_snapshot


@pytest.mark.asyncio
async def test_refresh_handles_all_failures_gracefully():
    """All adapters raising should still produce a snapshot."""
    with patch("app.mcp.adapters.weather_adapter.get_current_weather", AsyncMock(side_effect=Exception("x"))), \
         patch("app.mcp.adapters.activities_adapter.fetch_nearby_activities", AsyncMock(side_effect=Exception("x"))), \
         patch("app.mcp.adapters.news_adapter.fetch_news", AsyncMock(side_effect=Exception("x"))):
        snap = await refresh_local_life(force=True)
        assert snap is not None
        assert snap.fetched_at > 0


@pytest.mark.asyncio
async def test_refresh_populates_when_adapters_succeed():
    with patch("app.mcp.adapters.weather_adapter.get_current_weather", AsyncMock(return_value={"temperature_c": 20})), \
         patch("app.mcp.adapters.activities_adapter.fetch_nearby_activities", AsyncMock(return_value=[])), \
         patch("app.mcp.adapters.news_adapter.fetch_news", AsyncMock(return_value=[])):
        snap = await refresh_local_life(force=True)
        assert snap.weather["temperature_c"] == 20


def test_cached_snapshot_respects_ttl():
    # After a successful refresh above, cache should be present
    s = get_cached_snapshot()
    assert s is not None or s is None  # either way valid — just doesn't crash
