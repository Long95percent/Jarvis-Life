"""Shadow Roundtable — invisible inter-agent deliberation.

Agents discuss the user's current life context and each produce one
structured action decision. The user never sees this exchange.
Adapted from BrainstormExecutor but output is JSON action items, not prose.
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any

import structlog

from app.jarvis.agents import JARVIS_AGENTS, get_agent
from app.jarvis.models import LifeContext, RoundtableDecision, RoundtableResult

if TYPE_CHECKING:
    from app.llm.client import LLMClient

logger = structlog.get_logger("jarvis.shadow_roundtable")

_PARTICIPATING_AGENTS_DEFAULT = ["alfred", "maxwell", "nora", "mira", "leo"]
_SILENT_AGENTS = {"shadow"}  # never participate in roundtable


class ShadowRoundtable:
    """Background multi-agent deliberation that the user cannot see.

    Each participating agent receives the current life context and the
    roundtable trigger, then responds with a structured JSON action.
    """

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm_client = llm_client

    async def convene(
        self,
        trigger: str,
        context: LifeContext,
        participating_agents: list[str] | None = None,
    ) -> RoundtableResult:
        agents = [
            a for a in (participating_agents or _PARTICIPATING_AGENTS_DEFAULT)
            if a not in _SILENT_AGENTS
        ]

        start = time.perf_counter()
        decisions: list[RoundtableDecision] = []
        discussion: list[str] = []

        for agent_id in agents:
            decision = await self._agent_deliberate(agent_id, trigger, context, discussion)
            decisions.append(decision)
            discussion.append(f"{agent_id}: {decision.action} — {json.dumps(decision.payload)}")

        summary = self._build_summary(trigger, decisions)
        elapsed = round((time.perf_counter() - start) * 1000, 1)
        logger.info("jarvis.roundtable.done", trigger=trigger, agents=agents, elapsed_ms=elapsed)

        return RoundtableResult(trigger=trigger, decisions=decisions, summary=summary)

    async def _agent_deliberate(
        self,
        agent_id: str,
        trigger: str,
        context: LifeContext,
        discussion_so_far: list[str],
    ) -> RoundtableDecision:
        agent = get_agent(agent_id)
        discussion_text = "\n".join(discussion_so_far) or "(You are the first to deliberate.)"

        prompt = (
            f"## JARVIS Shadow Roundtable — Internal Deliberation\n"
            f"This conversation is NOT visible to the user.\n\n"
            f"## Trigger\n{trigger}\n\n"
            f"## Current Life Context\n"
            f"- Stress level: {context.stress_level}/10\n"
            f"- Schedule density: {context.schedule_density}/10\n"
            f"- Sleep quality: {context.sleep_quality}/10\n"
            f"- Mood trend: {context.mood_trend}\n"
            f"- Upcoming events: {len(context.active_events)}\n\n"
            f"## Other Agents' Decisions So Far\n{discussion_text}\n\n"
            f"## Your Task\n"
            f"As {agent['name']} ({agent['role']}), decide what action to take.\n"
            f"Respond with ONLY valid JSON in this schema:\n"
            f'{{"action": "send_message"|"update_context"|"schedule_followup"|"noop", '
            f'"payload": {{...}}}}\n\n'
            f"For send_message: payload = {{\"content\": \"<message to user>\"}}\n"
            f"For update_context: payload = {{\"field\": \"<field_name>\", \"value\": <value>}}\n"
            f"For schedule_followup: payload = {{\"delay_minutes\": <int>, \"trigger\": \"<trigger_name>\"}}\n"
            f"For noop: payload = {{}}\n\n"
            f"Only recommend send_message if the situation genuinely warrants user contact."
        )

        try:
            raw = await self.llm_client.chat(
                message=prompt,
                system_prompt=agent["system_prompt"],
                temperature=0.3,
            )
            parsed = self._parse_decision(raw.strip())
            return RoundtableDecision(agent_id=agent_id, **parsed)
        except Exception as exc:
            logger.error("jarvis.roundtable.agent_failed", agent_id=agent_id, error=str(exc))
            return RoundtableDecision(agent_id=agent_id, action="noop", payload={})

    def _parse_decision(self, raw: str) -> dict[str, Any]:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end == 0:
            return {"action": "noop", "payload": {}}
        try:
            data = json.loads(raw[start:end])
            action = data.get("action", "noop")
            if action not in {"send_message", "update_context", "schedule_followup", "noop"}:
                action = "noop"
            return {"action": action, "payload": data.get("payload", {})}
        except json.JSONDecodeError:
            return {"action": "noop", "payload": {}}

    def _build_summary(self, trigger: str, decisions: list[RoundtableDecision]) -> str:
        actions = [f"{d.agent_id}→{d.action}" for d in decisions]
        return f"Roundtable '{trigger}': {', '.join(actions)}"
