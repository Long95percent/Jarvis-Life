"""Plan-and-Execute graph definition using LangGraph StateGraph.

Flow: Planner -> Executor (loop) -> Replanner (on failure) -> Reporter
"""

from __future__ import annotations

from typing import Any, Literal

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph

from app.agent.plan_execute.executor import StepExecutor
from app.agent.plan_execute.planner import Planner
from app.agent.plan_execute.replan import Replanner
from app.agent.state import PlanExecuteState
from app.models.agent import PlanStep, StepResult

logger = structlog.get_logger("agent.plan_execute")


class PlanExecuteGraph:
    """Plan-and-Execute: plan first, execute step by step, replan on failure.

    Suitable for:
      - Complex multi-step tasks
      - Research and report generation
      - Project management and task decomposition
    """

    def __init__(self, llm: BaseChatModel, tools: list[BaseTool]):
        self.planner = Planner(llm)
        self.executor = StepExecutor(llm, {t.name: t for t in tools})
        self.replanner = Replanner(llm)
        self.llm = llm

    def build(self) -> Any:
        """Compile the Plan-and-Execute StateGraph."""
        graph = StateGraph(PlanExecuteState)

        graph.add_node("planner", self._plan_node)
        graph.add_node("executor", self._execute_step_node)
        graph.add_node("replanner", self._replan_node)
        graph.add_node("reporter", self._report_node)

        graph.add_edge(START, "planner")
        graph.add_edge("planner", "executor")
        graph.add_conditional_edges("executor", self._check_progress, {
            "continue": "executor",
            "replan": "replanner",
            "report": "reporter",
        })
        graph.add_edge("replanner", "executor")
        graph.add_edge("reporter", END)

        return graph.compile()

    async def _plan_node(self, state: PlanExecuteState) -> dict[str, Any]:
        """Generate the initial execution plan."""
        plan_steps = await self.planner.create_plan(state["input"])
        return {
            "plan": [s.model_dump() for s in plan_steps],
            "step_index": 0,
            "step_results": [],
            "completed_steps": [],
        }

    async def _execute_step_node(self, state: PlanExecuteState) -> dict[str, Any]:
        """Execute the current plan step."""
        plan = [PlanStep(**s) for s in state["plan"]]
        idx = state["step_index"]

        if idx >= len(plan):
            return {"final_answer": "All steps completed."}

        step = plan[idx]
        previous = [StepResult(**r) for r in state["step_results"]]
        result = await self.executor.execute_step(step, previous)

        step_results = list(state["step_results"])
        step_results.append(result.model_dump())

        completed = list(state["completed_steps"])
        completed.append(f"Step {idx}: {step.description} -> {'OK' if result.success else 'FAILED'}")

        update: dict[str, Any] = {
            "step_results": step_results,
            "completed_steps": completed,
            "step_index": idx + 1,
            "messages": [AIMessage(content=f"[Step {idx}] {result.output[:500]}")],
        }

        if not result.success:
            update["current_issue"] = result.error or "Step failed without error message"

        return update

    @staticmethod
    def _check_progress(state: PlanExecuteState) -> Literal["continue", "replan", "report"]:
        """Decide whether to continue, replan, or finish."""
        if state.get("current_issue"):
            return "replan"

        plan = state["plan"]
        idx = state["step_index"]

        if idx >= len(plan):
            return "report"

        return "continue"

    async def _replan_node(self, state: PlanExecuteState) -> dict[str, Any]:
        """Replan remaining steps based on the current issue."""
        original_plan = [PlanStep(**s) for s in state["plan"]]
        completed_results = [StepResult(**r) for r in state["step_results"]]
        issue = state.get("current_issue", "Unknown issue")

        new_steps = await self.replanner.replan(original_plan, completed_results, issue)

        return {
            "plan": [s.model_dump() for s in new_steps],
            "step_index": 0,
            "current_issue": None,
        }

    async def _report_node(self, state: PlanExecuteState) -> dict[str, Any]:
        """Synthesize final report from all step results."""
        completed = "\n".join(state["completed_steps"])
        response = await self.llm.ainvoke([
            HumanMessage(content=f"Summarize the results:\n\nOriginal task: {state['input']}\n\nCompleted steps:\n{completed}"),
        ])
        return {
            "final_answer": response.content,
            "messages": [AIMessage(content=response.content)],
        }
