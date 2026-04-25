"""File operations tool — read, write, and manage files.

Provides file system operations for the agent, with path restriction
to prevent access outside allowed directories.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.models.mcp import ToolCategory
from app.tools.base import ShadowLinkTool


class FileReadInput(BaseModel):
    path: str = Field(description="File path to read")
    max_lines: int = Field(default=100, ge=1, le=1000, description="Maximum lines to read")


class FileReadTool(ShadowLinkTool):
    """Read file contents."""

    name: str = "file_read"
    description: str = "Read the contents of a file. Returns the text content."
    args_schema: type[BaseModel] = FileReadInput
    category: ToolCategory = ToolCategory.FILE

    allowed_dirs: list[str] = Field(default_factory=lambda: ["./data"])

    def _run(self, path: str, max_lines: int = 100) -> str:
        raise NotImplementedError("Use async version")

    async def _arun(self, path: str, max_lines: int = 100) -> str:
        """Read a file with path restrictions."""
        file_path = Path(path).resolve()

        # Security: check path is within allowed directories
        allowed = any(str(file_path).startswith(str(Path(d).resolve())) for d in self.allowed_dirs)
        if not allowed:
            return f"Error: Access denied to {path}. Allowed directories: {self.allowed_dirs}"

        if not file_path.exists():
            return f"Error: File not found: {path}"

        try:
            lines = file_path.read_text(encoding="utf-8").splitlines()[:max_lines]
            return "\n".join(lines)
        except Exception as exc:
            return f"Error reading file: {exc}"
