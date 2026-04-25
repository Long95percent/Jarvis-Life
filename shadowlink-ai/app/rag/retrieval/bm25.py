"""BM25 keyword-based retrieval.

Sparse retrieval using BM25 scoring — excellent for exact keyword
matching and technical terminology. Complements dense retrieval
in hybrid configurations.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.models.rag import RAGChunk

logger = structlog.get_logger("rag.retrieval.bm25")


class BM25Retriever:
    """BM25 sparse keyword retrieval.

    Phase 0: Interface skeleton.
    Phase 3: Full BM25 implementation with tokenization.
    """

    def __init__(self, corpus: list[dict[str, Any]] | None = None):
        self.corpus = corpus or []
        self._index: Any = None

    def build_index(self, documents: list[dict[str, Any]]) -> None:
        """Build BM25 index from documents."""
        self.corpus = documents
        # Phase 3: Build actual BM25 index

    async def retrieve(self, query: str, top_k: int = 5) -> list[RAGChunk]:
        """Retrieve top-k documents by BM25 score."""
        if not self.corpus:
            return []

        # Phase 3: BM25 scoring
        return []
