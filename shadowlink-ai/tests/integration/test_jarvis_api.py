from unittest.mock import AsyncMock
import asyncio
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from fastapi.testclient import TestClient

from app.api.v1 import jarvis_router
from app.jarvis import persistence
from app.jarvis.agent_consultation import AgentConsultationResult
from app.jarvis.models import ProactiveMessage
from app.jarvis.persistence import (
    clear_collaboration_memories,
    save_collaboration_memory,
)
from app.mcp.adapters.calendar_adapter import delete_event, get_upcoming_events
from app.core.dependencies import set_resource
from app.core.dependencies import get_llm_client
from app.main import create_app
from app.mcp.registry import ToolRegistry
from app.tools.jarvis_tools import (
    Activity,
    JarvisActivityRankByEnergyTool,
    JarvisBreathingProtocolTool,
    JarvisBurnoutRiskAssessTool,
    JarvisCalendarAddTool,
    JarvisCalendarFindFreeSlotTool,
    JarvisCalendarUpcomingTool,
    JarvisCaffeineCutoffGuardTool,
    JarvisCheckinScheduleTool,
    JarvisContextSnapshotTool,
    JarvisDailyBriefingTool,
    JarvisDeadlineCheckTool,
    JarvisHydrationPlanTool,
    JarvisPlanActivitySlotTool,
    JarvisMealPlanTool,
    JarvisMeetingBriefTool,
    JarvisMoodJournalTool,
    JarvisNutritionLookupTool,
    JarvisRouteEstimateTool,
    JarvisSpecialistOrchestrateTool,
    JarvisTaskPrioritizeTool,
)


def test_pick_geocode_label_supports_display_name_and_district_fields():
    from app.jarvis.geocoding import pick_osm_geocode_label

    assert pick_osm_geocode_label({"address": {"city_district": "Xuanwu District"}}) == "Xuanwu District"
    assert pick_osm_geocode_label({"display_name": "Nanjing, Jiangsu, China"}) == "Nanjing"


@pytest.fixture
async def client(monkeypatch):
    app = create_app()

    # Override LLM client so the /chat endpoint does not require network or API keys
    mock_llm = AsyncMock()
    mock_llm.chat = AsyncMock(return_value="Good morning, sir. Your schedule is clear.")

    async def override_get_llm_client():
        return mock_llm

    app.dependency_overrides[get_llm_client] = override_get_llm_client

    async def no_consultations(**kwargs):
        return AgentConsultationResult([], "", [])

    async def no_mood_snapshot(*args, **kwargs):
        return None

    monkeypatch.setattr(jarvis_router, "run_agent_consultations", no_consultations)
    monkeypatch.setattr("app.jarvis.mood_care.detect_mood_snapshot_enhanced", no_mood_snapshot)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def client_with_mock_llm(monkeypatch):
    app = create_app()

    mock_llm = AsyncMock()
    mock_llm.chat = AsyncMock(return_value="Good morning, sir. Your schedule is clear.")

    async def override_get_llm_client():
        return mock_llm

    app.dependency_overrides[get_llm_client] = override_get_llm_client

    async def no_consultations(**kwargs):
        return AgentConsultationResult([], "", [])

    async def no_mood_snapshot(*args, **kwargs):
        return None

    monkeypatch.setattr(jarvis_router, "run_agent_consultations", no_consultations)
    monkeypatch.setattr("app.jarvis.mood_care.detect_mood_snapshot_enhanced", no_mood_snapshot)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, mock_llm


