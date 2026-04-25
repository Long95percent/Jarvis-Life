from app.jarvis.scenarios import JARVIS_SCENARIOS, get_scenario, list_scenarios


def test_five_scenarios_defined():
    assert len(JARVIS_SCENARIOS) == 5


def test_scenario_ids_unique():
    ids = [s.id for s in JARVIS_SCENARIOS.values()]
    assert len(ids) == len(set(ids))


def test_jarvis_scenarios_reference_valid_agents():
    from app.jarvis.agents import JARVIS_AGENTS
    for s in JARVIS_SCENARIOS.values():
        if s.agent_roster == "jarvis":
            for agent_id in s.agents:
                assert agent_id in JARVIS_AGENTS, f"{s.id} uses unknown agent {agent_id}"


def test_get_scenario_raises_for_unknown():
    import pytest
    with pytest.raises(KeyError):
        get_scenario("nonexistent")


def test_list_scenarios_returns_dicts():
    items = list_scenarios()
    assert len(items) == 5
    assert all(isinstance(i, dict) for i in items)
    assert all("id" in i and "name" in i and "agents" in i for i in items)
