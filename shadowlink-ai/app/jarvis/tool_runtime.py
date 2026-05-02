"""Jarvis tool runtime — role-based tool discovery and execution."""

from __future__ import annotations

import json
import re
import shlex
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from typing import Any

from app.core.dependencies import get_resource
from app.jarvis.agents import get_agent
from app.models.mcp import ToolInfo

_TOOL_BLOCK_RE = re.compile(
    r"<jarvis-tool>\s*(\{.*?\})\s*</jarvis-tool>",
    re.DOTALL | re.IGNORECASE,
)
_MODEL_TOOL_CALL_RE = re.compile(
    r"<tool_call\s+name=[\"']([^\"']+)[\"']\s*>\s*(\{.*?\})\s*</tool_call>",
    re.DOTALL | re.IGNORECASE,
)
_MODEL_TOOL_CALLS_BLOCK_RE = re.compile(
    r"<tool_calls>.*?</tool_calls>",
    re.DOTALL | re.IGNORECASE,
)
_LEGACY_ACTION_BLOCK_RE = re.compile(
    r"<jarvis-action>\s*(\{.*?\})\s*</jarvis-action>",
    re.DOTALL | re.IGNORECASE,
)
_EXECUTE_BASH_BLOCK_RE = re.compile(
    r"<execute_bash>\s*<arg\s+name=[\"']command[\"']>\s*(.*?)\s*</arg>\s*</execute_bash>",
    re.DOTALL | re.IGNORECASE,
)
_MAX_TOOL_CALLS_PER_TURN = 5

_CONFIRMATION_TYPE_BY_TOOL = {
    "jarvis_calendar_add": "calendar.add",
    "jarvis_calendar_delete": "calendar.delete",
    "jarvis_calendar_update": "calendar.update",
    "jarvis_plan_activity_slot": "calendar.add",
    "jarvis_context_update": "context.set",
    "jarvis_checkin_schedule": "checkin.schedule",
    "jarvis_mood_journal": "mood.journal",
    "jarvis_task_plan_decompose": "task.plan",
}


def _get_registry():
    return get_resource("tool_registry")


def _parse_iso_datetime(raw: Any) -> datetime | None:
    if not raw:
        return None
    try:
        value = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _as_naive_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _timestamp(value: datetime | None) -> float:
    normalized = _as_naive_utc(value)
    return normalized.timestamp() if normalized is not None else 0.0


def _build_schedule_guard(arguments: dict[str, Any]) -> dict[str, Any] | None:
    start = _parse_iso_datetime(arguments.get("start"))
    end = _parse_iso_datetime(arguments.get("end"))
    if start is None or end is None:
        return None

    now = datetime.utcnow()
    duration_minutes = max(15, int((_timestamp(end) - _timestamp(start)) / 60))
    horizon_hours = max(24, int((_timestamp(end) - now.timestamp()) / 3600) + 48)
    try:
        from app.mcp.adapters.calendar_adapter import get_upcoming_events

        events = get_upcoming_events(hours_ahead=horizon_hours)
    except Exception:
        events = []

    conflicts: list[dict[str, Any]] = []
    for event in events:
        event_start = _as_naive_utc(getattr(event, "start", None))
        event_end = _as_naive_utc(getattr(event, "end", None))
        if event_start is None or event_end is None:
            continue
        if _timestamp(event_end) > _timestamp(start) and _timestamp(event_start) < _timestamp(end):
            conflicts.append({
                "id": getattr(event, "id", None),
                "title": getattr(event, "title", "已有日程"),
                "start": event_start.isoformat(),
                "end": event_end.isoformat(),
                "stress_weight": getattr(event, "stress_weight", 1.0),
            })

    window_start = max(now, start - timedelta(hours=12))
    window_end = end + timedelta(hours=36)
    sorted_events = sorted(
        [
            item for item in events
            if _as_naive_utc(getattr(item, "start", None)) is not None and _as_naive_utc(getattr(item, "end", None)) is not None
            and _timestamp(getattr(item, "end")) > _timestamp(window_start)
            and _timestamp(getattr(item, "start")) < _timestamp(window_end)
        ],
        key=lambda item: _timestamp(getattr(item, "start")),
    )
    alternatives: list[dict[str, str]] = []
    cursor = window_start
    buffer = timedelta(minutes=15)
    required_seconds = duration_minutes * 60
    for event in sorted_events:
        event_start = _as_naive_utc(getattr(event, "start", None))
        event_end = _as_naive_utc(getattr(event, "end", None))
        if event_start is None or event_end is None:
            continue
        gap_end = event_start - buffer
        if _timestamp(gap_end) - _timestamp(cursor) >= required_seconds:
            alt_end = cursor + timedelta(minutes=duration_minutes)
            alternatives.append({"start": cursor.isoformat(), "end": alt_end.isoformat()})
        cursor = max(cursor, event_end + buffer)
        if len(alternatives) >= 3:
            break
    if len(alternatives) < 3 and _timestamp(window_end) - _timestamp(cursor) >= required_seconds:
        alternatives.append({"start": cursor.isoformat(), "end": (cursor + timedelta(minutes=duration_minutes)).isoformat()})

    is_past = _timestamp(start) <= now.timestamp()
    density_score = sum(float(getattr(event, "stress_weight", 1.0) or 1.0) for event in sorted_events)
    recommendation = "keep"
    reasons: list[str] = []
    if is_past:
        recommendation = "move"
        reasons.append("开始时间已经早于当前时间")
    if conflicts:
        recommendation = "move"
        reasons.append(f"与 {len(conflicts)} 条已有日程冲突")
    if density_score >= 6:
        if recommendation == "keep":
            recommendation = "review"
        reasons.append("附近日程密度偏高，建议留出缓冲")

    return {
        "checked": True,
        "recommendation": recommendation,
        "summary": "；".join(reasons) if reasons else "未发现明显时间冲突，安排可执行。",
        "conflicts": conflicts,
        "alternatives": alternatives[:3],
    }


