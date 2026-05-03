from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Any

import structlog

from app.jarvis.models import ProactiveMessage
from app.jarvis.persistence import (
    append_maxwell_workbench_log,
    get_jarvis_plan,
    has_proactive_routine_run,
    list_background_task_days,
    list_jarvis_plan_days,
    mark_overdue_planner_days_missed,
    push_planner_days_to_workbench,
    record_agent_event,
    save_proactive_message,
    save_proactive_routine_run,
    save_care_trigger_and_intervention,
    update_background_task_day,
    update_jarvis_plan_day,
)
from app.mcp.adapters.calendar_adapter import get_event, update_event

logger = structlog.get_logger("jarvis.planner_maintenance")

PLANNER_MAINTENANCE_ROUTINE_ID = "planner_daily_maintenance"
ACTIVE_PLAN_DAY_STATUSES = {"pending", "scheduled", "pushed", "rescheduled"}
ACTIVE_BACKGROUND_TASK_DAY_STATUSES = {"pending", "pushed", "rescheduled"}


def _json_from_text(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped, flags=re.IGNORECASE).strip()
        stripped = re.sub(r"```$", "", stripped).strip()
    try:
        data = json.loads(stripped)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
        if not match:
            return {}
        try:
            data = json.loads(match.group(0))
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}


def _sync_calendar_for_day(day: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any] | None:
    event_id = day.get("calendar_event_id")
    if not isinstance(event_id, str) or not event_id:
        return None
    existing = get_event(event_id)
    event_patch: dict[str, Any] = {}
    if patch.get("title"):
        event_patch["title"] = patch["title"]
    if "description" in patch:
        event_patch["notes"] = patch.get("description")
    plan_date = str(patch.get("plan_date") or day.get("plan_date") or "")[:10]
    start_time = patch.get("start_time", day.get("start_time"))
    end_time = patch.get("end_time", day.get("end_time"))
    if plan_date and start_time:
        event_patch["start"] = datetime.fromisoformat(f"{plan_date}T{str(start_time)[:5]}:00")
    elif existing is not None and plan_date:
        event_patch["start"] = datetime.fromisoformat(f"{plan_date}T{existing.start.time().isoformat(timespec='minutes')}:00")
    if plan_date and end_time:
        event_patch["end"] = datetime.fromisoformat(f"{plan_date}T{str(end_time)[:5]}:00")
    elif existing is not None and plan_date:
        event_patch["end"] = datetime.fromisoformat(f"{plan_date}T{existing.end.time().isoformat(timespec='minutes')}:00")
    if not event_patch:
        return existing.model_dump() if existing else None
    updated = update_event(event_id, **event_patch)
    return updated.model_dump() if updated else None


def _fallback_reschedule_days(future_days: list[dict[str, Any]], missed_count: int, today: str) -> dict[str, Any]:
    base = datetime.fromisoformat(f"{today[:10]}T00:00:00").date()
    days: list[dict[str, Any]] = []
    for index, day in enumerate(future_days):
        original = datetime.fromisoformat(f"{str(day.get('plan_date'))[:10]}T00:00:00").date()
        target = max(original + timedelta(days=missed_count), base + timedelta(days=index))
        days.append({
            "id": day["id"],
            "plan_date": target.isoformat(),
            "start_time": day.get("start_time"),
            "end_time": day.get("end_time"),
            "title": day.get("title"),
            "description": day.get("description"),
            "reason": "LLM ????? missed ????????????",
        })
    return {"days": days, "message": "?? missed ?????????", "fallback": True}


def _build_reschedule_prompt(plan: dict[str, Any], missed_days: list[dict[str, Any]], future_days: list[dict[str, Any]], today: str) -> str:
    payload = {
        "today": today[:10],
        "plan": {
            "id": plan.get("id"),
            "title": plan.get("title"),
            "goal": plan.get("goal"),
            "time_horizon": plan.get("time_horizon"),
        },
        "missed_days": [
            {"id": day.get("id"), "plan_date": day.get("plan_date"), "title": day.get("title"), "start_time": day.get("start_time"), "end_time": day.get("end_time")}
            for day in missed_days
        ],
        "future_days": [
            {"id": day.get("id"), "plan_date": day.get("plan_date"), "title": day.get("title"), "description": day.get("description"), "start_time": day.get("start_time"), "end_time": day.get("end_time"), "estimated_minutes": day.get("estimated_minutes")}
            for day in future_days
        ],
    }
    schema = {
        "days": [{
            "id": "existing future_days id",
            "plan_date": "YYYY-MM-DD",
            "start_time": "HH:MM or null",
            "end_time": "HH:MM or null",
            "title": "updated title",
            "description": "updated description",
            "reason": "why this move is appropriate",
        }],
        "message": "one concise user-facing sentence",
    }
    return (
        "You are Maxwell, the personal secretary. Some plan days were missed. "
        "Reschedule only the future_days listed in the input. Do not modify missed or completed history. "
        "Every returned date must be >= today. Preserve rhythm and duration when possible. "
        "Return strict JSON only, no Markdown.\n"
        f"Expected JSON schema: {json.dumps(schema, ensure_ascii=False)}\n"
        f"Input: {json.dumps(payload, ensure_ascii=False, default=str)}"
    )


