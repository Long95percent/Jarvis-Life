"""Runtime LLM configuration validation and safe diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from urllib.parse import urlparse

from app.config import settings


class LLMErrorCode(StrEnum):
    CONFIG_MISSING_API_KEY = "LLM_CONFIG_MISSING_API_KEY"
    CONFIG_MISSING_MODEL = "LLM_CONFIG_MISSING_MODEL"
    CONFIG_INVALID_BASE_URL = "LLM_CONFIG_INVALID_BASE_URL"
    PROVIDER_UNREACHABLE = "LLM_PROVIDER_UNREACHABLE"
    PROVIDER_AUTH_FAILED = "LLM_PROVIDER_AUTH_FAILED"
    PROVIDER_MODEL_NOT_FOUND = "LLM_PROVIDER_MODEL_NOT_FOUND"
    PROVIDER_ENDPOINT_NOT_FOUND = "LLM_PROVIDER_ENDPOINT_NOT_FOUND"
    PROVIDER_RATE_LIMITED = "LLM_PROVIDER_RATE_LIMITED"
    PROVIDER_TIMEOUT = "LLM_PROVIDER_TIMEOUT"
    PROVIDER_BAD_RESPONSE = "LLM_PROVIDER_BAD_RESPONSE"
    PROVIDER_HTTP_ERROR = "LLM_PROVIDER_HTTP_ERROR"


SUGGESTIONS: dict[str, str] = {
    LLMErrorCode.CONFIG_MISSING_API_KEY: "请配置有效的 LLM API Key，或确认当前 Base URL 指向无需鉴权的本地模型服务。",
    LLMErrorCode.CONFIG_MISSING_MODEL: "请配置非空模型名，并确认该模型已被当前 Provider 支持。",
    LLMErrorCode.CONFIG_INVALID_BASE_URL: "请将 LLM Base URL 配置为 http:// 或 https:// 开头的 OpenAI-compatible 地址。",
    LLMErrorCode.PROVIDER_UNREACHABLE: "连接 LLM Provider 失败：请检查网络、代理、Base URL 或本地模型服务是否启动。",
    LLMErrorCode.PROVIDER_AUTH_FAILED: "LLM Provider 鉴权失败：请检查 API Key 是否有效，以及当前账号是否有模型权限。",
    LLMErrorCode.PROVIDER_MODEL_NOT_FOUND: "LLM 模型不存在或无权限：请检查模型名，以及 Provider 是否支持该模型。",
    LLMErrorCode.PROVIDER_ENDPOINT_NOT_FOUND: "LLM 接口地址不存在：请检查 Base URL 是否应以 /v1 结尾。",
    LLMErrorCode.PROVIDER_RATE_LIMITED: "LLM Provider 触发限流：请稍后重试或切换可用额度更高的模型/Key。",
    LLMErrorCode.PROVIDER_TIMEOUT: "LLM 请求超时：请检查 Provider 延迟、网络，或调整 timeout_seconds。",
    LLMErrorCode.PROVIDER_BAD_RESPONSE: "LLM Provider 返回格式异常：请确认它兼容 OpenAI chat/completions 响应格式。",
    LLMErrorCode.PROVIDER_HTTP_ERROR: "LLM Provider 返回错误：请根据 HTTP 状态码和 Provider 控制台继续排查。",
}


@dataclass(slots=True)
class LLMRuntimeConfig:
    base_url: str
    model: str
    api_key: str
    timeout_seconds: int

    @classmethod
    def from_settings(cls) -> "LLMRuntimeConfig":
        return cls(
            base_url=(settings.llm.base_url or "").strip(),
            model=(settings.llm.model or "").strip(),
            api_key=(settings.llm.api_key or "").strip(),
            timeout_seconds=settings.llm.timeout_seconds,
        )

    @property
    def is_local_provider(self) -> bool:
        parsed = urlparse(self.base_url)
        host = (parsed.hostname or "").lower()
        return host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}

    def masked_api_key(self) -> str:
        return mask_api_key(self.api_key)

    def summary(self) -> dict[str, Any]:
        return {
            "base_url": self.base_url,
            "model": self.model,
            "api_key_present": bool(self.api_key),
            "api_key_masked": self.masked_api_key(),
            "timeout_seconds": self.timeout_seconds,
        }

    def validate(self) -> None:
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise LLMRuntimeError(
                LLMErrorCode.CONFIG_INVALID_BASE_URL,
                "LLM base_url must be an absolute http(s) URL.",
            )
        if not self.model:
            raise LLMRuntimeError(LLMErrorCode.CONFIG_MISSING_MODEL, "LLM model is empty.")
        if not self.api_key and not self.is_local_provider:
            raise LLMRuntimeError(
                LLMErrorCode.CONFIG_MISSING_API_KEY,
                "LLM api_key is required for non-local providers.",
            )


class LLMRuntimeError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.code = str(code)
        self.status_code = status_code
        self.suggestion = SUGGESTIONS.get(self.code, "请检查 LLM 配置和 Provider 返回的错误详情。")

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_code": self.code,
            "error": str(self),
            "suggestion": self.suggestion,
        }


def mask_api_key(api_key: str) -> str:
    if not api_key:
        return "(empty)"
    if len(api_key) <= 8:
        return "*" * len(api_key)
    return f"{api_key[:4]}...{api_key[-4:]}"


def current_llm_config() -> LLMRuntimeConfig:
    return LLMRuntimeConfig.from_settings()


def validate_current_llm_config() -> LLMRuntimeConfig:
    config = current_llm_config()
    config.validate()
    return config
