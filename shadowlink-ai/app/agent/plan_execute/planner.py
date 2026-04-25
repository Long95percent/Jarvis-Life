"""Plan generation module — produces structured execution plans from user input.

Uses an LLM to decompose complex tasks into ordered steps with tool assignments
and dependency tracking. Supports plan caching for repeated task patterns.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import structlog
from cachetools import TTLCache
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.models.agent import PlanStep

logger = structlog.get_logger("agent.planner")

PLANNER_PROMPT = """\
You are a task planning expert. Given a user request, decompose it into a structured \
execution plan with ordered steps.

Output a JSON array where each element has:
- "index": step number (0-based)
- "description": what this step accomplishes
- "tool": tool to use (null if no tool needed)
- "dependencies": list of step indices this depends on

Rules:
- Keep steps atomic and actionable
- Identify tool usage where beneficial
- Mark dependencies between steps
- Aim for 3-8 steps (avoid over-decomposition)
"""


class Planner:
    """Generates structured execution plans from natural language tasks."""

    def __init__(self, llm: BaseChatModel, *, cache_enabled: bool = True, cache_ttl: int = 3600):
        self.llm = llm
        self._cache: TTLCache[str, list[PlanStep]] | None = TTLCache(maxsize=256, ttl=cache_ttl) if cache_enabled else None

    async def create_plan(self, task: str, context: str = "") -> list[PlanStep]:
        """Generate a plan for the given task."""
        cache_key = self._cache_key(task)

        if self._cache is not None and cache_key in self._cache:
            await logger.ainfo("plan_cache_hit", task_preview=task[:80])
            return self._cache[cache_key]

        messages = [
            SystemMessage(content=PLANNER_PROMPT),
            HumanMessage(content=f"Task: {task}\n\nContext: {context}" if context else f"Task: {task}"),
        ]

        response = await self.llm.ainvoke(messages)
        steps = self._parse_plan(response.content)

        if self._cache is not None:
            self._cache[cache_key] = steps

        await logger.ainfo("plan_created", steps=len(steps), task_preview=task[:80])
        return steps

    @staticmethod
    def _parse_plan(content: str) -> list[PlanStep]:
        """Parse LLM output into a list of PlanStep objects."""
        try:
            # Extract JSON array from LLM response
            content = content.strip()
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            raw = json.loads(content)
            return [PlanStep(**step) for step in raw]
        except (json.JSONDecodeError, KeyError, TypeError):
            # Fallback: single step wrapping the entire task
            return [PlanStep(index=0, description=content or "Execute the task")]

    @staticmethod
    def _cache_key(task: str) -> str:
        """Generate a deterministic cache key from task text."""
        normalized = task.strip().lower()
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]
