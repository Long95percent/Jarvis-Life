"""Milvus Lite vector index — scalable vector search.

Milvus Lite runs as an embedded library (no server needed), making it
suitable for production deployments with larger datasets while maintaining
the simplicity of local development.

Phase 2+: Full implementation with collection management.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.models.rag import RAGChunk

logger = structlog.get_logger("rag.index.milvus")


class MilvusIndex:
    """Milvus Lite vector index.

    Features:
    - Embedded mode (no external server)
    - Collection per work mode for ambient isolation
    - Metadata filtering
    - Persistence to disk
    """

    def __init__(self, db_path: str = "./data/milvus.db", collection_name: str = "default"):
        self.db_path = db_path
        self.collection_name = collection_name
        self._client: Any = None

    async def add(self, embeddings: list[list[float]], metadata_list: list[dict[str, Any]]) -> None:
        """Add vectors with metadata. Phase 2+ implementation."""
        await logger.ainfo("milvus_add", count=len(embeddings), collection=self.collection_name)

    async def search(self, query_embedding: list[float], top_k: int = 5, filters: dict[str, Any] | None = None) -> list[RAGChunk]:
        """Search for similar vectors. Phase 2+ implementation."""
        return []

    async def delete(self, chunk_ids: list[str]) -> None:
        """Delete vectors by ID. Phase 2+ implementation."""
        pass
