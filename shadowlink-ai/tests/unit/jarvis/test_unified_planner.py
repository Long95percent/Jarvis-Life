import asyncio
import sqlite3
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest

from app.api.v1.jarvis_router import (
    CalendarEventRequest,
    CalendarEventUpdate,
    PendingActionConfirmRequest,
    PlanDayMoveRequest,
    PlanDayBulkUpdateRequest,
    add_calendar_event,
    cancel_plan_item,
    delete_background_task_day_item,
    delete_plan_item,
    complete_plan_day_item,
    confirm_pending_action_item,
    list_planner_calendar_items,
    list_planner_task_items,
    cleanup_duplicate_planner_tasks,
    move_plan_day_item,
    bulk_update_plan_day_items,
    update_background_task_item,
    BackgroundTaskUpdateRequest,
    project_plan_calendar_items,
    push_maxwell_daily_tasks,
    mark_overdue_planner_day_items,
    list_maxwell_workbench_items,
    create_plan_item,
    update_plan_item,
    update_calendar_event,
    PlanCreateRequest,
    PlanUpdateRequest,
    merge_plan_items,
    split_plan_item,
    PlanMergeRequest,
    PlanSplitRequest,
    PlanRescheduleRequest,
    _persist_task_plan_result,
    _find_duplicate_calendar_events,
    reschedule_plan_days,
)
from app.jarvis import persistence
from app.jarvis.planner_guard import validate_plan_day_move
from app.jarvis.stress_observation import aggregate_schedule_pressure_signals
from app.jarvis.planner_maintenance import run_planner_daily_maintenance, run_planner_daily_maintenance_once
from app.mcp.adapters import calendar_adapter
from app.tools.jarvis_tools import JarvisCalendarAddTool


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


def test_task_plan_auto_persist_projects_all_30_days_to_calendar():
    async def scenario():
        daily_plan = [
            {
                "date": f"2026-05-{day:02d}",
                "title": f"雅思训练 {day}",
                "start_time": "20:00",
                "end_time": "21:00",
                "estimated_minutes": 60,
            }
            for day in range(1, 31)
        ]
        result = await _persist_task_plan_result(
            arguments={
                "type": "task.plan",
                "ok": True,
                "plan": {
                    "id": "task-ielts-auto-30",
                    "title": "雅思备考计划",
                    "type": "long_project",
                    "source_agent": "maxwell",
                    "original_user_request": "我要考雅思，未来的30天，写入日程",
                    "goal": "未来 30 天完成雅思备考节奏",
                    "time_horizon": {"start_after": "2026-05-01", "target_date": "2026-05-30"},
                    "daily_plan": daily_plan,
                },
            },
            source_agent="maxwell",
        )
        plan_days = await persistence.list_jarvis_plan_days(plan_id=result["plan"]["id"], limit=100)
        calendar_items = await list_planner_calendar_items(start=datetime(2026, 5, 1), end=datetime(2026, 5, 31))
        return result, plan_days, calendar_items

    result, plan_days, calendar_items = asyncio.run(scenario())

    assert result["task_day_count"] == 30
    assert result["plan_day_count"] == 30
    assert result["calendar_projection_count"] == 30
    assert len(plan_days) == 30
    assert plan_days[0]["plan_date"] == "2026-05-01"
    assert plan_days[-1]["plan_date"] == "2026-05-30"
    assert len(calendar_items["items"]) == 30
    assert len([item for item in calendar_items["items"] if item["item_type"] == "calendar_event"]) == 30
    assert [item for item in calendar_items["items"] if item["item_type"] == "plan_day"] == []
    assert calendar_items["conflicts"] == []


def test_manual_plan_create_and_update_only_changes_plan_header():
    async def scenario():
        created = await create_plan_item(PlanCreateRequest(
            title="雅思备考",
            goal="三个月内完成雅思备考",
            original_user_request="我要考雅思",
            time_horizon={"target_date": "2026-08-01"},
        ))
        updated = await update_plan_item(created["id"], PlanUpdateRequest(
            title="雅思备考主计划",
            goal="先稳定推进听说读写",
            time_horizon={"target_date": "2026-08-15"},
        ))
        plans = await persistence.list_jarvis_plans(limit=10)
        days = await persistence.list_jarvis_plan_days(plan_id=created["id"], limit=10)
        return created, updated, plans, days

    created, updated, plans, days = asyncio.run(scenario())

    assert created["source_agent"] == "user_ui"
    assert created["plan_type"] == "long_term"
    assert updated["title"] == "雅思备考主计划"
    assert updated["goal"] == "先稳定推进听说读写"
    assert updated["time_horizon"]["target_date"] == "2026-08-15"
    assert len(plans) == 1
    assert days == []
    assert plans[0]["plan_type"] == "long_term"


