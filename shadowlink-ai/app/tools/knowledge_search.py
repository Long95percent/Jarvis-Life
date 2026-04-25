"""Knowledge search tool — query the local RAG knowledge base.

Wraps the RAG engine as a tool callable by agents, enabling
retrieval-augmented tool calls during agent execution.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.core.dependencies import get_resource
from app.models.mcp import ToolCategory
from app.models.rag import RAGRequest
from app.tools.base import ShadowLinkTool


class KnowledgeSearchInput(BaseModel):
    query: str = Field(description="Search query")
    mode_id: str = Field(default="general", description="Knowledge base partition (work mode)")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of results")


class KnowledgeSearchTool(ShadowLinkTool):
    """Search the local knowledge base using RAG."""

    name: str = "knowledge_search"
    description: str = (
        "Search the local knowledge base for relevant documents and information. "
        "Use this when the user asks about uploaded documents or needs context from their files."
    )
    args_schema: type[BaseModel] = KnowledgeSearchInput
    category: ToolCategory = ToolCategory.KNOWLEDGE

    def _run(self, query: str, mode_id: str = "general", top_k: int = 5) -> str:
        raise NotImplementedError("Use async version")

    async def _arun(self, query: str, mode_id: str = "general", top_k: int = 5) -> str:
        """Search knowledge base via RAG engine."""
        rag_engine = get_resource("rag_engine")
        if rag_engine is None:
            return "Knowledge base is not initialized. No documents have been uploaded yet."

        request = RAGRequest(query=query, mode_id=mode_id, top_k=top_k)
        response = await rag_engine.query(request)

        if not response.chunks:
            return f"No relevant documents found for: {query}"

        lines = [f"Found {len(response.chunks)} relevant chunks:\n"]
        for i, chunk in enumerate(response.chunks, 1):
            source = chunk.source or "unknown"
            lines.append(f"[{i}] (score: {chunk.score:.3f}) Source: {source}")
            lines.append(f"    {chunk.content[:300]}...")
            lines.append("")
        return "\n".join(lines)