async def _generate_reschedule(plan: dict[str, Any], missed_days: list[dict[str, Any]], future_days: list[dict[str, Any]], today: str, llm_client: Any | None) -> dict[str, Any]:
    if llm_client is None:
        return _fallback_reschedule_days(future_days, len(missed_days), today)
    prompt = _build_reschedule_prompt(plan, missed_days, future_days, today)
    raw = await llm_client.chat(
        message=prompt,
        system_prompt="?? Maxwell???????????????? JSON???? Markdown?",
        temperature=0.2,
        max_tokens=1800,
    )
    parsed = _json_from_text(str(raw))
    days = parsed.get("days") if isinstance(parsed.get("days"), list) else []
    valid_ids = {day["id"] for day in future_days}
    cleaned = []
    for item in days:
        if not isinstance(item, dict) or item.get("id") not in valid_ids:
            continue
        plan_date = str(item.get("plan_date") or "")[:10]
        if not plan_date or plan_date < today[:10]:
            continue
        cleaned.append(item)
    if not cleaned:
        fallback = _fallback_reschedule_days(future_days, len(missed_days), today)
        fallback["llm_raw"] = str(raw)
        fallback["fallback_reason"] = "LLM ??????????? days?"
        return fallback
    return {"days": cleaned, "message": str(parsed.get("message") or "??? missed ?????????"), "fallback": False, "llm_raw": str(raw)}


async def reschedule_plan_after_missed(plan_id: str, missed_days: list[dict[str, Any]], today: str, llm_client: Any | None = None) -> dict[str, Any]:
    plan = await get_jarvis_plan(plan_id)
    if plan is None or plan.get("status") == "cancelled":
        return {"plan_id": plan_id, "changed_count": 0, "skipped": "plan_not_found_or_cancelled"}
    all_days = await list_jarvis_plan_days(plan_id=plan_id, limit=2000)
    future_days = [
        day for day in all_days
        if str(day.get("plan_date") or "")[:10] >= today[:10]
        and day.get("status") in ACTIVE_PLAN_DAY_STATUSES
    ]
    if not future_days:
        await record_agent_event(
            event_type="plan.reschedule.skipped",
            agent_id="maxwell",
            plan_id=plan_id,
            payload={"reason": "no_future_days", "missed_day_ids": [day.get("id") for day in missed_days]},
        )
        return {"plan_id": plan_id, "changed_count": 0, "skipped": "no_future_days"}
    generated = await _generate_reschedule(plan, missed_days, future_days, today, llm_client)
    by_id = {day["id"]: day for day in future_days}
    changed = []
    for item in generated.get("days", []):
        original = by_id.get(item.get("id"))
        if original is None:
            continue
        patch = {
            "plan_date": str(item.get("plan_date") or original.get("plan_date"))[:10],
            "start_time": item.get("start_time", original.get("start_time")),
            "end_time": item.get("end_time", original.get("end_time")),
            "title": str(item.get("title") or original.get("title") or "????"),
            "description": item.get("description", original.get("description")),
            "status": "rescheduled",
            "reschedule_reason": str(item.get("reason") or "Maxwell ?? missed ??????"),
        }
        updated = await update_jarvis_plan_day(original["id"], patch, event_type="plan.rescheduled")
        if updated is None:
            continue
        calendar_event = _sync_calendar_for_day(updated, patch)
        changed.append({"before": original, "after": updated, "calendar_event": calendar_event})
        await append_maxwell_workbench_log(
            plan_day_id=updated.get("id"),
            event="逾期后自动重排",
            detail=f"{original.get('plan_date')} 调整到 {updated.get('plan_date')}；原因：{patch.get('reschedule_reason')}",
            category="auto_maintenance",
            source="planner_daily_maintenance",
        )
    await record_agent_event(
        event_type="plan.rescheduled",
        agent_id="maxwell",
        plan_id=plan_id,
        payload={
            "trigger": "missed_days",
            "today": today[:10],
            "missed_day_ids": [day.get("id") for day in missed_days],
            "changed_count": len(changed),
            "message": generated.get("message"),
            "fallback": generated.get("fallback", False),
        },
    )
    if changed:
        message = str(generated.get("message") or f"I noticed {len(missed_days)} missed plan day(s) and rescheduled the remaining plan.")
        await save_proactive_message(ProactiveMessage(
            agent_id="maxwell",
            agent_name="Maxwell",
            content=message,
            trigger="planner:missed_reschedule",
            priority="normal",
        ))
        await save_care_trigger_and_intervention(
            trigger_type="planner_missed_reschedule",
            severity="medium" if len(missed_days) < 3 else "high",
            reason="User missed one or more plan days; Maxwell automatically rescheduled future plan days.",
            evidence_ids=[{"source": "jarvis_plan_days", "id": day.get("id"), "plan_id": plan_id} for day in missed_days],
            content=f"I noticed you did not finish {len(missed_days)} planned item(s). Maxwell has already rescheduled the remaining plan so you do not need to rebuild it manually.",
            suggested_action={"type": "open_calendar_tasks", "plan_id": plan_id, "changed_count": len(changed)},
        )
    return {"plan_id": plan_id, "changed_count": len(changed), "changed": changed, "message": generated.get("message"), "fallback": generated.get("fallback", False)}


