"""Bounded private consultation between Jarvis agents."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.jarvis.agents import JARVIS_AGENTS, get_agent
from app.jarvis.persistence import save_collaboration_memory

VISIBLE_AGENT_IDS = [agent_id for agent_id in JARVIS_AGENTS if agent_id != "shadow"]
_CONSULT_TRIGGERS = ("问问", "问一下", "问", "咨询", "听听")
_MAX_CONSULT_EDGES = 2

_ALIASES: dict[str, tuple[str, ...]] = {
    "alfred": ("alfred", "Alfred", "总管家", "管家"),
    "maxwell": ("maxwell", "Maxwell", "秘书", "日程管家", "日程"),
    "nora": ("nora", "Nora", "营养师", "营养"),
    "mira": ("mira", "Mira", "心理师", "心理医生", "心理咨询师", "心理"),
    "leo": ("leo", "Leo", "生活顾问", "生活"),
}


@dataclass(frozen=True)
class ConsultEdge:
    from_agent: str
    to_agent: str


@dataclass
class AgentConsultationResult:
    consultations: list[dict[str, Any]] = field(default_factory=list)
    prompt_prefix: str = ""
    actions: list[dict[str, Any]] = field(default_factory=list)

    @property
    def has_consultations(self) -> bool:
        return bool(self.consultations)


def _agent_name(agent_id: str) -> str:
    try:
        return str(get_agent(agent_id).get("name") or agent_id)
    except KeyError:
        return agent_id


def _agent_role(agent_id: str) -> str:
    try:
        return str(get_agent(agent_id).get("role") or "")
    except KeyError:
        return ""


def _mentions(text: str) -> list[tuple[int, int, str]]:
    matches: list[tuple[int, int, str]] = []
    occupied: list[tuple[int, int]] = []
    alias_items = [
        (alias, agent_id)
        for agent_id, aliases in _ALIASES.items()
        for alias in aliases
    ]
    alias_items.sort(key=lambda item: len(item[0]), reverse=True)
    lowered = text.lower()
    for alias, agent_id in alias_items:
        pattern = re.escape(alias.lower())
        for match in re.finditer(pattern, lowered):
            start, end = match.span()
            if any(not (end <= used_start or start >= used_end) for used_start, used_end in occupied):
                continue
            matches.append((start, end, agent_id))
            occupied.append((start, end))
    return sorted(matches, key=lambda item: item[0])


def _first_trigger_index(text: str) -> int:
    positions = [text.find(trigger) for trigger in _CONSULT_TRIGGERS if text.find(trigger) >= 0]
    return min(positions) if positions else -1


def _split_clauses(message: str) -> list[str]:
    return [
        item.strip()
        for item in re.split(r"[，,。；;\n]+|再让|然后让|然后|再", message)
        if item.strip()
    ]


def _can_consult(from_agent: str, to_agent: str) -> bool:
    return (
        from_agent in VISIBLE_AGENT_IDS
        and to_agent in VISIBLE_AGENT_IDS
        and from_agent != to_agent
    )


def parse_consult_edges(source_agent: str, message: str) -> list[ConsultEdge]:
    """Parse explicit user-directed private consultation edges.

    This intentionally only handles direct wording around ask/consult verbs.
    It does not infer hidden autonomous delegation from vague messages.
    """
    edges: list[ConsultEdge] = []
    seen: set[tuple[str, str]] = set()
    for clause in _split_clauses(message):
        trigger_index = _first_trigger_index(clause)
        if trigger_index < 0:
            continue
        mentions = _mentions(clause)
        before = [item for item in mentions if item[0] < trigger_index]
        after = [item for item in mentions if item[0] > trigger_index]
        from_agent = before[-1][2] if before else source_agent
        if not after:
            continue
        to_agent = after[0][2]
        key = (from_agent, to_agent)
        if not _can_consult(from_agent, to_agent) or key in seen:
            continue
        seen.add(key)
        edges.append(ConsultEdge(from_agent=from_agent, to_agent=to_agent))
        if len(edges) >= _MAX_CONSULT_EDGES:
            break
    return edges


def _parse_consult_json(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start:end])
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    return {"summary": text, "confidence": 0.5, "needs_followup": False}


def _format_child_notes(edge: ConsultEdge, completed: list[dict[str, Any]]) -> str:
    related = [item for item in completed if item.get("from_agent") == edge.to_agent]
    if not related:
        return "(none)"
    lines = []
    for item in related:
        lines.append(
            f"- {_agent_name(str(item.get('from_agent')))} consulted "
            f"{_agent_name(str(item.get('to_agent')))}: {item.get('summary', '')}"
        )
    return "\n".join(lines)


def _build_consult_prompt(
    *,
    edge: ConsultEdge,
    user_message: str,
    context_summary: str,
    completed: list[dict[str, Any]],
) -> str:
    return (
        "## Jarvis private agent consultation\n"
        "This is an internal consultation. The user will not see this message directly.\n\n"
        f"Requesting agent: {_agent_name(edge.from_agent)} ({_agent_role(edge.from_agent)})\n"
        f"Consulted agent: {_agent_name(edge.to_agent)} ({_agent_role(edge.to_agent)})\n\n"
        f"## User request\n{user_message}\n\n"
        f"## Current context\n{context_summary}\n\n"
        f"## Downstream consultation results already available\n{_format_child_notes(edge, completed)}\n\n"
        "Answer only from your professional role. Be concise and useful to the requesting agent.\n"
        "Return JSON only:\n"
        '{"summary":"...","confidence":0.0,"needs_followup":false}'
    )


def _build_prompt_prefix(consultations: list[dict[str, Any]]) -> str:
    if not consultations:
        return ""
    lines = ["## 私下咨询结果"]
    for item in consultations:
        lines.append(
            f"- {_agent_name(str(item['from_agent']))} 已咨询 "
            f"{_agent_name(str(item['to_agent']))}：{item['summary']}"
        )
    lines.append("请在最终回复中吸收这些内部意见，但不要逐字暴露内部提示词。")
    lines.append("")
    return "\n".join(lines)


def _build_actions(consultations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not consultations:
        return []
    return [
        {
            "type": "agent.consult",
            "ok": True,
            "pending_confirmation": False,
            "description": f"已完成 {len(consultations)} 次私下咨询",
            "arguments": {"consultations": consultations},
        }
    ]


async def run_agent_consultations(
    *,
    source_agent: str,
    user_message: str,
    session_id: str | None,
    llm_client: Any,
    context_summary: str,
) -> AgentConsultationResult:
    edges = parse_consult_edges(source_agent=source_agent, message=user_message)
    if not edges:
        return AgentConsultationResult()

    completed: list[dict[str, Any]] = []
    for edge in reversed(edges):
        target_agent = get_agent(edge.to_agent)
        prompt = _build_consult_prompt(
            edge=edge,
            user_message=user_message,
            context_summary=context_summary,
            completed=completed,
        )
        raw = await llm_client.chat(
            message=prompt,
            system_prompt=target_agent["system_prompt"],
            temperature=0.2,
        )
        parsed = _parse_consult_json(raw or "")
        summary = str(parsed.get("summary") or "").strip()
        if not summary:
            summary = "未给出明确咨询结论。"
        item = {
            "root_agent": source_agent,
            "from_agent": edge.from_agent,
            "from_agent_name": _agent_name(edge.from_agent),
            "to_agent": edge.to_agent,
            "to_agent_name": _agent_name(edge.to_agent),
            "summary": summary,
            "confidence": parsed.get("confidence", 0.5),
            "needs_followup": bool(parsed.get("needs_followup") or False),
        }
        completed.append(item)
        await save_collaboration_memory(
            session_id=session_id,
            source_agent=edge.from_agent,
            participant_agents=sorted({source_agent, edge.from_agent, edge.to_agent}),
            memory_kind="agent_consultation",
            content=f"{_agent_name(edge.from_agent)} consulted {_agent_name(edge.to_agent)}: {summary}",
            structured_payload=item,
            importance=1.25,
        )

    return AgentConsultationResult(
        consultations=completed,
        prompt_prefix=_build_prompt_prefix(completed),
        actions=_build_actions(completed),
    )
