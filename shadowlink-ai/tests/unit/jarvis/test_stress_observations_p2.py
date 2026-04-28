import asyncio
from pathlib import Path
from uuid import uuid4

import pytest

from app.jarvis import persistence
from app.jarvis.stress_observation import aggregate_schedule_pressure_signals


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    db_dir = Path("data") / "test_dbs"
    db_dir.mkdir(parents=True, exist_ok=True)
    tmp = db_dir / f"jarvis-{uuid4().hex}.db"
    monkeypatch.setattr(persistence, "_DB_PATH", tmp)
    persistence._initialized = False
    yield tmp
    persistence._initialized = False


def test_plan_reschedule_events_become_pressure_signal():
    day = "2026-05-06"
    asyncio.run(persistence.record_agent_event(
        event_type="plan.rescheduled",
        agent_id="maxwell",
        plan_id="plan-pressure",
        plan_day_id="day-pressure",
        payload={"today": day, "reason": "missed day auto reschedule", "changed_count": 2},
    ))

    signals = asyncio.run(aggregate_schedule_pressure_signals(day))

    signal = next(item for item in signals if item["signal_type"] == "plan_reschedule_pressure")
    assert signal["score"] >= 5
    assert signal["source_refs"][0]["source"] == "jarvis_agent_events"


def test_continuous_high_pressure_streak_becomes_signal():
    for day in ["2026-05-07", "2026-05-08", "2026-05-09"]:
        asyncio.run(persistence.upsert_mood_snapshot(
            date=day,
            mood_score=4,
            stress_score=7.5,
            energy_score=3,
            sleep_risk_score=5,
            schedule_pressure_score=7.2,
            dominant_emotions=["stressed"],
            positive_events=[],
            negative_events=["压力偏高"],
            risk_flags=["stress_high"],
            summary=f"{day} 压力偏高",
            confidence=0.8,
        ))

    signals = asyncio.run(aggregate_schedule_pressure_signals("2026-05-09"))

    signal = next(item for item in signals if item["signal_type"] == "continuous_high_pressure")
    assert "连续 3 天" in signal["reason"]
    assert [item["date"] for item in signal["source_refs"]] == ["2026-05-07", "2026-05-08", "2026-05-09"]
