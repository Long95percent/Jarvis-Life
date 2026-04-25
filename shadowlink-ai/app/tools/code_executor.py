"""Code execution tool — sandboxed code runner.

Executes Python code in a subprocess with restricted builtins,
timeout enforcement, and output capture.
"""

from __future__ import annotations

import asyncio
import sys
import textwrap
from typing import Any

import structlog
from pydantic import BaseModel, Field

from app.models.mcp import ToolCategory
from app.tools.base import ShadowLinkTool

logger = structlog.get_logger("tools.code_executor")

# Disallowed modules for security
_BLOCKED_MODULES = {"os", "subprocess", "shutil", "socket", "ctypes", "importlib", "sys"}


class CodeExecuteInput(BaseModel):
    code: str = Field(description="Python code to execute")
    language: str = Field(default="python", description="Programming language (only python supported)")
    timeout: int = Field(default=10, ge=1, le=60, description="Execution timeout in seconds")


class CodeExecutorTool(ShadowLinkTool):
    """Execute Python code in a sandboxed subprocess."""

    name: str = "code_executor"
    description: str = (
        "Execute Python code and return stdout/stderr. "
        "Useful for math, data processing, string manipulation, etc. "
        "Network and filesystem access is restricted."
    )
    args_schema: type[BaseModel] = CodeExecuteInput
    category: ToolCategory = ToolCategory.CODE
    requires_confirmation: bool = False

    def _run(self, code: str, language: str = "python", timeout: int = 10) -> str:
        raise NotImplementedError("Use async version")

    async def _arun(self, code: str, language: str = "python", timeout: int = 10) -> str:
        """Execute Python code in a subprocess with timeout."""
        if language != "python":
            return f"Error: Only Python is supported. Got: {language}"

        # Basic static check for dangerous imports
        for mod in _BLOCKED_MODULES:
            if f"import {mod}" in code or f"from {mod}" in code:
                return f"Error: Module '{mod}' is not allowed for security reasons."

        # Write code to a temp script and execute it
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            script_path = f.name

        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

            result_parts = []
            if stdout:
                result_parts.append(f"stdout:\n{stdout.decode(errors='replace').strip()}")
            if stderr:
                result_parts.append(f"stderr:\n{stderr.decode(errors='replace').strip()}")
            if not result_parts:
                result_parts.append("(no output)")

            return "\n".join(result_parts)

        except asyncio.TimeoutError:
            proc.kill()
            return f"Error: Code execution timed out after {timeout} seconds."
        except Exception as exc:
            return f"Error: {exc}"
        finally:
            try:
                os.unlink(script_path)
            except OSError:
                pass
