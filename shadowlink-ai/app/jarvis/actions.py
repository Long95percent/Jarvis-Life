"""Legacy Jarvis action compatibility layer.

Jarvis now routes both read/write operations through the unified ToolRegistry.
This module remains only for backward-compatible imports and legacy
`<jarvis-action>` payloads.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.jarvis.tool_runtime import execute_tool_calls, to_action_results

_ACTION_RE = re.compile(
    r"<jarvis-action>\s*(\{.*?\})\s*</jarvis-action>",
    re.DOTALL | re.IGNORECASE,
)


def strip_action_blocks(text: str) -> tuple[str, list[dict[str, Any]]]:
    """Extract legacy action blocks without executing them."""
    actions: list[dict[str, Any]] = []
    for match in _ACTION_RE.finditer(text):
        raw = match.group(1)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and "type" in data:
            actions.append(data)
    clean_text = _ACTION_RE.sub("", text).strip()
    return clean_text, actions


def _to_tool_call(action: dict[str, Any]) -> dict[str, Any] | None:
    action_type = str(action.get("type", "")).strip()
    if action_type == "calendar.add":
        return {
            "tool_name": "jarvis_calendar_add",
            "arguments": {
                "title": action.get("title", ""),
                "start": action.get("start", ""),
                "end": action.get("end", ""),
                "stress_weight": action.get("stress_weight", 1.0),
            },
        }
    if action_type == "calendar.delete":
        return {
            "tool_name": "jarvis_calendar_delete",
            "arguments": {"event_id": action.get("event_id", "")},
        }
    if action_type == "calendar.update":
        return {
            "tool_name": "jarvis_calendar_update",
            "arguments": {
                key: value
                for key, value in {
                    "event_id": action.get("event_id", ""),
                    "title": action.get("title"),
                    "start": action.get("start"),
                    "end": action.get("end"),
                    "stress_weight": action.get("stress_weight"),
                }.items()
                if value is not None
            },
        }
    if action_type == "context.set":
        return {
            "tool_name": "jarvis_context_update",
            "arguments": {
                key: value
                for key, value in action.items()
                if key in {"stress_level", "schedule_density", "sleep_quality", "mood_trend"}
            },
        }
    return None


async def execute_actions(actions: list[dict[str, Any]], agent_id: str = "alfred") -> list[dict[str, Any]]:
    """Execute legacy actions via the unified registry-backed tool runtime."""
    tool_calls = [call for action in actions if (call := _to_tool_call(action)) is not None]
    results = await execute_tool_calls(agent_id, tool_calls)
    return to_action_results(results)