def test_manual_plan_merge_and_split_move_plan_days_with_events():
    async def scenario():
        source = await persistence.save_jarvis_plan(
            plan_id="plan-source",
            title="雅思口语",
            plan_type="long_term",
            source_agent="maxwell",
            original_user_request="练口语",
            days=[{"id": "day-source-1", "date": "2026-05-10", "title": "口语 part 1"}],
        )
        target = await persistence.save_jarvis_plan(
            plan_id="plan-target",
            title="雅思备考",
            plan_type="long_term",
            source_agent="maxwell",
            original_user_request="考雅思",
            days=[{"id": "day-target-1", "date": "2026-05-11", "title": "听力练习"}],
        )
        merged = await merge_plan_items(PlanMergeRequest(source_plan_id=source["id"], target_plan_id=target["id"], reason="same IELTS goal"))
        split = await split_plan_item(target["id"], PlanSplitRequest(title="雅思口语专项", plan_day_ids=["day-source-1"], reason="separate speaking track"))
        source_after = await persistence.get_jarvis_plan(source["id"])
        target_days = await persistence.list_jarvis_plan_days(plan_id=target["id"], limit=10)
        split_days = await persistence.list_jarvis_plan_days(plan_id=split["new_plan"]["id"], limit=10)
        target_events = await persistence.list_agent_events(plan_id=target["id"], limit=10)
        split_events = await persistence.list_agent_events(plan_id=split["new_plan"]["id"], limit=10)
        return merged, split, source_after, target_days, split_days, target_events, split_events

    merged, split, source_after, target_days, split_days, target_events, split_events = asyncio.run(scenario())

    assert merged["source_plan"]["status"] == "merged"
    assert source_after["status"] == "merged"
    assert merged["moved_day_count"] == 1
    assert split["moved_day_count"] == 1
    assert [day["id"] for day in target_days] == ["day-target-1"]
    assert [day["id"] for day in split_days] == ["day-source-1"]
    assert any(event["event_type"] == "plan.merged" for event in target_events)
    assert any(event["event_type"] == "plan.split" for event in split_events)


def test_plan_day_bulk_update_changes_multiple_days_and_records_events():
    async def scenario():
        plan = await persistence.save_jarvis_plan(
            plan_id="plan-bulk-days",
            title="bulk days",
            plan_type="long_term",
            days=[
                {"id": "bulk-day-1", "date": "2026-05-10", "title": "day 1"},
                {"id": "bulk-day-2", "date": "2026-05-11", "title": "day 2"},
            ],
        )
        completed = await bulk_update_plan_day_items(PlanDayBulkUpdateRequest(day_ids=["bulk-day-1", "bulk-day-2"], status="completed", reason="batch complete"))
        moved = await bulk_update_plan_day_items(PlanDayBulkUpdateRequest(day_ids=["bulk-day-1", "bulk-day-2"], shift_days=2, reason="batch postpone"))
        days = await persistence.list_jarvis_plan_days(plan_id=plan["id"], limit=10)
        events = await persistence.list_agent_events(plan_id=plan["id"], limit=20)
        return completed, moved, days, events

    completed, moved, days, events = asyncio.run(scenario())

    assert completed["changed_count"] == 2
    assert moved["changed_count"] == 2
    assert [day["status"] for day in days] == ["completed", "completed"]
    assert [day["plan_date"] for day in days] == ["2026-05-12", "2026-05-13"]
    assert any(event["event_type"] == "plan_day.bulk_updated" for event in events)


