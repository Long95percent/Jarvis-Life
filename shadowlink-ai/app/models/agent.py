"""Agent-related data models and LangGraph state re-exports."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# Re-export canonical state definitions from app.agent.state
from app.agent.state import AgentState, PlanExecuteState, SupervisorState

__all__ = [
    "AgentStrategy",
    "AgentRequest",
    "AgentResponse",
    "AgentStep",
    "PlanStep",
    "StepResult",
    "Delegation",
    "AgentDescriptor",
    "AgentState",
    "PlanExecuteState",
    "SupervisorState",
    "TaskComplexity",
]


# ── Enums ──


class AgentStrategy(str, Enum):
    """Available agent execution strategies."""

    REACT = "react"
    PLAN_EXECUTE = "plan_execute"
    SUPERVISOR = "supervisor"
    HIERARCHICAL = "hierarchical"
    SWARM = "swarm"
    HERMES = "hermes"
    BRAINSTORM = "brainstorm"
    DIRECT = "direct"  # simple LLM call, no agent loop


class TaskComplexity(str, Enum):
    """Task complexity classification for routing."""

    SIMPLE = "simple"  # Direct LLM answer
    MODERATE = "moderate"  # ReAct with tools
    COMPLEX = "complex"  # Plan-and-Execute
    MULTI_DOMAIN = "multi_domain"  # MultiAgent


# ── API Models (Pydantic) ──


class AgentRequest(BaseModel):
    """Request to execute an agent task."""

    session_id: str = Field(description="Chat session ID")
    mode_id: str = Field(default="general", description="Ambient work mode ID")
    message: str = Field(description="User message")
    strategy: AgentStrategy | None = Field(default=None, description="Force a specific strategy; None = auto-route")
    stream: bool = Field(default=True, description="Whether to stream the response")
    max_iterations: int = Field(default=15, ge=1, le=50, description="Max agent iterations")
    tools: list[str] | None = Field(default=None, description="Override available tool IDs")
    context: dict[str, Any] = Field(default_factory=dict, description="Additional context")


class AgentStep(BaseModel):
    """A single step in agent execution trace."""

    step_type: str = Field(description="thought | action | observation | answer | plan | replan")
    content: str = Field(default="")
    tool_name: str | None = None
    tool_input: dict[str, Any] = Field(default_factory=dict)
    tool_output: str | None = None
    token_count: int = 0
    latency_ms: float = 0.0


class PlanStep(BaseModel):
    """A single step in a plan."""

    index: int = Field(description="Step index (0-based)")
    description: str = Field(description="What this step does")
    tool: str | None = Field(default=None, description="Tool to use, if any")
    dependencies: list[int] = Field(default_factory=list, description="Indices of steps this depends on")
    status: str = Field(default="pending", description="pending | running | completed | failed | skipped")


class StepResult(BaseModel):
    """Result of executing a plan step."""

    step_index: int
    output: str = ""
    success: bool = True
    error: str | None = None
    latency_ms: float = 0.0


class Delegation(BaseModel):
    """Record of task delegation in multi-agent orchestration."""

    from_agent: str
    to_agent: str
    task: str
    result: str = ""
    latency_ms: float = 0.0


class AgentDescriptor(BaseModel):
    """Self-describing agent metadata for Hermes protocol."""

    name: str
    capabilities: list[str] = Field(default_factory=list)
    description: str = ""
    endpoint: str = ""
    max_concurrency: int = 1


class AgentResponse(BaseModel):
    """Non-streaming agent response."""

    session_id: str
    answer: str
    strategy: AgentStrategy
    steps: list[AgentStep] = Field(default_factory=list)
    total_tokens: int = 0
    total_latency_ms: float = 0.0


# ── LangGraph State Definitions ──
# Canonical definitions live in app.agent.state; re-exported above.