def _deferred_confirmation_result(
    *,
    tool_name: str,
    description: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    confirmation_arguments = dict(arguments)
    if tool_name == "jarvis_calendar_add":
        schedule_guard = _build_schedule_guard(confirmation_arguments)
        if schedule_guard is not None:
            confirmation_arguments["schedule_guard"] = schedule_guard
    return {
        "tool_name": tool_name,
        "success": True,
        "requires_confirmation": True,
        "confirmation_id": uuid4().hex,
        "description": description,
        "arguments": confirmation_arguments,
    }


def get_allowed_tool_names(agent_id: str) -> list[str]:
    agent = get_agent(agent_id)
    return list(agent.get("tool_whitelist", []))


def list_agent_tools(agent_id: str) -> list[ToolInfo]:
    registry = _get_registry()
    if registry is None:
        return []

    tools: list[ToolInfo] = []
    for tool_name in get_allowed_tool_names(agent_id):
        result = registry.get_tool(tool_name)
        if result is not None:
            tools.append(result[0])
    return tools


def build_toolkit_prompt(agent_id: str) -> str:
    tools = list_agent_tools(agent_id)
    if not tools:
        return ""

    lines = [
        "## 专属工具包",
        "你只能使用下方角色白名单工具；如果不需要最新数据或外部动作，请直接回答。",
        "如果需要工具，请只输出一个或多个 `<jarvis-tool>{...}</jarvis-tool>` 块，不要夹带其它文字。",
        "不要输出 `<execute_bash>`、shell 命令、代码块或伪终端命令；这些不会直接展示给用户。",
        "每个块格式固定为：",
        '<jarvis-tool>{"tool_name":"工具名","arguments":{"参数名":"参数值"}}</jarvis-tool>',
        f"单轮最多调用 {_MAX_TOOL_CALLS_PER_TURN} 个工具；禁止调用白名单之外的工具。",
        "凡是会改动日程或生活状态的写入工具，只能在用户明确要求执行时调用。",
        "",
        "### 可用工具",
    ]

    for tool in tools:
        schema = tool.input_schema or {}
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        arg_parts: list[str] = []
        for arg_name, meta in properties.items():
            arg_type = meta.get("type", "any")
            desc = meta.get("description", "")
            required_mark = "必填" if arg_name in required else "选填"
            detail = f"{arg_name}:{arg_type}（{required_mark}）"
            if desc:
                detail += f" {desc}"
            arg_parts.append(detail)
        args_text = "；".join(arg_parts) if arg_parts else "无参数"
        mode_text = "写操作" if tool.requires_confirmation else "只读"
        lines.append(f"- `{tool.name}`：{tool.description} [{mode_text}] 参数：{args_text}")

    lines.extend([
        "",
        "注意：工具返回后，你需要基于工具结果重新组织最终回复，不要把 `<jarvis-tool>` 标签展示给用户。",
    ])
    return "\n".join(lines)

def strip_tool_blocks(text: str) -> tuple[str, list[dict[str, Any]]]:
    calls: list[dict[str, Any]] = []

    for match in _TOOL_BLOCK_RE.finditer(text):
        raw = match.group(1)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue

        if not isinstance(data, dict):
            continue

        tool_name = data.get("tool_name")
        arguments = data.get("arguments", {})
        if not isinstance(tool_name, str):
            continue
        if not isinstance(arguments, dict):
            arguments = {}
        calls.append({"tool_name": tool_name, "arguments": arguments})

    for match in _MODEL_TOOL_CALL_RE.finditer(text):
        tool_name = match.group(1).strip()
        raw_arguments = match.group(2)
        try:
            arguments = json.loads(raw_arguments)
        except json.JSONDecodeError:
            arguments = {}
        if not isinstance(arguments, dict):
            arguments = {}
        if tool_name:
            calls.append({"tool_name": tool_name, "arguments": arguments})

    clean_text = _TOOL_BLOCK_RE.sub("", text)
    clean_text = _MODEL_TOOL_CALLS_BLOCK_RE.sub("", clean_text).strip()
    return clean_text, calls


def _legacy_action_to_tool_call(action: dict[str, Any]) -> dict[str, Any] | None:
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
        args = {
            "event_id": action.get("event_id", ""),
            "title": action.get("title"),
            "start": action.get("start"),
            "end": action.get("end"),
            "stress_weight": action.get("stress_weight"),
        }
        return {
            "tool_name": "jarvis_calendar_update",
            "arguments": {key: value for key, value in args.items() if value is not None},
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


def _execute_bash_to_tool_call(command: str) -> dict[str, Any] | None:
    try:
        parts = shlex.split(command, posix=False)
    except ValueError:
        return None

    if len(parts) < 4 or parts[0] != "jarvis_calendar_add":
        return None

    arguments: dict[str, Any] = {
        "start": parts[1].strip('"'),
        "end": parts[2].strip('"'),
        "title": parts[3].strip('"'),
    }
    index = 4
    while index < len(parts):
        key = parts[index]
        next_value = parts[index + 1] if index + 1 < len(parts) else ""
        if key == "--notes" and next_value:
            arguments["notes"] = next_value.strip('"')
            index += 2
            continue
        if key == "--location" and next_value:
            arguments["location"] = next_value.strip('"')
            index += 2
            continue
        if key == "--created-reason" and next_value:
            arguments["created_reason"] = next_value.strip('"')
            index += 2
            continue
        if key == "--route-required":
            arguments["route_required"] = str(next_value).lower() == "true"
            index += 2
            continue
        if key == "--requires-confirmation":
            index += 2
            continue
        index += 1

    return {"tool_name": "jarvis_calendar_add", "arguments": arguments}


def strip_tool_like_blocks(text: str) -> tuple[str, list[dict[str, Any]]]:
    clean_text, calls = strip_tool_blocks(text)
    legacy_calls: list[dict[str, Any]] = []

    for match in _LEGACY_ACTION_BLOCK_RE.finditer(clean_text):
        raw = match.group(1)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        mapped = _legacy_action_to_tool_call(data)
        if mapped is not None:
            legacy_calls.append(mapped)

    legacy_clean = _LEGACY_ACTION_BLOCK_RE.sub("", clean_text).strip()
    bash_calls: list[dict[str, Any]] = []
    for match in _EXECUTE_BASH_BLOCK_RE.finditer(legacy_clean):
        mapped = _execute_bash_to_tool_call(match.group(1))
        if mapped is not None:
            bash_calls.append(mapped)

    fully_clean = _EXECUTE_BASH_BLOCK_RE.sub("", legacy_clean).strip()
    return fully_clean, calls + legacy_calls + bash_calls


async def execute_tool_calls(
    agent_id: str,
    calls: list[dict[str, Any]],
    *,
    defer_confirmation_tools: set[str] | None = None,
) -> list[dict[str, Any]]:
    registry = _get_registry()
    allowed_names = set(get_allowed_tool_names(agent_id))
    deferred_names = defer_confirmation_tools or set()
    results: list[dict[str, Any]] = []

    if registry is None:
        return [{"tool_name": call.get("tool_name", ""), "success": False, "error": "Tool registry not initialized"} for call in calls]

    for call in calls[:_MAX_TOOL_CALLS_PER_TURN]:
        tool_name = str(call.get("tool_name", "")).strip()
        arguments = call.get("arguments", {})

        if tool_name not in allowed_names:
            results.append({
                "tool_name": tool_name,
                "success": False,
                "error": f"Tool '{tool_name}' is not allowed for agent '{agent_id}'",
            })
            continue

        registered = registry.get_tool(tool_name)
        if registered is None:
            results.append({
                "tool_name": tool_name,
                "success": False,
                "error": f"Tool '{tool_name}' is not registered",
            })
            continue

        tool_info, handler = registered

        if tool_name in deferred_names or (getattr(handler, "requires_confirmation", False) and tool_name != "jarvis_task_plan_decompose"):
            results.append(_deferred_confirmation_result(
                tool_name=tool_name,
                description=tool_info.description,
                arguments=arguments,
            ))
            continue

        try:
            if hasattr(handler, "safe_aexecute"):
                output = await handler.safe_aexecute(**arguments)
            elif hasattr(handler, "safe_arun"):
                output = await handler.safe_arun(**arguments)
            else:
                output = await handler(**arguments)
            results.append({
                "tool_name": tool_name,
                "success": True,
                "requires_confirmation": bool(getattr(handler, "requires_confirmation", False)),
                "confirmation_id": uuid4().hex if getattr(handler, "requires_confirmation", False) else None,
                "description": tool_info.description,
                "output": output,
            })
        except Exception as exc:
            results.append({
                "tool_name": tool_name,
                "success": False,
                "description": tool_info.description,
                "error": str(exc),
            })

    return results


def to_action_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    action_results: list[dict[str, Any]] = []
    for item in results:
        tool_name = str(item.get("tool_name", ""))
        if tool_name not in {
            "jarvis_calendar_add",
            "jarvis_calendar_delete",
            "jarvis_calendar_update",
            "jarvis_plan_activity_slot",
            "jarvis_context_update",
            "jarvis_checkin_schedule",
            "jarvis_mood_journal",
            "jarvis_task_plan_decompose",
        }:
            continue

        if item.get("requires_confirmation"):
            output = item.get("output") if isinstance(item.get("output"), dict) else {}
            arguments = item.get("arguments", {})
            if output:
                arguments = {**arguments, **output}
            action_results.append({
                "type": _CONFIRMATION_TYPE_BY_TOOL.get(tool_name, tool_name),
                "ok": True,
                "pending_confirmation": True,
                "confirmation_id": item.get("confirmation_id"),
                "tool_name": tool_name,
                "arguments": arguments,
                "description": item.get("description", ""),
            })
        elif item.get("success"):
            payload = item.get("output")
            if isinstance(payload, dict):
                action_results.append(payload)
            else:
                action_results.append({"type": tool_name, "ok": True, "detail": payload})
        else:
            fallback_type = _CONFIRMATION_TYPE_BY_TOOL.get(tool_name, tool_name)
            action_results.append({
                "type": fallback_type,
                "ok": False,
                "error": item.get("error", "unknown error"),
            })
    return action_results


def format_tool_results(results: list[dict[str, Any]]) -> str:
    lines = ["## 工具结果"]
    for item in results:
        lines.append(f"### {item['tool_name']}")
        if item.get("success"):
            payload = item.get("output")
            if isinstance(payload, str):
                lines.append(payload)
            else:
                lines.append(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        else:
            lines.append(f"调用失败：{item.get('error', 'unknown error')}")
        lines.append("")
    return "\n".join(lines).strip()


async def run_agent_turn(
    *,
    agent_id: str,
    llm_client: Any,
    message: str,
    system_prompt: str,
    temperature: float = 0.7,
    defer_confirmation_tools: set[str] | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    toolkit_prompt = build_toolkit_prompt(agent_id)
    first_message = f"{message}\n\n{toolkit_prompt}" if toolkit_prompt else message
    first_reply = await llm_client.chat(
        message=first_message,
        system_prompt=system_prompt,
        temperature=temperature,
    )
    first_reply = (first_reply or "").strip()
    draft_text, calls = strip_tool_like_blocks(first_reply)
    if not calls:
        return first_reply, []

    tool_results = await execute_tool_calls(
        agent_id,
        calls,
        defer_confirmation_tools=defer_confirmation_tools,
    )
    followup_parts = [message]
    if draft_text:
        followup_parts.extend(["", "## 你的上一版草稿（可重写）", draft_text])
    followup_parts.extend([
        "",
        format_tool_results(tool_results),
        "",
        "请基于工具结果给用户一个自然语言回复。",
        "不要再输出 `<jarvis-tool>`、`<jarvis-action>`、`<execute_bash>` 或任何命令格式。",
        "如果工具结果显示 requires_confirmation=true，请说明已经生成待确认卡片，需要用户确认后才会写入。",
        "如果工具失败，请用简短中文说明失败原因，并询问用户是否需要你重试。",
    ])

    final_reply = await llm_client.chat(
        message="\n".join(followup_parts),
        system_prompt=system_prompt,
        temperature=temperature,
    )
    clean_final, _ = strip_tool_like_blocks((final_reply or "").strip())
    return clean_final or draft_text or "", tool_results
