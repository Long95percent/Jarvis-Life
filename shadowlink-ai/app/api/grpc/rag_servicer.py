"""gRPC RAG service implementation.

Implements RAGService from proto/rag_service.proto.
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger("grpc.rag_servicer")


class RAGServicer:
    """gRPC RAG service implementation.

    Corresponds to proto/rag_service.proto:
      service RAGService {
          rpc Query (RAGRequest) returns (RAGResponse);
          rpc Ingest (IngestRequest) returns (IngestResponse);
      }
    """

    def __init__(self, rag_engine: Any = None):
        self.rag_engine = rag_engine

    async def Query(self, request: Any, context: Any) -> Any:
        """Execute RAG query from Java backend."""
        await logger.ainfo("grpc_rag_query", query=getattr(request, "query", "")[:80])
        # Phase 1+: Convert proto -> RAGRequest -> execute pipeline -> return proto
        return None

    async def Ingest(self, request: Any, context: Any) -> Any:
        """Handle document ingestion from Java backend."""
        await logger.ainfo("grpc_rag_ingest")
        return None


def register_rag_servicer(server: Any, servicer: RAGServicer) -> None:
    """Register the RAG servicer with a gRPC server."""
    pass
