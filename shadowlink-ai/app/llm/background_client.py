"""Background LLM client for low-priority Jarvis maintenance work."""

from __future__ import annotations

from typing import Any, AsyncIterator

from app.core.dependencies import get_resource
from app.llm.providers.openai import OpenAIProvider


class SidecarLLMClient:
    """Small OpenAI-compatible client used outside the user-facing agent path."""

    def __init__(self, provider: dict[str, Any]) -> None:
        self.provider_id = str(provider.get("id") or "")
        self.name = str(provider.get("name") or "Background model")
        self.base_url = str(provider["base_url"]).rstrip("/")
        self.model = str(provider["model"])
        self.temperature = float(provider.get("temperature", 0.0))
        self.max_tokens = int(provider.get("max_tokens", 1024))
        self._provider = OpenAIProvider(
            base_url=self.base_url,
            api_key=str(provider.get("api_key") or ""),
            default_model=self.model,
        )

    async def chat(
        self,
        message: str,
        *,
        model: str | None = None,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        return await self._provider.chat(
            message,
            model=model or self.model,
            system_prompt=system_prompt,
            temperature=self.temperature if temperature is None else temperature,
            max_tokens=self.max_tokens if max_tokens is None else max_tokens,
        )

    async def chat_stream(
        self,
        message: str,
        *,
        model: str | None = None,
        system_prompt: str | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[str]:
        async for chunk in self._provider.chat_stream(
            message,
            model=model or self.model,
            system_prompt=system_prompt,
            temperature=self.temperature if temperature is None else temperature,
        ):
            yield chunk


def build_background_llm_client(provider: dict[str, Any] | None) -> SidecarLLMClient | None:
    if not provider:
        return None
    return SidecarLLMClient(provider)


def get_background_llm_client() -> Any:
    """Return configured sidecar client, falling back to the primary LLM client."""

    return get_resource("background_llm_client") or get_resource("llm_client")
