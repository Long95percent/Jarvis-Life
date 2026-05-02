"""Common data models shared across all modules."""

from __future__ import annotations

import time
from enum import Enum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")

__all__ = [
    "Result",
    "PageResult",
    "StreamEvent",
    "StreamEventType",
    "ErrorDetail",
    "ModeContext",
    "TokenUsage",
    "LatencyMetrics",
]


class StreamEventType(str, Enum):
    """SSE event types for streaming responses."""

    TOKEN = "token"
    THOUGHT = "thought"
    ACTION = "action"
    OBSERVATION = "observation"
    PLAN = "plan"
    STEP_START = "step_start"
    STEP_RESULT = "step_result"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    RAG_CONTEXT = "rag_context"
    ERROR = "error"
    DONE = "done"
    HEARTBEAT = "heartbeat"
    AGENT_SPEAK = "agent_speak"
    IDEA_CREATED = "idea_created"
    PHASE_CHANGE = "phase_change"
    BRAINSTORM_DONE = "brainstorm_done"


class ErrorDetail(BaseModel):
    """Structured error detail."""

    code: str = Field(description="Error code, e.g. AGENT_TIMEOUT")
    message: str = Field(description="Human-readable error message")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional error context")


class Result(BaseModel, Generic[T]):
    """Unified API response wrapper, mirrors Java Result<T>."""

    success: bool = True
    code: int = 200
    message: str = "ok"
    data: T | None = None
    timestamp: int = Field(default_factory=lambda: int(time.time() * 1000))

    @classmethod
    def ok(cls, data: T | None = None, message: str = "ok") -> Result[T]:
        return cls(success=True, code=200, message=message, data=data)

    @classmethod
    def fail(cls, code: int = 500, message: str = "Internal Server Error", data: T | None = None) -> Result[T]:
        return cls(success=False, code=code, message=message, data=data)


class PageResult(BaseModel, Generic[T]):
    """Paginated response wrapper."""

    records: list[T] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    size: int = 20
    pages: int = 0


class StreamEvent(BaseModel):
    """Server-Sent Event payload for streaming responses."""

    event: StreamEventType
    data: dict[str, Any] = Field(default_factory=dict)
    session_id: str = ""
    step_id: str | None = None
    timestamp: int = Field(default_factory=lambda: int(time.time() * 1000))


class ModeContext(BaseModel):
    """Work mode context passed through the pipeline for ambient mode isolation."""

    mode_id: str = "general"
    system_prompt: str | None = None
    agent_config: dict[str, Any] = Field(default_factory=dict)
    tools_config: dict[str, Any] = Field(default_factory=dict)
    rag_config: dict[str, Any] = Field(default_factory=dict)
    theme_config: dict[str, Any] = Field(default_factory=dict)


class TokenUsage(BaseModel):
    """Token usage tracking."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model: str = ""


class LatencyMetrics(BaseModel):
    """Latency breakdown for observability."""

    total_ms: float = 0.0
    llm_ms: float = 0.0
    retrieval_ms: float = 0.0
    rerank_ms: float = 0.0
    tool_ms: float = 0.0
    embedding_ms: float = 0.0