async def reschedule_background_task_after_missed(task_id: str, missed_days: list[dict[str, Any]], today: str) -> dict[str, Any]:
    all_days = await list_background_task_days(task_id=task_id, limit=2000)
    future_days = [
        day for day in all_days
        if str(day.get("plan_date") or "")[:10] >= today[:10]
        and str(day.get("status") or "") in ACTIVE_BACKGROUND_TASK_DAY_STATUSES
    ]
    if not future_days:
        return {"task_id": task_id, "changed_count": 0, "changed": [], "skipped": "no_future_days"}

    missed_count = max(1, len(missed_days))
    base = datetime.fromisoformat(f"{today[:10]}T00:00:00").date()
    changed: list[dict[str, Any]] = []
    for index, day in enumerate(future_days):
        original = datetime.fromisoformat(f"{str(day.get('plan_date'))[:10]}T00:00:00").date()
        target = max(original + timedelta(days=missed_count), base + timedelta(days=index))
        updated = await update_background_task_day(day["id"], {
            "plan_date": target.isoformat(),
            "start_time": day.get("start_time"),
            "end_time": day.get("end_time"),
            "status": "rescheduled",
        })
        if updated:
            await append_maxwell_workbench_log(
                task_day_id=updated["id"],
                event="自动延期整理",
                detail=f"{day.get('plan_date')} 调整到 {updated.get('plan_date')}；原因：前序 {len(missed_days)} 项逾期未完成",
                category="auto_maintenance",
                source="planner_daily_maintenance",
            )
            changed.append(updated)
    if changed:
        await record_agent_event(
            event_type="background_task.rescheduled",
            agent_id="maxwell",
            payload={"task_id": task_id, "today": today[:10], "missed_count": len(missed_days), "changed_count": len(changed)},
        )
    return {"task_id": task_id, "changed_count": len(changed), "changed": changed, "message": f"Maxwell 已整理长期任务，顺延 {len(changed)} 个后续执行日。"}


async def run_planner_daily_maintenance(
    *,
    today: str,
    llm_client: Any | None = None,
    auto_reschedule: bool = True,
    push_today: bool = True,
) -> dict[str, Any]:
    missed = await mark_overdue_planner_days_missed(today)
    plan_days = missed.get("plan_days", [])
    by_plan: dict[str, list[dict[str, Any]]] = {}
    for day in plan_days:
        plan_id = day.get("plan_id")
        if isinstance(plan_id, str) and plan_id:
            by_plan.setdefault(plan_id, []).append(day)
    rescheduled = []
    if auto_reschedule:
        for plan_id, days in by_plan.items():
            rescheduled.append(await reschedule_plan_after_missed(plan_id, days, today, llm_client=llm_client))
    background_by_task: dict[str, list[dict[str, Any]]] = {}
    for day in missed.get("background_task_days", []):
        task_id = day.get("task_id")
        if isinstance(task_id, str) and task_id:
            background_by_task.setdefault(task_id, []).append(day)
    background_rescheduled = []
    if auto_reschedule:
        for task_id, days in background_by_task.items():
            background_rescheduled.append(await reschedule_background_task_after_missed(task_id, days, today))
    pushed = await push_planner_days_to_workbench(today) if push_today else []
    return {"today": today[:10], "missed": missed, "rescheduled": rescheduled, "background_rescheduled": background_rescheduled, "pushed_count": len(pushed), "pushed": pushed}


async def run_planner_daily_maintenance_once(
    *,
    today: str,
    llm_client: Any | None = None,
    auto_reschedule: bool = True,
    push_today: bool = True,
) -> dict[str, Any]:
    run_date = today[:10]
    if await has_proactive_routine_run(PLANNER_MAINTENANCE_ROUTINE_ID, run_date):
        return {"today": run_date, "skipped": "already_ran"}
    result = await run_planner_daily_maintenance(
        today=run_date,
        llm_client=llm_client,
        auto_reschedule=auto_reschedule,
        push_today=push_today,
    )
    await save_proactive_routine_run(
        routine_id=PLANNER_MAINTENANCE_ROUTINE_ID,
        run_date=run_date,
        message_id=None,
    )
    return result
