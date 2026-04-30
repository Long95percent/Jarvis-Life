import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.api.v1 import jarvis_router
from app.jarvis import persistence
from app.jarvis.intent_router import plan_agent_intent
from app.jarvis.models import LifeContext
from app.jarvis.tool_runtime import get_allowed_tool_names
from app.mcp.registry import ToolRegistry


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    tmp = Path(tempfile.mkdtemp()) / "jarvis.db"
    monkeypatch.setattr(persistence, "_DB_PATH", tmp)
    persistence._initialized = False
    yield tmp
    persistence._initialized = False


@pytest.mark.asyncio
async def test_local_life_cache_upserts_and_filters_future_items():
    now = datetime(2026, 4, 30, 9, 0)
    future = {
        "source_url": "https://events.example.com/market",
        "title": "周末手作市集",
        "item_type": "event",
        "category": "market",
        "venue": "社区广场",
        "address": "幸福路 1 号",
        "lat": 35.0,
        "lng": 139.0,
        "distance_m": 900,
        "starts_at": "2026-05-02T10:00:00+08:00",
        "ends_at": "2026-05-02T18:00:00+08:00",
        "expires_at": "2026-05-02T18:00:00+08:00",
        "summary": "附近的手作与轻食活动。",
        "fit_tags": ["low_effort", "food"],
        "confidence": 0.82,
        "date_confidence": "high",
        "location_label": "Tokyo",
        "query": "附近 周末 活动",
    }
    past = {
        **future,
        "source_url": "https://events.example.com/old",
        "title": "已经结束的展览",
        "starts_at": "2026-04-20T10:00:00+08:00",
        "ends_at": "2026-04-20T18:00:00+08:00",
        "expires_at": "2026-04-20T18:00:00+08:00",
    }

    await persistence.upsert_local_life_items([future, past], now_ts=now.timestamp())
    await persistence.upsert_local_life_items([{**future, "title": "周末手作市集更新"}], now_ts=(now + timedelta(minutes=1)).timestamp())

    items = await persistence.list_local_life_items(min_expires_at=now.isoformat(), limit=10)

    assert [item["source_url"] for item in items] == ["https://events.example.com/market"]
    assert items[0]["title"] == "周末手作市集更新"
    assert items[0]["fit_tags"] == ["low_effort", "food"]


@pytest.mark.asyncio
async def test_local_life_service_uses_cache_and_filters_expired_web_results(monkeypatch):
    from app.jarvis.local_life_search import LocalLifeSearchQuery, LocalLifeSearchService

    now = datetime(2026, 4, 30, 9, 0)
    calls: list[str] = []

    async def fake_web_search(query: str, max_results: int):
        calls.append(query)
        return [
            {
                "title": "附近陶艺体验",
                "source_url": "https://events.example.com/pottery",
                "summary": "5 月 3 日开放体验。",
                "venue": "小河工坊",
                "address": "小河路 8 号",
                "distance_m": 1200,
                "starts_at": "2026-05-03T14:00:00+08:00",
                "ends_at": "2026-05-03T16:00:00+08:00",
                "expires_at": "2026-05-03T16:00:00+08:00",
                "category": "workshop",
                "fit_tags": ["low_effort"],
            },
            {
                "title": "过期音乐会",
                "source_url": "https://events.example.com/old-concert",
                "summary": "4 月 20 日已结束。",
                "expires_at": "2026-04-20T21:00:00+08:00",
            },
        ]

    service = LocalLifeSearchService(web_search=fake_web_search)
    first = await service.search(
        LocalLifeSearchQuery(query="附近安静活动", category="recovery", radius_m=2000, limit=5),
        now=now,
    )
    second = await service.search(
        LocalLifeSearchQuery(query="附近安静活动", category="recovery", radius_m=2000, limit=5),
        now=now,
    )

    assert [item.title for item in first] == ["附近陶艺体验"]
    assert [item.title for item in second] == ["附近陶艺体验"]
    assert calls == ["附近安静活动"]