def test_background_task_archive_is_soft_but_delete_is_hard():
    async def scenario():
        await persistence.save_background_task(
            task_id="legacy-task-archive",
            title="legacy task",
            task_type="long_project",
            status="active",
            source_agent="maxwell",
            original_user_request="legacy",
            goal="cleanup legacy",
            time_horizon={},
            milestones=[],
            subtasks=[],
            calendar_candidates=[],
        )
        archived = await update_background_task_item("legacy-task-archive", BackgroundTaskUpdateRequest(status="archived"))
        deleted = await update_background_task_item("legacy-task-archive", BackgroundTaskUpdateRequest(status="deleted"))
        visible = await persistence.list_background_tasks(limit=10)
        deleted_list = await persistence.list_background_tasks(status="deleted", limit=10)
        return archived, deleted, visible, deleted_list

    archived, deleted, visible, deleted_list = asyncio.run(scenario())

    assert archived["status"] == "archived"
    assert deleted["status"] == "deleted"
    assert all(task["id"] != "legacy-task-archive" for task in visible)
    assert deleted_list == []


def test_deleting_background_task_deletes_linked_plan_projection():
    async def scenario():
        result = await _persist_task_plan_result(
            arguments={
                "type": "task.plan",
                "ok": True,
                "plan": {
                    "id": "task-delete-projection",
                    "title": "delete projection task",
                    "type": "long_project",
                    "source_agent": "maxwell",
                    "original_user_request": "delete projected long task",
                    "goal": "verify projection cleanup",
                    "time_horizon": {"start_after": "2026-05-20", "target_date": "2026-05-21"},
                    "daily_plan": [
                        {"date": "2026-05-20", "title": "delete day 1", "start_time": "20:00", "end_time": "21:00"},
                        {"date": "2026-05-21", "title": "delete day 2", "start_time": "20:00", "end_time": "21:00"},
                    ],
                },
            },
            source_agent="maxwell",
        )
        before = await list_planner_calendar_items(start=datetime(2026, 5, 20), end=datetime(2026, 5, 22))
        deleted = await update_background_task_item(result["task"]["id"], BackgroundTaskUpdateRequest(status="deleted"))
        after = await list_planner_calendar_items(start=datetime(2026, 5, 20), end=datetime(2026, 5, 22))
        linked_plans = await persistence.list_jarvis_plans(status="deleted", limit=10)
        linked_days = await persistence.list_jarvis_plan_days(plan_id=result["plan"]["id"], limit=10)
        deleted_task_list = await persistence.list_background_tasks(status="deleted", limit=10)
        deleted_events = await asyncio.to_thread(
            lambda: sqlite3.connect(persistence._DB_PATH).execute("SELECT COUNT(*) FROM jarvis_calendar_events WHERE status = 'deleted'").fetchone()[0]
        )
        return result, before, deleted, after, linked_plans, linked_days, deleted_task_list, deleted_events

    result, before, deleted, after, linked_plans, linked_days, deleted_task_list, deleted_events = asyncio.run(scenario())

    assert len([item for item in before["items"] if item["item_type"] == "calendar_event"]) == 2
    assert deleted["status"] == "deleted"
    assert after["items"] == []
    assert linked_plans == []
    assert linked_days == []
    assert deleted_task_list == []
    assert deleted_events == 0


def test_deleting_short_background_task_deletes_linked_projection():
    async def scenario():
        result = await _persist_task_plan_result(
            arguments={
                "type": "task.plan",
                "ok": True,
                "plan": {
                    "id": "task-delete-short-projection",
                    "title": "delete short projection task",
                    "type": "short_project",
                    "source_agent": "maxwell",
                    "original_user_request": "delete projected short task",
                    "goal": "verify short projection cleanup",
                    "time_horizon": {"target_date": "2026-05-22"},
                    "daily_plan": [
                        {"date": "2026-05-22", "title": "delete short day", "start_time": "09:00", "end_time": "10:00"},
                    ],
                },
            },
            source_agent="maxwell",
        )
        before = await list_planner_calendar_items(start=datetime(2026, 5, 22), end=datetime(2026, 5, 23))
        deleted = await update_background_task_item(result["task"]["id"], BackgroundTaskUpdateRequest(status="deleted"))
        after = await list_planner_calendar_items(start=datetime(2026, 5, 22), end=datetime(2026, 5, 23))
        linked_days = await persistence.list_jarvis_plan_days(plan_id=result["plan"]["id"], limit=10)
        return result, before, deleted, after, linked_days

    result, before, deleted, after, linked_days = asyncio.run(scenario())

    assert result["plan"]["plan_type"] == "short_term"
    assert len([item for item in before["items"] if item["item_type"] == "calendar_event"]) == 1
    assert deleted["status"] == "deleted"
    assert after["items"] == []
    assert linked_days == []


