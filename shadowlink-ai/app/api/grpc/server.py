"""gRPC server setup and lifecycle management.

Creates and configures the gRPC server that the Java backend connects to.
Supports health checking, reflection, and graceful shutdown.
"""

from __future__ import annotations

from typing import Any

import grpc
import structlog
from grpc import aio as grpc_aio

from app.config import settings

logger = structlog.get_logger("grpc.server")


async def create_grpc_server(
    agent_engine: Any = None,
    rag_engine: Any = None,
    tool_registry: Any = None,
) -> grpc_aio.Server:
    """Create and configure the gRPC async server."""
    server = grpc_aio.server(
        options=[
            ("grpc.max_send_message_length", settings.grpc.max_message_length),
            ("grpc.max_receive_message_length", settings.grpc.max_message_length),
        ]
    )

    # Phase 1+: Register servicers with generated proto stubs
    # from app.api.grpc.agent_servicer import AgentServicer, register_agent_servicer
    # from app.api.grpc.rag_servicer import RAGServicer, register_rag_servicer
    # from app.api.grpc.mcp_servicer import MCPBridgeServicer, register_mcp_servicer
    # register_agent_servicer(server, AgentServicer(agent_engine))
    # register_rag_servicer(server, RAGServicer(rag_engine))
    # register_mcp_servicer(server, MCPBridgeServicer(tool_registry))

    # Enable gRPC reflection for debugging
    if settings.grpc.reflection_enabled:
        from grpc_reflection.v1alpha import reflection

        service_names = [
            # Phase 1+: Add generated service descriptors
            reflection.SERVICE_NAME,
        ]
        reflection.enable_server_reflection(service_names, server)

    listen_addr = f"[::]:{settings.grpc.port}"
    server.add_insecure_port(listen_addr)

    await logger.ainfo("grpc_server_created", port=settings.grpc.port, reflection=settings.grpc.reflection_enabled)
    return server


async def start_grpc_server(server: grpc_aio.Server) -> None:
    """Start the gRPC server."""
    await server.start()
    await logger.ainfo("grpc_server_started", port=settings.grpc.port)


async def stop_grpc_server(server: grpc_aio.Server, grace_seconds: float = 5.0) -> None:
    """Gracefully stop the gRPC server."""
    await server.stop(grace_seconds)
    await logger.ainfo("grpc_server_stopped")
