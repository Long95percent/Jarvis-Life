"""Shadow preference learner — silent observer that builds the user profile.

Observes every exchange between user and any JARVIS agent. Occasionally
calls the LLM to extract a structured preference update. The extracted
preferences are stored in UserProfile and made available to all agents.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import structlog

from app.jarvis.agents import get_agent
from app.jarvis.models import UserProfile

if TYPE_CHECKING:
    from app.llm.client import LLMClient

logger = structlog.get_logger("jarvis.preference_learner")

_OBSERVE_EVERY_N = 5  # run LLM extraction every N observations to save tokens


class PreferenceLearner:
    """Silent background learner — never speaks to the user."""

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm_client = llm_client
        self._profile = UserProfile()
        self._buffer: list[dict] = []
        shadow = get_agent("shadow")
        self._system_prompt = shadow["system_prompt"]

    def get_profile(self) -> UserProfile:
        return self._profile.model_copy()

    async def observe(self, agent_id: str, user_message: str, agent_response: str) -> None:
        self._buffer.append({
            "agent": agent_id,
            "user": user_message,
            "agent_response": agent_response,
        })
        self._profile.interaction_count += 1

        if self._profile.interaction_count % _OBSERVE_EVERY_N == 0:
            await self._extract_preference()

    async def _extract_preference(self) -> None:
        recent = self._buffer[-_OBSERVE_EVERY_N:]
        exchanges = "\n".join(
            f"[{e['agent']}] User: {e['user']!r} | Agent: {e['agent_response']!r}"
            for e in recent
        )

        prompt = (
            f"## Recent Exchanges\n{exchanges}\n\n"
            "Based on these exchanges, identify ONE specific user preference.\n"
            "Respond ONLY with JSON: {\"key\": \"preference_key\", \"value\": <value>}\n"
            "If no clear preference is detectable, respond: {\"key\": null, \"value\": null}"
        )

        try:
            raw = await self.llm_client.chat(
                message=prompt,
                system_prompt=self._system_prompt,
                temperature=0.1,
            )
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start == -1:
                return
            data = json.loads(raw[start:end])
            key = data.get("key")
            value = data.get("value")
            if key:
                self._profile.record_preference(key, value)
                logger.info("jarvis.learner.preference_extracted", key=key, value=value)
        except Exception as exc:
            logger.warning("jarvis.learner.extract_failed", error=str(exc))
