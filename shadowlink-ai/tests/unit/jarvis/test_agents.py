import pytest

from pathlib import Path
from uuid import uuid4

from app.core.dependencies import get_resource, set_resource
from app.jarvis.agents import JARVIS_AGENTS, get_agent
from app.jarvis import persistence
from app.tools.jarvis_tools import JarvisTaskPlanDecomposeTool
from app.tools.jarvis_tools import JarvisCalendarUpcomingTool
from app.mcp.adapters import calendar_adapter

def test_all_visible_agents_and_shadow_defined():
    expected = {"alfred", "maxwell", "nora", "mira", "leo", "athena", "shadow"}
    assert set(JARVIS_AGENTS.keys()) == expected

def test_alfred_is_chief_coordinator():
    alfred = get_agent("alfred")
    assert alfred["role"] == "总管家"
    assert "schedule" in alfred["system_prompt"].lower() or "coordinator" in alfred["system_prompt"].lower()

def test_shadow_has_zero_interrupt_budget():
    shadow = get_agent("shadow")
    assert shadow["interrupt_budget"] == 0
    assert shadow["proactive_triggers"] == []


def test_athena_is_learning_strategist_with_unified_tools():
    athena = get_agent("athena")

    assert athena["role"] == "学习策略师"
    assert "learning strategist" in athena["system_prompt"].lower()
    assert "Maxwell" in athena["system_prompt"]
    assert "jarvis_task_plan_decompose" in athena["tool_whitelist"]
    assert "jarvis_deadline_check" in athena["tool_whitelist"]
    assert "jarvis_local_life_search" in athena["tool_whitelist"]
    assert athena["interrupt_budget"] >= 1

def test_each_agent_has_required_fields():
    required = {"name", "role", "system_prompt", "color", "icon", "proactive_triggers", "interrupt_budget"}
    for agent_id, agent in JARVIS_AGENTS.items():
        missing = required - set(agent.keys())
        assert not missing, f"{agent_id} missing fields: {missing}"


def test_maxwell_knows_daily_plan_task_days_and_workbench():
    prompt = get_agent("maxwell")["system_prompt"]

    assert "daily_plan" in prompt
    assert "background_task_days" in prompt
    assert "workbench" in prompt
    assert "jarvis_task_plan_decompose" in prompt


def test_task_plan_tool_returns_one_daily_item_per_known_day():
    import asyncio

    result = asyncio.run(JarvisTaskPlanDecomposeTool()._arun(
        user_request="帮我安排 7 天雅思学习计划，每天晚上学习 1 小时",
        target_start="2026-05-01T20:00:00",
        target_end="2026-05-07T21:00:00",
    ))

    daily_plan = result["plan"]["daily_plan"]

    assert result["ok"] is True
    assert result["daily_plan_count"] == 7
    assert len(daily_plan) == 7
    assert daily_plan[0]["date"] == "2026-05-01"
    assert daily_plan[-1]["date"] == "2026-05-07"
    assert all(item["status"] == "pending" for item in daily_plan)


def test_task_plan_tool_infers_full_30_day_horizon():
    import asyncio

    result = asyncio.run(JarvisTaskPlanDecomposeTool()._arun(
        user_request="我要考雅思，未来的 30 天都帮我安排学习计划并写入日程",
        target_start="2026-05-01T20:00:00",
    ))

    daily_plan = result["plan"]["daily_plan"]

    assert result["ok"] is True
    assert result["daily_plan_count"] == 30
    assert len(daily_plan) == 30
    assert daily_plan[0]["date"] == "2026-05-01"
    assert daily_plan[-1]["date"] == "2026-05-30"
    assert JarvisTaskPlanDecomposeTool().requires_confirmation is False


def test_task_plan_tool_writes_schedule_through_secretary_service(monkeypatch):
    import asyncio
    import json

    class FakeLLM:
        async def chat(self, **kwargs):
            return json.dumps({
                "schema_version": "secretary_long_plan.v1",
                "intent": "long_plan",
                "plan": {
                    "title": "雅思 2 天备考计划",
                    "goal": "完成两天基础训练",
                    "plan_type": "long_term",
                    "start_date": "2026-05-01",
                    "target_date": "2026-05-02",
                },
                "days": [
                    {"day_index": 1, "date": "2026-05-01", "start_time": "20:00", "end_time": "21:00", "title": "雅思听力", "description": "听力训练", "estimated_minutes": 60, "reason": "启动"},
                    {"day_index": 2, "date": "2026-05-02", "start_time": "20:00", "end_time": "21:00", "title": "雅思阅读", "description": "阅读训练", "estimated_minutes": 60, "reason": "继续"},
                ],
            }, ensure_ascii=False)

    async def scenario():
        db_dir = Path("data") / "test_dbs"
        db_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(persistence, "_DB_PATH", db_dir / f"jarvis-agent-secretary-{uuid4().hex}.db")
        persistence._initialized = False
        previous_llm = get_resource("llm_client")
        set_resource("llm_client", FakeLLM())
        try:
            result = await JarvisTaskPlanDecomposeTool()._arun(
                user_request="我要考雅思，未来 2 天帮我安排学习计划并写入日程",
                target_start="2026-05-01T20:00:00",
            )
        finally:
            set_resource("llm_client", previous_llm)
        days = await persistence.list_jarvis_plan_days(plan_id=result["plan"]["id"], limit=10)
        return result, days

    result, days = asyncio.run(scenario())
    assert result["type"] == "task.plan"
    assert result["ok"] is True
    assert result["source"] == "secretary_planning_service"
    assert result["plan"]["title"] == "雅思 2 天备考计划"
    assert len(days) == 2
    assert days[0]["title"] == "雅思听力"


def test_calendar_upcoming_tool_accepts_explicit_time_window(monkeypatch):
    import asyncio
    from datetime import datetime

    async def scenario():
        monkeypatch.setattr(persistence, "_DB_PATH", Path("data") / "test_dbs" / f"jarvis-upcoming-{uuid4().hex}.db")
        persistence._initialized = False
        calendar_adapter._events.clear()
        calendar_adapter.add_event(
            "已有会议",
            datetime.fromisoformat("2026-05-02T14:30:00+08:00"),
            datetime.fromisoformat("2026-05-02T15:00:00+08:00"),
        )
        return await JarvisCalendarUpcomingTool()._arun(
            start="2026-05-02T14:00:00+08:00",
            end="2026-05-02T16:00:00+08:00",
        )

    result = asyncio.run(scenario())
    assert len(result) == 1
    assert result[0]["title"] == "已有会议"
