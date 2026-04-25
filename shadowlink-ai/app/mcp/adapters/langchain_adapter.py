"""LangChain Tool <-> MCP adapter.

Converts between LangChain's BaseTool interface and MCP's tool protocol,
enabling seamless use of LangChain tools in MCP contexts and vice versa.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool, StructuredTool

from app.models.mcp import ToolCategory, ToolInfo


def langchain_to_mcp(tool: BaseTool) -> ToolInfo:
    """Convert a LangChain tool to MCP ToolInfo."""
    return ToolInfo(
        name=tool.name,
        description=tool.description or "",
        category=ToolCategory.SYSTEM,
        input_schema=tool.args_schema.model_json_schema() if tool.args_schema else {},
        is_async=tool.coroutine is not None if hasattr(tool, "coroutine") else False,
    )


def mcp_to_langchain(tool_info: ToolInfo, handler: Any) -> BaseTool:
    """Convert MCP ToolInfo + handler to a LangChain StructuredTool."""
    return StructuredTool.from_function(
        func=handler,
        name=tool_info.name,
        description=tool_info.description,
    )
