from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

from app.jarvis.tool_runtime import run_agent_turn, to_action_results


GraphStatus = Literal["running", "waiting_for_user", "finalized", "failed"]


@dataclass
class RoundtableRoleOutput:
    agent_id: str
    agent_name: str
    role: str
    content: str
    round_index: int
    summary: str = ""
    concerns: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    def to_minutes_item(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "summary": self.summary or self.content[:160],
        }


@dataclass
class RoundtableRoundSummary:
    round_index: int
    minutes: list[dict[str, Any]] = field(default_factory=list)
    consensus: list[str] = field(default_factory=list)
    disagreements: list[str] = field(default_factory=list)
    questions_for_user: list[str] = field(default_factory=list)
    next_round_focus: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "round_index": self.round_index,
            "minutes": self.minutes,
            "consensus": self.consensus,
            "disagreements": self.disagreements,
            "questions_for_user": self.questions_for_user,
            "next_round_focus": self.next_round_focus,
        }


@dataclass
class RoundtableGraphState:
    session_id: str
    scenario_id: str
    user_goal: str
    participants: list[str]
    round_index: int = 1
    context: dict[str, Any] = field(default_factory=dict)
    user_feedback_history: list[str] = field(default_factory=list)
    role_outputs: list[RoundtableRoleOutput] = field(default_factory=list)
    round_summaries: list[RoundtableRoundSummary] = field(default_factory=list)
    final_result: dict[str, Any] | None = None
    status: GraphStatus = "running"


@dataclass
class RoundtableAgentTurnResult:
    content: str
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    action_results: list[dict[str, Any]] = field(default_factory=list)


async def _persist_roundtable_agent_actions(
    *,
    session_id: str | None,
    agent_id: str,
    action_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not session_id:
        return action_results

    persisted: list[dict[str, Any]] = []
    for action in action_results:
        if not action.get("pending_confirmation"):
            persisted.append(action)
            continue
        try:
            from app.jarvis.persistence import save_pending_action

            arguments = action.get("arguments") if isinstance(action.get("arguments"), dict) else {}
            plan = arguments.get("plan") if isinstance(arguments.get("plan"), dict) else {}
            title = str(arguments.get("title") or plan.get("title") or action.get("type") or "圆桌待确认操作")
            saved = await save_pending_action(
                pending_id=str(action.get("confirmation_id")),
                action_type=str(action.get("type")),
                tool_name=str(action.get("tool_name") or ""),
                agent_id=agent_id,
                session_id=session_id,
                title=title,
                arguments=arguments,
            )
            persisted.append({**action, "pending_action_id": saved.get("id")})
        except Exception as exc:
            persisted.append({**action, "ok": False, "error": f"圆桌角色待确认动作保存失败：{exc}"})
    return persisted


async def run_roundtable_agent_turn(
    *,
    agent_id: str,
    llm_client: Any,
    message: str,
    system_prompt: str,
    temperature: float = 0.7,
    session_id: str | None = None,
    enable_tools: bool = True,
) -> RoundtableAgentTurnResult:
    if enable_tools:
        content, tool_results = await run_agent_turn(
            agent_id=agent_id,
            llm_client=llm_client,
            message=message,
            system_prompt=system_prompt,
            temperature=temperature,
            defer_confirmation_tools={"jarvis_task_plan_decompose"},
        )
    else:
        content = await llm_client.chat(
            message=message,
            system_prompt=system_prompt,
            temperature=temperature,
        )
        tool_results = []

    action_results = await _persist_roundtable_agent_actions(
        session_id=session_id,
        agent_id=agent_id,
        action_results=to_action_results(tool_results),
    )
    return RoundtableAgentTurnResult(
        content=(content or "").strip(),
        tool_results=tool_results,
        action_results=action_results,
    )


def roundtable_content_deltas(content: str, *, min_chunks: int = 2) -> list[str]:
    text = (content or "").strip()
    if not text:
        return [""]
    if min_chunks <= 1 or len(text) < 2:
        return [text]
    midpoint = max(1, len(text) // 2)
    return [text[:midpoint], text[midpoint:]]


def round_event(event: str, payload: dict[str, Any]) -> dict[str, str]:
    return {"event": event, "data": json.dumps(payload, ensure_ascii=False, default=str)}