def test_secretary_plan_endpoint_creates_long_plan(monkeypatch):
    app = create_app()
    mock_llm = AsyncMock()

    async def override_get_llm_client():
        return mock_llm

    app.dependency_overrides[get_llm_client] = override_get_llm_client
    db_dir = Path("data") / "test_dbs"
    db_dir.mkdir(parents=True, exist_ok=True)
    tmp = db_dir / f"jarvis-secretary-api-{uuid4().hex}.db"
    monkeypatch.setattr(persistence, "_DB_PATH", tmp)
    persistence._initialized = False
    mock_llm.chat = AsyncMock(return_value=json.dumps({
        "schema_version": "secretary_long_plan.v1",
        "intent": "long_plan",
        "plan": {
            "title": "雅思 3 天备考计划",
            "goal": "完成三天基础训练",
            "plan_type": "long_term",
            "start_date": "2026-05-01",
            "target_date": "2026-05-03",
        },
        "days": [
            {"day_index": 1, "date": "2026-05-01", "start_time": "19:30", "end_time": "21:00", "title": "听力诊断", "description": "听力", "estimated_minutes": 90, "reason": "start"},
            {"day_index": 2, "date": "2026-05-02", "start_time": "19:30", "end_time": "21:00", "title": "阅读训练", "description": "阅读", "estimated_minutes": 90, "reason": "continue"},
        ],
    }, ensure_ascii=False))

    client = TestClient(app)
    resp = client.post("/api/v1/jarvis/planner/secretary-plan", json={
        "intent": "long_plan",
        "message": "我要考雅思，未来 3 天帮我安排学习计划",
        "today": "2026-05-01",
        "auto_project_calendar": False,
    })

    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "long_plan"
    assert data["plan"]["title"] == "雅思 3 天备考计划"
    assert len(data["plan_days"]) == 2
    assert mock_llm.chat.await_count == 1
    persistence._initialized = False


def test_secretary_plan_endpoint_creates_short_schedule(monkeypatch):
    app = create_app()
    mock_llm = AsyncMock()

    async def override_get_llm_client():
        return mock_llm

    app.dependency_overrides[get_llm_client] = override_get_llm_client
    db_dir = Path("data") / "test_dbs"
    db_dir.mkdir(parents=True, exist_ok=True)
    tmp = db_dir / f"jarvis-secretary-short-api-{uuid4().hex}.db"
    monkeypatch.setattr(persistence, "_DB_PATH", tmp)
    persistence._initialized = False
    mock_llm.chat = AsyncMock(return_value=json.dumps({
        "schema_version": "secretary_schedule.v1",
        "intent": "short_schedule",
        "summary": "明晚安排一次雅思听力复习。",
        "items": [{
            "client_item_id": "short-1",
            "date": "2026-05-02",
            "start_time": "19:30",
            "end_time": "21:00",
            "title": "雅思听力复习",
            "description": "完成 Section 1-2 并整理错题。",
            "estimated_minutes": 90,
            "priority": "high",
            "reason": "用户指定明晚。",
        }],
    }, ensure_ascii=False))

    client = TestClient(app)
    resp = client.post("/api/v1/jarvis/planner/secretary-plan", json={
        "intent": "short_schedule",
        "message": "明天晚上帮我安排一次雅思听力复习",
        "today": "2026-05-01",
        "auto_project_calendar": False,
    })

    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "short_schedule"
    assert data["plan"]["plan_type"] == "short_term"
    assert data["plan_days"][0]["title"] == "雅思听力复习"
    assert mock_llm.chat.await_count == 1
    persistence._initialized = False


def test_secretary_plan_endpoint_reschedules_existing_plan(monkeypatch):
    app = create_app()
    mock_llm = AsyncMock()

    async def override_get_llm_client():
        return mock_llm

    app.dependency_overrides[get_llm_client] = override_get_llm_client
    db_dir = Path("data") / "test_dbs"
    db_dir.mkdir(parents=True, exist_ok=True)
    tmp = db_dir / f"jarvis-secretary-reschedule-api-{uuid4().hex}.db"
    monkeypatch.setattr(persistence, "_DB_PATH", tmp)
    persistence._initialized = False
    plan = asyncio.run(persistence.save_jarvis_plan(
        plan_id="plan-api-reschedule",
        title="雅思计划",
        plan_type="long_term",
        status="active",
        source_agent="maxwell",
        original_user_request="雅思计划",
        goal="备考",
        days=[{"id": "api-reschedule-day-1", "date": "2026-05-02", "title": "旧听力", "start_time": "19:00", "end_time": "20:00"}],
    ))
    mock_llm.chat = AsyncMock(return_value=json.dumps({
        "schema_version": "secretary_reschedule.v1",
        "intent": "reschedule_plan",
        "summary": "已重新安排。",
        "plan_id": plan["id"],
        "days": [{
            "id": "api-reschedule-day-1",
            "date": "2026-05-03",
            "start_time": "20:00",
            "end_time": "21:00",
            "title": "新听力",
            "description": "重排后继续听力",
            "estimated_minutes": 60,
            "reason": "用户未完成。",
        }],
    }, ensure_ascii=False))

    client = TestClient(app)
    resp = client.post("/api/v1/jarvis/planner/secretary-plan", json={
        "intent": "reschedule_plan",
        "message": "今天没完成，帮我重新安排后面的计划",
        "today": "2026-05-01",
        "plan_id": plan["id"],
        "plan_day_ids": ["api-reschedule-day-1"],
        "auto_project_calendar": False,
    })

    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "reschedule_plan"
    assert data["changed_count"] == 1
    assert data["plan_days"][0]["plan_date"] == "2026-05-03"
    assert data["plan_days"][0]["title"] == "新听力"
    assert mock_llm.chat.await_count == 1
    persistence._initialized = False


