"""Multi-query retrieval expansion.

Generates multiple reformulations of the original query using an LLM,
retrieves results for each variant, and merges them. This increases
recall by capturing different aspects of the user's intent.
"""

from __future__ import annotations

from typing import Any

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.models.rag import RAGChunk

logger = structlog.get_logger("rag.retrieval.multi_query")

MULTI_QUERY_PROMPT = """\
Generate 3 different reformulations of the following query. \
Each should capture a different aspect or perspective of the same information need.
Return only the 3 queries, one per line.

Original query: {query}
"""


class MultiQueryRetriever:
    """Multi-query expansion retriever.

    1. Generate N query variants via LLM
    2. Retrieve for each variant
    3. Deduplicate and merge results
    """

    def __init__(self, llm: BaseChatModel | None = None, base_retriever: Any = None, num_queries: int = 3):
        self.llm = llm
        self.base_retriever = base_retriever
        self.num_queries = num_queries

    async def generate_queries(self, query: str) -> list[str]:
        """Generate query reformulations."""
        if self.llm is None:
            return [query]

        response = await self.llm.ainvoke([
            SystemMessage(content=MULTI_QUERY_PROMPT.format(query=query)),
        ])
        queries = [q.strip() for q in response.content.strip().split("\n") if q.strip()]
        return [query] + queries[:self.num_queries]

    async def retrieve(self, query: str, top_k: int = 5) -> list[RAGChunk]:
        """Retrieve with multi-query expansion."""
        queries = await self.generate_queries(query)
        all_chunks: list[RAGChunk] = []
        seen_ids: set[str] = set()

        for q in queries:
            if self.base_retriever:
                chunks = await self.base_retriever.retrieve(q, top_k)
                for chunk in chunks:
                    key = chunk.chunk_id or chunk.content[:100]
                    if key not in seen_ids:
                        seen_ids.add(key)
                        all_chunks.append(chunk)

        return all_chunks[:top_k]
