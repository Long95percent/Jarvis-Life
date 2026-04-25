"""Ollama LLM provider — local model inference via Ollama.

Ollama serves local models with an OpenAI-compatible API.
"""

from __future__ import annotations

from app.llm.providers.openai import OpenAIProvider


class OllamaProvider(OpenAIProvider):
    """Ollama local model provider."""

    def __init__(self, base_url: str = "http://localhost:11434/v1", default_model: str = "llama3"):
        super().__init__(
            base_url=base_url,
            api_key="ollama",  # Ollama doesn't require a real key
            default_model=default_model,
        )
