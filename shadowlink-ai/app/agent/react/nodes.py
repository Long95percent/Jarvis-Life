"""Utility node functions for the ReAct graph.

Provides reusable node building blocks: system prompt injection,
memory loading, RAG context injection, and iteration guard.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import SystemMessage

from app.agent.state import AgentState


def inject_system_prompt(state: AgentState, system_prompt: str) -> dict[str, Any]:
    """Prepend a mode-specific system prompt to the message history."""
    messages = list(state["messages"])
    if not messages or not isinstance(messages[0], SystemMessage):
        messages.insert(0, SystemMessage(content=system_prompt))
    return {"messages": messages}


def inject_rag_context(state: AgentState) -> dict[str, Any]:
    """Inject RAG retrieval results into the conversation as a system message."""
    rag_context = state.get("rag_context", "")
    if not rag_context:
        return {}

    context_message = SystemMessage(
        content=f"[Retrieved Context]\n{rag_context}\n\nUse the above context to inform your response."
    )
    return {"messages": [context_message]}


def inject_memory_context(state: AgentState) -> dict[str, Any]:
    """Inject memory (short-term + long-term) as system context."""
    memory = state.get("memory_context", {})
    if not memory:
        return {}

    parts = []
    if short_term := memory.get("short_term"):
        parts.append(f"[Recent Context]\n{short_term}")
    if long_term := memory.get("long_term"):
        parts.append(f"[Long-term Memory]\n{long_term}")
    if episodic := memory.get("episodic"):
        parts.append(f"[Past Experiences]\n{episodic}")

    if not parts:
        return {}

    return {"messages": [SystemMessage(content="\n\n".join(parts))]}


def check_iteration_limit(state: AgentState) -> bool:
    """Return True if the agent has exceeded its iteration limit."""
    return state.get("iteration_count", 0) >= state.get("max_iterations", 15)
