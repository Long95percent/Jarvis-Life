"""File processing API endpoints — upload, parse, and process files."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, UploadFile

from app.config import settings
from app.file_processing.pipeline import FileProcessingPipeline
from app.models.common import Result
from app.models.mcp import FileProcessingRequest, FileProcessingResponse

router = APIRouter()


@router.post("/process")
async def process_file(request: FileProcessingRequest) -> Result[FileProcessingResponse]:
    """Process a local file through the parsing pipeline."""
    pipeline = FileProcessingPipeline()
    response = await pipeline.process(request)
    return Result.ok(data=response)


@router.post("/upload")
async def upload_file(file: UploadFile) -> Result[dict]:
    """Upload a file for processing.

    Saves to the configured upload directory and returns the path.
    """
    if not file.filename:
        return Result.fail(code=422, message="No filename provided")

    import aiofiles
    from pathlib import Path

    upload_dir = Path(settings.file_processing.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / file.filename

    async with aiofiles.open(str(dest), "wb") as f:
        content = await file.read()
        await f.write(content)

    return Result.ok(data={
        "file_path": str(dest),
        "file_name": file.filename,
        "size": len(content),
    })


@router.post("/upload-and-ingest")
async def upload_and_ingest(
    file: UploadFile,
    mode_id: str = "general",
) -> Result[dict]:
    """Upload a file, process it, and ingest into RAG index.

    Combines upload + parse + chunk + embed + index in a single call.
    """
    if not file.filename:
        return Result.fail(code=422, message="No filename provided")

    import aiofiles
    from pathlib import Path

    from app.core.dependencies import get_resource
    from app.models.rag import IngestRequest

    upload_dir = Path(settings.file_processing.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / file.filename

    # Save file
    async with aiofiles.open(str(dest), "wb") as f:
        content = await file.read()
        await f.write(content)

    # Ingest into RAG
    rag_engine = get_resource("rag_engine")
    if rag_engine is None:
        return Result.ok(data={
            "file_path": str(dest),
            "file_name": file.filename,
            "size": len(content),
            "indexed": False,
            "message": "File uploaded but RAG engine not initialized",
        })

    ingest_req = IngestRequest(file_paths=[str(dest)], mode_id=mode_id)
    ingest_resp = await rag_engine.ingest(ingest_req)

    return Result.ok(data={
        "file_path": str(dest),
        "file_name": file.filename,
        "size": len(content),
        "indexed": True,
        "chunks": ingest_resp.total_chunks,
        "mode_id": mode_id,
        "latency_ms": round(ingest_resp.latency_ms, 2),
    })


@router.get("/formats")
async def supported_formats() -> Result[list[str]]:
    """List supported file formats."""
    return Result.ok(data=settings.file_processing.supported_extensions)
