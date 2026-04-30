"""Shadow preference learner — silent observer that builds the user profile.

Observes every exchange between user and any JARVIS agent. Occasionally
calls the LLM to extract a structured preference update. The extracted
preferences are stored in UserProfile and made available to all agents.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import structlog

from app.jarvis.agents import JARVIS_AGENTS, get_agent
from app.jarvis.models import UserProfile
from app.jarvis.persistence import list_agent_preference_profiles, upsert_agent_preference_profile

if TYPE_CHECKING:
    from app.llm.client import LLMClient

logger = structlog.get_logger("jarvis.preference_learner")

_OBSERVE_EVERY_N = 5  # run LLM extraction every N observations to save tokens
_GLOBAL_AGENT_ID = "global"
_VISIBLE_AGENT_IDS = {agent_id for agent_id in JARVIS_AGENTS if agent_id != "shadow"}


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

    def set_llm_client(self, llm_client: Any) -> None:
        self.llm_client = llm_client

    async def observe(self, agent_id: str, user_message: str, agent_response: str) -> bool:
        self._buffer.append({
            "agent": agent_id,
            "user": user_message,
            "agent_response": agent_response,
        })
        self._profile.interaction_count += 1

        if self._profile.interaction_count % _OBSERVE_EVERY_N == 0:
            return await self._extract_preference()
        return False

    async def _extract_preference(self) -> bool:
        recent = self._buffer[-_OBSERVE_EVERY_N:]
        exchanges = "\n".join(
            f"[{e['agent']}] User: {e['user']!r} | Agent: {e['agent_response']!r}"
            for e in recent
        )

        prompt = (
            f"## Recent Exchanges\n{exchanges}\n\n"
            "Extract stable user preferences that should shape future Jarvis assistant behavior.\n"
            "Return JSON only. Preferred schema:\n"
            "{\"preferences\":[{\"key\":\"low_interrupt\",\"value\":\"...\",\"scope\":\"global|agent\","
            "\"target_agents\":[\"mira\"],\"confidence\":0.7,\"evidence\":\"short quote\"}]}\n"
            "Use scope=global for preferences all assistants should know. Use scope=agent for role-specific adaptation.\n"
            "Valid target_agents: alfred, maxwell, nora, mira, leo. Shadow must not be a target.\n"
            "If no clear preference is detectable, respond: {\"preferences\":[]}.\n"
            "Legacy fallback is accepted: {\"key\":\"preference_key\",\"value\":true}."
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
                return False
            data = json.loads(raw[start:end])
            return await self._persist_extracted_preferences(data, recent)
        except Exception as exc:
            logger.warning("jarvis.learner.extract_failed", error=str(exc))
            return False

    async def _persist_extracted_preferences(self, data: dict[str, Any], recent: list[dict]) -> bool:
        items = data.get("preferences")
        if not isinstance(items, list):
            key = data.get("key")
            value = data.get("value")
            if not key:
                return False
            items = [{
                "key": key,
                "value": value,
                "scope": "global",
                "target_agents": [],
                "confidence": 0.65,
                "evidence": "",
            }]

        latest_agent = str(recent[-1].get("agent") or "shadow") if recent else "shadow"
        latest_user = str(recent[-1].get("user") or "") if recent else ""
        saved_any = False
        for item in items:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key") or "").strip()
            value = item.get("value")
            if not key or value is None or value == "":
                continue
            value_text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
            confidence = _clamp_float(item.get("confidence"), default=0.65)
            evidence = str(item.get("evidence") or latest_user)[:240]
            self._profile.record_preference(key, value)

            target_agents = _normalize_target_agents(item.get("target_agents"))
            scope = str(item.get("scope") or "global").strip().lower()
            agent_ids = [_GLOBAL_AGENT_ID]
            if scope == "agent":
                agent_ids = target_agents or ([latest_agent] if latest_agent in _VISIBLE_AGENT_IDS else [])
            elif target_agents:
                agent_ids = [_GLOBAL_AGENT_ID, *target_agents]

            for agent_id in dict.fromkeys(agent_ids):
                if agent_id != _GLOBAL_AGENT_ID and agent_id not in _VISIBLE_AGENT_IDS:
                    continue
                await upsert_agent_preference_profile(
                    agent_id=agent_id,
                    preference_key=key,
                    preference_value=value_text,
                    confidence=confidence,
                    source_agent=latest_agent if latest_agent in JARVIS_AGENTS else "shadow",
                    source_excerpt=evidence,
                )
                saved_any = True
            logger.info("jarvis.learner.preference_extracted", key=key, value=value_text)
        return saved_any


def _clamp_float(value: Any, *, default: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = default
    return max(minimum, min(maximum, numeric))


def _normalize_target_agents(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    result: list[str] = []
    for item in raw:
        agent_id = str(item or "").strip().lower()
        if agent_id in _VISIBLE_AGENT_IDS and agent_id not in result:
            result.append(agent_id)
    return result


async def build_preference_profile_prefix(agent_id: str, limit: int = 6) -> str:
    global_profiles = await list_agent_preference_profiles(agent_id=_GLOBAL_AGENT_ID, limit=limit)
    agent_profiles = await list_agent_preference_profiles(agent_id=agent_id, limit=limit)
    if not global_profiles and not agent_profiles:
        return ""

    lines = ["## 偏好学习画像（后台自动学习，仅在相关时使用）"]
    for item in global_profiles[:limit]:
        lines.append(
            f"- [全局/{item['preference_key']}] {item['preference_value']} "
            f"(置信度 {float(item['confidence']):.2f}, 证据 {int(item['evidence_count'])})"
        )
    if agent_profiles:
        agent_name = get_agent(agent_id).get("name", agent_id) if agent_id in JARVIS_AGENTS else agent_id
        for item in agent_profiles[:limit]:
            lines.append(
                f"- [{agent_name}/{item['preference_key']}] {item['preference_value']} "
                f"(置信度 {float(item['confidence']):.2f}, 证据 {int(item['evidence_count'])})"
            )
    lines.append("")
    return "\n".join(lines)