@pytest.mark.asyncio
async def test_local_life_service_filters_cached_items_by_requested_radius():
    from app.jarvis.local_life_search import LocalLifeSearchQuery, LocalLifeSearchService

    now = datetime(2026, 4, 30, 9, 0)
    await persistence.upsert_local_life_items([
        {
            "source_url": "https://events.example.com/far-market",
            "title": "远处大型市集",
            "item_type": "event",
            "category": "activity",
            "venue": "远处广场",
            "distance_m": 10000,
            "starts_at": "2026-05-01T10:00:00+08:00",
            "ends_at": "2026-05-01T18:00:00+08:00",
            "expires_at": "2026-05-01T18:00:00+08:00",
            "summary": "同一个查询下较远的活动。",
            "fit_tags": ["activity"],
            "confidence": 0.9,
            "date_confidence": "high",
            "location_label": "Tokyo",
            "query": "附近活动",
        }
    ])

    async def no_web_search(query: str, max_results: int):
        return []

    service = LocalLifeSearchService(web_search=no_web_search)
    items = await service.search(
        LocalLifeSearchQuery(query="附近活动", category="activity", radius_m=2000, limit=5),
        now=now,
    )

    assert items == []


@pytest.mark.asyncio
async def test_local_life_service_filters_cached_fallback_when_web_search_fails():
    from app.jarvis.local_life_search import LocalLifeSearchQuery, LocalLifeSearchService

    now = datetime(2026, 4, 30, 9, 0)
    await persistence.upsert_local_life_items([
        {
            "source_url": "https://events.example.com/far-fallback",
            "title": "失败兜底里的远处活动",
            "item_type": "event",
            "category": "activity",
            "venue": "远处广场",
            "distance_m": 10000,
            "starts_at": "2026-05-01T10:00:00+08:00",
            "ends_at": "2026-05-01T18:00:00+08:00",
            "expires_at": "2026-05-01T18:00:00+08:00",
            "summary": "实时搜索失败时也不能返回这个远处缓存。",
            "fit_tags": ["activity"],
            "confidence": 0.9,
            "date_confidence": "high",
            "location_label": "Tokyo",
            "query": "附近活动失败兜底",
        }
    ])

    async def failing_web_search(query: str, max_results: int):
        raise RuntimeError("search backend unavailable")

    service = LocalLifeSearchService(web_search=failing_web_search)
    items = await service.search(
        LocalLifeSearchQuery(query="附近活动失败兜底", category="activity", radius_m=2000, limit=5),
        now=now,
    )

    assert items == []


@pytest.mark.asyncio
async def test_local_life_service_applies_window_days_to_cached_and_fetched_items():
    from app.jarvis.local_life_search import LocalLifeSearchQuery, LocalLifeSearchService

    now = datetime(2026, 4, 30, 9, 0)
    await persistence.upsert_local_life_items([
        {
            "source_url": "https://events.example.com/cached-late",
            "title": "二十天后的缓存活动",
            "item_type": "event",
            "category": "activity",
            "venue": "远期会场",
            "distance_m": 800,
            "starts_at": "2026-05-20T10:00:00+08:00",
            "ends_at": "2026-05-20T12:00:00+08:00",
            "expires_at": "2026-05-20T12:00:00+08:00",
            "summary": "超出这几天窗口。",
            "fit_tags": ["activity"],
            "confidence": 0.9,
            "date_confidence": "high",
            "location_label": "Tokyo",
            "query": "这几天附近活动",
        }
    ])

    async def fake_web_search(query: str, max_results: int):
        return [
            {
                "title": "明天小型展览",
                "source_url": "https://events.example.com/tomorrow",
                "summary": "明天开放。",
                "distance_m": 900,
                "starts_at": "2026-05-01T10:00:00+08:00",
                "ends_at": "2026-05-01T12:00:00+08:00",
                "expires_at": "2026-05-01T12:00:00+08:00",
                "category": "activity",
            },
            {
                "title": "二十天后的新活动",
                "source_url": "https://events.example.com/fetched-late",
                "summary": "很久以后。",
                "distance_m": 700,
                "starts_at": "2026-05-20T10:00:00+08:00",
                "ends_at": "2026-05-20T12:00:00+08:00",
                "expires_at": "2026-05-20T12:00:00+08:00",
                "category": "activity",
            },
        ]

    service = LocalLifeSearchService(web_search=fake_web_search)
    items = await service.search(
        LocalLifeSearchQuery(query="这几天附近活动", category="activity", radius_m=2000, window_days=3, limit=5),
        now=now,
    )

    assert [item.title for item in items] == ["明天小型展览"]


