"""FastAPI dependency injection providers.

These dependencies are resolved at request time and provide shared resources
such as the LLM client, RAG engine, Agent engine, and tool registry.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.config import Settings, settings


@lru_cache
def get_settings() -> Settings:
    """Return the singleton Settings instance (cacheable for DI)."""
    return settings


# The following dependency factories will be populated during lifespan startup.
# For Phase 0 they return placeholders; Phase 1+ will wire real instances.

_shared_resources: dict[str, Any] = {}


def set_resource(key: str, value: Any) -> None:
    """Register a shared resource (called during lifespan startup)."""
    _shared_resources[key] = value


def get_resource(key: str) -> Any:
    """Retrieve a shared resource by key."""
    return _shared_resources.get(key)


async def get_llm_client() -> Any:
    """Dependency: unified LLM client."""
    client = get_resource("llm_client")
    if client is not None:
        return client

    from app.llm.client import LLMClient

    client = LLMClient()
    client.initialize()
    set_resource("llm_client", client)
    return client


async def get_agent_engine() -> Any:
    """Dependency: agent orchestration engine."""
    return get_resource("agent_engine")


async def get_rag_engine() -> Any:
    """Dependency: RAG pipeline engine."""
    return get_resource("rag_engine")


async def get_tool_registry() -> Any:
    """Dependency: MCP tool registry."""
    return get_resource("tool_registry")
