"""RAG-related data models."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

__all__ = [
    "RAGRequest",
    "RAGResponse",
    "RAGChunk",
    "RAGTrace",
    "RetrievalMethod",
    "QueryClassification",
    "IngestRequest",
    "IngestResponse",
    "ChunkingStrategy",
    "EmbeddingConfig",
    "IndexInfo",
]


class RetrievalMethod(str, Enum):
    """Retrieval strategies."""

    VECTOR = "vector"
    BM25 = "bm25"
    HYBRID = "hybrid"
    MULTI_QUERY = "multi_query"
    SELF_RAG = "self_rag"


class QueryClassification(str, Enum):
    """Adaptive RAG query classification."""

    FACTUAL = "factual"  # Simple fact lookup
    ANALYTICAL = "analytical"  # Requires synthesis
    CREATIVE = "creative"  # Minimal RAG needed
    CONVERSATIONAL = "conversational"  # Context-dependent
    CODE = "code"  # Code-related query
    NO_RAG = "no_rag"  # RAG not beneficial


class ChunkingStrategy(str, Enum):
    """Document chunking strategies."""

    RECURSIVE = "recursive"
    SEMANTIC = "semantic"
    AGENTIC = "agentic"


class RAGRequest(BaseModel):
    """Request to the RAG pipeline."""

    query: str = Field(description="User query")
    mode_id: str = Field(default="general", description="Ambient work mode")
    session_id: str = Field(default="", description="Session for context-aware retrieval")
    top_k: int = Field(default=5, ge=1, le=50, description="Number of results to retrieve")
    retrieval_method: RetrievalMethod = Field(default=RetrievalMethod.HYBRID)
    rerank: bool = Field(default=True, description="Whether to apply reranking")
    filters: dict[str, Any] = Field(default_factory=dict, description="Metadata filters for retrieval")
    min_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Minimum relevance score threshold")


class RAGChunk(BaseModel):
    """A single retrieved chunk."""

    chunk_id: str = Field(default="", description="Unique chunk identifier")
    content: str = Field(description="Chunk text content")
    source: str = Field(default="", description="Source document path or URL")
    score: float = Field(default=0.0, description="Relevance score")
    metadata: dict[str, Any] = Field(default_factory=dict)
    page_number: int | None = None
    chunk_index: int | None = None


class RAGResponse(BaseModel):
    """RAG pipeline response."""

    chunks: list[RAGChunk] = Field(default_factory=list)
    answer: str = Field(default="", description="Generated answer (if generation enabled)")
    query_classification: QueryClassification = Field(default=QueryClassification.FACTUAL)
    rewritten_query: str = Field(default="", description="Query after rewriting")
    trace: RAGTrace | None = None


class RAGTrace(BaseModel):
    """Full RAG pipeline execution trace for observability."""

    trace_id: str = ""
    original_query: str = ""
    rewritten_query: str = ""
    query_classification: QueryClassification = QueryClassification.FACTUAL
    retrieval_method: RetrievalMethod = RetrievalMethod.HYBRID
    retrieved_count: int = 0
    after_rerank_count: int = 0
    crag_passed: bool = True
    total_latency_ms: float = 0.0
    retrieval_latency_ms: float = 0.0
    rerank_latency_ms: float = 0.0
    generation_latency_ms: float = 0.0
    quality_metrics: dict[str, float] = Field(default_factory=dict)


class IngestRequest(BaseModel):
    """Request to ingest documents into the index."""

    file_paths: list[str] = Field(default_factory=list, description="Local file paths to ingest")
    mode_id: str = Field(default="general", description="Index partition by mode")
    chunking_strategy: ChunkingStrategy = Field(default=ChunkingStrategy.RECURSIVE)
    chunk_size: int = Field(default=512, ge=64, le=4096)
    chunk_overlap: int = Field(default=64, ge=0, le=512)
    metadata: dict[str, Any] = Field(default_factory=dict, description="Custom metadata for all chunks")


class IngestResponse(BaseModel):
    """Response from document ingestion."""

    total_documents: int = 0
    total_chunks: int = 0
    failed_documents: list[str] = Field(default_factory=list)
    index_name: str = ""
    latency_ms: float = 0.0


class EmbeddingConfig(BaseModel):
    """Embedding model configuration."""

    model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    dimension: int = 384
    batch_size: int = 32
    normalize: bool = True
    device: str = "cpu"


class IndexInfo(BaseModel):
    """Information about a vector index."""

    name: str
    total_vectors: int = 0
    dimension: int = 384
    mode_id: str = "general"
    backend: str = "faiss"
    last_updated: str = ""
