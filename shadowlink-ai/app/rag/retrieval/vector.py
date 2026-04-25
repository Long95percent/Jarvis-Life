"""Vector similarity retrieval using FAISS or Milvus backends.

Dense retrieval via embedding similarity — the foundation of
modern RAG systems. Supports both FAISS (local) and Milvus (scalable).
"""

from __future__ import annotations

from typing import Any

import structlog

from app.models.rag import RAGChunk

logger = structlog.get_logger("rag.retrieval.vector")


class VectorRetriever:
    """Dense vector similarity retrieval.

    Phase 0: Interface skeleton.
    Phase 3: Full FAISS/Milvus integration.
    """

    def __init__(self, index: Any = None, embedding_fn: Any = None):
        self.index = index
        self.embedding_fn = embedding_fn

    async def retrieve(self, query: str, top_k: int = 5, filters: dict[str, Any] | None = None) -> list[RAGChunk]:
        """Retrieve top-k similar chunks."""
        if self.index is None or self.embedding_fn is None:
            return []

        # Phase 3: embed query -> search index -> return chunks
        return []
