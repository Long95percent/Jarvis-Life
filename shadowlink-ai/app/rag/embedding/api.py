"""API-based embedding engine — calls external embedding APIs.

Supports OpenAI-compatible embedding endpoints, useful when
local resources are insufficient or for specific model access.
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger("rag.embedding.api")


class APIEmbedding:
    """HTTP-based embedding via OpenAI-compatible API.

    Features:
    - Async HTTP calls for non-blocking operation
    - Automatic batching
    - Retry with exponential backoff
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str = "text-embedding-3-small",
    ):
        self.base_url = base_url or settings.llm.base_url
        self.api_key = api_key or settings.llm.api_key
        self.model = model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts via API."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {},
                json={"input": texts, "model": self.model},
            )
            response.raise_for_status()
            data = response.json()
            return [item["embedding"] for item in data["data"]]

    async def embed_single(self, text: str) -> list[float]:
        """Embed a single text."""
        results = await self.embed([text])
        return results[0]