def test_deleting_background_task_day_hard_deletes_database_row_and_projection():
    async def scenario():
        await persistence.save_background_task(
            task_id="task-day-hard-delete",
            title="task day hard delete",
            task_type="short_project",
            status="active",
            source_agent="maxwell",
            original_user_request="delete one task day",
            goal="delete one task day",
            time_horizon={},
            milestones=[],
            subtasks=[],
            calendar_candidates=[],
        )
        days = await persistence.save_background_task_days(
            task_id="task-day-hard-delete",
            daily_plan=[{"date": "2026-05-23", "title": "hard delete task day", "start_time": "08:00", "end_time": "09:00"}],
        )
        event = calendar_adapter.add_event(
            "hard delete task day",
            datetime.fromisoformat("2026-05-23T08:00:00"),
            datetime.fromisoformat("2026-05-23T09:00:00"),
            source="planner_projection",
        )
        with sqlite3.connect(persistence._DB_PATH) as con:
            con.execute("UPDATE background_task_days SET calendar_event_id = ? WHERE id = ?", (event.id, days[0]["id"]))
            con.commit()
        deleted = await delete_background_task_day_item(days[0]["id"])
        remaining_days = await persistence.list_background_task_days(task_id="task-day-hard-delete", limit=10)
        remaining_event_count = await asyncio.to_thread(
            lambda: sqlite3.connect(persistence._DB_PATH).execute("SELECT COUNT(*) FROM jarvis_calendar_events WHERE id = ?", (event.id,)).fetchone()[0]
        )
        return deleted, remaining_days, remaining_event_count

    deleted, remaining_days, remaining_event_count = asyncio.run(scenario())

    assert deleted["task_day"]["status"] == "deleted"
    assert remaining_days == []
    assert remaining_event_count == 0


def test_duplicate_long_term_goal_confirmation_updates_existing_task_and_plan():
    async def scenario():
        for index, pending_id in enumerate(["pending-ielts-first", "pending-ielts-second"], start=1):
            await persistence.save_pending_action(
                pending_id=pending_id,
                action_type="task.plan",
                tool_name="jarvis_task_plan_decompose",
                agent_id="maxwell",
                session_id=f"session-ielts-{index}",
                title="雅思备考计划",
                arguments={
                    "plan": {
                        "id": f"task-random-{index}",
                        "title": "雅思备考计划",
                        "type": "future_project" if index == 1 else "recurring_plan",
                        "source_agent": "maxwell",
                        "original_user_request": "我要考雅思",
                        "goal": "雅思备考计划",
                        "time_horizon": {"start_after": "2026-05-01", "target_date": "2026-05-14"},
                        "daily_plan": [
                            {"date": "2026-05-01", "title": "雅思听力训练", "start_time": "20:00", "end_time": "21:00", "estimated_minutes": 60},
                            {"date": "2026-05-02", "title": f"雅思阅读训练 {index}", "start_time": "20:00", "end_time": "21:00", "estimated_minutes": 60},
                        ],
                    }
                },
            )
            await confirm_pending_action_item(pending_id, PendingActionConfirmRequest())

        tasks = await persistence.list_background_tasks(limit=20)
        plans = await persistence.list_jarvis_plans(limit=20)
        plan_days = await persistence.list_jarvis_plan_days(plan_id=plans[0]["id"], limit=20)
        return tasks, plans, plan_days

    tasks, plans, plan_days = asyncio.run(scenario())
    assert len(tasks) == 1
    assert tasks[0]["title"] == "雅思备考计划"
    assert tasks[0]["task_type"] == "long_project"
    assert len(plans) == 1
    assert plans[0]["source_background_task_id"] == tasks[0]["id"]
    assert [day["title"] for day in plan_days] == ["雅思听力训练", "雅思阅读训练 2"]


