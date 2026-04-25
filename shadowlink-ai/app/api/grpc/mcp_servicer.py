"""gRPC MCP bridge service implementation.

Implements MCPBridge from proto/mcp_service.proto.
Allows the Java backend to discover and call tools via gRPC.
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger("grpc.mcp_servicer")


class MCPBridgeServicer:
    """gRPC MCP bridge service implementation.

    Corresponds to proto/mcp_service.proto:
      service MCPBridge {
          rpc ListTools (ListToolsRequest) returns (ListToolsResponse);
          rpc CallTool (ToolCallRequest) returns (ToolCallResponse);
      }
    """

    def __init__(self, tool_registry: Any = None):
        self.tool_registry = tool_registry

    async def ListTools(self, request: Any, context: Any) -> Any:
        """List available tools via gRPC."""
        await logger.ainfo("grpc_list_tools")
        return None

    async def CallTool(self, request: Any, context: Any) -> Any:
        """Call a tool via gRPC."""
        tool_name = getattr(request, "tool_name", "unknown")
        await logger.ainfo("grpc_call_tool", tool=tool_name)
        return None


def register_mcp_servicer(server: Any, servicer: MCPBridgeServicer) -> None:
    """Register the MCP bridge servicer with a gRPC server."""
    pass
