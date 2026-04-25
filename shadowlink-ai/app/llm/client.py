"""Unified LLM client — single interface to multiple LLM providers.

Routes requests to the appropriate provider based on model name.
Applies middleware chain: rate limiting -> caching -> token counting.
"""

from __future__ import annotations

from typing import Any, AsyncIterator

import structlog

from app.config import settings
from app.llm.providers.openai import OpenAIProvider

logger = structlog.get_logger("llm.client")


class LLMClient:
    """Unified LLM client with provider routing and middleware.

    Usage:
        client = LLMClient()
        response = await client.chat("Hello", model="gpt-4o-mini")
        async for chunk in client.chat_stream("Hello"):
            print(chunk)
    """

    # Provider prefix routing: model name prefix -> provider class
    PROVIDER_PREFIXES: dict[str, str] = {
        "gpt-": "openai",
        "o1-": "openai",
        "deepseek-": "deepseek",
        "claude-": "anthropic",
    }

    def __init__(self) -> None:
        self._providers: dict[str, Any] = {}
        self._default_provider: Any = None

    def initialize(self) -> None:
        """Initialize providers from config. Called during app startup."""
        # Default: OpenAI-compatible provider
        self._default_provider = OpenAIProvider(
            base_url=settings.llm.base_url,
            api_key=settings.llm.api_key,
            default_model=settings.llm.model,
        )
        self._providers["openai"] = self._default_provider

        logger.info("llm_client_initialized", providers=list(self._providers.keys()))

    def _resolve_provider(self, model: str | None = None) -> Any:
        """Resolve the provider for a given model name."""
        if model:
            for prefix, provider_name in self.PROVIDER_PREFIXES.items():
                if model.startswith(prefix) and provider_name in self._providers:
                    return self._providers[provider_name]

        return self._default_provider

    async def chat(
        self,
        message: str,
        *,
        model: str | None = None,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Send a chat message and get a response."""
        provider = self._resolve_provider(model)
        if provider is None:
            return "[LLM Client] No provider configured"

        return await provider.chat(
            message=message,
            model=model,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def chat_stream(
        self,
        message: str,
        *,
        model: str | None = None,
        system_prompt: str | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[str]:
        """Send a chat message and stream the response."""
        provider = self._resolve_provider(model)
        if provider is None:
            yield "[LLM Client] No provider configured"
            return

        async for chunk in provider.chat_stream(
            message=message,
            model=model,
            system_prompt=system_prompt,
            temperature=temperature,
        ):
            yield chunk

    def get_langchain_llm(self, model: str | None = None) -> Any:
        """Get a LangChain-compatible ChatModel for the given model.

        Used by agent graphs that need a LangChain LLM directly.
        """
        provider = self._resolve_provider(model)
        if provider and hasattr(provider, "get_langchain_llm"):
            return provider.get_langchain_llm(model)
        return None