@pytest.mark.asyncio
async def test_local_life_tool_is_whitelisted_and_registered(monkeypatch):
    from app.core.dependencies import set_resource
    from app.tools.jarvis_tools import JarvisLocalLifeSearchTool

    for agent_id in ["maxwell", "nora", "mira", "leo"]:
        assert "jarvis_local_life_search" in get_allowed_tool_names(agent_id)

    async def fake_search(self, query):
        return [
            {
                "source_url": "https://events.example.com/cafe",
                "title": "轻食市集",
                "expires_at": "2026-05-01T17:00:00+08:00",
            }
        ]

    monkeypatch.setattr("app.jarvis.local_life_search.LocalLifeSearchService.search", fake_search)
    registry = ToolRegistry()
    tool = JarvisLocalLifeSearchTool()
    registry.register(tool.to_tool_info(), tool)
    set_resource("tool_registry", registry)

    result = await tool._arun(query="附近健康轻食", category="food", limit=3)

    assert result[0]["title"] == "轻食市集"
    assert result[0]["source_url"] == "https://events.example.com/cafe"


def test_private_intent_routes_local_life_for_each_visible_role():
    cases = [
        ("leo", "周末附近有什么轻松活动？"),
        ("mira", "附近有没有安静一点的展览，适合恢复一下？"),
        ("nora", "附近有没有健康一点的市集或者轻食活动？"),
        ("maxwell", "帮我找一个附近这几天可以安排进日程的活动"),
        ("athena", "附近有没有适合学习间隙放松一下的展览？"),
    ]

    for agent_id, message in cases:
        decision = plan_agent_intent(agent_id, message, local_now=datetime(2026, 4, 30, 9, 0))
        assert decision.next_action == "call_tool"
        assert decision.tool_name == "jarvis_local_life_search"
        assert decision.slots["min_date"] == "2026-04-30"


@pytest.mark.asyncio
async def test_roundtable_context_reads_cached_local_life_without_live_search():
    await persistence.upsert_local_life_items([
        {
            "source_url": "https://events.example.com/gallery",
            "title": "晚间小型展览",
            "item_type": "event",
            "category": "recovery",
            "venue": "街角画廊",
            "address": "安静路 2 号",
            "distance_m": 700,
            "starts_at": "2026-04-30T18:00:00+08:00",
            "ends_at": "2026-04-30T20:00:00+08:00",
            "expires_at": "2026-04-30T20:00:00+08:00",
            "summary": "低刺激的短时展览。",
            "fit_tags": ["low_effort", "quiet"],
            "confidence": 0.8,
            "date_confidence": "high",
            "location_label": "Tokyo",
            "query": "附近安静活动",
        }
    ])

    prefix = await jarvis_router._build_local_life_context_prefix(now=datetime(2026, 4, 30, 9, 0), limit=5)

    assert "## 近期本地生活机会" in prefix
    assert "晚间小型展览" in prefix
    assert "街角画廊" in prefix


@pytest.mark.asyncio
async def test_context_prefix_filters_cached_local_life_by_window_and_radius():
    await persistence.upsert_local_life_items([
        {
            "source_url": "https://events.example.com/near",
            "title": "明天附近小展",
            "item_type": "event",
            "category": "recovery",
            "venue": "街角画廊",
            "distance_m": 700,
            "starts_at": "2026-05-01T18:00:00+08:00",
            "ends_at": "2026-05-01T20:00:00+08:00",
            "expires_at": "2026-05-01T20:00:00+08:00",
            "summary": "低刺激的短时展览。",
            "fit_tags": ["low_effort", "quiet"],
            "confidence": 0.8,
            "date_confidence": "high",
            "location_label": "Tokyo",
            "query": "附近安静活动",
        },
        {
            "source_url": "https://events.example.com/late",
            "title": "二十天后的展览",
            "item_type": "event",
            "category": "recovery",
            "venue": "远期画廊",
            "distance_m": 600,
            "starts_at": "2026-05-20T18:00:00+08:00",
            "ends_at": "2026-05-20T20:00:00+08:00",
            "expires_at": "2026-05-20T20:00:00+08:00",
            "summary": "超出近期窗口。",
            "fit_tags": ["low_effort"],
            "confidence": 0.9,
            "date_confidence": "high",
            "location_label": "Tokyo",
            "query": "附近安静活动",
        },
        {
            "source_url": "https://events.example.com/far",
            "title": "十公里外的展览",
            "item_type": "event",
            "category": "recovery",
            "venue": "远处画廊",
            "distance_m": 10000,
            "starts_at": "2026-05-01T18:00:00+08:00",
            "ends_at": "2026-05-01T20:00:00+08:00",
            "expires_at": "2026-05-01T20:00:00+08:00",
            "summary": "超出附近半径。",
            "fit_tags": ["low_effort"],
            "confidence": 0.95,
            "date_confidence": "high",
            "location_label": "Tokyo",
            "query": "附近安静活动",
        },
    ])

    prefix = await jarvis_router._build_local_life_context_prefix(
        now=datetime(2026, 4, 30, 9, 0),
        limit=5,
        window_days=14,
        radius_m=3000,
    )

    assert "明天附近小展" in prefix
    assert "二十天后的展览" not in prefix
    assert "十公里外的展览" not in prefix


