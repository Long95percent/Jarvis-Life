"""Shared collaboration memory helpers for Jarvis agents."""

from __future__ import annotations

from typing import Any

from app.jarvis.agents import JARVIS_AGENTS
from app.jarvis.persistence import (
    get_relevant_collaboration_memories,
    save_collaboration_memory,
)

TEAM_AGENT_IDS = [agent_id for agent_id in JARVIS_AGENTS if agent_id != "shadow"]
_CONSTRAINT_HINTS = (
    "记住",
    "以后",
    "不要",
    "别再",
    "尽量",
    "必须",
    "不想",
    "优先",
    "晚上不要",
    "晚上不想",
)


def is_user_constraint(message: str) -> bool:
    text = message.strip()
    return any(hint in text for hint in _CONSTRAINT_HINTS)


async def remember_user_constraint(message: str, source_agent: str) -> None:
    await save_collaboration_memory(
        source_agent=source_agent,
        participant_agents=TEAM_AGENT_IDS,
        memory_kind="user_constraint",
        content=message.strip(),
        structured_payload={"message": message.strip()},
        importance=1.5,
    )


async def remember_tool_actions(agent_id: str, tool_results: list[dict[str, Any]]) -> None:
    for item in tool_results:
        if not item.get("success"):
            continue
        tool_name = str(item.get("tool_name", ""))
        if tool_name not in {
            "jarvis_calendar_add",
            "jarvis_calendar_delete",
            "jarvis_calendar_update",
            "jarvis_plan_activity_slot",
            "jarvis_context_update",
            "jarvis_checkin_schedule",
            "jarvis_mood_journal",
        }:
            continue
        output = item.get("output")
        summary = output if isinstance(output, str) else str(output)
        await save_collaboration_memory(
            source_agent=agent_id,
            participant_agents=TEAM_AGENT_IDS,
            memory_kind="tool_action",
            content=f"{agent_id} executed {tool_name}: {summary[:300]}",
            structured_payload=output if isinstance(output, dict) else {"output": summary},
            importance=1.2,
        )


async def remember_coordination_summary(
    *,
    source_agent: str,
    participant_agents: list[str],
    goal: str,
    summary: str,
    payload: dict[str, Any],
) -> None:
    await save_collaboration_memory(
        source_agent=source_agent,
        participant_agents=sorted(set(participant_agents)),
        memory_kind="coordination_summary",
        content=summary or goal,
        structured_payload={"goal": goal, **payload},
        importance=1.4,
    )


async def remember_roundtable_turn(
    *,
    session_id: str,
    source_agent: str,
    participant_agents: list[str],
    memory_kind: str,
    content: str,
    payload: dict[str, Any] | None = None,
    importance: float = 1.0,
) -> None:
    await save_collaboration_memory(
        session_id=session_id,
        source_agent=source_agent,
        participant_agents=participant_agents,
        memory_kind=memory_kind,
        content=content,
        structured_payload=payload or {},
        importance=importance,
    )


async def build_collaboration_memory_prefix(agent_id: str, limit: int = 6) -> str:
    memories = await get_relevant_collaboration_memories(agent_id, limit=limit)
    if not memories:
        return ""

    lines = ["## 共享协作记忆"]
    for item in memories:
        source = item.get("source_agent", "system")
        kind = item.get("memory_kind", "memory")
        lines.append(f"- [{kind}] {source}: {item.get('content', '')}")
    lines.append("")
    return "\n".join(lines)
