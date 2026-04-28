import asyncio
from pathlib import Path
from uuid import uuid4

import pytest

from app.api.v1.jarvis_router import CareFeedbackRequest, care_message_feedback_endpoint
from app.jarvis import persistence
from app.jarvis.care_triggers import evaluate_care_triggers
from app.jarvis.models import LifeContext
from app.jarvis.proactive_routines import ProactiveRoutineScheduler


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    db_dir = Path("data") / "test_dbs"
    db_dir.mkdir(parents=True, exist_ok=True)
    tmp = db_dir / f"jarvis-{uuid4().hex}.db"
    monkeypatch.setattr(persistence, "_DB_PATH", tmp)
    persistence._initialized = False
    from app.jarvis import user_settings
    monkeypatch.setattr(user_settings, "_SETTINGS_FILE", db_dir / f"settings-{uuid4().hex}.json")
    user_settings._cached = None
    yield tmp
    persistence._initialized = False
    user_settings._cached = None


def _snapshot(day: str, *, stress: float = 8, risk_flags: list[str] | None = None):
    return asyncio.run(persistence.upsert_mood_snapshot(
        date=day,
        mood_score=4,
        stress_score=stress,
        energy_score=3,
        sleep_risk_score=6,
        schedule_pressure_score=8,
        dominant_emotions=["stressed"],
        positive_events=[],
        negative_events=[],
        risk_flags=risk_flags or [],
        summary=f"{day} high stress",
        confidence=0.8,
    ))


def test_task_overload_generates_care_trigger_with_message_and_evidence():
    day = "2026-05-20"
    _snapshot(day)
    asyncio.run(persistence.replace_stress_signals(
        date=day,
        signals=[{"signal_type": "task_load_high", "severity": "high", "score": 8, "reason": "当天任务过多。", "source_refs": [{"source": "background_task_days", "id": "d1"}]}],
    ))

    results = asyncio.run(evaluate_care_triggers(day))

    assert len(results) == 1
    assert results[0]["trigger"]["trigger_type"] == "task_overload"
    assert results[0]["trigger"]["evidence_ids"]
    assert results[0]["message"]["trigger"] == "task_overload"


def test_daily_budget_prevents_unlimited_repeated_care_messages():
    day = "2026-05-21"
    _snapshot(day, risk_flags=["high_risk_observation"])
    asyncio.run(persistence.replace_stress_signals(
        date=day,
        signals=[{"signal_type": "task_load_high", "severity": "high", "score": 9, "reason": "任务爆满。", "source_refs": [{"source": "test"}]}],
    ))

    first = asyncio.run(evaluate_care_triggers(day))
    second = asyncio.run(evaluate_care_triggers(day))

    assert first
    assert second == []


def test_too_frequent_feedback_reduces_daily_budget():
    day = "2026-05-22"
    _snapshot(day, risk_flags=["high_risk_observation"])
    first = asyncio.run(evaluate_care_triggers(day))
    message_id = first[0]["message"]["id"]
    asyncio.run(care_message_feedback_endpoint(message_id, CareFeedbackRequest(feedback="too_frequent")))

    next_day = "2026-05-23"
    _snapshot(next_day, risk_flags=["high_risk_observation"])
    asyncio.run(persistence.replace_stress_signals(
        date=next_day,
        signals=[{"signal_type": "task_load_high", "severity": "high", "score": 9, "reason": "任务爆满。", "source_refs": [{"source": "test"}]}],
    ))
    results = asyncio.run(evaluate_care_triggers(next_day))

    assert len(results) == 1


def test_high_risk_copy_uses_safety_boundary_not_diagnosis():
    day = "2026-05-24"
    _snapshot(day, risk_flags=["high_risk_observation"])

    results = asyncio.run(evaluate_care_triggers(day))
    content = results[0]["message"]["content"]

    assert "不会给你做诊断" in content
    assert "可信任的人" in content
    assert "紧急求助渠道" in content
    assert "你得了" not in content


def test_snooze_feedback_hides_message_until_later():
    day = "2026-05-25"
    _snapshot(day, risk_flags=["high_risk_observation"])
    result = asyncio.run(evaluate_care_triggers(day))[0]
    message_id = result["message"]["id"]

    feedback = asyncio.run(care_message_feedback_endpoint(message_id, CareFeedbackRequest(feedback="snooze", snooze_minutes=120)))
    visible = asyncio.run(persistence.list_proactive_messages(include_read=True))

    assert feedback["intervention"]["status"] == "snoozed"
    assert visible == []


def test_routine_automatically_runs_care_triggers(monkeypatch):
    day = "2026-05-26"
    _snapshot(day, risk_flags=["high_risk_observation"])
    scheduler = ProactiveRoutineScheduler()
    now = __import__("datetime").datetime.fromisoformat(f"{day}T14:00:00")
    ctx = LifeContext(last_updated=now, source_agent="system")
    monkeypatch.setattr("app.jarvis.user_settings.get_enabled_agents", lambda agent_ids=None: [])

    results = asyncio.run(scheduler.check_routines(ctx, now=now))

    care_results = [item for item in results if item.get("routine_id") == "care_trigger"]
    assert len(care_results) == 1
    assert care_results[0]["result"]["trigger"]["trigger_type"] == "high_risk_keyword"


def test_negative_feedback_extends_cooldown_for_same_trigger_type():
    day = "2026-05-27"
    _snapshot(day)
    asyncio.run(persistence.replace_stress_signals(
        date=day,
        signals=[{"signal_type": "task_load_high", "severity": "high", "score": 9, "reason": "overload", "source_refs": [{"source": "test"}]}],
    ))
    first = asyncio.run(evaluate_care_triggers(day))
    asyncio.run(care_message_feedback_endpoint(first[0]["message"]["id"], CareFeedbackRequest(feedback="not_needed")))

    next_day = "2026-05-28"
    _snapshot(next_day)
    asyncio.run(persistence.replace_stress_signals(
        date=next_day,
        signals=[{"signal_type": "task_load_high", "severity": "high", "score": 9, "reason": "overload again", "source_refs": [{"source": "test"}]}],
    ))

    assert asyncio.run(evaluate_care_triggers(next_day)) == []
