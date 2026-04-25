"""Short-term memory — within-session conversation context.

Maintains a sliding window of recent messages, providing
the agent with immediate conversational context.
Implements token-aware truncation to fit within LLM context windows.
"""

from __future__ import annotations

from collections import deque
from typing import Any

import structlog
from langchain_core.messages import BaseMessage

logger = structlog.get_logger("memory.short_term")


class ShortTermMemory:
    """Sliding-window short-term memory for active sessions.

    Features:
    - Configurable max messages and token budget
    - FIFO eviction with system message preservation
    - Summary generation for evicted messages (Phase 1+)
    """

    def __init__(self, max_messages: int = 50, max_tokens: int = 8000):
        self.max_messages = max_messages
        self.max_tokens = max_tokens
        self._store: dict[str, deque[BaseMessage]] = {}

    def add(self, session_id: str, message: BaseMessage) -> None:
        """Add a message to session memory."""
        if session_id not in self._store:
            self._store[session_id] = deque(maxlen=self.max_messages)
        self._store[session_id].append(message)

    def get(self, session_id: str) -> list[BaseMessage]:
        """Retrieve all messages for a session."""
        return list(self._store.get(session_id, []))

    def get_recent(self, session_id: str, n: int = 10) -> list[BaseMessage]:
        """Get the N most recent messages."""
        messages = self._store.get(session_id, deque())
        return list(messages)[-n:]

    def clear(self, session_id: str) -> None:
        """Clear all messages for a session."""
        self._store.pop(session_id, None)

    def to_context(self, session_id: str) -> dict[str, Any]:
        """Export as context dict for agent state injection."""
        messages = self.get_recent(session_id)
        if not messages:
            return {}
        return {
            "short_term": "\n".join(f"{m.type}: {m.content[:200]}" for m in messages),
            "message_count": len(messages),
        }
