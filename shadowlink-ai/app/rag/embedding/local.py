"""Local embedding engine using SentenceTransformers.

Runs entirely on CPU (or GPU if available). Supports models like
all-MiniLM-L6-v2, BGE-small, E5-small for fast, cost-free embeddings.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.config import settings

logger = structlog.get_logger("rag.embedding.local")


class LocalEmbedding:
    """SentenceTransformers-based local embedding engine.

    Features:
    - CPU-first with optional GPU acceleration
    - Batch encoding for throughput
    - Normalized embeddings for cosine similarity
    - Model lazy-loading on first use
    """

    def __init__(
        self,
        model_name: str | None = None,
        device: str | None = None,
        batch_size: int | None = None,
    ):
        self.model_name = model_name or settings.rag.embedding_model
        self.device = device or settings.rag.embedding_device
        self.batch_size = batch_size or settings.rag.embedding_batch_size
        self._model: Any = None

    def _load_model(self) -> Any:
        """Lazy-load the SentenceTransformer model."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name, device=self.device)
            logger.info("embedding_model_loaded", model=self.model_name, device=self.device)
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts."""
        model = self._load_model()
        embeddings = model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embeddings.tolist()

    def embed_single(self, text: str) -> list[float]:
        """Embed a single text."""
        return self.embed([text])[0]

    @property
    def dimension(self) -> int:
        """Return the embedding dimension."""
        model = self._load_model()
        return model.get_sentence_embedding_dimension()
