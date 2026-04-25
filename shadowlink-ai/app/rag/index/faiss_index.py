"""FAISS vector index — local, zero-dependency vector search.

Best for single-machine deployments and moderate-scale indices.
Supports flat, IVF, and HNSW index types.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

from app.models.rag import RAGChunk

logger = structlog.get_logger("rag.index.faiss")


class FAISSIndex:
    """FAISS-based vector index with persistence.

    Features:
    - Lazy initialization (first insert triggers build)
    - Disk persistence for index and metadata
    - Mode-partitioned indices for ambient isolation
    """

    def __init__(self, index_path: str, dimension: int = 384):
        self.index_path = Path(index_path)
        self.dimension = dimension
        self._index: Any = None
        self._metadata: list[dict[str, Any]] = []

    def _ensure_dir(self) -> None:
        self.index_path.mkdir(parents=True, exist_ok=True)

    def _load(self) -> None:
        """Load index from disk if exists."""
        import faiss

        idx_file = self.index_path / "index.faiss"
        meta_file = self.index_path / "metadata.json"

        if idx_file.exists():
            self._index = faiss.read_index(str(idx_file))
            if meta_file.exists():
                self._metadata = json.loads(meta_file.read_text(encoding="utf-8"))
        else:
            self._index = faiss.IndexFlatIP(self.dimension)  # Inner product (cosine with normalized vectors)

    def save(self) -> None:
        """Persist index to disk."""
        import faiss

        self._ensure_dir()
        faiss.write_index(self._index, str(self.index_path / "index.faiss"))
        (self.index_path / "metadata.json").write_text(
            json.dumps(self._metadata, ensure_ascii=False), encoding="utf-8"
        )

    def add(self, embeddings: list[list[float]], metadata_list: list[dict[str, Any]]) -> None:
        """Add vectors with metadata to the index."""
        import numpy as np

        if self._index is None:
            self._load()

        vectors = np.array(embeddings, dtype=np.float32)
        self._index.add(vectors)
        self._metadata.extend(metadata_list)

    def search(self, query_embedding: list[float], top_k: int = 5) -> list[RAGChunk]:
        """Search for the most similar vectors."""
        import numpy as np

        if self._index is None:
            self._load()

        if self._index.ntotal == 0:
            return []

        query = np.array([query_embedding], dtype=np.float32)
        scores, indices = self._index.search(query, min(top_k, self._index.ntotal))

        chunks = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self._metadata):
                continue
            meta = self._metadata[idx]
            chunks.append(RAGChunk(
                chunk_id=meta.get("chunk_id", f"chunk_{idx}"),
                content=meta.get("content", ""),
                source=meta.get("source", ""),
                score=float(score),
                metadata=meta,
            ))
        return chunks

    @property
    def total_vectors(self) -> int:
        if self._index is None:
            self._load()
        return self._index.ntotal if self._index else 0
