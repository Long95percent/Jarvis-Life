import asyncio
from datetime import date as Date, datetime, time as Time
from pathlib import Path
from uuid import uuid4

import pytest

from app.api.v1.jarvis_router import PsychologicalTrackingTogglePayload, clear_care_data, get_care_day_detail, get_care_trends, toggle_psychological_tracking
from app.jarvis import persistence
from app.jarvis.care_trends import build_care_day_detail, build_care_trends


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


def _save_snapshot(day: str, *, mood: float, stress: float, energy: float, pressure: float):
    return asyncio.run(persistence.upsert_mood_snapshot(
        date=day,
        mood_score=mood,
        stress_score=stress,
        energy_score=energy,
        sleep_risk_score=4.0,
        schedule_pressure_score=pressure,
        dominant_emotions=["focused"],
        positive_events=[],
        negative_events=[],
        risk_flags=["schedule_density_high"] if pressure >= 5 else [],
        summary=f"{day} 测试快照",
        confidence=0.7,
    ))


def test_care_trends_returns_week_series_and_day_details():
    _save_snapshot("2026-05-01", mood=6, stress=5, energy=7, pressure=4)
    _save_snapshot("2026-05-03", mood=4, stress=8, energy=3, pressure=8)
    asyncio.run(persistence.replace_stress_signals(
        date="2026-05-03",
        signals=[{
            "signal_type": "schedule_density_high",
            "severity": "high",
            "score": 8,
            "reason": "当天日程密度偏高。",
            "source_refs": [{"source": "calendar_events", "title": "会议"}],
        }],
    ))

    trends = asyncio.run(build_care_trends("week", end="2026-05-03"))

    assert trends["start"] == "2026-04-27"
    assert trends["end"] == "2026-05-03"
    assert len(trends["series"]) == 7
    last = trends["series"][-1]
    assert last["date"] == "2026-05-03"
    assert last["schedule_pressure_score"] == 8
    assert trends["details"]["2026-05-03"]["stress_signals"][0]["reason"] == "当天日程密度偏高。"
    assert trends["details"]["2026-05-03"]["explanations"]


def test_care_trends_router_uses_snapshot_data():
    _save_snapshot("2026-05-10", mood=7, stress=3, energy=8, pressure=2)

    trends = asyncio.run(get_care_trends(range="week", end="2026-05-10"))

    assert trends["series"][-1]["mood_score"] == 7
    assert trends["details"]["2026-05-10"]["snapshot"]["summary"] == "2026-05-10 测试快照"


def test_tracking_toggle_disables_trend_data():
    _save_snapshot("2026-05-11", mood=7, stress=3, energy=8, pressure=2)

    toggle = asyncio.run(toggle_psychological_tracking(PsychologicalTrackingTogglePayload(enabled=False)))
    trends = asyncio.run(get_care_trends(range="week", end="2026-05-11"))

    assert toggle["psychological_tracking_enabled"] is False
    assert trends["tracking_enabled"] is False
    assert trends["series"][-1]["mood_score"] is None
    assert trends["details"]["2026-05-11"]["explanations"] == ["心理趋势追踪已关闭。"]


def test_care_day_detail_explains_pressure_energy_and_care_trigger():
    day = "2026-05-13"
    asyncio.run(persistence.save_emotion_observation(
        session_id="s-detail",
        agent_id="mira",
        primary_emotion="tired",
        secondary_emotions=["stressed"],
        valence=-0.5,
        arousal=0.7,
        stress_score=8,
        fatigue_score=8,
        risk_level="medium",
        confidence=0.8,
        evidence_summary="用户表达疲惫和压力偏高",
        signals=["low_energy", "stress_signal"],
        source="test",
        created_at=datetime.combine(Date.fromisoformat(day), Time(hour=12)).timestamp(),
    ))
    asyncio.run(persistence.save_behavior_observation(
        date=day,
        session_id="s-detail",
        agent_id="mira",
        observation_type="beyond_bedtime",
        expected_bedtime="23:00",
        expected_wake="07:00",
        deviation_minutes=90,
        source="test",
    ))
    asyncio.run(persistence.replace_stress_signals(
        date=day,
        signals=[{
            "signal_type": "task_load_high",
            "severity": "high",
            "score": 8,
            "reason": "当天任务密度偏高且休息窗口不足",
            "source_refs": [{"source": "jarvis_plan_days"}],
        }],
        source="test",
    ))
    asyncio.run(persistence.upsert_mood_snapshot(
        date=day,
        mood_score=3,
        stress_score=8,
        energy_score=2,
        sleep_risk_score=8,
        schedule_pressure_score=8,
        dominant_emotions=["tired"],
        positive_events=["完成任务：复盘材料"],
        negative_events=["用户表达疲惫和压力偏高"],
        risk_flags=["stress_high", "beyond_bedtime"],
        summary="当天压力高、能量低，且存在晚睡信号。",
        confidence=0.85,
    ))
    asyncio.run(persistence.save_care_trigger_and_intervention(
        trigger_type="task_overload",
        severity="high",
        reason="当天任务密度偏高且休息窗口不足",
        evidence_ids=[{"source": "jarvis_stress_signals", "date": day}],
        content="建议先减少今晚任务负载。",
    ))

    detail = asyncio.run(build_care_day_detail(day))

    assert detail["snapshot"]["stress_score"] == 8
    assert len(detail["emotion_observations"]) == 1
    assert len(detail["behavior_observations"]) == 1
    assert len(detail["stress_signals"]) == 1
    assert len(detail["care_triggers"]) == 1
    joined = "\n".join(detail["explanations"])
    assert "任务/日程压力" in joined
    assert "作息信号" in joined
    assert "低能量表达" in joined
    assert "关怀触发" in joined
    assert "正向来源" in joined


def test_care_day_detail_router_hides_data_when_tracking_disabled():
    _save_snapshot("2026-05-14", mood=7, stress=3, energy=8, pressure=2)

    asyncio.run(toggle_psychological_tracking(PsychologicalTrackingTogglePayload(enabled=False)))
    detail = asyncio.run(get_care_day_detail("2026-05-14"))

    assert detail["emotion_observations"] == []
    assert detail["stress_signals"] == []
    assert detail["behavior_observations"] == []
    assert detail["care_triggers"] == []
    assert detail["explanations"] == ["心理趋势追踪已关闭。"]


def test_clear_care_data_deletes_snapshots_and_signals():
    _save_snapshot("2026-05-12", mood=5, stress=7, energy=4, pressure=8)
    asyncio.run(persistence.save_behavior_observation(
        date="2026-05-12",
        session_id="s-clear",
        agent_id="mira",
        observation_type="late_night_usage",
        expected_bedtime="23:00",
        expected_wake="07:00",
    ))
    asyncio.run(persistence.replace_stress_signals(
        date="2026-05-12",
        signals=[{"signal_type": "task_load_high", "severity": "high", "score": 8, "reason": "任务过多", "source_refs": [{"source": "test"}]}],
    ))

    result = asyncio.run(clear_care_data())
    trends = asyncio.run(get_care_trends(range="week", end="2026-05-12"))

    assert result["deleted"]["jarvis_mood_snapshots"] == 1
    assert result["deleted"]["jarvis_behavior_observations"] == 1
    assert result["deleted"]["jarvis_stress_signals"] == 1
    assert trends["series"][-1]["mood_score"] is None
