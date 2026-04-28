import asyncio
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest

from app.api.v1.jarvis_router import (
    CalendarEventRequest,
    PendingActionConfirmRequest,
    PlanDayMoveRequest,
    add_calendar_event,
    cancel_plan_item,
    complete_plan_day_item,
    confirm_pending_action_item,
    list_planner_calendar_items,
    move_plan_day_item,
    project_plan_calendar_items,
    push_maxwell_daily_tasks,
    mark_overdue_planner_day_items,
    list_maxwell_workbench_items,
    PlanRescheduleRequest,
    reschedule_plan_days,
)
from app.jarvis import persistence
from app.jarvis.stress_observation import aggregate_schedule_pressure_signals
from app.jarvis.planner_maintenance import run_planner_daily_maintenance, run_planner_daily_maintenance_once
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


def test_task_plan_confirmation_writes_unified_plan_days():
    async def scenario():
        await persistence.save_pending_action(
            pending_id="pending-plan-unified",
            action_type="task.plan",
            tool_name="jarvis_task_plan_decompose",
            agent_id="maxwell",
            session_id="session-plan",
            title="30 ???????",
            arguments={
                "plan": {
                    "id": "task-ielts-30",
                    "title": "30 ???????",
                    "type": "long_project",
                    "source_agent": "maxwell",
                    "original_user_request": "???? 30 ???????",
                    "goal": "??????????",
                    "time_horizon": {"start_after": "2026-05-01", "target_date": "2026-05-30"},
                    "daily_plan": [
                        {"date": "2026-05-01", "title": "????", "start_time": "20:00", "end_time": "21:00", "estimated_minutes": 60},
                        {"date": "2026-05-02", "title": "????", "start_time": "20:00", "end_time": "21:00", "estimated_minutes": 60},
                    ],
                }
            },
        )
        response = await confirm_pending_action_item("pending-plan-unified", PendingActionConfirmRequest())
        plans = await persistence.list_jarvis_plans(limit=10)
        days = await persistence.list_jarvis_plan_days(plan_id=response["result"]["plan"]["id"], limit=10)
        return response, plans, days

    response, plans, days = asyncio.run(scenario())
    assert response["result"]["task_day_count"] == 2
    assert response["result"]["plan_day_count"] == 2
    assert plans[0]["source_background_task_id"] == "task-ielts-30"
    assert plans[0]["plan_type"] == "long_term"
    assert [day["title"] for day in days] == ["????", "????"]
    assert all(day["source_task_day_id"] for day in days)


def test_manual_calendar_event_creates_short_term_plan_day_and_calendar_items():
    async def scenario():
        result = await add_calendar_event(CalendarEventRequest(
            title="??????",
            start=datetime.fromisoformat("2026-05-03T15:00:00"),
            end=datetime.fromisoformat("2026-05-03T16:00:00"),
            source="user_ui",
            created_reason="????????",
        ))
        items = await list_planner_calendar_items(
            start=datetime.fromisoformat("2026-05-03T00:00:00"),
            end=datetime.fromisoformat("2026-05-04T00:00:00"),
        )
        return result, items

    result, items = asyncio.run(scenario())
    plan_day = result["plan_day"]
    assert plan_day["title"] == "??????"
    assert plan_day["calendar_event_id"] == result["event_id"]
    assert {item["item_type"] for item in items["items"]} >= {"calendar_event", "plan_day"}


def test_plan_day_move_complete_and_cancel_sync_calendar_event():
    async def scenario():
        created = await add_calendar_event(CalendarEventRequest(
            title="????",
            start=datetime.fromisoformat("2026-05-04T19:00:00"),
            end=datetime.fromisoformat("2026-05-04T20:00:00"),
            source="user_ui",
            created_reason="????????",
        ))
        day_id = created["plan_day"]["id"]
        event_id = created["event_id"]
        moved = await move_plan_day_item(day_id, PlanDayMoveRequest(plan_date="2026-05-05", start_time="20:00", end_time="21:00", reason="??????"))
        completed = await complete_plan_day_item(day_id)
        cancelled = await cancel_plan_item(created["plan_day"]["plan_id"])
        return event_id, moved, completed, cancelled

    event_id, moved, completed, cancelled = asyncio.run(scenario())
    event = calendar_adapter.get_event(event_id)
    assert moved["plan_day"]["status"] == "rescheduled"
    assert event is not None
    assert event.start.isoformat().startswith("2026-05-05T20:00")
    assert completed["plan_day"]["status"] == "completed"
    assert cancelled["plan"]["status"] == "cancelled"


