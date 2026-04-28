import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from app.api.v1.jarvis_router import list_care_stress_signals
from app.jarvis import persistence
from app.jarvis.mood_snapshot import aggregate_mood_snapshot
from app.jarvis.stress_observation import aggregate_schedule_pressure_signals
from app.mcp.adapters import calendar_adapter


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    db_dir = Path("data") / "test_dbs"
    db_dir.mkdir(parents=True, exist_ok=True)
    tmp = db_dir / f"jarvis-{uuid4().hex}.db"
    monkeypatch.setattr(persistence, "_DB_PATH", tmp)
    persistence._initialized = False
    calendar_adapter._events.clear()
    yield tmp
    calendar_adapter._events.clear()
    persistence._initialized = False


def _add_heavy_calendar_day(day: str):
    base = datetime.fromisoformat(f"{day}T09:00:00")
    for index in range(4):
        start = base + timedelta(hours=index * 2)
        calendar_adapter.add_event(
            title=f"高压日程 {index + 1}",
            start=start,
            end=start + timedelta(minutes=75),
            stress_weight=1.4,
        )
    calendar_adapter.add_event(
        title="晚间复盘",
        start=datetime.fromisoformat(f"{day}T20:30:00"),
        end=datetime.fromisoformat(f"{day}T22:00:00"),
        stress_weight=1.2,
    )


async def _add_task_load(day: str):
    await persistence.save_background_task(
        task_id="task-pressure",
        title="压力测试任务",
        task_type="long_project",
        source_agent="maxwell",
        original_user_request="安排很多任务",
        goal="测试压力观测",
        time_horizon={"target_date": day},
        milestones=[],
        subtasks=[],
        calendar_candidates=[],
    )
    days = await persistence.save_background_task_days(
        task_id="task-pressure",
        daily_plan=[
            {"date": day, "title": f"任务 {index}", "estimated_minutes": 60}
            for index in range(5)
        ],
    )
    await persistence.update_background_task_day_status(days[0]["id"], "missed")
    await persistence.push_background_task_days_to_workbench(plan_date=day)


def test_schedule_pressure_signals_are_explainable():
    day = "2026-05-03"
    _add_heavy_calendar_day(day)
    asyncio.run(_add_task_load(day))

    signals = asyncio.run(aggregate_schedule_pressure_signals(day))

    types = {item["signal_type"] for item in signals}
    assert "schedule_density_high" in types
    assert "task_load_high" in types
    assert "missed_tasks" in types
    assert all(item["reason"] for item in signals)
    assert all(item["source_refs"] for item in signals)


def test_stress_signal_debug_api_can_refresh_and_query():
    day = "2026-05-04"
    _add_heavy_calendar_day(day)

    refreshed = asyncio.run(list_care_stress_signals(date=day, refresh=True))
    listed = asyncio.run(list_care_stress_signals(date=day))

    assert refreshed
    assert listed
    assert listed[0]["date"] == day


def test_stress_signals_enter_daily_mood_snapshot():
    day = "2026-05-05"
    _add_heavy_calendar_day(day)
    asyncio.run(_add_task_load(day))

    snapshot = asyncio.run(aggregate_mood_snapshot(day))

    assert snapshot is not None
    assert snapshot["schedule_pressure_score"] >= 5
    assert "schedule_density_high" in snapshot["risk_flags"]
    assert "压力 signal" in snapshot["summary"]
