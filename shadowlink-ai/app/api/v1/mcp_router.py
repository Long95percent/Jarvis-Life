"""MCP API endpoints — tool listing, calling, and plugin management."""

from __future__ import annotations

import time

from fastapi import APIRouter

from app.core.dependencies import get_resource
from app.models.common import Result
from app.models.mcp import PluginInfo, ToolCallRequest, ToolCallResponse, ToolInfo

router = APIRouter()


@router.get("/tools")
async def list_tools() -> Result[list[ToolInfo]]:
    """List all available tools (built-in + MCP + plugins)."""
    registry = get_resource("tool_registry")
    if registry is None:
        return Result.ok(data=[])
    return Result.ok(data=registry.list_tools())


@router.post("/tools/call")
async def call_tool(request: ToolCallRequest) -> Result[ToolCallResponse]:
    """Execute a tool call by name with given arguments."""
    registry = get_resource("tool_registry")
    if registry is None:
        return Result.ok(data=ToolCallResponse(
            tool_name=request.tool_name, success=False, error="Tool registry not initialized",
        ))

    result = registry.get_tool(request.tool_name)
    if result is None:
        return Result.ok(data=ToolCallResponse(
            tool_name=request.tool_name, success=False, error=f"Tool '{request.tool_name}' not found",
        ))

    tool_info, handler = result
    start = time.perf_counter()
    try:
        output = await handler.safe_arun(**request.arguments)
        elapsed = (time.perf_counter() - start) * 1000
        return Result.ok(data=ToolCallResponse(
            tool_name=request.tool_name, success=True, output=output, latency_ms=elapsed,
        ))
    except Exception as exc:
        elapsed = (time.perf_counter() - start) * 1000
        return Result.ok(data=ToolCallResponse(
            tool_name=request.tool_name, success=False, error=str(exc), latency_ms=elapsed,
        ))


@router.get("/plugins")
async def list_plugins() -> Result[list[PluginInfo]]:
    """List all loaded plugins."""
    return Result.ok(data=[])


@router.post("/plugins/{plugin_name}/reload")
async def reload_plugin(plugin_name: str) -> Result[None]:
    """Reload a specific plugin. Phase 1+ implementation."""
    return Result.ok(message=f"Plugin '{plugin_name}' reload requested")
