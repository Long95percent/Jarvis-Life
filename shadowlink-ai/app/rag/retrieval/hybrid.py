"""Hybrid retrieval with Reciprocal Rank Fusion (RRF).

Combines dense (vector) and sparse (BM25) retrieval using RRF
to produce a unified ranked result list. Proven to outperform
either method alone in most benchmarks.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.models.rag import RAGChunk
from app.rag.retrieval.bm25 import BM25Retriever
from app.rag.retrieval.vector import VectorRetriever

logger = structlog.get_logger("rag.retrieval.hybrid")


class HybridRetriever:
    """Hybrid retrieval: Vector + BM25 fused via RRF.

    RRF Formula: score(d) = Σ 1/(k + rank_i(d))
    where k is a constant (default 60) and rank_i is the rank in retrieval method i.
    """

    def __init__(
        self,
        vector_retriever: VectorRetriever | None = None,
        bm25_retriever: BM25Retriever | None = None,
        rrf_k: int = 60,
    ):
        self.vector_retriever = vector_retriever
        self.bm25_retriever = bm25_retriever
        self.rrf_k = rrf_k

    async def retrieve(self, query: str, top_k: int = 5, filters: dict[str, Any] | None = None) -> list[RAGChunk]:
        """Perform hybrid retrieval with RRF fusion."""
        # Retrieve from both sources (2x top_k for better fusion)
        vector_results = await self.vector_retriever.retrieve(query, top_k * 2, filters) if self.vector_retriever else []
        bm25_results = await self.bm25_retriever.retrieve(query, top_k * 2) if self.bm25_retriever else []

        if not vector_results and not bm25_results:
            return []

        # Apply RRF fusion
        return self._rrf_fuse(vector_results, bm25_results, top_k)

    def _rrf_fuse(self, *result_lists: list[RAGChunk], top_k: int = 5) -> list[RAGChunk]:
        """Apply Reciprocal Rank Fusion across multiple result lists."""
        scores: dict[str, float] = {}
        chunk_map: dict[str, RAGChunk] = {}

        for results in result_lists:
            for rank, chunk in enumerate(results):
                key = chunk.chunk_id or chunk.content[:100]
                scores[key] = scores.get(key, 0.0) + 1.0 / (self.rrf_k + rank + 1)
                chunk_map[key] = chunk

        # Sort by RRF score descending
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        fused = []
        for key, score in ranked[:top_k]:
            chunk = chunk_map[key]
            chunk.score = score
            fused.append(chunk)

        return fused
