"""Semantic cache middleware — caches LLM responses for similar queries.

Reduces redundant API calls by caching responses keyed by
a hash of the prompt. Phase 2+: embedding-based semantic similarity
for fuzzy cache hits.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any

import structlog
from cachetools import TTLCache

logger = structlog.get_logger("llm.middleware.cache")


class SemanticCache:
    """LLM response cache with TTL expiration.

    Phase 0: Exact match caching (prompt hash).
    Phase 2+: Embedding similarity for semantic matching.
    """

    def __init__(self, maxsize: int = 1000, ttl: int = 3600):
        self._cache: TTLCache[str, dict[str, Any]] = TTLCache(maxsize=maxsize, ttl=ttl)
        self._hits = 0
        self._misses = 0

    def get(self, prompt: str, model: str = "") -> str | None:
        """Look up a cached response."""
        key = self._make_key(prompt, model)
        entry = self._cache.get(key)
        if entry:
            self._hits += 1
            return entry["response"]
        self._misses += 1
        return None

    def put(self, prompt: str, response: str, model: str = "") -> None:
        """Cache an LLM response."""
        key = self._make_key(prompt, model)
        self._cache[key] = {
            "response": response,
            "model": model,
            "cached_at": time.time(),
        }

    def get_stats(self) -> dict[str, Any]:
        """Get cache hit/miss stats."""
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total if total > 0 else 0,
            "size": len(self._cache),
        }

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _make_key(prompt: str, model: str) -> str:
        content = f"{model}:{prompt}"
        return hashlib.sha256(content.encode()).hexdigest()[:24]
