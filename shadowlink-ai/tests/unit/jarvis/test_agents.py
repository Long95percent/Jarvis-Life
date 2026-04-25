from app.jarvis.agents import JARVIS_AGENTS, get_agent

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