def test_background_task_listing_collapses_existing_duplicate_long_term_tasks():
    async def scenario():
        for index, task_type in enumerate(["future_project", "recurring_plan", "long_project"], start=1):
            await persistence.save_background_task(
                task_id=f"legacy-ielts-{index}",
                title="雅思备考计划",
                task_type=task_type,
                status="active",
                source_agent="maxwell",
                original_user_request="我要考雅思",
                goal="雅思备考计划",
                time_horizon={},
                milestones=[],
                subtasks=[],
                calendar_candidates=[],
            )
        return await persistence.list_background_tasks(limit=20)

    tasks = asyncio.run(scenario())
    assert len(tasks) == 1
    assert tasks[0]["title"] == "雅思备考计划"


def test_cleanup_duplicate_long_term_tasks_merges_rows_and_relations():
    async def scenario():
        for index, task_type in enumerate(["future_project", "recurring_plan", "long_project"], start=1):
            task_id = f"legacy-ielts-{index}"
            await persistence.save_background_task(
                task_id=task_id,
                title="雅思备考计划",
                task_type=task_type,
                status="active",
                source_agent="maxwell",
                original_user_request="我要考雅思",
                goal="雅思备考计划",
                time_horizon={},
                milestones=[],
                subtasks=[],
                calendar_candidates=[],
            )
            await persistence.save_background_task_days(
                task_id=task_id,
                daily_plan=[{"id": f"day-{index}", "date": f"2026-05-0{index}", "title": f"雅思训练 {index}"}],
            )
            await persistence.save_jarvis_plan(
                plan_id=f"plan-legacy-{index}",
                title="雅思备考计划",
                plan_type="long_term",
                status="active",
                source_background_task_id=task_id,
                original_user_request="我要考雅思",
                goal="雅思备考计划",
                days=[{"id": f"plan-day-{index}", "date": f"2026-05-0{index}", "title": f"雅思计划 {index}", "source_task_day_id": f"day-{index}"}],
            )

        result = await persistence.cleanup_duplicate_background_tasks()
        tasks = await persistence.list_background_tasks(limit=20)
        all_days = await persistence.list_background_task_days(limit=20)
        plans = await persistence.list_jarvis_plans(limit=20)
        plan_days = []
        for plan in plans:
            plan_days.extend(await persistence.list_jarvis_plan_days(plan_id=plan["id"], limit=20))
        return result, tasks, all_days, plans, plan_days

    result, tasks, all_days, plans, plan_days = asyncio.run(scenario())
    assert result["deleted_tasks"] == 2
    assert len(tasks) == 1
    canonical_id = tasks[0]["id"]
    assert tasks[0]["task_type"] == "long_project"
    assert {day["task_id"] for day in all_days} == {canonical_id}
    assert {plan["source_background_task_id"] for plan in plans} == {canonical_id}
    assert {day["source_task_day_id"] for day in plan_days} == {"day-1", "day-2", "day-3"}


def test_planner_task_items_use_plans_as_primary_model_and_hide_linked_background_tasks():
    async def scenario():
        await persistence.save_background_task(
            task_id="task-linked",
            title="雅思备考计划",
            task_type="long_project",
            status="active",
            source_agent="maxwell",
            original_user_request="我要考雅思",
            goal="雅思备考计划",
            time_horizon={},
            milestones=[],
            subtasks=[],
            calendar_candidates=[],
        )
        await persistence.save_jarvis_plan(
            plan_id="plan-linked",
            title="雅思备考计划",
            plan_type="long_term",
            status="active",
            source_background_task_id="task-linked",
            original_user_request="我要考雅思",
            goal="雅思备考计划",
            days=[],
        )
        await persistence.save_background_task(
            task_id="task-orphan",
            title="临时后台任务",
            task_type="short_project",
            status="active",
            source_agent="maxwell",
            original_user_request="临时后台任务",
            goal="临时后台任务",
            time_horizon={},
            milestones=[],
            subtasks=[],
            calendar_candidates=[],
        )
        return await list_planner_task_items()

    items = asyncio.run(scenario())
    assert [item["id"] for item in items] == ["plan-linked", "task-orphan"]
    assert [item["item_type"] for item in items] == ["plan", "background_task"]
    assert items[0]["source_background_task_id"] == "task-linked"
    assert items[1]["source_background_task_id"] is None