@pytest.mark.asyncio
async def test_proactive_routines_can_append_cached_local_life_opportunity():
    from app.jarvis.proactive_routines import build_local_life_opportunity_hint

    await persistence.upsert_local_life_items([
        {
            "source_url": "https://events.example.com/market",
            "title": "午后轻食市集",
            "item_type": "event",
            "category": "food",
            "venue": "社区广场",
            "address": "幸福路 1 号",
            "distance_m": 900,
            "starts_at": "2026-04-30T12:00:00+08:00",
            "ends_at": "2026-04-30T16:00:00+08:00",
            "expires_at": "2026-04-30T16:00:00+08:00",
            "summary": "附近的轻食和饮品摊位。",
            "fit_tags": ["food", "low_effort"],
            "confidence": 0.82,
            "date_confidence": "high",
            "location_label": "Tokyo",
            "query": "附近轻食",
        }
    ])

    hint = await build_local_life_opportunity_hint("nora", now=datetime(2026, 4, 30, 9, 0))

    assert "午后轻食市集" in hint
    assert "900m" in hint


@pytest.mark.asyncio
async def test_proactive_hint_filters_cached_local_life_by_window_and_radius():
    from app.jarvis.proactive_routines import build_local_life_opportunity_hint

    await persistence.upsert_local_life_items([
        {
            "source_url": "https://events.example.com/food-near",
            "title": "明天附近轻食市集",
            "item_type": "event",
            "category": "food",
            "venue": "社区广场",
            "distance_m": 900,
            "starts_at": "2026-05-01T12:00:00+08:00",
            "ends_at": "2026-05-01T16:00:00+08:00",
            "expires_at": "2026-05-01T16:00:00+08:00",
            "summary": "附近轻食。",
            "fit_tags": ["food", "low_effort"],
            "confidence": 0.8,
            "date_confidence": "high",
            "location_label": "Tokyo",
            "query": "附近轻食",
        },
        {
            "source_url": "https://events.example.com/food-late",
            "title": "二十天后的轻食市集",
            "item_type": "event",
            "category": "food",
            "venue": "远期广场",
            "distance_m": 800,
            "starts_at": "2026-05-20T12:00:00+08:00",
            "ends_at": "2026-05-20T16:00:00+08:00",
            "expires_at": "2026-05-20T16:00:00+08:00",
            "summary": "超出近期窗口。",
            "fit_tags": ["food"],
            "confidence": 0.95,
            "date_confidence": "high",
            "location_label": "Tokyo",
            "query": "附近轻食",
        },
        {
            "source_url": "https://events.example.com/food-far",
            "title": "十公里外轻食市集",
            "item_type": "event",
            "category": "food",
            "venue": "远处广场",
            "distance_m": 10000,
            "starts_at": "2026-05-01T12:00:00+08:00",
            "ends_at": "2026-05-01T16:00:00+08:00",
            "expires_at": "2026-05-01T16:00:00+08:00",
            "summary": "超出附近半径。",
            "fit_tags": ["food"],
            "confidence": 0.9,
            "date_confidence": "high",
            "location_label": "Tokyo",
            "query": "附近轻食",
        },
    ])

    hint = await build_local_life_opportunity_hint("nora", now=datetime(2026, 4, 30, 9, 0))

    assert "明天附近轻食市集" in hint
    assert "二十天后的轻食市集" not in hint
    assert "十公里外轻食市集" not in hint


