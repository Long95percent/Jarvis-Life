"""Index lifecycle manager — manages multiple indices partitioned by work mode.

Each ambient work mode gets its own index partition, ensuring
that RAG results are mode-specific and contextually relevant.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.config import settings
from app.models.rag import IndexInfo
from app.rag.index.faiss_index import FAISSIndex

logger = structlog.get_logger("rag.index.manager")


class IndexManager:
    """Manages vector indices across work modes.

    Each mode_id maps to a separate index partition:
    - general -> ./data/faiss_index/general/
    - code    -> ./data/faiss_index/code/
    - research -> ./data/faiss_index/research/
    """

    def __init__(self, base_path: str | None = None, dimension: int | None = None):
        self.base_path = base_path or settings.rag.faiss_index_path
        self.dimension = dimension or settings.rag.embedding_dimension
        self._indices: dict[str, FAISSIndex] = {}

    def get_index(self, mode_id: str = "general") -> FAISSIndex:
        """Get or create the index for a work mode."""
        if mode_id not in self._indices:
            index_path = f"{self.base_path}/{mode_id}"
            self._indices[mode_id] = FAISSIndex(index_path, self.dimension)
        return self._indices[mode_id]

    def list_indices(self) -> list[IndexInfo]:
        """List all active indices with their stats."""
        infos = []
        for mode_id, index in self._indices.items():
            infos.append(IndexInfo(
                name=f"idx_{mode_id}",
                total_vectors=index.total_vectors,
                dimension=self.dimension,
                mode_id=mode_id,
                backend="faiss",
            ))
        return infos

    def save_all(self) -> None:
        """Persist all indices to disk."""
        for mode_id, index in self._indices.items():
            index.save()
            logger.info("index_saved", mode_id=mode_id, vectors=index.total_vectors)

    def delete_index(self, mode_id: str) -> bool:
        """Delete a mode's index."""
        if mode_id in self._indices:
            del self._indices[mode_id]
            return True
        return False
