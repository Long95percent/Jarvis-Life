"""MCP Client — connects to external MCP servers for tool discovery and invocation.

Supports two transport modes:
  - stdio: spawns a subprocess and communicates via stdin/stdout JSON-RPC
  - http/sse: connects to an HTTP endpoint with SSE streaming

Implements the MCP protocol for:
  - tools/list: discover available tools
  - tools/call: invoke a tool with arguments
  - Connection lifecycle management
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

import httpx
import structlog

from app.models.mcp import ToolCallRequest, ToolCallResponse, ToolInfo, ToolCategory

logger = structlog.get_logger("mcp.client")


class MCPConnection:
    """A single connection to an MCP server."""

    def __init__(self, server_name: str, transport: str, endpoint: str) -> None:
        self.server_name = server_name
        self.transport = transport  # "stdio" or "http"
        self.endpoint = endpoint
        self.process: asyncio.subprocess.Process | None = None
        self.http_client: httpx.AsyncClient | None = None
        self.tools: list[ToolInfo] = []
        self._request_id = 0

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id


class MCPClient:
    """MCP Client for connecting to external tool servers.

    Supports:
    - stdio transport (subprocess with JSON-RPC over stdin/stdout)
    - HTTP transport (REST + SSE endpoints)
    - Tool discovery and caching
    - Async tool invocation
    """

    def __init__(self) -> None:
        self._connections: dict[str, MCPConnection] = {}

    async def connect(self, server_name: str, transport: str, endpoint: str) -> bool:
        """Connect to an MCP server.

        Args:
            server_name: Friendly name for the server.
            transport: "stdio" or "http".
            endpoint: Command string (stdio) or URL (http).

        Returns:
            True if connection succeeded.
        """
        conn = MCPConnection(server_name, transport, endpoint)

        try:
            if transport == "stdio":
                await self._connect_stdio(conn)
            elif transport in ("http", "sse"):
                await self._connect_http(conn)
            else:
                await logger.aerror("mcp_unknown_transport", transport=transport)
                return False

            self._connections[server_name] = conn
            await logger.ainfo("mcp_connected", server=server_name, transport=transport)
            return True

        except Exception as exc:
            await logger.aerror("mcp_connect_failed", server=server_name, error=str(exc))
            return False

    async def _connect_stdio(self, conn: MCPConnection) -> None:
        """Connect via stdio — spawn process and send initialize."""
        parts = conn.endpoint.split()
        conn.process = await asyncio.create_subprocess_exec(
            *parts,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Send MCP initialize request
        init_msg = {
            "jsonrpc": "2.0",
            "id": conn._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "shadowlink-ai", "version": "0.1.0"},
            },
        }
        await self._stdio_send(conn, init_msg)
        response = await self._stdio_recv(conn)

        if response and "result" in response:
            await logger.ainfo("mcp_stdio_initialized", server=conn.server_name)
            # Send initialized notification
            await self._stdio_send(conn, {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            })
        else:
            raise ConnectionError(f"MCP initialize failed: {response}")

    async def _connect_http(self, conn: MCPConnection) -> None:
        """Connect via HTTP — create async client."""
        conn.http_client = httpx.AsyncClient(base_url=conn.endpoint, timeout=30.0)
        # Test connectivity
        try:
            resp = await conn.http_client.get("/")
            await logger.ainfo("mcp_http_connected", server=conn.server_name, status=resp.status_code)
        except httpx.ConnectError:
            raise ConnectionError(f"Cannot reach MCP server at {conn.endpoint}")

    async def _stdio_send(self, conn: MCPConnection, msg: dict) -> None:
        """Send a JSON-RPC message via stdio."""
        if conn.process is None or conn.process.stdin is None:
            return
        payload = json.dumps(msg) + "\n"
        conn.process.stdin.write(payload.encode())
        await conn.process.stdin.drain()

    async def _stdio_recv(self, conn: MCPConnection, timeout: float = 10.0) -> dict | None:
        """Read a JSON-RPC response from stdout."""
        if conn.process is None or conn.process.stdout is None:
            return None
        try:
            line = await asyncio.wait_for(conn.process.stdout.readline(), timeout=timeout)
            if line:
                return json.loads(line.decode())
        except (asyncio.TimeoutError, json.JSONDecodeError):
            pass
        return None

    async def discover_tools(self, server_name: str) -> list[ToolInfo]:
        """Discover tools from a connected MCP server."""
        conn = self._connections.get(server_name)
        if conn is None:
            return []

        try:
            if conn.transport == "stdio":
                return await self._discover_stdio(conn)
            elif conn.transport in ("http", "sse"):
                return await self._discover_http(conn)
        except Exception as exc:
            await logger.aerror("mcp_discover_failed", server=server_name, error=str(exc))
        return []

    async def _discover_stdio(self, conn: MCPConnection) -> list[ToolInfo]:
        """Discover tools via stdio JSON-RPC."""
        msg = {"jsonrpc": "2.0", "id": conn._next_id(), "method": "tools/list", "params": {}}
        await self._stdio_send(conn, msg)
        response = await self._stdio_recv(conn)

        if not response or "result" not in response:
            return []

        tools_data = response["result"].get("tools", [])
        tools = []
        for t in tools_data:
            tool = ToolInfo(
                name=t.get("name", ""),
                description=t.get("description", ""),
                category=ToolCategory.MCP,
                parameters=t.get("inputSchema", {}),
                source=f"mcp:{conn.server_name}",
            )
            tools.append(tool)

        conn.tools = tools
        await logger.ainfo("mcp_tools_discovered", server=conn.server_name, count=len(tools))
        return tools

    async def _discover_http(self, conn: MCPConnection) -> list[ToolInfo]:
        """Discover tools via HTTP endpoint."""
        if conn.http_client is None:
            return []

        resp = await conn.http_client.post("/tools/list", json={})
        if resp.status_code != 200:
            return []

        data = resp.json()
        tools_data = data.get("tools", data.get("result", {}).get("tools", []))
        tools = []
        for t in tools_data:
            tool = ToolInfo(
                name=t.get("name", ""),
                description=t.get("description", ""),
                category=ToolCategory.MCP,
                parameters=t.get("inputSchema", {}),
                source=f"mcp:{conn.server_name}",
            )
            tools.append(tool)

        conn.tools = tools
        return tools

    async def call_tool(self, server_name: str, request: ToolCallRequest) -> ToolCallResponse:
        """Call a tool on a connected MCP server."""
        conn = self._connections.get(server_name)
        if conn is None:
            return ToolCallResponse(
                tool_name=request.tool_name,
                success=False,
                error=f"Server '{server_name}' not connected",
            )

        try:
            if conn.transport == "stdio":
                return await self._call_stdio(conn, request)
            elif conn.transport in ("http", "sse"):
                return await self._call_http(conn, request)
            else:
                return ToolCallResponse(tool_name=request.tool_name, success=False, error="Unknown transport")
        except Exception as exc:
            return ToolCallResponse(tool_name=request.tool_name, success=False, error=str(exc))

    async def _call_stdio(self, conn: MCPConnection, request: ToolCallRequest) -> ToolCallResponse:
        """Invoke a tool via stdio JSON-RPC."""
        msg = {
            "jsonrpc": "2.0",
            "id": conn._next_id(),
            "method": "tools/call",
            "params": {"name": request.tool_name, "arguments": request.arguments},
        }
        await self._stdio_send(conn, msg)
        response = await self._stdio_recv(conn, timeout=30.0)

        if not response:
            return ToolCallResponse(tool_name=request.tool_name, success=False, error="No response from MCP server")

        if "error" in response:
            err = response["error"]
            return ToolCallResponse(
                tool_name=request.tool_name,
                success=False,
                error=f"MCP error {err.get('code', 0)}: {err.get('message', '')}",
            )

        result = response.get("result", {})
        content_parts = result.get("content", [])
        output_parts = []
        for part in content_parts:
            if part.get("type") == "text":
                output_parts.append(part.get("text", ""))
            elif part.get("type") == "image":
                output_parts.append(f"[image: {part.get('mimeType', 'unknown')}]")

        return ToolCallResponse(
            tool_name=request.tool_name,
            success=not result.get("isError", False),
            output="\n".join(output_parts) or str(result),
        )

    async def _call_http(self, conn: MCPConnection, request: ToolCallRequest) -> ToolCallResponse:
        """Invoke a tool via HTTP endpoint."""
        if conn.http_client is None:
            return ToolCallResponse(tool_name=request.tool_name, success=False, error="HTTP client not initialized")

        resp = await conn.http_client.post(
            "/tools/call",
            json={"name": request.tool_name, "arguments": request.arguments},
        )

        if resp.status_code != 200:
            return ToolCallResponse(tool_name=request.tool_name, success=False, error=f"HTTP {resp.status_code}")

        data = resp.json()
        result = data.get("result", data)
        content_parts = result.get("content", [])
        output_parts = [p.get("text", str(p)) for p in content_parts] if content_parts else [str(result)]

        return ToolCallResponse(
            tool_name=request.tool_name,
            success=not result.get("isError", False),
            output="\n".join(output_parts),
        )

    async def disconnect(self, server_name: str) -> None:
        """Disconnect from an MCP server and clean up resources."""
        conn = self._connections.pop(server_name, None)
        if conn is None:
            return

        if conn.process is not None:
            try:
                conn.process.terminate()
                await asyncio.wait_for(conn.process.wait(), timeout=5.0)
            except (asyncio.TimeoutError, ProcessLookupError):
                conn.process.kill()

        if conn.http_client is not None:
            await conn.http_client.aclose()

        await logger.ainfo("mcp_disconnected", server=server_name)

    async def disconnect_all(self) -> None:
        """Disconnect from all servers."""
        for name in list(self._connections.keys()):
            await self.disconnect(name)

    @property
    def connected_servers(self) -> list[str]:
        return list(self._connections.keys())

    def get_all_tools(self) -> list[ToolInfo]:
        """Get all discovered tools across all connected servers."""
        tools: list[ToolInfo] = []
        for conn in self._connections.values():
            tools.extend(conn.tools)
        return tools