@pytest.mark.asyncio
async def test_get_life_context(client):
    resp = await client.get("/api/v1/jarvis/context")
    assert resp.status_code == 200
    data = resp.json()
    assert "stress_level" in data
    assert "mood_trend" in data


@pytest.mark.asyncio
async def test_update_life_context(client):
    resp = await client.post("/api/v1/jarvis/context", json={
        "stress_level": 8.0,
        "mood_trend": "negative",
    })
    assert resp.status_code == 200
    assert resp.json()["stress_level"] == 8.0


@pytest.mark.asyncio
async def test_get_time_context_uses_saved_profile_timezone(client):
    profile_resp = await client.patch(
        "/api/v1/jarvis/profile",
        json={"location": {"label": "New York", "timezone": "America/New_York"}},
    )
    assert profile_resp.status_code == 200

    resp = await client.get("/api/v1/jarvis/time/context?browser_timezone=Asia/Tokyo")

    assert resp.status_code == 200
    data = resp.json()
    assert data["timezone"] == "America/New_York"
    assert data["location_label"] == "New York"
    assert "local_date" in data
    assert "utc_offset" in data


@pytest.mark.asyncio
async def test_get_time_context_rejects_bad_browser_timezone(client):
    await client.patch("/api/v1/jarvis/profile", json={"location": {"timezone": ""}})

    resp = await client.get("/api/v1/jarvis/time/context?browser_timezone=Mars/Olympus")

    assert resp.status_code == 400
    assert "Invalid timezone" in resp.json()["detail"]


