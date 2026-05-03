from __future__ import annotations

import json
import re
from typing import Any
from uuid import uuid4

from app.jarvis.persistence import (
    append_maxwell_workbench_log,
    get_jarvis_plan,
    hard_delete_jarvis_plan,
    list_jarvis_plans,
    list_jarvis_plan_days,
    save_jarvis_plan,
    update_jarvis_plan_day,
)
from app.jarvis.planner_guard import validate_plan_day_move
from app.jarvis.planner_calendar_projection import project_plan_days_to_calendar, sync_plan_day_calendar_event
from app.jarvis.secretary_scheduler import (
    parse_secretary_long_plan_response,
    parse_secretary_reschedule_response,
    parse_secretary_schedule_response,
)


def _day_from_schedule_item(item: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "id": item.get("id") or item.get("client_item_id") or f"day_secretary_{uuid4().hex}",
        "date": item["date"],
        "title": item["title"],
        "description": item.get("description"),
        "start_time": item.get("start_time"),
        "end_time": item.get("end_time"),
        "estimated_minutes": item.get("estimated_minutes"),
        "sort_order": item.get("day_index", index),
        "raw_payload": item,
    }


def _validate_days_for_write(days: list[dict[str, Any]], *, today: str) -> None:
    for day in days:
        validate_plan_day_move(
            {"plan_date": day.get("date"), "start_time": day.get("start_time"), "end_time": day.get("end_time")},
            {"plan_date": day.get("date"), "start_time": day.get("start_time"), "end_time": day.get("end_time")},
            today=today,
        )


def _normalize_secretary_identity(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"\s+", "", text)
    return re.sub(r"[\W_]+", "", text, flags=re.UNICODE)


def _secretary_identity_candidates(*values: Any) -> set[str]:
    return {normalized for value in values if (normalized := _normalize_secretary_identity(value))}


async def _replace_existing_secretary_plan(
    *,
    plan_type: str,
    title: str,
    goal: str | None,
    original_user_request: str,
    start_date: str | None,
    target_date: str | None,
) -> str | None:
    candidates = _secretary_identity_candidates(title, goal, original_user_request)
    if not candidates:
        return None
    for plan in await list_jarvis_plans(limit=500):
        if str(plan.get("plan_type") or "") != plan_type:
            continue
        horizon = plan.get("time_horizon") if isinstance(plan.get("time_horizon"), dict) else {}
        same_start = not start_date or not horizon.get("start_date") or str(horizon.get("start_date"))[:10] == start_date[:10]
        same_target = not target_date or not horizon.get("target_date") or str(horizon.get("target_date"))[:10] == target_date[:10]
        if not (same_start and same_target):
            continue
        existing_candidates = _secretary_identity_candidates(plan.get("title"), plan.get("goal"), plan.get("original_user_request"))
        if candidates & existing_candidates:
            plan_id = str(plan["id"])
            await hard_delete_jarvis_plan(plan_id)
            return plan_id
    return None


async def _call_secretary_llm(*, llm_client: Any, intent: str, message: str, context: dict[str, Any]) -> str:
    prompt = (
        "You are Maxwell, the user's schedule secretary. Return strict JSON only. "
        "Do not include Markdown fences. "
        f"Intent: {intent}\n"
        f"User request: {message}\n"
        f"Context: {json.dumps(context, ensure_ascii=False, default=str)}"
    )
    raw = await llm_client.chat(
        message=prompt,
        system_prompt="You are Maxwell. Return only the requested schedule JSON schema.",
        temperature=0.2,
        max_tokens=4000,
    )
    return str(raw)


async def _run_short_schedule(*, parsed: dict[str, Any], message: str, today: str, auto_project_calendar: bool) -> dict[str, Any]:
    days = [_day_from_schedule_item(item, index) for index, item in enumerate(parsed["items"])]
    _validate_days_for_write(days, today=today)
    first = days[0]
    title = str(first.get("title") or "秘书短期安排")
    goal = str(parsed.get("summary") or "")
    existing_plan_id = await _replace_existing_secretary_plan(
        plan_type="short_term",
        title=title,
        goal=goal,
        original_user_request=message,
        start_date=str(first.get("date") or ""),
        target_date=str(days[-1].get("date") or ""),
    )
    plan = await save_jarvis_plan(
        plan_id=existing_plan_id or f"plan_secretary_short_{uuid4().hex}",
        title=title,
        plan_type="short_term",
        status="active",
        source_agent="maxwell",
        original_user_request=message,
        goal=goal,
        time_horizon={"start_date": first.get("date"), "target_date": days[-1].get("date")},
        raw_payload={"schema": parsed.get("schema_version"), "secretary": parsed},
        days=days,
    )
    plan_days = await list_jarvis_plan_days(plan_id=plan["id"], limit=2000)
    calendar_events = []
    if auto_project_calendar:
        calendar_events = await project_plan_days_to_calendar(plan_days, source_agent=plan.get("source_agent"), reason="Secretary short schedule projection")
        plan_days = await list_jarvis_plan_days(plan_id=plan["id"], limit=2000)
    return {"intent": "short_schedule", "summary": parsed.get("summary"), "plan": plan, "plan_days": plan_days, "calendar_events": calendar_events, "warnings": []}


