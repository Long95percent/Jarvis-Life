"""Long-term memory — persistent cross-session knowledge.

Stores user preferences, learned facts, and interaction patterns
that persist across sessions. Uses file-based storage for Phase 0,
upgradeable to vector DB in production.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger("memory.long_term")


class MemoryEntry:
    """A single long-term memory entry."""

    def __init__(self, key: str, content: str, category: str = "general", metadata: dict[str, Any] | None = None):
        self.key = key
        self.content = content
        self.category = category
        self.metadata = metadata or {}
        self.created_at = time.time()
        self.last_accessed = time.time()
        self.access_count = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "content": self.content,
            "category": self.category,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "access_count": self.access_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryEntry:
        entry = cls(key=data["key"], content=data["content"], category=data.get("category", "general"), metadata=data.get("metadata", {}))
        entry.created_at = data.get("created_at", time.time())
        entry.last_accessed = data.get("last_accessed", time.time())
        entry.access_count = data.get("access_count", 0)
        return entry


class LongTermMemory:
    """File-based long-term memory store.

    Phase 0: JSON file storage.
    Phase 2+: Vector DB with semantic search.

    Features:
    - Agent self-editing (Letta pattern): agent can add/update/delete memories
    - Category-based organization (preferences, facts, patterns)
    - Access frequency tracking for relevance scoring
    """

    def __init__(self, storage_path: str = "./data/memory"):
        self._storage_path = Path(storage_path)
        self._storage_path.mkdir(parents=True, exist_ok=True)
        self._memories: dict[str, MemoryEntry] = {}
        self._load()

    def _load(self) -> None:
        """Load memories from disk."""
        memory_file = self._storage_path / "long_term.json"
        if memory_file.exists():
            try:
                data = json.loads(memory_file.read_text(encoding="utf-8"))
                self._memories = {k: MemoryEntry.from_dict(v) for k, v in data.items()}
            except (json.JSONDecodeError, KeyError):
                self._memories = {}

    def _save(self) -> None:
        """Persist memories to disk."""
        memory_file = self._storage_path / "long_term.json"
        data = {k: v.to_dict() for k, v in self._memories.items()}
        memory_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def add(self, key: str, content: str, category: str = "general", metadata: dict[str, Any] | None = None) -> None:
        """Add or update a memory entry."""
        self._memories[key] = MemoryEntry(key=key, content=content, category=category, metadata=metadata)
        self._save()

    def get(self, key: str) -> MemoryEntry | None:
        """Retrieve a memory entry by key."""
        entry = self._memories.get(key)
        if entry:
            entry.last_accessed = time.time()
            entry.access_count += 1
        return entry

    def search(self, query: str, category: str | None = None, limit: int = 10) -> list[MemoryEntry]:
        """Simple keyword search over memories. Phase 2+: semantic search."""
        results = []
        query_lower = query.lower()
        for entry in self._memories.values():
            if category and entry.category != category:
                continue
            if query_lower in entry.content.lower() or query_lower in entry.key.lower():
                results.append(entry)
        return sorted(results, key=lambda e: e.access_count, reverse=True)[:limit]

    def delete(self, key: str) -> bool:
        """Delete a memory entry."""
        if key in self._memories:
            del self._memories[key]
            self._save()
            return True
        return False

    def to_context(self, query: str = "", category: str | None = None) -> dict[str, Any]:
        """Export relevant memories as context dict for agent state."""
        if query:
            entries = self.search(query, category=category)
        else:
            entries = sorted(self._memories.values(), key=lambda e: e.last_accessed, reverse=True)[:10]

        if not entries:
            return {}

        return {
            "long_term": "\n".join(f"[{e.category}] {e.key}: {e.content}" for e in entries),
            "entry_count": len(entries),
        }
