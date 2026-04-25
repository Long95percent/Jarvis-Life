"""Brainstorm executor -- multi-agent round-table discussion."""

from __future__ import annotations

import re
import time
import uuid
from typing import TYPE_CHECKING, Any, AsyncIterator

import structlog

from app.agent.brainstorm.agents import AGENTS, AGENT_ORDER_CONVERGE, AGENT_ORDER_DIVERGE
from app.models.agent import AgentRequest, AgentResponse, AgentStep, AgentStrategy
from app.models.common import StreamEvent, StreamEventType

if TYPE_CHECKING:
    from app.llm.client import LLMClient

logger = structlog.get_logger("agent.brainstorm")

DIVERGE_ROUNDS = 2
MAX_HISTORY_CHARS = 3000


class BrainstormExecutor:

    def __init__(self, llm_client: LLMClient, tools: list | None = None) -> None:
        self.llm_client = llm_client
        self.tools = tools or []

    async def execute(self, request: AgentRequest) -> AgentResponse:
        steps: list[AgentStep] = []
        full_answer = ""
        async for event in self.execute_stream(request):
            if event.event == StreamEventType.AGENT_SPEAK:
                full_answer += event.data.get("content", "") + "\n\n"
                steps.append(AgentStep(
                    step_type="agent_speak",
                    content=event.data.get("content", ""),
                ))
        return AgentResponse(
            session_id=request.session_id,
            answer=full_answer.strip(),
            strategy=AgentStrategy.BRAINSTORM,
            steps=steps,
        )

    async def execute_stream(self, request: AgentRequest) -> AsyncIterator[StreamEvent]:
        topic = request.message
        session_id = request.session_id
        conversation: list[dict[str, str]] = []
        ideas: list[dict[str, Any]] = []
        start = time.perf_counter()

        previous_discussion = request.context.get("previous_discussion", "")
        user_feedback = request.context.get("user_feedback", [])
        user_profile = request.context.get("user_profile", {})

        context_prefix = self._build_context_prefix(previous_discussion, user_feedback, user_profile)

        def _event(event_type: StreamEventType, data: dict[str, Any]) -> StreamEvent:
            return StreamEvent(event=event_type, data=data, session_id=session_id)

        # ── Phase 1: Moderator opens ──
        yield _event(StreamEventType.PHASE_CHANGE, {"phase": "diverge", "round": 1})

        opening_instruction = (
            "Open this brainstorming session. Analyze the topic, "
            "identify 2-3 key angles to explore, and invite the team to share ideas."
        )
        if context_prefix:
            opening_instruction = context_prefix + "\n\n" + opening_instruction

        opening = await self._agent_speak(
            agent_id="moderator",
            topic=topic,
            conversation=conversation,
            phase_instruction=opening_instruction,
        )
        conversation.append({"role": "moderator", "content": opening})
        yield self._speak_event(session_id, "moderator", opening, 1, "diverge")

        # ── Phase 2: Diverge rounds ──
        for round_num in range(1, DIVERGE_ROUNDS + 1):
            if round_num > 1:
                yield _event(StreamEventType.PHASE_CHANGE, {"phase": "diverge", "round": round_num})

            for agent_id in AGENT_ORDER_DIVERGE:
                if round_num == 1:
                    instruction = "Share your initial thoughts and ideas on this topic."
                else:
                    instruction = (
                        "Build on the discussion so far. Respond to others' points, "
                        "add new ideas, and deepen your analysis."
                    )

                content = await self._agent_speak(
                    agent_id=agent_id,
                    topic=topic,
                    conversation=conversation,
                    phase_instruction=instruction,
                )
                conversation.append({"role": agent_id, "content": content})
                yield self._speak_event(session_id, agent_id, content, round_num, "diverge")

                extracted = self._extract_ideas(content, agent_id, round_num)
                for idea in extracted:
                    ideas.append(idea)
                    yield _event(StreamEventType.IDEA_CREATED, idea)

        # ── Phase 3: Converge ──
        converge_round = DIVERGE_ROUNDS + 1
        yield _event(StreamEventType.PHASE_CHANGE, {"phase": "converge", "round": converge_round})

        for agent_id in AGENT_ORDER_CONVERGE:
            if agent_id == "synthesizer":
                instruction = (
                    "Synthesize the best ideas from the discussion. "
                    "Combine complementary proposals and present a unified recommendation."
                )
            else:
                instruction = (
                    "Provide a final critical evaluation of the synthesized proposal. "
                    "Note strengths, remaining risks, and suggested improvements."
                )

            content = await self._agent_speak(
                agent_id=agent_id,
                topic=topic,
                conversation=conversation,
                phase_instruction=instruction,
            )
            conversation.append({"role": agent_id, "content": content})
            yield self._speak_event(session_id, agent_id, content, converge_round, "converge")

        # ── Phase 4: Conclude ──
        conclude_round = converge_round + 1
        yield _event(StreamEventType.PHASE_CHANGE, {"phase": "conclude", "round": conclude_round})

        conclusion = await self._agent_speak(
            agent_id="moderator",
            topic=topic,
            conversation=conversation,
            phase_instruction=(
                "Wrap up this brainstorming session. Present the final conclusions:\n"
                "1. Top 3 ideas with brief rationale\n"
                "2. Key consensus points\n"
                "3. Open questions for future exploration\n"
                "Be structured and actionable."
            ),
        )
        conversation.append({"role": "moderator", "content": conclusion})
        yield self._speak_event(session_id, "moderator", conclusion, conclude_round, "conclude")

        elapsed_ms = (time.perf_counter() - start) * 1000
        yield _event(StreamEventType.BRAINSTORM_DONE, {
            "synthesis": conclusion,
            "idea_count": len(ideas),
            "rounds": conclude_round,
            "latency_ms": round(elapsed_ms, 2),
        })
        yield _event(StreamEventType.DONE, {
            "strategy": "brainstorm",
            "total_rounds": conclude_round,
        })

    async def _agent_speak(
        self,
        agent_id: str,
        topic: str,
        conversation: list[dict[str, str]],
        phase_instruction: str,
    ) -> str:
        agent = AGENTS[agent_id]
        history_text = self._format_conversation(conversation)

        prompt = (
            f"## Brainstorming Topic\n{topic}\n\n"
            f"## Discussion So Far\n{history_text}\n\n"
            f"## Your Task\n{phase_instruction}\n\n"
            "Keep your response focused and under 200 words."
        )

        try:
            response = await self.llm_client.chat(
                message=prompt,
                system_prompt=agent["system_prompt"],
                temperature=agent.get("temperature", 0.7),
            )
            return response.strip()
        except Exception as e:
            logger.error(f"Brainstorm agent {agent_id} failed: {e}")
            return f"[{agent['name_zh']} encountered an error: {e}]"

    def _speak_event(
        self, session_id: str, agent_id: str, content: str, round_num: int, phase: str,
    ) -> StreamEvent:
        agent = AGENTS[agent_id]
        return StreamEvent(
            event=StreamEventType.AGENT_SPEAK,
            data={
                "agent_id": agent_id,
                "agent_name": agent["name_zh"],
                "agent_name_en": agent["name"],
                "agent_color": agent["color"],
                "agent_icon": agent["icon"],
                "content": content,
                "round": round_num,
                "phase": phase,
            },
            session_id=session_id,
        )

    def _format_conversation(self, conversation: list[dict[str, str]]) -> str:
        if not conversation:
            return "(No discussion yet -- you are the first to speak.)"

        parts: list[str] = []
        total_chars = 0
        for entry in reversed(conversation):
            agent = AGENTS.get(entry["role"], {})
            name = agent.get("name_zh", entry["role"])
            line = f"**{name}**: {entry['content']}"
            if total_chars + len(line) > MAX_HISTORY_CHARS:
                parts.insert(0, "(...earlier discussion summarized...)")
                break
            parts.insert(0, line)
            total_chars += len(line)

        return "\n\n".join(parts)

    def _build_context_prefix(
        self,
        previous_discussion: str,
        user_feedback: list[dict[str, Any]],
        user_profile: dict[str, Any],
    ) -> str:
        parts: list[str] = []

        if previous_discussion:
            truncated = previous_discussion[:4000]
            parts.append(f"## Previous Discussion\n{truncated}")

        if user_feedback:
            lines = []
            for fb in user_feedback[:20]:
                agent_id = fb.get("agent_id", "unknown")
                vote = fb.get("vote")
                comment = fb.get("comment")
                if vote:
                    lines.append(f"- {agent_id}: {'liked' if vote == 'up' else 'disliked'}")
                if comment:
                    lines.append(f"  Comment: {comment}")
            if lines:
                parts.append("## User Feedback on Previous Round\n" + "\n".join(lines))

        if user_profile:
            prefs = user_profile.get("agent_preferences", {})
            pref_lines = [f"- {k}: score {v}" for k, v in prefs.items() if v != 0]
            if pref_lines:
                parts.append(
                    "## User Preference Profile\n"
                    "Adapt your responses based on these cumulative preferences:\n"
                    + "\n".join(pref_lines)
                )

        return "\n\n".join(parts)

    def _extract_ideas(self, content: str, author: str, round_num: int) -> list[dict[str, Any]]:
        ideas: list[dict[str, Any]] = []
        for match in re.finditer(r"(?:^|\n)\s*\d+[\.\)]\s*(.+)", content):
            idea_text = match.group(1).strip()
            if len(idea_text) < 10:
                continue
            ideas.append({
                "id": f"idea-{round_num}-{author}-{uuid.uuid4().hex[:6]}",
                "content": idea_text[:200],
                "author": author,
                "round": round_num,
            })
        return ideas[:5]