async def _run_long_plan(*, parsed: dict[str, Any], message: str, today: str, auto_project_calendar: bool) -> dict[str, Any]:
    days = [_day_from_schedule_item(item, index) for index, item in enumerate(parsed["days"])]
    _validate_days_for_write(days, today=today)
    plan_payload = parsed["plan"]
    title = str(plan_payload["title"])
    plan_type = str(plan_payload.get("plan_type") or "long_term")
    goal = str(plan_payload.get("goal") or "")
    start_date = str(plan_payload.get("start_date") or days[0].get("date") or "")
    target_date = str(plan_payload.get("target_date") or days[-1].get("date") or "")
    existing_plan_id = await _replace_existing_secretary_plan(
        plan_type=plan_type,
        title=title,
        goal=goal,
        original_user_request=message,
        start_date=start_date,
        target_date=target_date,
    )
    plan = await save_jarvis_plan(
        plan_id=existing_plan_id or f"plan_secretary_long_{uuid4().hex}",
        title=title,
        plan_type=plan_type,
        status="active",
        source_agent="maxwell",
        original_user_request=message,
        goal=goal,
        time_horizon={"start_date": start_date, "target_date": target_date},
        raw_payload={"schema": parsed.get("schema_version"), "secretary": parsed},
        days=days,
    )
    plan_days = await list_jarvis_plan_days(plan_id=plan["id"], limit=2000)
    calendar_events = []
    if auto_project_calendar:
        calendar_events = await project_plan_days_to_calendar(plan_days, source_agent=plan.get("source_agent"), reason="Secretary long plan projection")
        plan_days = await list_jarvis_plan_days(plan_id=plan["id"], limit=2000)
    return {"intent": "long_plan", "summary": parsed.get("summary") or plan_payload.get("goal"), "plan": plan, "plan_days": plan_days, "calendar_events": calendar_events, "warnings": []}


async def _run_reschedule(*, parsed: dict[str, Any], message: str, today: str, plan_id: str | None, auto_project_calendar: bool) -> dict[str, Any]:
    target_plan_id = plan_id or str(parsed.get("plan_id") or "")
    plan = await get_jarvis_plan(target_plan_id)
    if plan is None:
        raise ValueError(f"plan not found: {target_plan_id}")
    existing_days = await list_jarvis_plan_days(plan_id=target_plan_id, limit=2000)
    existing_by_id = {day["id"]: day for day in existing_days}
    changed = []
    for item in parsed["days"]:
        original = existing_by_id.get(item["id"])
        if original is None:
            raise ValueError(f"unknown plan day id: {item['id']}")
        patch = {
            "plan_date": item["date"],
            "start_time": item.get("start_time"),
            "end_time": item.get("end_time"),
            "title": item.get("title"),
            "description": item.get("description"),
            "estimated_minutes": item.get("estimated_minutes"),
            "status": "rescheduled",
            "reschedule_reason": item.get("reason") or message,
        }
        validate_plan_day_move(original, patch, today=today)
        updated = await update_jarvis_plan_day(original["id"], patch, event_type="plan.rescheduled")
        if updated:
            if auto_project_calendar:
                sync_plan_day_calendar_event(updated, patch)
            changed.append(updated)
            await append_maxwell_workbench_log(
                plan_day_id=updated.get("id"),
                event="完成延期重排",
                detail=f"{original.get('plan_date')} 调整到 {updated.get('plan_date')}；原因：{patch.get('reschedule_reason') or '用户请求秘书重排'}",
                category="secretary_reschedule",
                source="maxwell_skill",
            )
    changed_count = len(changed)
    calendar_events = []
    if auto_project_calendar:
        calendar_events = await project_plan_days_to_calendar(changed, source_agent=plan.get("source_agent"), reason="Secretary reschedule projection")
        changed = await list_jarvis_plan_days(plan_id=target_plan_id, limit=2000)
    return {"intent": "reschedule_plan", "summary": parsed.get("summary"), "plan": plan, "changed_count": changed_count, "plan_days": changed, "calendar_events": calendar_events, "warnings": []}


async def run_secretary_plan_request(
    *,
    intent: str,
    message: str,
    today: str,
    llm_client: Any,
    plan_id: str | None = None,
    plan_day_ids: list[str] | None = None,
    timezone: str | None = None,
    auto_project_calendar: bool = True,
) -> dict[str, Any]:
    context = {"today": today[:10], "timezone": timezone, "plan_id": plan_id, "plan_day_ids": plan_day_ids or []}
    raw = await _call_secretary_llm(llm_client=llm_client, intent=intent, message=message, context=context)
    if intent == "short_schedule":
        return await _run_short_schedule(parsed=parse_secretary_schedule_response(raw), message=message, today=today[:10], auto_project_calendar=auto_project_calendar)
    if intent == "long_plan":
        return await _run_long_plan(parsed=parse_secretary_long_plan_response(raw), message=message, today=today[:10], auto_project_calendar=auto_project_calendar)
    if intent == "reschedule_plan":
        return await _run_reschedule(parsed=parse_secretary_reschedule_response(raw), message=message, today=today[:10], plan_id=plan_id, auto_project_calendar=auto_project_calendar)
    raise ValueError(f"unsupported secretary planning intent: {intent}")