@pytest.mark.anyio
async def test_browser_location_returns_city_timezone_and_weather(client, monkeypatch):
    async def fake_fetch_location_metadata(lat: float, lng: float):
        assert lat == 32.0603
        assert lng == 118.7969
        return {"label": "Nanjing", "weather": {"temperature_c": 25.0, "weather_code": 1}}

    monkeypatch.setattr(jarvis_router, "_fetch_browser_location_metadata", fake_fetch_location_metadata)

    resp = await client.post(
        "/api/v1/jarvis/time/browser-location",
        json={"lat": 32.0603, "lng": 118.7969, "browser_timezone": "Asia/Shanghai"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["label"] == "Nanjing"
    assert data["timezone"] == "Asia/Shanghai"
    assert data["weather"]["temperature_c"] == 25.0


@pytest.mark.anyio
async def test_city_location_saves_when_weather_fails(client, monkeypatch):
    async def fake_geocode_city(city_name: str):
        assert city_name == "南京"

        class _Result:
            def to_dict(self):
                return {"label": "南京市", "lat": 32.060255, "lng": 118.796877, "provider": "amap"}

        return _Result()

    async def fake_fetch_weather(lat: float, lng: float):
        raise RuntimeError("weather unavailable")

    monkeypatch.setattr("app.jarvis.geocoding.geocode_city", fake_geocode_city)
    monkeypatch.setattr(jarvis_router, "_fetch_weather_for_location", fake_fetch_weather)

    resp = await client.post(
        "/api/v1/jarvis/time/city-location",
        json={"city_name": "南京", "browser_timezone": "Asia/Shanghai"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["label"] == "南京市"
    assert data["lat"] == 32.060255
    assert data["lng"] == 118.796877
    assert data["weather"]["error"] == "weather unavailable"


@pytest.mark.asyncio
async def test_chat_with_agent(client):
    resp = await client.post("/api/v1/jarvis/chat", json={
        "agent_id": "alfred",
        "message": "What's on my schedule today?",
        "session_id": "test-session",
    })
    assert resp.status_code == 200
    assert "content" in resp.json()

    context_resp = await client.get("/api/v1/jarvis/context")
    assert context_resp.status_code == 200
    assert context_resp.json()["source_agent"] == "user_chat"


@pytest.mark.anyio
async def test_chat_with_agent_uses_browser_timezone_for_default_profile(client_with_mock_llm):
    client, mock_llm = client_with_mock_llm
    await client.patch(
        "/api/v1/jarvis/profile",
        json={"location": {"label": "", "timezone": "Asia/Tokyo", "timezone_source": "auto"}},
    )

    resp = await client.post("/api/v1/jarvis/chat", json={
        "agent_id": "alfred",
        "message": "Plan my morning",
        "session_id": "browser-timezone-session",
        "browser_timezone": "America/Los_Angeles",
    })

    assert resp.status_code == 200
    first_call = mock_llm.chat.await_args_list[0].kwargs
    assert "America/Los_Angeles" in first_call["message"]
    assert "Asia/Tokyo" not in first_call["message"]


@pytest.mark.asyncio
async def test_chat_with_agent_uses_role_whitelisted_tools(client_with_mock_llm):
    client, mock_llm = client_with_mock_llm
    registry = ToolRegistry()
    tool = JarvisContextSnapshotTool()
    registry.register(tool.to_tool_info(), tool)
    set_resource("tool_registry", registry)
    mock_llm.chat = AsyncMock(side_effect=[
        '<jarvis-tool>{"tool_name":"jarvis_context_snapshot","arguments":{"include_events":true}}</jarvis-tool>',
        "我看到你现在压力偏高，先把今天最重要的一件事做完，其他安排可以稍后再看。",
    ])

    resp = await client.post("/api/v1/jarvis/chat", json={
        "agent_id": "mira",
        "message": "我最近有点累，今天该怎么安排？",
        "session_id": "tool-session",
    })

    assert resp.status_code == 200
    body = resp.json()
    assert body["content"].startswith("我看到你现在压力偏高")
    assert mock_llm.chat.await_count == 2

    first_prompt = mock_llm.chat.await_args_list[0].kwargs["message"]
    assert "jarvis_context_snapshot" in first_prompt
    assert "jarvis_local_activities" not in first_prompt


@pytest.mark.asyncio
async def test_chat_with_agent_uses_registry_for_mutating_tools(client_with_mock_llm):
    client, mock_llm = client_with_mock_llm
    registry = ToolRegistry()
    read_tool = JarvisContextSnapshotTool()
    write_tool = JarvisCalendarAddTool()
    registry.register(read_tool.to_tool_info(), read_tool)
    registry.register(write_tool.to_tool_info(), write_tool)
    set_resource("tool_registry", registry)
    walk_start = (datetime.utcnow() + timedelta(days=1)).replace(hour=19, minute=0, second=0, microsecond=0)
    walk_end = walk_start + timedelta(minutes=30)
    mock_llm.chat = AsyncMock(side_effect=[
        f'<jarvis-tool>{{"tool_name":"jarvis_calendar_add","arguments":{{"title":"晚间散步","start":"{walk_start.isoformat()}","end":"{walk_end.isoformat()}","stress_weight":0.5}}}}</jarvis-tool>',
        "已经帮你把晚间散步加入日程，时间是今晚 19:00 到 19:30。",
    ])

    resp = await client.post("/api/v1/jarvis/chat", json={
        "agent_id": "alfred",
        "message": "帮我把今晚七点到七点半的散步加入日程",
        "session_id": "mutating-session",
    })

    assert resp.status_code == 200
    body = resp.json()
    assert body["content"].startswith("已经帮你把晚间散步加入日程")
    assert body["actions"] is not None
    assert body["actions"][0]["type"] == "calendar.add"
    assert body["actions"][0]["ok"] is True


@pytest.mark.asyncio
async def test_alfred_prompt_exposes_orchestration_tools_only_to_alfred(client_with_mock_llm):
    client, mock_llm = client_with_mock_llm
    registry = ToolRegistry()
    for tool in [
        JarvisContextSnapshotTool(),
        JarvisDailyBriefingTool(),
        JarvisSpecialistOrchestrateTool(),
    ]:
        registry.register(tool.to_tool_info(), tool)
    set_resource("tool_registry", registry)

    mock_llm.chat = AsyncMock(return_value="收到，我来帮你统筹安排。")

    alfred_resp = await client.post("/api/v1/jarvis/chat", json={
        "agent_id": "alfred",
        "message": "帮我统筹一下今天安排",
        "session_id": "alfred-tools",
    })
    assert alfred_resp.status_code == 200
    alfred_prompt = mock_llm.chat.await_args_list[0].kwargs["message"]
    assert "jarvis_daily_briefing" in alfred_prompt
    assert "jarvis_specialist_orchestrate" in alfred_prompt

    mock_llm.chat.reset_mock(return_value=True)
    mock_llm.chat = AsyncMock(return_value="我先看一下今天的节奏。")

    maxwell_resp = await client.post("/api/v1/jarvis/chat", json={
        "agent_id": "maxwell",
        "message": "今天日程怎么样？",
        "session_id": "maxwell-tools",
    })
    assert maxwell_resp.status_code == 200
    maxwell_prompt = mock_llm.chat.await_args_list[0].kwargs["message"]
    assert "jarvis_daily_briefing" not in maxwell_prompt
    assert "jarvis_specialist_orchestrate" not in maxwell_prompt


@pytest.mark.asyncio
async def test_maxwell_prompt_exposes_schedule_management_tools(client_with_mock_llm):
    client, mock_llm = client_with_mock_llm
    registry = ToolRegistry()
    for tool in [
        JarvisContextSnapshotTool(),
        JarvisMeetingBriefTool(),
        JarvisTaskPrioritizeTool(),
        JarvisDeadlineCheckTool(),
        JarvisCalendarFindFreeSlotTool(),
    ]:
        registry.register(tool.to_tool_info(), tool)
    set_resource("tool_registry", registry)

    mock_llm.chat = AsyncMock(return_value="我来先看一下日程和任务优先级。")
    resp = await client.post("/api/v1/jarvis/chat", json={
        "agent_id": "maxwell",
        "message": "今天我先做什么？顺便看看有没有合适会议空档。",
        "session_id": "maxwell-specialized",
    })
    assert resp.status_code == 200
    prompt = mock_llm.chat.await_args_list[0].kwargs["message"]
    assert "jarvis_meeting_brief" in prompt
    assert "jarvis_task_prioritize" in prompt
    assert "jarvis_deadline_check" in prompt
    assert "jarvis_calendar_find_free_slot" in prompt
    assert "jarvis_specialist_orchestrate" not in prompt


@pytest.mark.asyncio
async def test_maxwell_tools_support_user_visible_workflows():
    base = (datetime.utcnow() + timedelta(days=1)).replace(hour=15, minute=0, second=0, microsecond=0)
    meeting_start = base
    meeting_end = base + timedelta(hours=1)
    deadline_at = base.replace(hour=18)
    window_start = base.replace(hour=14)
    window_end = base.replace(hour=18)
    registry_tools = {
        "meeting": JarvisMeetingBriefTool(),
        "prioritize": JarvisTaskPrioritizeTool(),
        "deadline": JarvisDeadlineCheckTool(),
        "free_slot": JarvisCalendarFindFreeSlotTool(),
        "calendar_add": JarvisCalendarAddTool(),
    }

    add_result = await registry_tools["calendar_add"]._arun(
        title="项目例会",
        start=meeting_start.isoformat(),
        end=meeting_end.isoformat(),
        stress_weight=1.0,
    )
    assert add_result["ok"] is True
    event_id = add_result["event_id"]

    brief = await registry_tools["meeting"]._arun(
        event_id=event_id,
        objective="确认本周交付计划",
        agenda=["确认 blocker", "敲定 owner"],
    )
    assert brief["ok"] is True
    assert brief["event"]["title"] == "项目例会"
    assert brief["checklist"]

    prioritized = await registry_tools["prioritize"]._arun(tasks=[
        {
            "title": "提交周报",
            "deadline": deadline_at.isoformat(),
            "importance": 4,
            "estimated_minutes": 30,
            "energy_level": "low",
            "must_do": True,
        },
        {
            "title": "整理下周想法",
            "deadline": "2026-04-26T12:00:00",
            "importance": 2,
            "estimated_minutes": 90,
            "energy_level": "high",
            "must_do": False,
        },
    ])
    assert prioritized["ok"] is True
    assert prioritized["ordered_tasks"][0]["title"] == "提交周报"

    deadline_check = await registry_tools["deadline"]._arun(items=[
        {
            "title": "提交周报",
            "due_at": deadline_at.isoformat(),
            "estimated_minutes": 30,
            "importance": 4,
        },
    ])
    assert deadline_check["ok"] is True
    assert deadline_check["summary"]

    free_slot = await registry_tools["free_slot"]._arun(
        duration_minutes=30,
        window_start=window_start.isoformat(),
        window_end=window_end.isoformat(),
        preferred_period="afternoon",
        buffer_minutes=10,
    )
    assert free_slot["ok"] is True
    assert free_slot["slots"]


@pytest.mark.asyncio
async def test_nora_prompt_exposes_nutrition_tools_only_to_nora(client_with_mock_llm):
    client, mock_llm = client_with_mock_llm
    registry = ToolRegistry()
    for tool in [
        JarvisContextSnapshotTool(),
        JarvisMealPlanTool(),
        JarvisNutritionLookupTool(),
        JarvisHydrationPlanTool(),
        JarvisCaffeineCutoffGuardTool(),
    ]:
        registry.register(tool.to_tool_info(), tool)
    set_resource("tool_registry", registry)

    mock_llm.chat = AsyncMock(return_value="我先按你的状态做饮食安排。")
    resp = await client.post("/api/v1/jarvis/chat", json={
        "agent_id": "nora",
        "message": "帮我安排今天怎么吃喝，下午还能不能喝咖啡？",
        "session_id": "nora-specialized",
    })
    assert resp.status_code == 200
    prompt = mock_llm.chat.await_args_list[0].kwargs["message"]
    assert "jarvis_meal_plan" in prompt
    assert "jarvis_nutrition_lookup" in prompt
    assert "jarvis_hydration_plan" in prompt
    assert "jarvis_caffeine_cutoff_guard" in prompt
    assert "jarvis_meeting_brief" not in prompt


@pytest.mark.asyncio
async def test_nora_tools_support_user_visible_workflows():
    meal_tool = JarvisMealPlanTool()
    lookup_tool = JarvisNutritionLookupTool()
    hydration_tool = JarvisHydrationPlanTool()
    caffeine_tool = JarvisCaffeineCutoffGuardTool()

    meal_plan = await meal_tool._arun(
        meals=["breakfast", "lunch", "dinner"],
        include_snack=True,
        dietary_restrictions=["dairy_free"],
        goal="steady_energy",
    )
    assert meal_plan["ok"] is True
    assert meal_plan["meals"]

    lookup = await lookup_tool._arun(food_name="coffee", goal="sleep_friendly")
    assert lookup["ok"] is True
    assert lookup["caffeine_mg"] > 0

    hydration = await hydration_tool._arun(activity_level="medium")
    assert hydration["ok"] is True
    assert hydration["target_ml"] >= 1800
    assert hydration["schedule"]

    caffeine = await caffeine_tool._arun(
        beverage_name="coffee",
        proposed_time="2026-04-24T16:30:00",
        caffeine_mg=95,
    )
    assert caffeine["ok"] is True
    assert "cutoff_time" in caffeine


@pytest.mark.asyncio
async def test_mira_prompt_exposes_support_tools_only_to_mira(client_with_mock_llm):
    client, mock_llm = client_with_mock_llm
    registry = ToolRegistry()
    for tool in [
        JarvisContextSnapshotTool(),
        JarvisCalendarUpcomingTool(),
        JarvisCheckinScheduleTool(),
        JarvisBreathingProtocolTool(),
        JarvisMoodJournalTool(),
        JarvisBurnoutRiskAssessTool(),
    ]:
        registry.register(tool.to_tool_info(), tool)
    set_resource("tool_registry", registry)

    mock_llm.chat = AsyncMock(return_value="我们先稳一下节奏。")
    resp = await client.post("/api/v1/jarvis/chat", json={
        "agent_id": "mira",
        "message": "我今天有点绷不住了。",
        "session_id": "mira-specialized",
    })
    assert resp.status_code == 200
    prompt = mock_llm.chat.await_args_list[0].kwargs["message"]
    assert "jarvis_checkin_schedule" in prompt
    assert "jarvis_breathing_protocol" in prompt
    assert "jarvis_mood_journal" in prompt
    assert "jarvis_burnout_risk_assess" in prompt
    assert "jarvis_meal_plan" not in prompt


@pytest.mark.asyncio
async def test_mira_tools_support_user_visible_workflows(monkeypatch, tmp_path):
    monkeypatch.setattr("app.tools.jarvis_tools.app_settings.data_dir", str(tmp_path))
    breathing_tool = JarvisBreathingProtocolTool()
    burnout_tool = JarvisBurnoutRiskAssessTool()
    journal_tool = JarvisMoodJournalTool()
    checkin_tool = JarvisCheckinScheduleTool()

    breathing = await breathing_tool._arun(goal="calm_down", duration_minutes=3, intensity="grounding")
    assert breathing["ok"] is True
    assert breathing["steps"]

    burnout = await burnout_tool._arun(
        user_message="我最近真的有点扛不住，晚上也睡不好。",
        recent_signals=["连续疲惫", "不想说话"],
    )
    assert burnout["ok"] is True
    assert burnout["risk_level"] in {"medium", "high"}

    journal = await journal_tool._arun(
        mood="anxious",
        intensity=7,
        triggers=["投资人同步会", "时间紧"],
        body_signals=["肩膀紧", "心跳快"],
        note="下午开始明显紧张",
    )
    assert journal["ok"] is True
    assert journal["entry_id"].startswith("mood-")

    checkin = await checkin_tool._arun(delay_hours=12, duration_minutes=10, note="晚间轻回访")
    assert checkin["ok"] is True
    assert checkin["type"] == "checkin.schedule"


@pytest.mark.asyncio
async def test_leo_prompt_exposes_activity_execution_tools_only_to_leo(client_with_mock_llm):
    client, mock_llm = client_with_mock_llm
    registry = ToolRegistry()
    for tool in [
        JarvisContextSnapshotTool(),
        JarvisActivityRankByEnergyTool(),
        JarvisRouteEstimateTool(),
        JarvisPlanActivitySlotTool(),
    ]:
        registry.register(tool.to_tool_info(), tool)
    set_resource("tool_registry", registry)

    mock_llm.chat = AsyncMock(return_value="我来按你的体力和空档挑活动。")
    resp = await client.post("/api/v1/jarvis/chat", json={
        "agent_id": "leo",
        "message": "给我挑个今天能做的轻量活动，并直接安排进日程。",
        "session_id": "leo-specialized",
    })
    assert resp.status_code == 200
    prompt = mock_llm.chat.await_args_list[0].kwargs["message"]
    assert "jarvis_activity_rank_by_energy" in prompt
    assert "jarvis_route_estimate" in prompt
    assert "jarvis_plan_activity_slot" in prompt
    assert "jarvis_burnout_risk_assess" not in prompt


@pytest.mark.asyncio
async def test_leo_tools_support_user_visible_workflows(monkeypatch):
    for event in get_upcoming_events(hours_ahead=168):
        delete_event(event.id)

    fake_activities = [
        Activity(name="Ueno Park", category="park", lat=35.71, lng=139.77, distance_m=900, address="Tokyo"),
        Activity(name="City Museum", category="museum", lat=35.70, lng=139.75, distance_m=1400, address="Tokyo"),
        Activity(name="Fitness Lab", category="gym", lat=35.68, lng=139.74, distance_m=2200, address="Tokyo"),
    ]

    async def fake_fetch_nearby_activities(*args, **kwargs):
        return fake_activities

    monkeypatch.setattr("app.tools.jarvis_tools.fetch_nearby_activities", fake_fetch_nearby_activities)

    add_tool = JarvisCalendarAddTool()
    await add_tool._arun(
        title="现有会议",
        start="2026-04-24T15:00:00",
        end="2026-04-24T16:00:00",
        stress_weight=1.0,
    )

    rank_tool = JarvisActivityRankByEnergyTool()
    route_tool = JarvisRouteEstimateTool()
    plan_tool = JarvisPlanActivitySlotTool()

    ranked = await rank_tool._arun(energy_level="low", limit=2)
    assert ranked["ok"] is True
    assert ranked["activities"][0]["name"] == "Ueno Park"

    route = await route_tool._arun(activity_name="Ueno Park", travel_mode="walking")
    assert route["ok"] is True
    assert route["estimated_minutes"] > 0

    planned = await plan_tool._arun(
        activity_name="Ueno Park",
        duration_minutes=45,
        preferred_period="afternoon",
        travel_mode="walking",
        horizon_hours=48,
    )
    assert planned["ok"] is True
    assert planned["type"] == "calendar.add"
    assert "Leo 活动" in planned["title"]


@pytest.mark.asyncio
async def test_private_chat_injects_shared_collaboration_memory(client_with_mock_llm):
    client, mock_llm = client_with_mock_llm
    await clear_collaboration_memories()
    await save_collaboration_memory(
        source_agent="alfred",
        participant_agents=["alfred", "nora"],
        memory_kind="coordination_summary",
        content="Alfred 与 Nora 已为用户确定：下午按补水计划执行，16:30 后停咖啡。",
        structured_payload={"summary": "hydration + caffeine plan"},
    )

    registry = ToolRegistry()
    registry.register(JarvisContextSnapshotTool().to_tool_info(), JarvisContextSnapshotTool())
    set_resource("tool_registry", registry)

    mock_llm.chat = AsyncMock(return_value="我会沿用之前协同好的饮食节奏。")
    resp = await client.post("/api/v1/jarvis/chat", json={
        "agent_id": "nora",
        "message": "今天继续按之前那个节奏来。",
        "session_id": "shared-memory-nora",
    })
    assert resp.status_code == 200
    prompt = mock_llm.chat.await_args_list[0].kwargs["message"]
    assert "共享协作记忆" in prompt
    assert "下午按补水计划执行" in prompt


@pytest.mark.asyncio
async def test_global_user_constraint_reaches_other_agents(client_with_mock_llm):
    client, mock_llm = client_with_mock_llm
    await clear_collaboration_memories()
    await save_collaboration_memory(
        source_agent="alfred",
        participant_agents=[],
        memory_kind="user_constraint",
        content="用户明确表示：晚上不想安排任何外出活动。",
        structured_payload={"message": "晚上不想安排任何外出活动"},
    )

    registry = ToolRegistry()
    registry.register(JarvisContextSnapshotTool().to_tool_info(), JarvisContextSnapshotTool())
    set_resource("tool_registry", registry)

    mock_llm.chat = AsyncMock(return_value="那我就只给你白天或室内方案。")
    resp = await client.post("/api/v1/jarvis/chat", json={
        "agent_id": "leo",
        "message": "帮我安排今天活动。",
        "session_id": "shared-memory-leo",
    })
    assert resp.status_code == 200
    prompt = mock_llm.chat.await_args_list[0].kwargs["message"]
    assert "晚上不想安排任何外出活动" in prompt


@pytest.mark.asyncio
async def test_get_proactive_messages_is_non_destructive(client, monkeypatch):
    tmp = Path(tempfile.mkdtemp()) / "jarvis.db"
    monkeypatch.setattr(persistence, "_DB_PATH", tmp)
    persistence._initialized = False
    saved = await persistence.save_proactive_message(
        ProactiveMessage(
            agent_id="alfred",
            agent_name="Alfred",
            content="压力偏高，我来帮你看今天的重点。",
            trigger="stress_spike",
        )
    )

    first = await client.get("/api/v1/jarvis/messages")
    second = await client.get("/api/v1/jarvis/messages")

    assert first.status_code == 200
    assert second.status_code == 200
    assert [msg["id"] for msg in first.json()] == [saved["id"]]
    assert [msg["id"] for msg in second.json()] == [saved["id"]]
    persistence._initialized = False


@pytest.mark.asyncio
async def test_mark_proactive_message_read_updates_state(client, monkeypatch):
    tmp = Path(tempfile.mkdtemp()) / "jarvis.db"
    monkeypatch.setattr(persistence, "_DB_PATH", tmp)
    persistence._initialized = False
    saved = await persistence.save_proactive_message(
        ProactiveMessage(
            agent_id="mira",
            agent_name="Mira",
            content="我注意到你最近情绪有些下降。",
            trigger="mood_declining",
        )
    )

    read_resp = await client.post(f"/api/v1/jarvis/messages/{saved['id']}/read")
    unread_resp = await client.get("/api/v1/jarvis/messages")
    history_resp = await client.get("/api/v1/jarvis/messages?include_read=true")

    assert read_resp.status_code == 200
    assert read_resp.json()["status"] == "read"
    assert read_resp.json()["read"] is True
    assert unread_resp.json() == []
    assert [msg["id"] for msg in history_resp.json()] == [saved["id"]]
    persistence._initialized = False
