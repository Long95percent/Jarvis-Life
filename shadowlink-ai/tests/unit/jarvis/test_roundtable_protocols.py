from pathlib import Path

from app.jarvis.roundtable_protocols import get_roundtable_protocol


EXPECTED_PHASES = {
    "schedule_coord": ["context_scan", "conflict_check", "role_proposal", "crossfire", "alfred_decision"],
    "study_energy_decision": ["energy_gate", "task_value_check", "minimum_viable_study", "crossfire", "decision"],
    "local_lifestyle": ["collect_constraints", "discover_candidates", "enrich_candidates", "feasibility_score", "energy_filter", "rank_options", "plan_candidate"],
    "emotional_care": ["safety_check", "emotional_validation", "body_support", "low_stimulation_options", "care_summary"],
    "weekend_recharge": ["recovery_goal", "available_blocks", "activity_rest_balance", "crossfire", "weekend_rhythm"],
    "work_brainstorm": ["frame_problem", "ingest_context", "divergent_ideas", "cluster_ideas", "critic_review", "synthesis", "validation_plan"],
}


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
    assert protocol.phases[4].id == "critic_review"
    assert protocol.phases[-1].id == "validation_plan"
    assert protocol.handoff_target == "maxwell"


def test_all_scenario_phase_sequences_are_specialized():
    for scenario_id, expected_phases in EXPECTED_PHASES.items():
        protocol = get_roundtable_protocol(scenario_id)

        assert [phase.id for phase in protocol.phases] == expected_phases


def test_protocol_modes_handoffs_and_write_boundaries_are_stable():
    expected = {
        "schedule_coord": ("decision", "maxwell", "pending_confirmation_only"),
        "study_energy_decision": ("decision", "maxwell", "pending_confirmation_only"),
        "local_lifestyle": ("brainstorm", "maxwell", "optional_pending_confirmation"),
        "emotional_care": ("brainstorm", "mira", "no_direct_write"),
        "weekend_recharge": ("brainstorm", "maxwell", "optional_pending_confirmation"),
        "work_brainstorm": ("brainstorm", "maxwell", "no_direct_write"),
    }

    for scenario_id, (mode, handoff_target, write_mode) in expected.items():
        protocol = get_roundtable_protocol(scenario_id)

        assert protocol.mode == mode
        assert protocol.handoff_target == handoff_target
        assert protocol.tool_policy["write_mode"] == write_mode


def test_protocol_result_contracts_match_roundtable_modes():
    for scenario_id in EXPECTED_PHASES:
        protocol = get_roundtable_protocol(scenario_id)
        fields = protocol.result_contract["fields"]

        if protocol.mode == "decision":
            assert "recommended_option" in fields
            assert "actions" in fields
        else:
            assert "themes" in fields
            assert "ideas" in fields


def test_protocols_expose_scenario_specific_result_semantics():
    expected_semantic_fields = {
        "schedule_coord": "calendar_adjustment_candidates",
        "study_energy_decision": "minimum_study_block",
        "local_lifestyle": "ranked_activities",
        "emotional_care": "low_barrier_actions",
        "weekend_recharge": "weekend_rhythm",
        "work_brainstorm": "minimum_validation_steps",
    }

    for scenario_id, semantic_field in expected_semantic_fields.items():
        protocol = get_roundtable_protocol(scenario_id)

        assert semantic_field in protocol.result_contract["semantic_fields"]


def test_roundtable_contract_documents_scenario_protocols():
    repo_root = Path(__file__).resolve().parents[4]
    contract = (repo_root / "docs" / "解耦接口说明" / "roundtable-api-contract.md").read_text(encoding="utf-8")

    assert "ScenarioProtocol" in contract
    assert "crossfire" in contract
    assert "context_scan -> conflict_check -> role_proposal -> crossfire -> alfred_decision" in contract