def test_planner_task_items_do_not_expose_decomposed_plan_days_as_tasks():
    async def scenario():
        await persistence.save_jarvis_plan(
            plan_id="plan-ielts-30-top-level",
            title="雅思 30 天备考计划",
            plan_type="long_term",
            status="active",
            source_agent="maxwell",
            original_user_request="我要考雅思，未来 30 天",
            goal="完成 30 天雅思备考",
            days=[
                {"id": f"ielts-day-{index}", "date": f"2026-05-{index:02d}", "title": f"5/{index} 雅思训练", "start_time": "20:00", "end_time": "21:00"}
                for index in range(1, 6)
            ],
        )
        return await list_planner_task_items()

    items = asyncio.run(scenario())

    assert [item["id"] for item in items] == ["plan-ielts-30-top-level"]
    assert items[0]["item_type"] == "plan"
    assert not any(item["id"].startswith("ielts-day-") for item in items)


def test_cleanup_duplicate_planner_tasks_endpoint_supports_preview_and_execute():
    async def scenario():
        for index in range(2):
            await persistence.save_background_task(
                task_id=f"preview-ielts-{index}",
                title="雅思备考计划",
                task_type="long_project",
                status="active",
                source_agent="maxwell",
                original_user_request="我要考雅思",
                goal="雅思备考计划",
                time_horizon={},
                milestones=[],
                subtasks=[],
                calendar_candidates=[],
            )

        preview = await cleanup_duplicate_planner_tasks(execute=False)
        with sqlite3.connect(persistence._DB_PATH) as con:
            raw_count_after_preview = con.execute("SELECT COUNT(*) FROM background_tasks").fetchone()[0]
        executed = await cleanup_duplicate_planner_tasks(execute=True)
        with sqlite3.connect(persistence._DB_PATH) as con:
            raw_count_after_execute = con.execute("SELECT COUNT(*) FROM background_tasks").fetchone()[0]
        tasks_after_execute = await persistence.list_background_tasks(limit=20)
        return preview, raw_count_after_preview, executed, raw_count_after_execute, tasks_after_execute

    preview, raw_count_after_preview, executed, raw_count_after_execute, tasks_after_execute = asyncio.run(scenario())
    assert preview["execute"] is False
    assert preview["duplicate_group_count"] == 1
    assert preview["deleted_tasks"] == 0
    assert raw_count_after_preview == 2
    assert executed["execute"] is True
    assert executed["deleted_tasks"] == 1
    assert raw_count_after_execute == 1
    assert len(tasks_after_execute) == 1


def test_manual_calendar_event_creates_short_term_plan_day_but_calendar_items_are_deduped():
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
    assert [item["item_type"] for item in items["items"]] == ["calendar_event"]


def test_manual_calendar_event_update_syncs_backing_plan_day_and_calendar_projection():
    async def scenario():
        created = await add_calendar_event(CalendarEventRequest(
            title="Original calendar task",
            start=datetime.fromisoformat("2026-05-03T15:00:00"),
            end=datetime.fromisoformat("2026-05-03T16:00:00"),
            source="user_ui",
            created_reason="manual create",
        ))
        event_id = created["event_id"]
        day_id = created["plan_day"]["id"]

        updated = await update_calendar_event(event_id, CalendarEventUpdate(
            title="Updated calendar task",
            start=datetime.fromisoformat("2026-05-04T09:30:00"),
            end=datetime.fromisoformat("2026-05-04T10:15:00"),
            notes="updated notes",
            status="confirmed",
        ))
        days = await persistence.list_jarvis_plan_days(plan_id=created["plan_day"]["plan_id"], limit=10)
        items = await list_planner_calendar_items(
            start=datetime.fromisoformat("2026-05-04T00:00:00"),
            end=datetime.fromisoformat("2026-05-05T00:00:00"),
        )
        return event_id, day_id, updated, days, items

    event_id, day_id, updated, days, items = asyncio.run(scenario())
    synced_day = next(day for day in days if day["id"] == day_id)
    assert updated["event"]["title"] == "Updated calendar task"
    assert synced_day["title"] == "Updated calendar task"
    assert synced_day["description"] == "updated notes"
    assert synced_day["plan_date"] == "2026-05-04"
    assert synced_day["start_time"] == "09:30"
    assert synced_day["end_time"] == "10:15"
    assert synced_day["calendar_event_id"] == event_id
    assert [(item["item_type"], item["id"], item["title"]) for item in items["items"]] == [
        ("calendar_event", event_id, "Updated calendar task")
    ]


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


