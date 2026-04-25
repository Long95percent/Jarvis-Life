"""ShadowLink AI Service — FastAPI application entry point."""

from __future__ import annotations

from fastapi import FastAPI

from app.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.lifespan import lifespan
from app.core.logging import setup_logging
from app.core.middleware import register_middleware

# ── Bootstrap logging before anything else ──
setup_logging(
    log_level=settings.log_level,
    json_output=(settings.env == "prod"),
)


def create_app() -> FastAPI:
    """Application factory — builds and configures the FastAPI app."""
    application = FastAPI(
        title="ShadowLink AI Service",
        version=settings.version,
        description=(
            "Enterprise-grade AI service: Agent orchestration (ReAct / Plan-and-Execute / MultiAgent), "
            "9-step RAG pipeline, MCP tool protocol, and ambient work mode support."
        ),
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
    )

    # ── Middleware stack ──
    register_middleware(application)

    # ── Exception handlers ──
    register_exception_handlers(application)

    # ── Routers ──
    _register_routers(application)

    return application


def _register_routers(application: FastAPI) -> None:
    """Register all API routers."""
    from app.api.v1 import agent_router, file_router, health_router, jarvis_router, mcp_router, rag_router, settings_router, system_router

    application.include_router(health_router.router, tags=["health"])
    application.include_router(agent_router.router, prefix="/v1/agent", tags=["agent"])
    application.include_router(rag_router.router, prefix="/v1/rag", tags=["rag"])
    application.include_router(mcp_router.router, prefix="/v1/mcp", tags=["mcp"])
    application.include_router(file_router.router, prefix="/v1/file", tags=["file"])
    application.include_router(settings_router.router, prefix="/v1/settings", tags=["settings"])
    application.include_router(system_router.router, prefix="/v1/system", tags=["system"])
    application.include_router(jarvis_router.router, prefix="/api/v1", tags=["jarvis"])


app = create_app()
