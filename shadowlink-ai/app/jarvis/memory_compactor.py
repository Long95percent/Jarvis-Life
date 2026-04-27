"""Lifecycle compaction for old raw Jarvis memories."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

from app.jarvis.persistence import archive_jarvis_memories, list_jarvis_memories, save_jarvis_memory

_last_compaction_run_at: float | None = None


def _group_key(memory: dict[str, Any]) -> tuple[str, str]:
    owner = str(memory.get("owner_agent_id") or memory.get("source_agent") or "system")
    sensitivity = str(memory.get("sensitivity") or "normal")
    return owner, sensitivity


def _summary_for_group(memories: list[dict[str, Any]]) -> str:
    parts = [str(item.get("content") or "").strip() for item in memories if str(item.get("content") or "").strip()]
    joined = "；".join(parts[:4])
    return f"压缩记忆：{joined[:360]}"


async def compact_old_raw_memories(cutoff_days: int = 7, limit: int = 80) -> dict[str, Any]:
    cutoff = time.time() - cutoff_days * 86400
    active = await list_jarvis_memories(limit=limit)
    old_raw = [
        item for item in active
        if item.get("memory_tier") == "raw"
        and float(item.get("created_at") or 0) <= cutoff
    ]
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in old_raw:
        groups[_group_key(item)].append(item)

    condensed: list[dict[str, Any]] = []
    archived_ids: list[int] = []
    for (owner, sensitivity), items in groups.items():
        source_agent = owner if owner != "system" else str(items[0].get("source_agent") or "system")
        allowed = sorted({agent for item in items for agent in (item.get("allowed_agent_ids") or [])})
        source_ids = [int(item["id"]) for item in items if item.get("id") is not None]
        importance = max(float(item.get("importance") or 0.5) for item in items)
        visibility = "sensitive_summary" if sensitivity in {"private", "sensitive"} else "global"
        if visibility == "sensitive_summary" and not allowed:
            allowed = [owner] if owner != "system" else [source_agent]
        condensed_item = await save_jarvis_memory(
            memory_kind="summary",
            content=_summary_for_group(items),
            source_agent=source_agent,
            session_id=None,
            source_text=None,
            sensitivity=sensitivity,
            confidence=max(float(item.get("confidence") or 0.6) for item in items),
            importance=importance,
            memory_tier="condensed",
            visibility=visibility,
            owner_agent_id=owner,
            allowed_agent_ids=allowed,
            compressed_from_ids=source_ids,
            decay_score=0.0,
        )
        condensed.append(condensed_item)
        archived_ids.extend(source_ids)

    archived_count = await archive_jarvis_memories(archived_ids)
    return {
        "compacted_count": archived_count,
        "condensed_count": len(condensed),
        "condensed_memories": condensed,
        "archived_ids": archived_ids,
    }


async def maybe_compact_old_raw_memories(
    *,
    cutoff_days: int = 7,
    min_interval_seconds: int = 3600,
    force: bool = False,
) -> dict[str, Any]:
    """Run compaction at most once per interval to keep chat latency bounded."""
    global _last_compaction_run_at
    now = time.time()
    if not force and _last_compaction_run_at is not None and now - _last_compaction_run_at < min_interval_seconds:
        return {
            "skipped": True,
            "reason": "interval_not_elapsed",
            "compacted_count": 0,
            "condensed_count": 0,
            "condensed_memories": [],
            "archived_ids": [],
        }
    _last_compaction_run_at = now
    result = await compact_old_raw_memories(cutoff_days=cutoff_days)
    result["skipped"] = False
    return result
