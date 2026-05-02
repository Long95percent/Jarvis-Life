from app.jarvis.roundtable_protocols import get_roundtable_protocol


def test_all_roundtable_scenarios_have_protocols():
    scenarios = [
        "schedule_coord",
        "study_energy_decision",
        "local_lifestyle",
        "emotional_care",
        "weekend_recharge",
        "work_brainstorm",
    ]

    protocols = [get_roundtable_protocol(scenario_id) for scenario_id in scenarios]

    assert [protocol.scenario_id for protocol in protocols] == scenarios
    assert [protocol.mode for protocol in protocols] == [
        "decision",
        "decision",
        "brainstorm",
        "brainstorm",
        "brainstorm",
        "brainstorm",
    ]


def test_schedule_coord_protocol_is_conflict_first():
    protocol = get_roundtable_protocol("schedule_coord")

    assert protocol.phases[0].id == "context_scan"
    assert protocol.phases[1].id == "conflict_check"
    assert protocol.phases[-1].id == "alfred_decision"
    assert protocol.handoff_target == "maxwell"


def test_work_brainstorm_protocol_is_workshop_style():
    protocol = get_roundtable_protocol("work_brainstorm")

    assert protocol.phases[0].id == "frame_problem"
    assert protocol.phases[2].id == "critic_review"
    assert protocol.phases[-1].id == "validation_plan"
    assert protocol.handoff_target == "maxwell"
