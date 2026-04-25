"""Health check endpoints for liveness, readiness, and service info."""

from __future__ import annotations

import time

from fastapi import APIRouter

from app.config import settings
from app.models.common import Result

router = APIRouter()

_start_time = time.time()


@router.get("/health")
async def health() -> Result[dict]:
    """Liveness check — returns OK if the service is running."""
    return Result.ok(data={
        "status": "ok",
        "service": settings.app_name,
        "version": settings.version,
        "env": settings.env,
        "uptime_seconds": round(time.time() - _start_time, 1),
    })


@router.get("/ready")
async def readiness() -> Result[dict]:
    """Readiness check — verifies critical dependencies are available."""
    checks: dict[str, str] = {
        "llm_client": "pending",  # Phase 1+: check LLM connectivity
        "rag_engine": "pending",  # Phase 1+: check index loaded
        "grpc_server": "pending",  # Phase 1+: check gRPC listening
    }
    return Result.ok(data={"ready": True, "checks": checks})
