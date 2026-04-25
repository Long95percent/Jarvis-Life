"""gRPC Agent service implementation.

Implements the AgentService defined in proto/agent_service.proto.
Handles streaming agent execution requests from the Java backend.

Note: Proto-generated stubs (*_pb2.py, *_pb2_grpc.py) will be generated
during build via `grpc_tools.protoc`. For Phase 0, this is a structural
placeholder with the full implementation pattern.
"""

from __future__ import annotations

from typing import Any, AsyncIterator

import structlog

logger = structlog.get_logger("grpc.agent_servicer")


class AgentServicer:
    """gRPC Agent service implementation.

    Corresponds to proto/agent_service.proto:
      service AgentService {
          rpc Chat (AgentRequest) returns (stream AgentEvent);
          rpc Cancel (CancelRequest) returns (CancelResponse);
      }
    """

    def __init__(self, agent_engine: Any = None):
        self.agent_engine = agent_engine

    async def Chat(self, request: Any, context: Any) -> AsyncIterator[Any]:
        """Handle streaming agent chat requests from Java backend.

        Receives AgentRequest proto, converts to internal model,
        executes agent, and streams AgentEvent protos back.
        """
        await logger.ainfo("grpc_agent_chat", session_id=getattr(request, "session_id", "unknown"))
        # Phase 1+: Convert proto -> internal model -> execute -> stream proto events
        yield  # Placeholder for streaming response
        return

    async def Cancel(self, request: Any, context: Any) -> Any:
        """Cancel a running agent execution."""
        await logger.ainfo("grpc_agent_cancel", execution_id=getattr(request, "execution_id", "unknown"))
        # Phase 1+: Signal cancellation to the running agent graph
        return None


def register_agent_servicer(server: Any, servicer: AgentServicer) -> None:
    """Register the agent servicer with a gRPC server.

    Phase 1+: Will import generated pb2_grpc and call add_AgentServiceServicer_to_server.
    """
    pass
