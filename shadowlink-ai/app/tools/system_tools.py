"""System tools — time, calculations, and utility operations.

Provides basic utility tools that are always available regardless
of work mode configuration.
"""

from __future__ import annotations

import datetime
import math
from typing import Any

from pydantic import BaseModel, Field

from app.models.mcp import ToolCategory
from app.tools.base import ShadowLinkTool


class CurrentTimeInput(BaseModel):
    timezone: str = Field(default="Asia/Shanghai", description="Timezone name")


class CurrentTimeTool(ShadowLinkTool):
    """Get the current date and time."""

    name: str = "current_time"
    description: str = "Get the current date and time in the specified timezone."
    args_schema: type[BaseModel] = CurrentTimeInput
    category: ToolCategory = ToolCategory.SYSTEM

    def _run(self, timezone: str = "Asia/Shanghai") -> str:
        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo(timezone)
            now = datetime.datetime.now(tz)
            return f"Current time ({timezone}): {now.strftime('%Y-%m-%d %H:%M:%S %Z')}"
        except Exception:
            if timezone in {"Asia/Shanghai", "China", "CST", "UTC+8", "UTC+08:00"}:
                tz = datetime.timezone(datetime.timedelta(hours=8), name="UTC+08:00")
                now = datetime.datetime.now(tz)
                return f"Current time (Asia/Shanghai fallback): {now.strftime('%Y-%m-%d %H:%M:%S %Z')}"
            now = datetime.datetime.now(datetime.timezone.utc)
            return f"Current UTC time: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}"

    async def _arun(self, timezone: str = "Asia/Shanghai") -> str:
        return self._run(timezone)


class CalculatorInput(BaseModel):
    expression: str = Field(description="Mathematical expression to evaluate")


class CalculatorTool(ShadowLinkTool):
    """Evaluate mathematical expressions safely."""

    name: str = "calculator"
    description: str = "Evaluate a mathematical expression. Supports basic math, trig, log, etc."
    args_schema: type[BaseModel] = CalculatorInput
    category: ToolCategory = ToolCategory.SYSTEM

    # Safe math functions
    _SAFE_GLOBALS: dict[str, Any] = {
        "__builtins__": {},
        "abs": abs, "round": round, "min": min, "max": max,
        "sin": math.sin, "cos": math.cos, "tan": math.tan,
        "sqrt": math.sqrt, "log": math.log, "log10": math.log10,
        "pi": math.pi, "e": math.e, "pow": pow,
    }

    def _run(self, expression: str) -> str:
        try:
            result = eval(expression, self._SAFE_GLOBALS)  # noqa: S307
            return str(result)
        except Exception as exc:
            return f"Error: {exc}"

    async def _arun(self, expression: str) -> str:
        return self._run(expression)
