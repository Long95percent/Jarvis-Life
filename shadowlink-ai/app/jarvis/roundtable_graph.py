from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal


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


def round_event(event: str, payload: dict[str, Any]) -> dict[str, str]:
    return {"event": event, "data": json.dumps(payload, ensure_ascii=False, default=str)}
