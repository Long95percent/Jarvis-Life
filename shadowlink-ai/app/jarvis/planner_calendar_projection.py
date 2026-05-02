from __future__ import annotations

from datetime import datetime
from typing import Any

from app.jarvis.persistence import update_jarvis_plan_day
from app.mcp.adapters.calendar_adapter import add_event, get_event, update_event


def _combine_plan_day_datetime(plan_day: dict[str, Any], time_value: str | None, fallback: datetime | None = None) -> datetime | None:
    if not time_value:
        return fallback
    try:
        return datetime.fromisoformat(f"{str(plan_day.get('plan_date') or '')[:10]}T{time_value[:5]}:00")
    except ValueError:
        return fallback


def plan_day_has_projectable_time(day: dict[str, Any]) -> bool:
    return bool(day.get("plan_date") and day.get("start_time") and day.get("end_time"))


async def project_plan_day_to_calendar(
    day: dict[str, Any],
    *,
    source_agent: str | None = None,
    reason: str = "Project plan day to calendar",
) -> dict[str, Any] | None:
    if day.get("calendar_event_id") or not plan_day_has_projectable_time(day):
        return None
    start = datetime.fromisoformat(f"{str(day['plan_date'])[:10]}T{str(day['start_time'])[:5]}:00")
    end = datetime.fromisoformat(f"{str(day['plan_date'])[:10]}T{str(day['end_time'])[:5]}:00")
    event = add_event(
        str(day.get("title") or "计划安排"),
        start,
        end,
        1.0,
        notes=day.get("description") if isinstance(day.get("description"), str) else None,
        source="planner_projection",
        source_agent=source_agent,
        created_reason=reason,
        status="confirmed",
    )
    updated = await update_jarvis_plan_day(
        day["id"],
        {"calendar_event_id": event.id, "status": day.get("status") or "scheduled"},
        event_type="calendar.changed",
    )
    return {"event": event.model_dump(), "plan_day": updated}


async def project_plan_days_to_calendar(
    days: list[dict[str, Any]],
    *,
    source_agent: str | None = None,
    reason: str = "Project plan days to calendar",
) -> list[dict[str, Any]]:
    projected = []
    for day in days:
        if day.get("status") in {"completed", "cancelled", "deleted", "missed"}:
            continue
        result = await project_plan_day_to_calendar(day, source_agent=source_agent, reason=reason)
        if result is not None:
            projected.append(result)
    return projected


def sync_plan_day_calendar_event(plan_day: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any] | None:
    calendar_event_id = plan_day.get("calendar_event_id")
    if not isinstance(calendar_event_id, str) or not calendar_event_id:
        return None

    existing = get_event(calendar_event_id)
    event_patch: dict[str, Any] = {}
    if "title" in patch:
        event_patch["title"] = plan_day.get("title")
    if "description" in patch:
        event_patch["notes"] = plan_day.get("description")
    if "status" in patch:
        if plan_day.get("status") == "cancelled":
            event_patch["status"] = "cancelled"
        elif plan_day.get("status") == "deleted":
            event_patch["status"] = "deleted"
        else:
            event_patch["status"] = "confirmed"
    if any(key in patch for key in ("plan_date", "start_time", "end_time")):
        start_dt = _combine_plan_day_datetime(plan_day, plan_day.get("start_time"), existing.start if existing else None)
        end_dt = _combine_plan_day_datetime(plan_day, plan_day.get("end_time"), existing.end if existing else None)
        if start_dt is not None:
            event_patch["start"] = start_dt
        if end_dt is not None:
            event_patch["end"] = end_dt
    if not event_patch:
        return existing.model_dump() if existing else None
    updated = update_event(calendar_event_id, **event_patch)
    return updated.model_dump() if updated else None
