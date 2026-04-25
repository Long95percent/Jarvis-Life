"""Swarm MultiAgent pattern — decentralized peer-to-peer collaboration.

Agents operate as equal peers, sharing observations and reaching consensus
through multiple rounds of proposal and evaluation. No central coordinator.
"""

from __future__ import annotations

from typing import Any

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from app.agent.state import SwarmState

logger = structlog.get_logger("agent.swarm")


class SwarmGraph:
    """Swarm collaboration: agents negotiate and reach consensus.

    Each agent independently analyzes the task, proposes a solution,
    and evaluates peers' proposals. Consensus is reached when proposals
    converge or max rounds are exhausted.
    """

    def __init__(self, llm: BaseChatModel, agent_names: list[str], max_rounds: int = 3):
        self.llm = llm
        self.agent_names = agent_names
        self.max_rounds = max_rounds

    def build(self) -> Any:
        """Compile the Swarm StateGraph."""
        graph = StateGraph(SwarmState)

        graph.add_node("propose", self._propose_node)
        graph.add_node("evaluate", self._evaluate_node)
        graph.add_node("synthesize", self._synthesize_node)

        graph.add_edge(START, "propose")
        graph.add_edge("propose", "evaluate")
        graph.add_conditional_edges("evaluate", self._check_consensus, {
            "continue": "propose",
            "done": "synthesize",
        })
        graph.add_edge("synthesize", END)

        return graph.compile()

    async def _propose_node(self, state: SwarmState) -> dict[str, Any]:
        """Each agent proposes a solution."""
        outputs: dict[str, str] = {}
        for name in self.agent_names:
            previous = state.get("agent_outputs", {}).get(name, "")
            peer_outputs = {k: v for k, v in state.get("agent_outputs", {}).items() if k != name}

            response = await self.llm.ainvoke([
                SystemMessage(content=f"You are agent '{name}'. Propose a solution."),
                HumanMessage(content=(
                    f"Task: {state['task']}\n"
                    f"Your previous proposal: {previous or '(none)'}\n"
                    f"Peer proposals: {peer_outputs or '(none)'}"
                )),
            ])
            outputs[name] = response.content

        return {"agent_outputs": outputs, "round_count": state.get("round_count", 0) + 1}

    async def _evaluate_node(self, state: SwarmState) -> dict[str, Any]:
        """Evaluate convergence of proposals."""
        proposals = state.get("agent_outputs", {})
        if len(set(proposals.values())) <= 1:
            return {"consensus": True}

        # Use LLM to check if proposals are semantically aligned
        response = await self.llm.ainvoke([
            SystemMessage(content="Evaluate if these proposals are substantially aligned."),
            HumanMessage(content=f"Proposals:\n{proposals}\n\nRespond with 'ALIGNED' or 'DIVERGENT'."),
        ])
        consensus = "ALIGNED" in response.content.upper()
        return {"consensus": consensus}

    @staticmethod
    def _check_consensus(state: SwarmState) -> str:
        if state.get("consensus", False):
            return "done"
        if state.get("round_count", 0) >= state.get("max_rounds", 3):
            return "done"
        return "continue"

    async def _synthesize_node(self, state: SwarmState) -> dict[str, Any]:
        """Synthesize final answer from agent proposals."""
        proposals = state.get("agent_outputs", {})
        response = await self.llm.ainvoke([
            SystemMessage(content="Synthesize the best answer from these proposals."),
            HumanMessage(content=f"Task: {state['task']}\nProposals:\n{proposals}"),
        ])
        return {"messages": [AIMessage(content=response.content)]}
