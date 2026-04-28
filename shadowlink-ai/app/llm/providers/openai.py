"""OpenAI-compatible LLM provider.

Supports any API that implements the OpenAI chat completions format,
including local models served via vLLM, Ollama, LM Studio, etc.
"""

from __future__ import annotations

from typing import Any, AsyncIterator

import httpx
import structlog

from app.config import settings
from app.llm.runtime_config import LLMErrorCode, LLMRuntimeError

logger = structlog.get_logger("llm.providers.openai")


def _summarize_http_error(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except Exception:
        payload = None

    message = ""
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = str(error.get("message") or error.get("code") or error)
        elif isinstance(payload.get("message"), str):
            message = payload["message"]
        elif isinstance(payload.get("detail"), str):
            message = payload["detail"]
    if not message:
        message = response.text[:500]
    return f"LLM HTTP {response.status_code} from {response.request.url}: {message}".strip()



def _map_http_error(response: httpx.Response) -> LLMRuntimeError:
    status_code = response.status_code
    message = _summarize_http_error(response)
    lowered = message.lower()
    if status_code in {401, 403}:
        code = LLMErrorCode.PROVIDER_AUTH_FAILED
    elif status_code == 404 and "model" in lowered:
        code = LLMErrorCode.PROVIDER_MODEL_NOT_FOUND
    elif status_code == 404:
        code = LLMErrorCode.PROVIDER_ENDPOINT_NOT_FOUND
    elif status_code == 429:
        code = LLMErrorCode.PROVIDER_RATE_LIMITED
    else:
        code = LLMErrorCode.PROVIDER_HTTP_ERROR
    return LLMRuntimeError(code, message, status_code=status_code)


def _map_request_error(exc: httpx.RequestError) -> LLMRuntimeError:
    if isinstance(exc, httpx.TimeoutException):
        code = LLMErrorCode.PROVIDER_TIMEOUT
    elif isinstance(exc, httpx.ConnectError):
        code = LLMErrorCode.PROVIDER_UNREACHABLE
    else:
        code = LLMErrorCode.PROVIDER_UNREACHABLE
    return LLMRuntimeError(code, str(exc) or exc.__class__.__name__)

class OpenAIProvider:
    """OpenAI-compatible API provider."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        default_model: str | None = None,
    ):
        self.base_url = (base_url or settings.llm.base_url).rstrip("/")
        self.api_key = api_key or settings.llm.api_key
        self.default_model = default_model or settings.llm.model
        self.timeout = settings.llm.timeout_seconds

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def chat(
        self,
        message: str,
        *,
        model: str | None = None,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Non-streaming chat completion."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})

        payload: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature if temperature is not None else settings.llm.temperature,
            "max_tokens": max_tokens if max_tokens is not None else settings.llm.max_tokens,
        }

        try:
            async with httpx.AsyncClient(timeout=float(self.timeout)) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                )
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    raise _map_http_error(response) from exc
                data = response.json()
        except LLMRuntimeError:
            raise
        except httpx.RequestError as exc:
            raise _map_request_error(exc) from exc
        except ValueError as exc:
            raise LLMRuntimeError(LLMErrorCode.PROVIDER_BAD_RESPONSE, "LLM response is not valid JSON.") from exc

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMRuntimeError(
                LLMErrorCode.PROVIDER_BAD_RESPONSE,
                f"LLM response format invalid: {str(data)[:500]}",
            ) from exc

    async def chat_stream(
        self,
        message: str,
        *,
        model: str | None = None,
        system_prompt: str | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[str]:
        """Streaming chat completion via SSE."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})

        payload: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature if temperature is not None else settings.llm.temperature,
            "stream": True,
        }

        try:
            async with httpx.AsyncClient(timeout=float(self.timeout)) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                ) as response:
                    try:
                        response.raise_for_status()
                    except httpx.HTTPStatusError as exc:
                        raise _map_http_error(response) from exc
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str.strip() == "[DONE]":
                                break
                            try:
                                import json

                                data = json.loads(data_str)
                                delta = data["choices"][0].get("delta", {})
                                if content := delta.get("content"):
                                    yield content
                            except (json.JSONDecodeError, KeyError, IndexError):
                                continue
        except LLMRuntimeError:
            raise
        except httpx.RequestError as exc:
            raise _map_request_error(exc) from exc

    def get_langchain_llm(self, model: str | None = None) -> Any:
        """Return a LangChain ChatOpenAI instance."""
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            base_url=self.base_url,
            api_key=self.api_key or "not-needed",
            model=model or self.default_model,
            temperature=settings.llm.temperature,
            max_tokens=settings.llm.max_tokens,
            streaming=True,
        )