def test_stress_observation_reads_unified_plan_days():
    async def scenario():
        await persistence.save_jarvis_plan(
            plan_id="plan-pressure-unified",
            title="??????",
            plan_type="long_term",
            status="active",
            source_agent="maxwell",
            original_user_request="????????",
            goal="??????",
            days=[
                {"date": "2026-05-06", "title": f"???? {index}", "estimated_minutes": 90}
                for index in range(5)
            ],
        )
        return await aggregate_schedule_pressure_signals("2026-05-06")

    signals = asyncio.run(scenario())
    task_load = [signal for signal in signals if signal["signal_type"] == "task_load_high"]
    assert task_load
    assert any(ref["source"] == "jarvis_plan_days" for ref in task_load[0]["source_refs"])



def test_confirmed_long_plan_projects_timed_days_to_calendar():
    async def scenario():
        await persistence.save_pending_action(
            pending_id="pending-projection",
            action_type="task.plan",
            tool_name="jarvis_task_plan_decompose",
            agent_id="maxwell",
            session_id="session-projection",
            title="timed plan",
            arguments={
                "plan": {
                    "id": "task-projection",
                    "title": "timed plan",
                    "type": "long_project",
                    "daily_plan": [
                        {"date": "2026-05-07", "title": "timed day 1", "start_time": "09:00", "end_time": "10:00"},
                        {"date": "2026-05-08", "title": "timed day 2", "start_time": "11:00", "end_time": "12:00"},
                    ],
                }
            },
        )
        response = await confirm_pending_action_item("pending-projection", PendingActionConfirmRequest())
        plan_id = response["result"]["plan"]["id"]
        days = await persistence.list_jarvis_plan_days(plan_id=plan_id, limit=10)
        events = calendar_adapter.get_events_between(datetime.fromisoformat("2026-05-07T00:00:00"), datetime.fromisoformat("2026-05-09T00:00:00"))
        second_projection = await project_plan_calendar_items(plan_id)
        return response, days, events, second_projection

    response, days, events, second_projection = asyncio.run(scenario())
    assert response["result"]["calendar_projection_count"] == 2
    assert all(day["calendar_event_id"] for day in days)
    assert [event.title for event in events] == ["timed day 1", "timed day 2"]
    assert second_projection["projected_count"] == 0


def test_plan_days_push_to_workbench_and_overdue_missed():
    async def scenario():
        await persistence.save_jarvis_plan(
            plan_id="plan-workbench",
            title="workbench plan",
            plan_type="long_term",
            status="active",
            days=[
                {"date": "2026-05-09", "title": "today plan day", "start_time": "08:00", "end_time": "09:00"},
                {"date": "2026-05-08", "title": "old plan day", "start_time": "08:00", "end_time": "09:00"},
            ],
        )
        pushed = await push_maxwell_daily_tasks(plan_date="2026-05-09")
        workbench = await list_maxwell_workbench_items(plan_date="2026-05-09")
        missed = await mark_overdue_planner_day_items(today="2026-05-10")
        days = await persistence.list_jarvis_plan_days(plan_id="plan-workbench", limit=10)
        return pushed, workbench, missed, days

    pushed, workbench, missed, days = asyncio.run(scenario())
    assert pushed["pushed_count"] == 1
    assert pushed["items"][0]["plan_day_id"]
    assert workbench[0]["plan_day_id"]
    assert missed["missed_count"] >= 2
    assert {day["status"] for day in days} == {"missed"}


