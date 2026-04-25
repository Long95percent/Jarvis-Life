"""Dynamic re-planning module — adjusts plans when steps fail or context changes.

The Replanner reviews completed results and current issues to produce
an updated plan that adapts to new information.
"""

from __future__ import annotations

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.models.agent import PlanStep, StepResult

logger = structlog.get_logger("agent.replanner")

REPLANNER_PROMPT = """\
You are a task re-planning expert. A plan is being executed but needs adjustment.

Original plan:
{plan}

Completed steps and results:
{completed}

Current issue:
{issue}

Create an updated plan (JSON array) for the REMAINING steps only. \
Adjust strategy based on what was learned from completed steps.
"""


class Replanner:
    """Re-plans remaining steps based on execution results and issues."""

    def __init__(self, llm: BaseChatModel):
        self.llm = llm

    async def replan(
        self,
        original_plan: list[PlanStep],
        completed_results: list[StepResult],
        issue: str,
    ) -> list[PlanStep]:
        """Generate an updated plan for remaining steps."""
        plan_desc = "\n".join(f"  {s.index}. {s.description} (tool: {s.tool or 'none'})" for s in original_plan)
        completed_desc = "\n".join(
            f"  Step {r.step_index}: {'OK' if r.success else 'FAILED'} — {r.output[:200]}"
            for r in completed_results
        ) or "(none)"

        response = await self.llm.ainvoke([
            SystemMessage(content=REPLANNER_PROMPT.format(
                plan=plan_desc,
                completed=completed_desc,
                issue=issue,
            )),
            HumanMessage(content="Please provide the updated plan as a JSON array."),
        ])

        new_steps = self._parse_replan(response.content, start_index=len(completed_results))
        await logger.ainfo("replanned", new_steps=len(new_steps), issue_preview=issue[:100])
        return new_steps

    @staticmethod
    def _parse_replan(content: str, start_index: int) -> list[PlanStep]:
        """Parse re-planner LLM output into PlanStep list."""
        import json

        try:
            content = content.strip()
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            raw = json.loads(content)
            steps = []
            for i, step_data in enumerate(raw):
                step_data["index"] = start_index + i
                steps.append(PlanStep(**step_data))
            return steps
        except (json.JSONDecodeError, KeyError, TypeError):
            return [PlanStep(index=start_index, description=content or "Continue with adjusted approach")]
