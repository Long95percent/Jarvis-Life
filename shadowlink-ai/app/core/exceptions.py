"""Custom exception classes and FastAPI exception handlers."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = structlog.get_logger("exceptions")


class ShadowLinkError(Exception):
    """Base exception for all ShadowLink AI service errors."""

    def __init__(self, code: str, message: str, status_code: int = 500, details: dict[str, Any] | None = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class AgentError(ShadowLinkError):
    """Agent execution error."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(code="AGENT_ERROR", message=message, status_code=500, details=details)


class AgentTimeoutError(ShadowLinkError):
    """Agent exceeded max iterations or time limit."""

    def __init__(self, message: str = "Agent execution timed out"):
        super().__init__(code="AGENT_TIMEOUT", message=message, status_code=504)


class RAGError(ShadowLinkError):
    """RAG pipeline error."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(code="RAG_ERROR", message=message, status_code=500, details=details)


class ToolExecutionError(ShadowLinkError):
    """Tool call execution failure."""

    def __init__(self, tool_name: str, message: str):
        super().__init__(
            code="TOOL_ERROR",
            message=f"Tool '{tool_name}' failed: {message}",
            status_code=500,
            details={"tool_name": tool_name},
        )


class FileProcessingError(ShadowLinkError):
    """File parsing or processing failure."""

    def __init__(self, file_path: str, message: str):
        super().__init__(
            code="FILE_PROCESSING_ERROR",
            message=message,
            status_code=422,
            details={"file_path": file_path},
        )


class ConfigurationError(ShadowLinkError):
    """Invalid configuration."""

    def __init__(self, message: str):
        super().__init__(code="CONFIG_ERROR", message=message, status_code=500)


class LLMProviderError(ShadowLinkError):
    """LLM provider call failure."""

    def __init__(self, provider: str, message: str):
        super().__init__(
            code="LLM_PROVIDER_ERROR",
            message=f"LLM provider '{provider}' error: {message}",
            status_code=502,
            details={"provider": provider},
        )


def register_exception_handlers(app: FastAPI) -> None:
    """Register custom exception handlers on the FastAPI app."""

    @app.exception_handler(ShadowLinkError)
    async def shadowlink_error_handler(request: Request, exc: ShadowLinkError) -> JSONResponse:
        await logger.awarning(
            "business_error",
            code=exc.code,
            message=exc.message,
            path=request.url.path,
            details=exc.details,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "code": exc.status_code,
                "message": exc.message,
                "data": {"error_code": exc.code, **exc.details},
            },
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "code": 422,
                "message": str(exc),
                "data": None,
            },
        )
