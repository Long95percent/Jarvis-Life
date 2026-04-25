"""OpenAI Function Calling <-> MCP adapter.

Converts between OpenAI's function calling format and MCP's tool protocol,
enabling use of OpenAI function definitions as MCP tools.
"""

from __future__ import annotations

from typing import Any

from app.models.mcp import ToolCategory, ToolInfo


def openai_function_to_mcp(function_def: dict[str, Any]) -> ToolInfo:
    """Convert an OpenAI function definition to MCP ToolInfo."""
    return ToolInfo(
        name=function_def.get("name", "unknown"),
        description=function_def.get("description", ""),
        category=ToolCategory.MCP_EXTERNAL,
        input_schema=function_def.get("parameters", {}),
    )


def mcp_to_openai_function(tool_info: ToolInfo) -> dict[str, Any]:
    """Convert MCP ToolInfo to OpenAI function format."""
    return {
        "type": "function",
        "function": {
            "name": tool_info.name,
            "description": tool_info.description,
            "parameters": tool_info.input_schema,
        },
    }
