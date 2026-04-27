import pytest

from app.jarvis.agents import JARVIS_AGENTS, get_agent
from app.tools.jarvis_tools import JarvisTaskPlanDecomposeTool

def test_all_six_agents_defined():
    expected = {"alfred", "maxwell", "nora", "mira", "leo", "shadow"}
    assert set(JARVIS_AGENTS.keys()) == expected

def test_alfred_is_chief_coordinator():
    alfred = get_agent("alfred")
    assert alfred["role"] == "总管家"
    assert "schedule" in alfred["system_prompt"].lower() or "coordinator" in alfred["system_prompt"].lower()

def test_shadow_has_zero_interrupt_budget():
    shadow = get_agent("shadow")
    assert shadow["interrupt_budget"] == 0
    assert shadow["proactive_triggers"] == []

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


@pytest.mark.asyncio
async def test_task_plan_tool_returns_one_daily_item_per_known_day():
    result = await JarvisTaskPlanDecomposeTool()._arun(
        user_request="帮我安排 7 天雅思学习计划，每天晚上学习 1 小时",
        target_start="2026-05-01T20:00:00",
        target_end="2026-05-07T21:00:00",
    )

    daily_plan = result["plan"]["daily_plan"]

    assert result["ok"] is True
    assert result["daily_plan_count"] == 7
    assert len(daily_plan) == 7
    assert daily_plan[0]["date"] == "2026-05-01"
    assert daily_plan[-1]["date"] == "2026-05-07"
    assert all(item["status"] == "pending" for item in daily_plan)
