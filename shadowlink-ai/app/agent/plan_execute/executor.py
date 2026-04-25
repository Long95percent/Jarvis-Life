"""Step executor — runs individual plan steps using tools and LLM.

Each step may involve tool calls, LLM reasoning, or both.
Tracks latency and success/failure for observability.
"""

from __future__ import annotations

import time
from typing import Any

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool

from app.models.agent import PlanStep, StepResult

logger = structlog.get_logger("agent.executor")

EXECUTOR_PROMPT = """\
You are executing step {index} of a plan.

Step description: {description}
Tool to use: {tool}

Previous step results:
{previous_results}

Execute this step and provide a clear, concise result.
"""


class StepExecutor:
    """Executes individual plan steps with tool support."""

    def __init__(self, llm: BaseChatModel, tools: dict[str, BaseTool]):
        self.llm = llm
        self.tools = tools

    async def execute_step(
        self,
        step: PlanStep,
        previous_results: list[StepResult],
    ) -> StepResult:
        """Execute a single plan step and return the result."""
        start = time.perf_counter()

        try:
            # If step specifies a tool, try to use it
            if step.tool and step.tool in self.tools:
                result = await self._execute_with_tool(step, previous_results)
            else:
                result = await self._execute_with_llm(step, previous_results)

            elapsed = (time.perf_counter() - start) * 1000
            await logger.ainfo("step_executed", index=step.index, latency_ms=round(elapsed, 2))

            return StepResult(
                step_index=step.index,
                output=result,
                success=True,
                latency_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            await logger.aerror("step_failed", index=step.index, error=str(exc))
            return StepResult(
                step_index=step.index,
                output="",
                success=False,
                error=str(exc),
                latency_ms=elapsed,
            )

    async def _execute_with_tool(self, step: PlanStep, previous_results: list[StepResult]) -> str:
        """Execute step using the specified tool."""
        tool = self.tools[step.tool]  # type: ignore[index]

        # Use LLM to generate tool input
        prompt = self._build_prompt(step, previous_results)
        response = await self.llm.ainvoke([
            SystemMessage(content="Generate the input for the tool call. Return only the tool arguments as JSON."),
            HumanMessage(content=prompt),
        ])

        tool_result = await tool.ainvoke(response.content)
        return str(tool_result)

    async def _execute_with_llm(self, step: PlanStep, previous_results: list[StepResult]) -> str:
        """Execute step using only LLM reasoning."""
        prompt = self._build_prompt(step, previous_results)
        response = await self.llm.ainvoke([HumanMessage(content=prompt)])
        return response.content

    @staticmethod
    def _build_prompt(step: PlanStep, previous_results: list[StepResult]) -> str:
        prev_summary = "\n".join(
            f"  Step {r.step_index}: {'OK' if r.success else 'FAILED'} — {r.output[:200]}"
            for r in previous_results
        ) or "(none)"

        return EXECUTOR_PROMPT.format(
            index=step.index,
            description=step.description,
            tool=step.tool or "(none)",
            previous_results=prev_summary,
        )
