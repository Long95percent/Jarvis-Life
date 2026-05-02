import asyncio
import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest

from app.jarvis import persistence
from app.jarvis.secretary_planning_service import run_secretary_plan_request
from app.mcp.adapters import calendar_adapter


class FakeSecretaryLLM:
    def __init__(self, payload: dict):
        self.payload = payload
        self.calls = []

    async def chat(self, **kwargs):
        self.calls.append(kwargs)
        return json.dumps(self.payload, ensure_ascii=False)


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    db_dir = Path("data") / "test_dbs"
    db_dir.mkdir(parents=True, exist_ok=True)
    tmp = db_dir / f"jarvis-secretary-{uuid4().hex}.db"
    monkeypatch.setattr(persistence, "_DB_PATH", tmp)
    persistence._initialized = False
    calendar_adapter._events.clear()
    yield tmp
    calendar_adapter._events.clear()
    persistence._initialized = False


def test_secretary_short_schedule_writes_short_term_plan_day():
    async def scenario():
        llm = FakeSecretaryLLM({
            "schema_version": "secretary_schedule.v1",
            "intent": "short_schedule",
            "summary": "明晚安排一次雅思听力复习。",
            "items": [{
                "client_item_id": "item-1",
                "date": "2026-05-02",
                "start_time": "19:30",
                "end_time": "21:00",
                "title": "雅思听力复习",
                "description": "完成 Section 1-2 并整理错题。",
                "estimated_minutes": 90,
                "priority": "high",
                "reason": "用户指定明晚。",
            }],
        })
        result = await run_secretary_plan_request(
            intent="short_schedule",
            message="明天晚上帮我安排一次雅思听力复习",
            today="2026-05-01",
            llm_client=llm,
            auto_project_calendar=False,
        )
        days = await persistence.list_jarvis_plan_days(plan_id=result["plan"]["id"], limit=10)
        return result, days, llm.calls

    result, days, calls = asyncio.run(scenario())
    assert result["intent"] == "short_schedule"
    assert result["plan"]["plan_type"] == "short_term"
    assert len(days) == 1
    assert days[0]["title"] == "雅思听力复习"
    assert calls


def test_secretary_long_plan_writes_one_plan_with_many_days():
    async def scenario():
        llm = FakeSecretaryLLM({
            "schema_version": "secretary_long_plan.v1",
            "intent": "long_plan",
            "plan": {
                "title": "雅思 3 天备考计划",
                "goal": "完成三天基础训练",
                "plan_type": "long_term",
                "start_date": "2026-05-01",
                "target_date": "2026-05-03",
            },
            "days": [
                {"day_index": 1, "date": "2026-05-01", "start_time": "19:30", "end_time": "21:00", "title": "听力诊断", "description": "听力", "estimated_minutes": 90, "reason": "start"},
                {"day_index": 2, "date": "2026-05-02", "start_time": "19:30", "end_time": "21:00", "title": "阅读训练", "description": "阅读", "estimated_minutes": 90, "reason": "continue"},
            ],
        })
        result = await run_secretary_plan_request(
            intent="long_plan",
            message="我要考雅思，未来 3 天帮我安排学习计划",
            today="2026-05-01",
            llm_client=llm,
            auto_project_calendar=False,
        )
        plans = await persistence.list_jarvis_plans(limit=10)
        days = await persistence.list_jarvis_plan_days(plan_id=result["plan"]["id"], limit=10)
        return result, plans, days

    result, plans, days = asyncio.run(scenario())
    assert result["intent"] == "long_plan"
    assert len(plans) == 1
    assert plans[0]["title"] == "雅思 3 天备考计划"
    assert len(days) == 2
    assert [day["title"] for day in days] == ["听力诊断", "阅读训练"]


def test_secretary_repeated_long_plan_replaces_existing_projection_instead_of_duplication():
    async def scenario():
        payload = {
            "schema_version": "secretary_long_plan.v1",
            "intent": "long_plan",
            "plan": {
                "title": "IELTS 30 day plan",
                "goal": "finish IELTS prep",
                "plan_type": "long_term",
                "start_date": "2026-05-01",
                "target_date": "2026-05-30",
            },
            "days": [
                {
                    "day_index": day,
                    "date": f"2026-05-{day:02d}",
                    "start_time": "20:00",
                    "end_time": "21:00",
                    "title": f"IELTS day {day}",
                    "description": "practice",
                    "estimated_minutes": 60,
                    "reason": "daily practice",
                }
                for day in range(1, 31)
            ],
        }
        for _ in range(2):
            await run_secretary_plan_request(
                intent="long_plan",
                message="arrange IELTS study for the next 30 days",
                today="2026-05-01",
                llm_client=FakeSecretaryLLM(payload),
                auto_project_calendar=True,
            )
        plans = await persistence.list_jarvis_plans(limit=10)
        events = calendar_adapter.get_events_between(
            datetime.fromisoformat("2026-05-01T00:00:00"),
            datetime.fromisoformat("2026-05-31T00:00:00"),
        )
        return plans, events

    plans, events = asyncio.run(scenario())

    assert len(plans) == 1
    assert len(events) == 30
    assert len({(event.title, event.start.isoformat(), event.end.isoformat()) for event in events}) == 30


