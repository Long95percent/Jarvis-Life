"""RAG API endpoints — query, ingest, and index management."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, UploadFile

from app.core.dependencies import get_rag_engine
from app.models.common import Result
from app.models.rag import IngestRequest, IngestResponse, IndexInfo, RAGRequest, RAGResponse
from app.rag.engine import RAGEngine

router = APIRouter()


@router.post("/query")
async def rag_query(
    request: RAGRequest,
    engine: Any = Depends(get_rag_engine),
) -> Result[RAGResponse]:
    """Execute the 9-step RAG pipeline.

    Steps: classify -> rewrite -> retrieve -> fuse -> rerank -> quality gate -> assemble -> generate -> trace
    """
    rag = engine or RAGEngine()
    response = await rag.query(request)
    return Result.ok(data=response)


@router.post("/ingest")
async def rag_ingest(
    request: IngestRequest,
    engine: Any = Depends(get_rag_engine),
) -> Result[IngestResponse]:
    """Ingest documents into the RAG index.

    Pipeline: parse -> chunk -> embed -> index
    """
    rag = engine or RAGEngine()
    response = await rag.ingest(request)
    return Result.ok(data=response)


@router.get("/indices")
async def list_indices(
    engine: Any = Depends(get_rag_engine),
) -> Result[list[IndexInfo]]:
    """List all RAG index partitions and their stats."""
    if engine is None:
        return Result.ok(data=[])
    return Result.ok(data=engine._index_manager.list_indices())


@router.delete("/indices/{mode_id}")
async def delete_index(
    mode_id: str,
    engine: Any = Depends(get_rag_engine),
) -> Result[None]:
    """Delete a mode-specific RAG index."""
    if engine and engine._index_manager.delete_index(mode_id):
        return Result.ok(message=f"Index for mode '{mode_id}' deleted")
    return Result.fail(code=404, message=f"Index for mode '{mode_id}' not found")