def test_reschedule_plan_days_updates_calendar_projection():
    async def scenario():
        plan = await persistence.save_jarvis_plan(
            plan_id="plan-reschedule",
            title="reschedule plan",
            plan_type="long_term",
            status="active",
            days=[{"date": "2026-05-11", "title": "move me", "start_time": "09:00", "end_time": "10:00"}],
        )
        await project_plan_calendar_items(plan["id"])
        changed = await reschedule_plan_days(plan["id"], PlanRescheduleRequest(days=[PlanDayMoveRequest(plan_date="2026-05-12", start_time="14:00", end_time="15:00", reason="manual reschedule")], reason="manual reschedule"))
        days = await persistence.list_jarvis_plan_days(plan_id=plan["id"], limit=10)
        event_id = days[0]["calendar_event_id"]
        event = calendar_adapter.get_event(event_id)
        return changed, days, event

    changed, days, event = asyncio.run(scenario())
    assert changed["changed_count"] == 1
    assert days[0]["plan_date"] == "2026-05-12"
    assert event is not None
    assert event.start.isoformat().startswith("2026-05-12T14:00")



class MockPlannerLLM:
    def __init__(self):
        self.calls = []

    async def chat(self, **kwargs):
        self.calls.append(kwargs)
        return '{"days":[{"id":"future-day","plan_date":"2026-05-13","start_time":"15:00","end_time":"16:00","title":"rescheduled future","description":"moved after missed day","reason":"missed previous work"}],"message":"I found a missed item and rescheduled the next plan day."}'


def test_daily_maintenance_uses_llm_to_reschedule_after_missed():
    async def scenario():
        await persistence.save_jarvis_plan(
            plan_id="plan-auto-reschedule",
            title="auto reschedule plan",
            plan_type="long_term",
            status="active",
            days=[
                {"id": "missed-day", "date": "2026-05-10", "title": "missed old", "start_time": "09:00", "end_time": "10:00"},
                {"id": "future-day", "date": "2026-05-12", "title": "future original", "start_time": "09:00", "end_time": "10:00"},
            ],
        )
        llm = MockPlannerLLM()
        result = await run_planner_daily_maintenance(today="2026-05-11", llm_client=llm, auto_reschedule=True, push_today=False)
        days = await persistence.list_jarvis_plan_days(plan_id="plan-auto-reschedule", limit=10)
        messages = await persistence.list_proactive_messages(agent_id="maxwell", limit=10)
        return result, days, messages, llm.calls

    result, days, messages, calls = asyncio.run(scenario())
    by_id = {day["id"]: day for day in days}
    assert calls
    assert result["rescheduled"][0]["changed_count"] == 1
    assert by_id["missed-day"]["status"] == "missed"
    assert by_id["future-day"]["plan_date"] == "2026-05-13"
    assert by_id["future-day"]["status"] == "rescheduled"
    assert messages and messages[0]["trigger"] == "planner:missed_reschedule"


def test_daily_maintenance_once_is_idempotent():
    async def scenario():
        await persistence.save_jarvis_plan(
            plan_id="plan-maintenance-once",
            title="once plan",
            plan_type="long_term",
            status="active",
            days=[{"id": "old-once", "date": "2026-05-10", "title": "old"}],
        )
        first = await run_planner_daily_maintenance_once(today="2026-05-11", llm_client=None, auto_reschedule=True, push_today=False)
        second = await run_planner_daily_maintenance_once(today="2026-05-11", llm_client=None, auto_reschedule=True, push_today=False)
        return first, second

    first, second = asyncio.run(scenario())
    assert "missed" in first
    assert second["skipped"] == "already_ran"



def test_calendar_events_are_persistent_and_availability_reports_conflicts():
    async def scenario():
        first = await add_calendar_event(CalendarEventRequest(
            title="persisted event A",
            start=datetime.fromisoformat("2026-05-14T09:00:00"),
            end=datetime.fromisoformat("2026-05-14T10:00:00"),
            source="user_ui",
        ))
        await add_calendar_event(CalendarEventRequest(
            title="persisted event B",
            start=datetime.fromisoformat("2026-05-14T09:30:00"),
            end=datetime.fromisoformat("2026-05-14T10:30:00"),
            source="user_ui",
        ))
        calendar_adapter._events.clear()
        items = await list_planner_calendar_items(
            start=datetime.fromisoformat("2026-05-14T00:00:00"),
            end=datetime.fromisoformat("2026-05-15T00:00:00"),
        )
        event = calendar_adapter.get_event(first["event_id"])
        return items, event

    items, event = asyncio.run(scenario())
    assert event is not None
    assert event.title == "persisted event A"
    assert len([item for item in items["items"] if item["item_type"] == "calendar_event"]) == 2
    assert items["conflicts"]
    assert items["free_windows"]
