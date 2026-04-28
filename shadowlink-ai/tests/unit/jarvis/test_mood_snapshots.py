import asyncio
from datetime import date as Date, datetime, time as Time
from pathlib import Path
from uuid import uuid4

import pytest

from app.jarvis import persistence
from app.jarvis.mood_snapshot import aggregate_mood_snapshot
from app.jarvis.mood_snapshot_maintenance import ensure_mood_snapshots


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    db_dir = Path("data") / "test_dbs"
    db_dir.mkdir(parents=True, exist_ok=True)
    tmp = db_dir / f"jarvis-{uuid4().hex}.db"
    monkeypatch.setattr(persistence, "_DB_PATH", tmp)
    persistence._initialized = False
    yield tmp
    persistence._initialized = False


def _save_observation(day: str, *, primary: str, risk: str, stress: float, fatigue: float, valence: float, signals: list[str] | None = None):
    return asyncio.run(persistence.save_emotion_observation(
        session_id=f"s-{day}",
        agent_id="mira",
        primary_emotion=primary,
        secondary_emotions=signals or [],
        valence=valence,
        arousal=0.6,
        stress_score=stress,
        fatigue_score=fatigue,
        risk_level=risk,
        confidence=0.7,
        evidence_summary="测试摘要",
        signals=signals or [],
        source="test",
        created_at=datetime.combine(Date.fromisoformat(day), Time(hour=12)).timestamp(),
    ))


def test_aggregate_multiple_emotion_observations_into_daily_snapshot():
    day = "2026-04-28"
    _save_observation(day, primary="tired", risk="medium", stress=7, fatigue=8, valence=-0.5, signals=["low_energy"])
    _save_observation(day, primary="stressed", risk="medium", stress=8, fatigue=5, valence=-0.4, signals=["stress_signal"])

    snapshot = asyncio.run(aggregate_mood_snapshot(day))

    assert snapshot is not None
    assert snapshot["date"] == day
    assert snapshot["stress_score"] >= 7
    assert snapshot["energy_score"] < 5
    assert "tired" in snapshot["dominant_emotions"]
    assert "repeated_medium_risk" in snapshot["risk_flags"]


def test_no_data_day_does_not_generate_misleading_snapshot():
    snapshot = asyncio.run(aggregate_mood_snapshot("2026-04-29"))

    assert snapshot is None
    assert asyncio.run(persistence.list_mood_snapshots(start="2026-04-29", end="2026-04-29")) == []


def test_high_risk_observation_enters_risk_flags():
    day = "2026-04-30"
    _save_observation(day, primary="crisis_signal", risk="high", stress=9, fatigue=8, valence=-0.8, signals=["safety_risk_signal"])

    snapshot = asyncio.run(aggregate_mood_snapshot(day))

    assert snapshot is not None
    assert "high_risk_observation" in snapshot["risk_flags"]
    assert snapshot["mood_score"] < 3
    assert snapshot["confidence"] > 0


def test_behavior_observations_enter_daily_snapshot_sleep_risk():
    day = "2026-05-01"
    asyncio.run(persistence.save_behavior_observation(
        date=day,
        session_id="s-behavior-snapshot",
        agent_id="mira",
        observation_type="beyond_bedtime",
        expected_bedtime="23:00",
        expected_wake="07:00",
        actual_last_active_at=datetime.combine(Date.fromisoformat(day), Time(hour=23, minute=45)).timestamp(),
        deviation_minutes=45,
        source="test",
    ))

    snapshot = asyncio.run(aggregate_mood_snapshot(day))

    assert snapshot is not None
    assert snapshot["sleep_risk_score"] == 8.0
    assert "beyond_bedtime" in snapshot["risk_flags"]
    assert "1 条行为 observation" in snapshot["summary"]


def test_positive_sources_enter_daily_snapshot_events():
    day = "2026-05-02"
    _save_observation(day, primary="happy", risk="low", stress=2, fatigue=2, valence=0.7, signals=["positive_mood"])
    asyncio.run(persistence.save_behavior_observation(
        date=day,
        session_id="s-rest-snapshot",
        agent_id="mira",
        observation_type="on_time_rest",
        expected_bedtime="23:00",
        expected_wake="07:00",
        source="test",
    ))
    asyncio.run(persistence.replace_stress_signals(
        date=day,
        signals=[{
            "signal_type": "workload_reduced",
            "severity": "low",
            "score": 1,
            "reason": "用户减少了今晚任务负载",
        }],
        source="test",
    ))
    asyncio.run(persistence.save_background_task(
        task_id="task-positive-snapshot",
        title="路演准备",
        task_type="project",
        source_agent="maxwell",
        original_user_request="帮我安排路演准备",
    ))
    days = asyncio.run(persistence.save_background_task_days(
        task_id="task-positive-snapshot",
        daily_plan=[{"date": day, "title": "完成路演讲稿", "estimated_minutes": 45}],
    ))
    asyncio.run(persistence.update_background_task_day_status(days[0]["id"], "completed"))

    snapshot = asyncio.run(aggregate_mood_snapshot(day))

    assert snapshot is not None
    assert any("完成任务：完成路演讲稿" in item for item in snapshot["positive_events"])
    assert any("表达积极情绪" in item for item in snapshot["positive_events"])
    assert any("按时休息" in item for item in snapshot["positive_events"])
    assert any("减少任务负载" in item for item in snapshot["positive_events"])
    assert "正向事件" in snapshot["summary"]


def test_ensure_mood_snapshots_backfills_missing_days_and_refreshes_today(monkeypatch):
    yesterday = "2026-05-03"
    today = "2026-05-04"
    _save_observation(yesterday, primary="stressed", risk="medium", stress=7, fatigue=6, valence=-0.4)
    _save_observation(today, primary="relaxed", risk="low", stress=2, fatigue=2, valence=0.6)

    monkeypatch.setattr("app.jarvis.user_settings.is_psychological_tracking_enabled", lambda: True)
    result = asyncio.run(ensure_mood_snapshots(today=today, backfill_days=2, include_today=True))

    assert result["skipped"] is False
    assert result["checked"] == [yesterday, today]
    assert [item["date"] for item in result["created"]] == [yesterday, today]
    snapshots = asyncio.run(persistence.list_mood_snapshots(start=yesterday, end=today))
    assert {item["date"] for item in snapshots} == {yesterday, today}


def test_ensure_mood_snapshots_skips_existing_past_day_but_refreshes_today(monkeypatch):
    yesterday = "2026-05-05"
    today = "2026-05-06"
    _save_observation(yesterday, primary="tired", risk="medium", stress=6, fatigue=7, valence=-0.4)
    _save_observation(today, primary="calm", risk="low", stress=2, fatigue=2, valence=0.5)
    asyncio.run(aggregate_mood_snapshot(yesterday))

    monkeypatch.setattr("app.jarvis.user_settings.is_psychological_tracking_enabled", lambda: True)
    result = asyncio.run(ensure_mood_snapshots(today=today, backfill_days=2, include_today=True))

    assert result["checked"] == [yesterday, today]
    assert [item["date"] for item in result["created"]] == [today]


def test_ensure_mood_snapshots_respects_tracking_switch(monkeypatch):
    monkeypatch.setattr("app.jarvis.user_settings.is_psychological_tracking_enabled", lambda: False)

    result = asyncio.run(ensure_mood_snapshots(today="2026-05-07", backfill_days=2, include_today=True))

    assert result == {"skipped": True, "reason": "psychological_tracking_disabled", "created": [], "checked": []}