def test_delete_plan_hides_task_and_deletes_calendar_projection():
    async def scenario():
        created = await persistence.save_jarvis_plan(
            plan_id="plan-delete-test",
            title="删除测试计划",
            plan_type="long_term",
            status="active",
            source_agent="maxwell",
            original_user_request="创建一个可以删除的计划",
            goal="验证查看所有任务可以删除",
            days=[{"id": "delete-test-day", "date": "2026-05-08", "title": "删除测试日", "start_time": "20:00", "end_time": "21:00"}],
        )
        projected = await project_plan_calendar_items(created["id"])
        deleted = await delete_plan_item(created["id"])
        visible_plans = await persistence.list_jarvis_plans(limit=20)
        deleted_plans = await persistence.list_jarvis_plans(status="deleted", limit=20)
        days = await persistence.list_jarvis_plan_days(plan_id=created["id"], limit=20)
        deleted_event_count = await asyncio.to_thread(
            lambda: sqlite3.connect(persistence._DB_PATH).execute("SELECT COUNT(*) FROM jarvis_calendar_events WHERE status = 'deleted'").fetchone()[0]
        )
        return projected, deleted, visible_plans, deleted_plans, days, deleted_event_count

    projected, deleted, visible_plans, deleted_plans, days, deleted_event_count = asyncio.run(scenario())
    assert projected["projected_count"] == 1
    assert deleted["plan"]["status"] == "deleted"
    assert all(plan["id"] != deleted["plan"]["id"] for plan in visible_plans)
    assert deleted_plans == []
    assert days == []
    assert deleted["calendar_events"] == []
    assert deleted_event_count == 0


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


def test_plan_day_move_rejects_past_date():
    async def scenario():
        plan = await persistence.save_jarvis_plan(
            plan_id="plan-past-guard",
            title="past guard",
            plan_type="long_term",
            goal="test",
            days=[{"id": "past-guard-day", "date": "2026-05-02", "title": "future day", "start_time": "19:00", "end_time": "20:00"}],
        )
        day = (await persistence.list_jarvis_plan_days(plan_id=plan["id"], limit=10))[0]
        with pytest.raises(ValueError, match="past date"):
            validate_plan_day_move(
                {"id": day["id"], "plan_date": "2026-05-02", "start_time": "19:00", "end_time": "20:00"},
                {"plan_date": "2026-04-30", "start_time": "19:00", "end_time": "20:00"},
                today="2026-05-01",
            )

    asyncio.run(scenario())


def test_move_plan_day_item_rejects_past_date_before_persisting():
    async def scenario():
        plan = await persistence.save_jarvis_plan(
            plan_id="plan-route-past-guard",
            title="route past guard",
            plan_type="long_term",
            goal="test",
            days=[{"id": "route-past-guard-day", "date": "2026-05-02", "title": "future day", "start_time": "19:00", "end_time": "20:00"}],
        )
        day = (await persistence.list_jarvis_plan_days(plan_id=plan["id"], limit=10))[0]
        with pytest.raises(Exception) as exc:
            await move_plan_day_item(
                day["id"],
                PlanDayMoveRequest(plan_date="2026-04-30", start_time="19:00", end_time="20:00", reason="bad move"),
            )
        current = await persistence.list_jarvis_plan_days(plan_id=plan["id"], limit=10)
        return exc.value, current[0]

    error, day = asyncio.run(scenario())
    assert getattr(error, "status_code", None) == 422
    assert getattr(error, "detail", {}).get("code") == "planner_guard_violation"
    assert day["plan_date"] == "2026-05-02"



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


def test_planner_calendar_items_handles_timezone_aware_confirmed_events():
    async def scenario():
        await add_calendar_event(CalendarEventRequest(
            title="秘书确认日程",
            start=datetime.fromisoformat("2026-05-15T09:00:00+08:00"),
            end=datetime.fromisoformat("2026-05-15T10:00:00+08:00"),
            source="agent_pending_confirmation",
            source_agent="maxwell",
        ))
        await persistence.save_jarvis_plan(
            plan_id="plan-naive-day",
            title="本地计划日",
            plan_type="short_term",
            status="active",
            source_agent="maxwell",
            original_user_request="安排本地计划日",
            goal="本地计划日",
            days=[{"id": "naive-day", "date": "2026-05-15", "title": "本地计划日", "start_time": "09:30", "end_time": "10:30"}],
        )
        return await list_planner_calendar_items(
            start=datetime.fromisoformat("2026-05-15T00:00:00+08:00"),
            end=datetime.fromisoformat("2026-05-16T00:00:00+08:00"),
        )

    items = asyncio.run(scenario())

    assert len(items["items"]) >= 2
    assert items["conflicts"]
    assert items["free_windows"]


