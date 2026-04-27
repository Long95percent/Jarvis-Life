"""Bounded, role-aware long-term memory recall."""

from __future__ import annotations

import re
import time
from typing import Any

from app.jarvis.agents import JARVIS_AGENTS, get_agent
from app.jarvis.persistence import list_jarvis_memories, mark_jarvis_memories_used

_AGENT_KIND_WEIGHTS: dict[str, set[str]] = {
    "nora": {"preference", "constraint", "mood_signal", "rhythm_signal", "care_preference", "fact"},
    "mira": {"mood_signal", "rhythm_signal", "care_preference", "preference", "constraint"},
    "maxwell": {"long_term_goal", "preference", "constraint", "rhythm_signal", "fact"},
    "leo": {"preference", "mood_signal", "rhythm_signal", "fact", "relationship"},
    "alfred": {"preference", "constraint", "long_term_goal", "mood_signal", "rhythm_signal", "relationship", "fact", "care_preference"},
}

_AGENT_KEYWORDS: dict[str, set[str]] = {
    "nora": {"吃", "饮食", "营养", "咖啡", "水", "压力", "睡眠", "低刺激", "温热", "饭"},
    "mira": {"压力", "焦虑", "情绪", "睡眠", "崩溃", "难受", "安抚", "低打扰"},
    "maxwell": {"安排", "日程", "计划", "提醒", "学习", "任务", "deadline", "会议", "复盘"},
    "leo": {"活动", "社交", "恢复", "出门", "散步", "周末", "兴趣"},
    "alfred": {"安排", "计划", "压力", "目标", "偏好", "约束", "状态"},
}


def _tokens(text: str) -> set[str]:
    lowered = text.lower()
    ascii_tokens = set(re.findall(r"[a-z0-9_]+", lowered))
    cjk_tokens = {chunk for chunk in re.findall(r"[\u4e00-\u9fff]{2,}", text)}
    chars = {char for char in text if "\u4e00" <= char <= "\u9fff"}
    return ascii_tokens | cjk_tokens | chars


def _is_visible(memory: dict[str, Any], agent_id: str) -> bool:
    visibility = str(memory.get("visibility") or "global")
    owner = str(memory.get("owner_agent_id") or memory.get("source_agent") or "")
    allowed = set(memory.get("allowed_agent_ids") or [])
    if visibility == "global":
        return True
    if visibility == "private_raw":
        return agent_id == owner or agent_id in allowed
    if visibility == "agent_scoped":
        return agent_id == owner or agent_id in allowed
    if visibility == "sensitive_summary":
        return not allowed or agent_id == owner or agent_id in allowed
    return agent_id == owner or agent_id in allowed


def _score(memory: dict[str, Any], agent_id: str, user_message: str, now: float) -> float:
    score = float(memory.get("importance") or 0.5) * 3
    updated_at = float(memory.get("updated_at") or memory.get("created_at") or now)
    age_days = max(0.0, (now - updated_at) / 86400)
    score += max(0.0, 1.2 - age_days * 0.08)

    kind = str(memory.get("memory_kind") or "")
    if kind in _AGENT_KIND_WEIGHTS.get(agent_id, set()):
        score += 1.0

    owner = str(memory.get("owner_agent_id") or memory.get("source_agent") or "")
    if owner == agent_id or memory.get("source_agent") == agent_id:
        score += 0.8

    content_tokens = _tokens(str(memory.get("content") or ""))
    query_tokens = _tokens(user_message)
    overlap = len(content_tokens & query_tokens)
    score += min(2.0, overlap * 0.35)
    agent_keyword_overlap = len(content_tokens & _AGENT_KEYWORDS.get(agent_id, set()))
    score += min(1.2, agent_keyword_overlap * 0.3)

    tier = str(memory.get("memory_tier") or "raw")
    visibility = str(memory.get("visibility") or "global")
    if tier == "condensed":
        score += 0.35
    if visibility == "private_raw" and owner != agent_id:
        score -= 5.0
    if visibility == "sensitive_summary":
        score -= 0.15
    score -= float(memory.get("decay_score") or 0.0)
    return score


async def recall_bounded_memories(agent_id: str, user_message: str, limit: int = 6) -> list[dict[str, Any]]:
    if agent_id not in JARVIS_AGENTS or agent_id == "shadow":
        return []
    candidates = await list_jarvis_memories(limit=120)
    now = time.time()
    visible = [item for item in candidates if _is_visible(item, agent_id)]
    ranked = sorted(
        visible,
        key=lambda item: _score(item, agent_id, user_message, now),
        reverse=True,
    )
    return ranked[:limit]


async def build_bounded_memory_recall_prefix(agent_id: str, user_message: str, limit: int = 6) -> str:
    memories = await recall_bounded_memories(agent_id, user_message, limit=limit)
    if not memories:
        return ""
    memory_ids = [int(item["id"]) for item in memories if item.get("id") is not None]
    await mark_jarvis_memories_used(memory_ids)

    agent_name = get_agent(agent_id).get("name", agent_id)
    lines = [f"## 长期记忆（有边界共享，当前角色：{agent_name}）"]
    for item in memories:
        kind = item.get("memory_kind", "memory")
        tier = item.get("memory_tier", "raw")
        visibility = item.get("visibility", "global")
        sensitivity = item.get("sensitivity", "normal")
        marker = f"{kind}/{tier}/{visibility}"
        if sensitivity in {"private", "sensitive"}:
            marker += "/隐私摘要"
        lines.append(f"- [{marker}] {item.get('content', '')}")
    lines.append("")
    return "\n".join(lines)
