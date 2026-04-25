"""LLM-based reranking — uses an LLM to score document relevance.

More expensive but potentially more accurate than cross-encoders,
especially for nuanced or domain-specific relevance judgments.

Phase 2+: Full implementation with structured output parsing.
"""

from __future__ import annotations

from typing import Any

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.models.rag import RAGChunk

logger = structlog.get_logger("rag.reranking.llm_rerank")

LLM_RERANK_PROMPT = """\
Score the relevance of the following document to the query on a scale of 0-10.
Return ONLY the numeric score.

Query: {query}
Document: {document}
"""


class LLMReranker:
    """LLM-based document reranking."""

    def __init__(self, llm: BaseChatModel | None = None):
        self.llm = llm

    async def rerank(self, query: str, chunks: list[RAGChunk], top_k: int | None = None) -> list[RAGChunk]:
        """Rerank chunks using LLM relevance scoring."""
        if self.llm is None or not chunks:
            return chunks

        scored_chunks = []
        for chunk in chunks:
            try:
                response = await self.llm.ainvoke([
                    SystemMessage(content=LLM_RERANK_PROMPT.format(query=query, document=chunk.content[:500])),
                ])
                score = float(response.content.strip())
                chunk.score = min(max(score / 10.0, 0.0), 1.0)
            except (ValueError, TypeError):
                chunk.score = 0.0
            scored_chunks.append(chunk)

        ranked = sorted(scored_chunks, key=lambda c: c.score, reverse=True)
        return ranked[:top_k] if top_k else ranked
