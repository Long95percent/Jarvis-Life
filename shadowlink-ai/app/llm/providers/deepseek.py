"""DeepSeek LLM provider — extends OpenAI-compatible base.

DeepSeek uses the OpenAI API format with their own endpoint.
"""

from __future__ import annotations

from app.llm.providers.openai import OpenAIProvider


class DeepSeekProvider(OpenAIProvider):
    """DeepSeek API provider."""

    def __init__(self, api_key: str = "", default_model: str = "deepseek-chat"):
        super().__init__(
            base_url="https://api.deepseek.com/v1",
            api_key=api_key,
            default_model=default_model,
        )