def test_calendar_add_allows_same_title_on_different_days():
    async def scenario():
        first = await add_calendar_event(CalendarEventRequest(
            title="奶茶",
            start=datetime.fromisoformat("2026-05-16T09:00:00+08:00"),
            end=datetime.fromisoformat("2026-05-16T10:00:00+08:00"),
            source="agent_pending_confirmation",
            source_agent="maxwell",
        ))
        second = await add_calendar_event(CalendarEventRequest(
            title="奶茶",
            start=datetime.fromisoformat("2026-05-17T20:00:00+08:00"),
            end=datetime.fromisoformat("2026-05-17T21:00:00+08:00"),
            source="agent_pending_confirmation",
            source_agent="maxwell",
        ))
        return first, second

    first, second = asyncio.run(scenario())

    assert first["event_id"] != second["event_id"]


def test_calendar_add_rejects_duplicate_title_on_same_day_even_when_time_differs():
    async def scenario():
        await add_calendar_event(CalendarEventRequest(
            title="奶茶",
            start=datetime.fromisoformat("2026-05-16T09:00:00+08:00"),
            end=datetime.fromisoformat("2026-05-16T10:00:00+08:00"),
            source="agent_pending_confirmation",
            source_agent="maxwell",
        ))
        return await add_calendar_event(CalendarEventRequest(
            title="奶茶",
            start=datetime.fromisoformat("2026-05-16T20:00:00+08:00"),
            end=datetime.fromisoformat("2026-05-16T21:00:00+08:00"),
            source="agent_pending_confirmation",
            source_agent="maxwell",
        ))

    with pytest.raises(Exception) as exc:
        asyncio.run(scenario())

    assert "duplicate_calendar_event" in str(exc.value)


def test_duplicate_calendar_lookup_only_checks_request_day():
    async def scenario():
        await add_calendar_event(CalendarEventRequest(
            title="奶茶",
            start=datetime.fromisoformat("2026-05-16T09:00:00+08:00"),
            end=datetime.fromisoformat("2026-05-16T10:00:00+08:00"),
            source="agent_pending_confirmation",
            source_agent="maxwell",
        ))
        next_day_req = CalendarEventRequest(
            title="奶茶",
            start=datetime.fromisoformat("2026-05-17T20:00:00+08:00"),
            end=datetime.fromisoformat("2026-05-17T21:00:00+08:00"),
            source="agent_pending_confirmation",
            source_agent="maxwell",
        )
        same_day_req = CalendarEventRequest(
            title="奶茶",
            start=datetime.fromisoformat("2026-05-16T20:00:00+08:00"),
            end=datetime.fromisoformat("2026-05-16T21:00:00+08:00"),
            source="agent_pending_confirmation",
            source_agent="maxwell",
        )
        return _find_duplicate_calendar_events(next_day_req), _find_duplicate_calendar_events(same_day_req)

    next_day_duplicates, same_day_duplicates = asyncio.run(scenario())

    assert next_day_duplicates == []
    assert len(same_day_duplicates) == 1


def test_calendar_tool_accepts_timezone_aware_trip_events_without_naive_aware_crash():
    async def scenario():
        tool = JarvisCalendarAddTool()
        first = await tool._arun(
            title="抵达无锡，先放行李",
            start="2026-05-04T13:00:00+08:00",
            end="2026-05-04T14:00:00+08:00",
        )
        second = await tool._arun(
            title="鼋头渚（太湖+仙岛）",
            start="2026-05-04T14:00:00+08:00",
            end="2026-05-04T16:30:00+08:00",
        )
        events = calendar_adapter.get_events_between(
            datetime.fromisoformat("2026-05-04T00:00:00"),
            datetime.fromisoformat("2026-05-05T00:00:00"),
        )
        return first, second, events

    first, second, events = asyncio.run(scenario())

    assert first["ok"] is True
    assert second["ok"] is True
    assert len(events) == 2
