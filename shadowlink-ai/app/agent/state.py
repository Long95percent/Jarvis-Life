"""Agent state definitions for LangGraph graph execution.

These TypedDicts are the core state schemas that flow through LangGraph
StateGraphs. Each agent strategy has its own state shape.
"""

from __future__ import annotations

from typing import Annotated, Any, Sequence, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """ReAct Agent state — reasoning + acting loop.

    Fields:
        messages: Conversation history (auto-merged via add_messages reducer).
        mode_id: Current ambient work mode for context isolation.
        tools_available: List of tool names the agent can invoke.
        memory_context: Retrieved memory (short-term + long-term).
        rag_context: Injected RAG retrieval results.
        iteration_count: Current loop iteration (for safety limit).
        max_iterations: Maximum allowed iterations.
        reflection_notes: Notes from Reflexion self-critique.
    """

    messages: Annotated[Sequence[BaseMessage], add_messages]
    mode_id: str
    tools_available: list[str]
    memory_context: dict[str, Any]
    rag_context: str
    iteration_count: int
    max_iterations: int
    reflection_notes: list[str]


class PlanExecuteState(TypedDict):
    """Plan-and-Execute Agent state — plan first, then execute step by step.

    Fields:
        messages: Conversation history.
        input: Original user input.
        plan: List of planned steps (serialized PlanStep dicts).
        step_index: Index of the current step being executed.
        step_results: Results from completed steps.
        completed_steps: Human-readable descriptions of completed steps.
        current_issue: Issue that triggered re-planning (None if on track).
        final_answer: The assembled final answer (None until report phase).
        plan_cache_key: Hash key for plan caching.
    """

    messages: Annotated[Sequence[BaseMessage], add_messages]
    input: str
    plan: list[dict[str, Any]]
    step_index: int
    step_results: list[dict[str, Any]]
    completed_steps: list[str]
    current_issue: str | None
    final_answer: str | None
    plan_cache_key: str


class SupervisorState(TypedDict):
    """Supervisor MultiAgent state — one supervisor routes to expert agents.

    Fields:
        messages: Conversation history.
        task: The original task description.
        current_agent: Which expert agent is currently active.
        agent_results: Collected results from each expert.
        delegation_history: Full delegation audit trail.
        next_action: Supervisor's routing decision.
        iteration_count: Safety counter.
    """

    messages: Annotated[Sequence[BaseMessage], add_messages]
    task: str
    current_agent: str | None
    agent_results: dict[str, str]
    delegation_history: list[dict[str, Any]]
    next_action: str
    iteration_count: int


class SwarmState(TypedDict):
    """Swarm Agent state — decentralized peer-to-peer collaboration.

    Fields:
        messages: Shared conversation history.
        task: The original task.
        agent_outputs: Each agent's latest output.
        consensus: Whether agents have reached consensus.
        round_count: Current negotiation round.
        max_rounds: Maximum rounds before forced conclusion.
    """

    messages: Annotated[Sequence[BaseMessage], add_messages]
    task: str
    agent_outputs: dict[str, str]
    consensus: bool
    round_count: int
    max_rounds: int