@pytest.mark.asyncio
async def test_proactive_routine_only_adds_local_life_hint_for_matching_context(monkeypatch):
    from app.jarvis.proactive_routines import ProactiveRoutineScheduler

    calls: list[str] = []

    async def fake_hint(agent_id: str, **kwargs):
        calls.append(agent_id)
        return " 附近机会。"

    async def no_care_triggers(date: str):
        return []

    async def skipped_maintenance(**kwargs):
        return {"skipped": True}

    monkeypatch.setattr("app.jarvis.proactive_routines.build_local_life_opportunity_hint", fake_hint)
    monkeypatch.setattr("app.jarvis.care_triggers.evaluate_care_triggers", no_care_triggers)
    monkeypatch.setattr("app.jarvis.mood_snapshot_maintenance.ensure_mood_snapshots", skipped_maintenance)
    monkeypatch.setattr("app.jarvis.planner_maintenance.run_planner_daily_maintenance_once", skipped_maintenance)
    monkeypatch.setattr("app.jarvis.user_settings.get_enabled_agents", lambda default=None: default or [])

    scheduler = ProactiveRoutineScheduler()
    morning_ctx = LifeContext(
        stress_level=3.0,
        schedule_density=3.0,
        sleep_quality=7.0,
        last_updated=datetime(2026, 4, 30, 8, 0),
        source_agent="user_chat",
    )
    morning = await scheduler.check_routines(morning_ctx, now=datetime(2026, 4, 30, 8, 30))

    midday_ctx = LifeContext(
        stress_level=7.5,
        schedule_density=4.0,
        sleep_quality=7.0,
        last_updated=datetime(2026, 4, 30, 12, 0),
        source_agent="user_chat",
    )
    midday = await scheduler.check_routines(midday_ctx, now=datetime(2026, 4, 30, 12, 10))

    assert "附近机会" not in morning[0]["content"]
    assert "附近机会" in midday[0]["content"]
    assert calls == ["nora"]


@pytest.mark.asyncio
async def test_existing_local_life_aggregator_exposes_cached_opportunities(monkeypatch):
    from app.jarvis import local_life_aggregator

    local_life_aggregator._cache = None
    tomorrow = (datetime.now() + timedelta(days=1)).date().isoformat()
    await persistence.upsert_local_life_items([
        {
            "source_url": "https://events.example.com/walk",
            "title": "河边轻松散步活动",
            "item_type": "event",
            "category": "recovery",
            "venue": "河边步道",
            "address": "河边路",
            "distance_m": 500,
            "starts_at": f"{tomorrow}T09:00:00+08:00",
            "ends_at": f"{tomorrow}T10:00:00+08:00",
            "expires_at": f"{tomorrow}T10:00:00+08:00",
            "summary": "低负担散步。",
            "fit_tags": ["recovery", "low_effort"],
            "confidence": 0.8,
            "date_confidence": "high",
            "location_label": "Tokyo",
            "query": "附近恢复活动",
        }
    ])

    async def fake_weather(**kwargs):
        return {"temperature_c": 20}

    async def fake_activities(**kwargs):
        return []

    async def fake_news(**kwargs):
        return []

    monkeypatch.setattr("app.mcp.adapters.weather_adapter.get_current_weather", fake_weather)
    monkeypatch.setattr("app.mcp.adapters.activities_adapter.fetch_nearby_activities", fake_activities)
    monkeypatch.setattr("app.mcp.adapters.news_adapter.fetch_news", fake_news)
    monkeypatch.setattr("app.mcp.adapters.calendar_adapter.get_upcoming_events", lambda hours_ahead=24: [])
    monkeypatch.setattr("app.mcp.adapters.calendar_adapter.compute_schedule_density", lambda: 0.0)

    snapshot = await local_life_aggregator.refresh_local_life(force=True)

    assert snapshot.opportunities[0]["title"] == "河边轻松散步活动"
    assert snapshot.sources["opportunities"] == "local_life_cache"
    local_life_aggregator._cache = None
