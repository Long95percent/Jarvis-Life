"""MCP Server — exposes ShadowLink tools via the Model Context Protocol.

Allows external LLM clients to discover and invoke ShadowLink's built-in
tools through the standardized MCP protocol. Supports both stdio and
HTTP transport modes.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.models.mcp import ToolCallRequest, ToolCallResponse, ToolInfo

logger = structlog.get_logger("mcp.server")


class MCPServer:
    """MCP Server implementation.

    Exposes ShadowLink's tool registry as MCP-compatible tools.
    External AI agents can discover and call these tools.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolInfo] = {}
        self._handlers: dict[str, Any] = {}

    def register_tool(self, tool_info: ToolInfo, handler: Any) -> None:
        """Register a tool with its handler function."""
        self._tools[tool_info.name] = tool_info
        self._handlers[tool_info.name] = handler
        logger.info("mcp_tool_registered", tool=tool_info.name)

    async def list_tools(self) -> list[ToolInfo]:
        """List all available tools (MCP tools/list)."""
        return list(self._tools.values())

    async def call_tool(self, request: ToolCallRequest) -> ToolCallResponse:
        """Execute a tool call (MCP tools/call)."""
        if request.tool_name not in self._handlers:
            return ToolCallResponse(
                tool_name=request.tool_name,
                success=False,
                error=f"Tool '{request.tool_name}' not found",
            )

        handler = self._handlers[request.tool_name]
        try:
            import time

            start = time.perf_counter()
            result = await handler(**request.arguments)
            elapsed = (time.perf_counter() - start) * 1000

            return ToolCallResponse(
                tool_name=request.tool_name,
                success=True,
                output=str(result),
                latency_ms=elapsed,
            )
        except Exception as exc:
            await logger.aerror("mcp_tool_error", tool=request.tool_name, error=str(exc))
            return ToolCallResponse(
                tool_name=request.tool_name,
                success=False,
                error=str(exc),
            )
