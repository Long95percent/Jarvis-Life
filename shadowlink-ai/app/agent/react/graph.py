"""ReAct loop graph definition using LangGraph StateGraph.

Implements: Thought -> Action -> Observation -> (Reflect) -> Repeat
With optional Reflexion self-critique for improved reasoning quality.
"""

from __future__ import annotations

from typing import Any, Literal

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from app.agent.state import AgentState

logger = structlog.get_logger("agent.react")


class ReactGraph:
    """ReAct loop: Thought -> Action -> Observation -> Repeat.

    Suitable for:
      - Simple Q&A with tool augmentation
      - Real-time interactive tasks
      - Information retrieval and aggregation

    Features:
      - Configurable max iterations (safety guard)
      - Optional Reflexion self-critique node
      - Mode-aware system prompt injection
    """

    def __init__(self, llm: BaseChatModel, tools: list[BaseTool], *, reflection_enabled: bool = True):
        self.llm = llm
        self.tools = tools
        self.reflection_enabled = reflection_enabled
        self.tool_node = ToolNode(tools)

    def build(self) -> Any:
        """Compile the ReAct StateGraph."""
        graph = StateGraph(AgentState)

        graph.add_node("reason", self._reason_node)
        graph.add_node("act", self.tool_node)
        if self.reflection_enabled:
            graph.add_node("reflect", self._reflect_node)

        graph.add_edge(START, "reason")
        graph.add_conditional_edges("reason", self._should_continue, self._routing_map())
        graph.add_edge("act", "reason")
        if self.reflection_enabled:
            graph.add_edge("reflect", "reason")

        return graph.compile()

    def _routing_map(self) -> dict[str, str]:
        routes: dict[str, str] = {"act": "act", "end": END}
        if self.reflection_enabled:
            routes["reflect"] = "reflect"
        return routes

    async def _reason_node(self, state: AgentState) -> dict[str, Any]:
        """LLM reasoning step: decide next action or produce final answer."""
        iteration = state.get("iteration_count", 0)
        max_iter = state.get("max_iterations", 15)

        if iteration >= max_iter:
            return {
                "messages": [AIMessage(content="Maximum iterations reached. Providing best available answer.")],
                "iteration_count": iteration,
            }

        try:
            llm_with_tools = self.llm.bind_tools(self.tools)
            response = await llm_with_tools.ainvoke(state["messages"])
        except Exception as e:
            logger.error(f"LLM invoke error: {e}")
            return {
                "messages": [AIMessage(content=f"An error occurred while calling the LLM: {str(e)}")],
                "iteration_count": iteration + 1,
            }

        return {
            "messages": [response],
            "iteration_count": iteration + 1,
        }

    def _should_continue(self, state: AgentState) -> Literal["act", "reflect", "end"]:
        """Route based on the last message: tool call -> act, otherwise -> end."""
        last_message = state["messages"][-1]

        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "act"

        # Trigger reflection every N iterations if enabled
        iteration = state.get("iteration_count", 0)
        if self.reflection_enabled and iteration > 0 and iteration % 5 == 0:
            return "reflect"

        return "end"

    async def _reflect_node(self, state: AgentState) -> dict[str, Any]:
        """Reflexion self-critique: evaluate reasoning quality and suggest improvements."""
        reflection_prompt = (
            "Review the reasoning so far. Are there any logical gaps, "
            "missed considerations, or better approaches? Be concise."
        )

        response = await self.llm.ainvoke([
            SystemMessage(content="You are a reasoning quality reviewer."),
            *state["messages"],
            SystemMessage(content=reflection_prompt),
        ])

        notes = list(state.get("reflection_notes", []))
        notes.append(response.content)

        return {
            "messages": [SystemMessage(content=f"[Reflection] {response.content}")],
            "reflection_notes": notes,
        }