def test_secretary_short_schedule_auto_projects_calendar_event():
    async def scenario():
        llm = FakeSecretaryLLM({
            "schema_version": "secretary_schedule.v1",
            "intent": "short_schedule",
            "summary": "明晚安排一次雅思听力复习。",
            "items": [{
                "client_item_id": "item-project-1",
                "date": "2026-05-02",
                "start_time": "19:30",
                "end_time": "21:00",
                "title": "雅思听力复习",
                "description": "完成 Section 1-2 并整理错题。",
                "estimated_minutes": 90,
                "priority": "high",
                "reason": "用户指定明晚。",
            }],
        })
        result = await run_secretary_plan_request(
            intent="short_schedule",
            message="明天晚上帮我安排一次雅思听力复习",
            today="2026-05-01",
            llm_client=llm,
            auto_project_calendar=True,
        )
        days = await persistence.list_jarvis_plan_days(plan_id=result["plan"]["id"], limit=10)
        events = calendar_adapter.get_events_between(
            datetime.fromisoformat("2026-05-02T00:00:00"),
            datetime.fromisoformat("2026-05-03T00:00:00"),
        )
        return result, days, events

    result, days, events = asyncio.run(scenario())
    assert len(result["calendar_events"]) == 1
    assert len(events) == 1
    assert events[0].title == "雅思听力复习"
    assert days[0]["calendar_event_id"] == events[0].id


def test_secretary_reschedule_updates_existing_future_days():
    async def scenario():
        plan = await persistence.save_jarvis_plan(
            plan_id="plan-reschedule-mvp",
            title="雅思计划",
            plan_type="long_term",
            status="active",
            source_agent="maxwell",
            original_user_request="雅思计划",
            goal="备考",
            days=[{"id": "day-reschedule-1", "date": "2026-05-02", "title": "旧听力", "start_time": "19:00", "end_time": "20:00"}],
        )
        llm = FakeSecretaryLLM({
            "schema_version": "secretary_reschedule.v1",
            "intent": "reschedule_plan",
            "summary": "已重新安排。",
            "plan_id": plan["id"],
            "days": [{
                "id": "day-reschedule-1",
                "date": "2026-05-03",
                "start_time": "20:00",
                "end_time": "21:00",
                "title": "新听力",
                "description": "重排后继续听力",
                "estimated_minutes": 60,
                "reason": "用户未完成。",
            }],
        })
        result = await run_secretary_plan_request(
            intent="reschedule_plan",
            message="今天没完成，帮我重新安排",
            today="2026-05-01",
            llm_client=llm,
            plan_id=plan["id"],
            auto_project_calendar=False,
        )
        days = await persistence.list_jarvis_plan_days(plan_id=plan["id"], limit=10)
        return result, days

    result, days = asyncio.run(scenario())
    assert result["intent"] == "reschedule_plan"
    assert result["changed_count"] == 1
    assert days[0]["plan_date"] == "2026-05-03"
    assert days[0]["title"] == "新听力"
    assert days[0]["status"] == "rescheduled"


def test_secretary_service_rejects_past_dates_before_writing():
    async def scenario():
        llm = FakeSecretaryLLM({
            "schema_version": "secretary_schedule.v1",
            "intent": "short_schedule",
            "summary": "bad",
            "items": [{"client_item_id": "bad", "date": "2026-04-30", "start_time": "19:30", "end_time": "21:00", "title": "过去任务"}],
        })
        with pytest.raises(ValueError, match="past date"):
            await run_secretary_plan_request(
                intent="short_schedule",
                message="安排过去",
                today="2026-05-01",
                llm_client=llm,
            )
        return await persistence.list_jarvis_plans(limit=10)

    plans = asyncio.run(scenario())
    assert plans == []
