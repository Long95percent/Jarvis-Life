"""Anthropic (Claude) LLM provider.

Uses the Anthropic Messages API format. Phase 1+ will implement
full streaming with proper content block handling.
"""

from __future__ import annotations

from typing import Any, AsyncIterator

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger("llm.providers.anthropic")


class AnthropicProvider:
    """Anthropic Claude API provider."""

    def __init__(self, api_key: str = "", default_model: str = "claude-sonnet-4-6"):
        self.api_key = api_key
        self.default_model = default_model
        self.base_url = "https://api.anthropic.com/v1"
        self.timeout = settings.llm.timeout_seconds

    async def chat(
        self,
        message: str,
        *,
        model: str | None = None,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Non-streaming chat via Anthropic Messages API."""
        payload: dict[str, Any] = {
            "model": model or self.default_model,
            "max_tokens": max_tokens or settings.llm.max_tokens,
            "messages": [{"role": "user", "content": message}],
        }
        if system_prompt:
            payload["system"] = system_prompt
        if temperature is not None:
            payload["temperature"] = temperature

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=float(self.timeout)) as client:
            response = await client.post(
                f"{self.base_url}/messages",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"]

    async def chat_stream(
        self,
        message: str,
        *,
        model: str | None = None,
        system_prompt: str | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[str]:
        """Streaming chat via Anthropic Messages API with SSE."""
        import json as _json

        payload: dict[str, Any] = {
            "model": model or self.default_model,
            "max_tokens": settings.llm.max_tokens,
            "messages": [{"role": "user", "content": message}],
            "stream": True,
        }
        if system_prompt:
            payload["system"] = system_prompt
        if temperature is not None:
            payload["temperature"] = temperature

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=float(self.timeout)) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/messages",
                headers=headers,
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        event = _json.loads(data_str)
                    except _json.JSONDecodeError:
                        continue
                    # Extract text from content_block_delta events
                    if event.get("type") == "content_block_delta":
                        delta = event.get("delta", {})
                        if delta.get("type") == "text_delta" and delta.get("text"):
                            yield delta["text"]
