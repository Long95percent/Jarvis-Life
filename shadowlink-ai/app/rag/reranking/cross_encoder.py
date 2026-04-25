"""Cross-encoder reranking using BGE-reranker or similar models.

Cross-encoders jointly encode query + document pairs, producing
more accurate relevance scores than bi-encoders (used in retrieval).
Trade-off: slower but much more precise.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.config import settings
from app.models.rag import RAGChunk

logger = structlog.get_logger("rag.reranking.cross_encoder")


class CrossEncoderReranker:
    """Cross-encoder reranking model.

    Uses models like BAAI/bge-reranker-base to score query-document pairs.
    Lazy-loads the model on first use to avoid startup overhead.
    """

    def __init__(self, model_name: str | None = None, device: str = "cpu"):
        self.model_name = model_name or settings.rag.rerank_model
        self.device = device
        self._model: Any = None

    def _load_model(self) -> Any:
        """Lazy-load the reranker model."""
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder

                self._model = CrossEncoder(self.model_name, device=self.device)
                logger.info("reranker_loaded", model=self.model_name)
            except ImportError:
                logger.warning("cross_encoder_not_available", msg="sentence-transformers not installed with cross-encoder support")
                return None
        return self._model

    async def rerank(self, query: str, chunks: list[RAGChunk], top_k: int | None = None) -> list[RAGChunk]:
        """Rerank chunks by cross-encoder relevance score."""
        model = self._load_model()
        if model is None or not chunks:
            return chunks

        pairs = [(query, chunk.content) for chunk in chunks]
        scores = model.predict(pairs)

        for chunk, score in zip(chunks, scores):
            chunk.score = float(score)

        ranked = sorted(chunks, key=lambda c: c.score, reverse=True)
        return ranked[:top_k] if top_k else ranked
