from app.jarvis.escalation import evaluate_escalation
from app.jarvis.models import LifeContext


def _ctx(**overrides):
    return LifeContext(**{**{"stress_level": 0, "schedule_density": 0, "mood_trend": "neutral"}, **overrides})


def test_high_stress_keyword_triggers_urgent_emotional_care():
    hint = evaluate_escalation(
        user_message="我最近压力特别大",
        agent_id="mira",
        context=_ctx(stress_level=8.5),
    )
    assert hint is not None
    assert hint.scenario_id == "emotional_care"
    assert hint.severity == "urgent"


def test_moderate_stress_is_suggest_not_urgent():
    hint = evaluate_escalation(
        user_message="我有点焦虑",
        agent_id="mira",
        context=_ctx(stress_level=5.0),
    )
    assert hint is not None
    assert hint.severity == "suggest"


def test_schedule_keyword_with_high_density_urgent():
    hint = evaluate_escalation(
        user_message="明天的会议我怎么安排啊",
        agent_id="maxwell",
        context=_ctx(schedule_density=8.0),
    )
    assert hint is not None
    assert hint.scenario_id == "schedule_coord"
    assert hint.severity == "urgent"


def test_neutral_chat_no_escalation():
    hint = evaluate_escalation(
        user_message="你好呀",
        agent_id="alfred",
        context=_ctx(),
    )
    assert hint is None


def test_weekend_keyword_suggests_recharge():
    hint = evaluate_escalation(
        user_message="周末想放松一下",
        agent_id="leo",
        context=_ctx(),
    )
    assert hint is not None
    assert hint.scenario_id == "weekend_recharge"


def test_lifestyle_keyword_suggests_local():
    hint = evaluate_escalation(
        user_message="今晚吃什么好呢",
        agent_id="nora",
        context=_ctx(),
    )
    assert hint is not None
    assert hint.scenario_id == "local_lifestyle"
