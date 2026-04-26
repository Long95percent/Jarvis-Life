"""Lightweight memory extraction and recall for real Jarvis chat turns.

This module intentionally starts rule-based: it gives Step 3.6 a real,
low-risk closed loop before adding LLM extraction or vector routing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import structlog

from app.jarvis.persistence import (
    list_jarvis_memories,
    mark_jarvis_memories_used,
    save_jarvis_memory,
)

logger = structlog.get_logger("jarvis.memory_extractor")


@dataclass(frozen=True)
class MemoryCandidate:
    memory_kind: str
    content: str
    sensitivity: str = "normal"
    confidence: float = 0.65
    importance: float = 0.6
    payload: dict[str, Any] | None = None


_PREFERENCE_HINTS = (
    "我喜欢",
    "我更喜欢",
    "我偏好",
    "我希望",
    "以后",
    "记住",
    "别再",
    "不要",
    "少提醒",
    "频繁提醒",
    "别太频繁",
    "低打扰",
    "先共情",
    "直接一点",
    "简短一点",
)

_MOOD_HINTS = (
    "焦虑",
    "压力大",
    "压力很大",
    "崩溃",
    "难受",
    "疲惫",
    "累",
    "emo",
    "心情不好",
    "不想见人",
)

_RHYTHM_HINTS = (
    "熬夜",
    "睡不着",
    "失眠",
    "晚睡",
    "早起",
    "起不来",
    "作息",
    "睡眠",
)

_LONG_TERM_HINTS = (
    "备考",
    "雅思",
    "ielts",
    "考研",
    "考试",
    "长期",
    "目标",
    "暑假旅行",
    "旅行计划",
)

_RELATION_HINTS = (
    "是我的同事",
    "是我同事",
    "是我的朋友",
    "是我朋友",
    "是我的家人",
    "是我家人",
    "是我的老师",
    "是我老师",
)


def _contains_any(text: str, hints: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(hint.lower() in lowered for hint in hints)


def _clamp(value: Any, default: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = default
    return max(minimum, min(maximum, numeric))


def _candidate_key(candidate: MemoryCandidate) -> tuple[str, str]:
    return candidate.memory_kind, " ".join(candidate.content.strip().split())


def _dedupe_candidates(candidates: list[MemoryCandidate]) -> list[MemoryCandidate]:
    result: list[MemoryCandidate] = []
    seen: set[tuple[str, str]] = set()
    for candidate in candidates:
        key = _candidate_key(candidate)
        if key in seen:
            continue
        seen.add(key)
        result.append(candidate)
    return result


def _parse_llm_json(raw: str) -> list[dict[str, Any]]:
    text = raw.strip()
    if not text:
        return []
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end <= start:
        return []
    data = json.loads(text[start:end])
    memories = data.get("memories", [])
    return memories if isinstance(memories, list) else []


def _candidate_from_llm_item(item: dict[str, Any]) -> MemoryCandidate | None:
    memory_kind = str(item.get("memory_kind") or "").strip()
    content = str(item.get("content") or "").strip()
    if memory_kind not in {"fact", "relationship", "preference", "constraint", "long_term_goal", "mood_signal", "rhythm_signal", "care_preference"}:
        return None
    if not content or len(content) < 6:
        return None
    sensitivity = str(item.get("sensitivity") or "normal").strip()
    if sensitivity not in {"normal", "private", "sensitive"}:
        sensitivity = "normal"
    payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
    return MemoryCandidate(
        memory_kind=memory_kind,
        content=content,
        sensitivity=sensitivity,
        confidence=_clamp(item.get("confidence"), 0.65),
        importance=_clamp(item.get("importance"), 0.6),
        payload={"source": "llm_memory_extractor", **payload},
    )


def extract_memory_candidates(user_message: str, agent_reply: str = "") -> list[MemoryCandidate]:
    text = user_message.strip()
    if not text:
        return []

    candidates: list[MemoryCandidate] = []
    source_payload = {"source": "chat_turn", "agent_reply_excerpt": agent_reply[:160]}

    if _contains_any(text, _PREFERENCE_HINTS):
        sensitivity = "private" if _contains_any(text, _MOOD_HINTS + _RHYTHM_HINTS) else "normal"
        candidates.append(
            MemoryCandidate(
                memory_kind="preference",
                content=f"用户表达了偏好/约束：{text}",
                sensitivity=sensitivity,
                confidence=0.72,
                importance=0.75,
                payload={**source_payload, "category": "communication_or_care_preference"},
            )
        )

    if _contains_any(text, _MOOD_HINTS):
        candidates.append(
            MemoryCandidate(
                memory_kind="mood_signal",
                content=f"用户近期出现情绪压力信号：{text}",
                sensitivity="private",
                confidence=0.68,
                importance=0.8,
                payload={**source_payload, "privacy": "mental_health_related"},
            )
        )

    if _contains_any(text, _RHYTHM_HINTS):
        candidates.append(
            MemoryCandidate(
                memory_kind="rhythm_signal",
                content=f"用户近期出现生活节律/睡眠信号：{text}",
                sensitivity="private",
                confidence=0.68,
                importance=0.78,
                payload={**source_payload, "privacy": "life_rhythm_related"},
            )
        )

    if _contains_any(text, _LONG_TERM_HINTS):
        candidates.append(
            MemoryCandidate(
                memory_kind="long_term_goal",
                content=f"用户提到长期目标或未来任务：{text}",
                sensitivity="normal",
                confidence=0.65,
                importance=0.72,
                payload={**source_payload, "category": "goal_or_project"},
            )
        )

    if _contains_any(text, _RELATION_HINTS):
        candidates.append(
            MemoryCandidate(
                memory_kind="relationship",
                content=f"用户提到人际关系信息：{text}",
                sensitivity="normal",
                confidence=0.7,
                importance=0.7,
                payload={**source_payload, "category": "entity_relation"},
            )
        )

    return _dedupe_candidates(candidates)


async def extract_memory_candidates_with_llm(
    *,
    user_message: str,
    agent_reply: str,
    llm_client: Any | None,
) -> list[MemoryCandidate]:
    rule_candidates = extract_memory_candidates(user_message, agent_reply)
    if llm_client is None:
        return rule_candidates

    prompt = (
        "请从这轮私人助理对话中提取值得长期保存的记忆。\n"
        "只保存稳定、可复用的信息；不要保存寒暄、一次性临时状态或无关原文。\n"
        "允许的 memory_kind: fact, relationship, preference, constraint, long_term_goal, mood_signal, rhythm_signal, care_preference。\n"
        "sensitivity 只能是 normal/private/sensitive；心理、睡眠、健康、压力类必须 private 或 sensitive。\n"
        "每条 content 用中文概括，不要超过 80 字。最多 5 条。\n\n"
        f"User: {user_message}\n"
        f"Agent: {agent_reply}\n\n"
        "严格只输出 JSON：\n"
        "{\"memories\":[{\"memory_kind\":\"preference\",\"content\":\"...\",\"sensitivity\":\"normal\",\"confidence\":0.7,\"importance\":0.6,\"payload\":{}}]}\n"
        "如果没有值得保存的信息，输出 {\"memories\":[]}。"
    )
    try:
        raw = await llm_client.chat(
            message=prompt,
            system_prompt="你是私人助理系统的长期记忆提取器，只输出可解析 JSON。",
            temperature=0.0,
            max_tokens=700,
        )
        llm_candidates = [candidate for item in _parse_llm_json(raw) if (candidate := _candidate_from_llm_item(item))]
        if not llm_candidates:
            return rule_candidates
        return _dedupe_candidates([*llm_candidates, *rule_candidates])[:8]
    except Exception as exc:
        logger.warning("jarvis.memory.llm_extract_failed", error=str(exc))
        return rule_candidates


async def extract_and_save_chat_memories(
    *,
    user_message: str,
    agent_reply: str,
    source_agent: str,
    session_id: str | None,
    llm_client: Any | None = None,
) -> list[dict[str, Any]]:
    saved: list[dict[str, Any]] = []
    candidates = await extract_memory_candidates_with_llm(
        user_message=user_message,
        agent_reply=agent_reply,
        llm_client=llm_client,
    )
    for candidate in candidates:
        try:
            item = await save_jarvis_memory(
                memory_kind=candidate.memory_kind,
                content=candidate.content,
                source_agent=source_agent,
                session_id=session_id,
                source_text=user_message,
                structured_payload=candidate.payload,
                sensitivity=candidate.sensitivity,
                confidence=candidate.confidence,
                importance=candidate.importance,
            )
            saved.append(item)
        except Exception as exc:
            logger.warning(
                "jarvis.memory.save_candidate_failed",
                memory_kind=candidate.memory_kind,
                error=str(exc),
            )
    return saved


async def build_memory_recall_prefix(agent_id: str, limit: int = 6) -> str:
    memories = await list_jarvis_memories(limit=limit)
    if not memories:
        return ""

    memory_ids = [int(item["id"]) for item in memories if item.get("id") is not None]
    await mark_jarvis_memories_used(memory_ids)

    lines = ["## 长期记忆（仅在相关时使用，避免过度引用原文）"]
    for item in memories:
        kind = item.get("memory_kind", "memory")
        sensitivity = item.get("sensitivity", "normal")
        content = item.get("content", "")
        if sensitivity in {"private", "sensitive"}:
            lines.append(f"- [{kind}/隐私] {content}")
        else:
            lines.append(f"- [{kind}] {content}")
    lines.append("")
    return "\n".join(lines)
