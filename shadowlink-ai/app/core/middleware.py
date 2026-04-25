"""FastAPI middleware stack: request ID, logging, error handling, CORS."""

from __future__ import annotations

import time
import uuid
from typing import Any

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.config import settings

logger = structlog.get_logger("middleware")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Inject a unique request ID into every request for traceability."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:12])
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Log every HTTP request with method, path, status, and latency."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Skip noisy health checks
        if request.url.path not in ("/health", "/healthz", "/ready"):
            await logger.ainfo(
                "http_request",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                latency_ms=round(elapsed_ms, 2),
                client=request.client.host if request.client else "unknown",
            )
        return response


class GlobalExceptionMiddleware(BaseHTTPMiddleware):
    """Catch unhandled exceptions and return structured JSON error."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:
            await logger.aerror(
                "unhandled_exception",
                error=str(exc),
                path=request.url.path,
                exc_info=True,
            )
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "code": 500,
                    "message": f"Unhandled server exception at {request.url.path}: {str(exc) or exc.__class__.__name__}",
                    "data": {
                        "error_type": exc.__class__.__name__,
                        "error": str(exc) or exc.__class__.__name__,
                        "path": request.url.path,
                        "suggestion": "请根据 X-Request-ID 在 AI 服务日志中定位完整堆栈。",
                    },
                },
            )


def register_middleware(app: FastAPI) -> None:
    """Register all middleware in correct order (outermost first)."""
    # CORS must be outermost
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(GlobalExceptionMiddleware)
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestIdMiddleware)
