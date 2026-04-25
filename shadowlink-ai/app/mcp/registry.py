"""Unified tool registry — aggregates built-in, MCP, and plugin tools.

Single point of access for all tools available to the agent engine.
Manages tool lifecycle, discovery, and access control per work mode.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.models.mcp import ToolCategory, ToolInfo

logger = structlog.get_logger("mcp.registry")


class ToolRegistry:
    """Unified tool registry.

    Aggregates tools from:
    1. Built-in tools (app/tools/)
    2. MCP server (local tools exposed via MCP)
    3. MCP client (external tools from remote servers)
    4. Plugins (dynamically loaded plugins)
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolInfo] = {}
        self._handlers: dict[str, Any] = {}
        self._mode_restrictions: dict[str, set[str]] = {}  # mode_id -> allowed tool names

    def register(self, tool_info: ToolInfo, handler: Any) -> None:
        """Register a tool with its handler."""
        self._tools[tool_info.name] = tool_info
        self._handlers[tool_info.name] = handler

    def unregister(self, name: str) -> None:
        """Remove a tool from the registry."""
        self._tools.pop(name, None)
        self._handlers.pop(name, None)

    def get_tool(self, name: str) -> tuple[ToolInfo, Any] | None:
        """Get a tool's info and handler."""
        if name in self._tools:
            return self._tools[name], self._handlers[name]
        return None

    def list_tools(self, category: ToolCategory | None = None, mode_id: str | None = None) -> list[ToolInfo]:
        """List available tools, optionally filtered by category or mode."""
        tools = list(self._tools.values())

        if category:
            tools = [t for t in tools if t.category == category]

        if mode_id and mode_id in self._mode_restrictions:
            allowed = self._mode_restrictions[mode_id]
            tools = [t for t in tools if t.name in allowed]

        return tools

    def set_mode_restrictions(self, mode_id: str, allowed_tools: set[str]) -> None:
        """Set which tools are available in a specific work mode."""
        self._mode_restrictions[mode_id] = allowed_tools

    def get_handler(self, name: str) -> Any | None:
        """Get just the handler for a tool."""
        return self._handlers.get(name)

    @property
    def tool_count(self) -> int:
        return len(self._tools)
