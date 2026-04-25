"""Supervisor MultiAgent pattern — one supervisor coordinates expert agents.

Topology:
    ┌──────────┐
    │Supervisor│──────┬──────┬──────┬──────┐
    └──────────┘      │      │      │      │
               ┌──────┴┐ ┌──┴───┐ ┌┴────┐ ┌┴──────┐
               │Coder  │ │Writer│ │RAG  │ │Review │
               │Agent  │ │Agent │ │Agent│ │Agent  │
               └───────┘ └──────┘ └─────┘ └───────┘

The supervisor analyzes the task, delegates to the most appropriate expert,
collects results, and decides whether to delegate further or finish.
"""

from __future__ import annotations

from typing import Any, Literal

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from app.agent.state import SupervisorState

logger = structlog.get_logger("agent.supervisor")

SUPERVISOR_PROMPT = """\
You are a supervisor coordinating a team of expert agents. Analyze the task and \
decide which expert to delegate to next, or finish if the task is complete.

Available experts: {experts}

Respond with EXACTLY one of: {options}

Current task: {task}
Results so far: {results}
"""


class SupervisorGraph:
    """Supervisor pattern: one coordinator dispatches to specialized agents."""

    def __init__(
        self,
        llm: BaseChatModel,
        expert_agents: dict[str, Any],
        max_iterations: int = 10,
    ):
        self.llm = llm
        self.expert_agents = expert_agents
        self.max_iterations = max_iterations

    def build(self) -> Any:
        """Compile the Supervisor StateGraph."""
        graph = StateGraph(SupervisorState)

        graph.add_node("supervisor", self._supervisor_node)
        for name, agent in self.expert_agents.items():
            graph.add_node(name, self._make_expert_node(name, agent))

        expert_names = list(self.expert_agents.keys())
        routing: dict[str, str] = {name: name for name in expert_names}
        routing["FINISH"] = END

        graph.add_edge(START, "supervisor")
        graph.add_conditional_edges("supervisor", self._route, routing)

        for name in expert_names:
            graph.add_edge(name, "supervisor")

        return graph.compile()

    async def _supervisor_node(self, state: SupervisorState) -> dict[str, Any]:
        """Supervisor decides which expert to invoke next."""
        expert_names = list(self.expert_agents.keys())
        options = expert_names + ["FINISH"]
        results_summary = "\n".join(f"  {k}: {v[:200]}" for k, v in state.get("agent_results", {}).items()) or "(none)"

        response = await self.llm.ainvoke([
            SystemMessage(content=SUPERVISOR_PROMPT.format(
                experts=", ".join(expert_names),
                options=", ".join(options),
                task=state["task"],
                results=results_summary,
            )),
            *state["messages"],
        ])

        decision = response.content.strip()
        if decision not in options:
            decision = "FINISH"

        iteration = state.get("iteration_count", 0)
        if iteration >= self.max_iterations:
            decision = "FINISH"

        return {
            "next_action": decision,
            "current_agent": decision if decision != "FINISH" else None,
            "iteration_count": iteration + 1,
        }

    def _route(self, state: SupervisorState) -> str:
        """Route based on supervisor's decision."""
        return state.get("next_action", "FINISH")

    @staticmethod
    def _make_expert_node(name: str, agent: Any) -> Any:
        """Create a wrapper node for an expert agent.

        If the agent has a `.run(task, context)` coroutine (i.e. it is an
        ExpertAgent from executor.py), it will be called for real execution.
        Otherwise raises NotImplementedError — use SupervisorExecutor for
        production execution with real expert agents.
        """

        async def node(state: SupervisorState) -> dict[str, Any]:
            task = state["task"]
            prev_results = state.get("agent_results", {})
            context = "\n".join(f"{k}: {v[:300]}" for k, v in prev_results.items()) if prev_results else ""

            if hasattr(agent, "run") and callable(agent.run):
                result = await agent.run(task, context=context)
            else:
                raise NotImplementedError(
                    f"Expert agent '{name}' has no run() method. "
                    "Use SupervisorExecutor from app.agent.multi_agent.executor "
                    "which provides real ExpertAgent instances."
                )

            agent_results = dict(prev_results)
            agent_results[name] = result

            history = list(state.get("delegation_history", []))
            history.append({"from_agent": "supervisor", "to_agent": name, "task": task[:200], "result": result[:300]})

            return {
                "agent_results": agent_results,
                "delegation_history": history,
                "messages": [AIMessage(content=f"[{name}] {result}")],
            }

        return node
