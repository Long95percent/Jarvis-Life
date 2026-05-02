from __future__ import annotations

import json
from datetime import date
from typing import Any, Callable


def _load_strict_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```") or text.endswith("```"):
        raise ValueError("secretary response must be strict JSON without Markdown fences")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("secretary response must be strict JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("secretary response must be a JSON object")
    return data


def _require_schema(data: dict[str, Any], schema_version: str) -> None:
    if data.get("schema_version") != schema_version:
        raise ValueError(f"expected schema_version {schema_version}")


def _require_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"missing {field}")
    return text


def _require_date(value: Any, field: str) -> str:
    text = _require_text(value, field)[:10]
    date.fromisoformat(text)
    return text


def _validate_time_range(item: dict[str, Any]) -> None:
    start = item.get("start_time")
    end = item.get("end_time")
    if start is None or end is None:
        raise ValueError("missing start_time or end_time")
    if str(start)[:5] >= str(end)[:5]:
        raise ValueError("start_time must be before end_time")


def _validate_schedule_item(item: Any, *, require_id: bool = False) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError("schedule item must be an object")
    if require_id:
        _require_text(item.get("id"), "id")
    _require_date(item.get("date"), "date")
    _require_text(item.get("title"), "title")
    _validate_time_range(item)
    return item


def _validate_items(data: dict[str, Any], key: str, validator: Callable[[Any], dict[str, Any]]) -> list[dict[str, Any]]:
    items = data.get(key)
    if not isinstance(items, list) or not items:
        raise ValueError(f"{key} must be a non-empty list")
    return [validator(item) for item in items]


def parse_secretary_schedule_response(raw: str) -> dict[str, Any]:
    data = _load_strict_json_object(raw)
    _require_schema(data, "secretary_schedule.v1")
    _require_text(data.get("intent"), "intent")
    _require_text(data.get("summary"), "summary")
    data["items"] = _validate_items(data, "items", lambda item: _validate_schedule_item(item))
    return data


def parse_secretary_long_plan_response(raw: str) -> dict[str, Any]:
    data = _load_strict_json_object(raw)
    _require_schema(data, "secretary_long_plan.v1")
    _require_text(data.get("intent"), "intent")
    plan = data.get("plan")
    if not isinstance(plan, dict):
        raise ValueError("plan must be an object")
    _require_text(plan.get("title"), "plan.title")
    _require_text(plan.get("goal"), "plan.goal")
    _require_text(plan.get("plan_type"), "plan.plan_type")
    _require_date(plan.get("start_date"), "plan.start_date")
    _require_date(plan.get("target_date"), "plan.target_date")
    data["days"] = _validate_items(data, "days", lambda item: _validate_schedule_item(item))
    return data


def parse_secretary_reschedule_response(raw: str) -> dict[str, Any]:
    data = _load_strict_json_object(raw)
    _require_schema(data, "secretary_reschedule.v1")
    _require_text(data.get("intent"), "intent")
    _require_text(data.get("summary"), "summary")
    _require_text(data.get("plan_id"), "plan_id")
    data["days"] = _validate_items(data, "days", lambda item: _validate_schedule_item(item, require_id=True))
    return data
