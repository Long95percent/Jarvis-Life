from __future__ import annotations

from datetime import date
from typing import Any


def _date_key(value: Any) -> str:
    return str(value or "")[:10]


def validate_not_past(plan_date: str, *, today: str) -> None:
    target = _date_key(plan_date)
    current = _date_key(today)
    if not target:
        raise ValueError("missing plan date")
    date.fromisoformat(target)
    date.fromisoformat(current)
    if target < current:
        raise ValueError(f"past date is not allowed: {target} < {current}")


def validate_time_range(start_time: str | None, end_time: str | None) -> None:
    if start_time and end_time and str(start_time)[:5] >= str(end_time)[:5]:
        raise ValueError("start_time must be before end_time")


def validate_plan_day_move(original: dict[str, Any], patch: dict[str, Any], *, today: str) -> None:
    plan_date = _date_key(patch.get("plan_date") or original.get("plan_date"))
    start_time = patch.get("start_time", original.get("start_time"))
    end_time = patch.get("end_time", original.get("end_time"))
    validate_not_past(plan_date, today=today)
    validate_time_range(start_time, end_time)
