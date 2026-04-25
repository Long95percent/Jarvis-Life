"""Token counter middleware — tracks token usage across LLM calls.

Provides usage metrics for cost tracking and context window management.
"""

from __future__ import annotations

import threading

import structlog

from app.models.common import TokenUsage

logger = structlog.get_logger("llm.middleware.token_counter")


class TokenCounter:
    """Thread-safe token usage tracker."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._total_prompt: int = 0
        self._total_completion: int = 0
        self._call_count: int = 0

    def record(self, usage: TokenUsage) -> None:
        """Record token usage from an LLM call."""
        with self._lock:
            self._total_prompt += usage.prompt_tokens
            self._total_completion += usage.completion_tokens
            self._call_count += 1

    def get_stats(self) -> dict[str, int]:
        """Get aggregated token usage stats."""
        with self._lock:
            return {
                "total_prompt_tokens": self._total_prompt,
                "total_completion_tokens": self._total_completion,
                "total_tokens": self._total_prompt + self._total_completion,
                "call_count": self._call_count,
            }

    def reset(self) -> None:
        """Reset all counters."""
        with self._lock:
            self._total_prompt = 0
            self._total_completion = 0
            self._call_count = 0

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Rough token count estimation (4 chars ~= 1 token for English, 2 chars for Chinese)."""
        ascii_chars = sum(1 for c in text if ord(c) < 128)
        non_ascii = len(text) - ascii_chars
        return (ascii_chars // 4) + (non_ascii // 2) + 1
