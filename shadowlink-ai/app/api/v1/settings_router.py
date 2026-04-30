"""Settings API — LLM provider management and runtime configuration."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import httpx
import structlog
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.config import settings
from app.core.dependencies import get_resource, set_resource
from app.models.common import Result

logger = structlog.get_logger("api.settings")
router = APIRouter()

# ── Data persistence ──────────────────────────────────────────────

_DATA_DIR = Path(settings.data_dir)
_PROVIDERS_FILE = _DATA_DIR / "llm_providers.json"


def _ensure_data_dir() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_providers() -> dict:
    """Load provider config from JSON file; auto-seed from .env on first run."""
    _ensure_data_dir()
    if _PROVIDERS_FILE.exists():
        try:
            with open(_PROVIDERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("providers"):
                data.setdefault("background_id", None)
                return data
        except (json.JSONDecodeError, KeyError):
            pass

    # First run — seed from .env settings if an API key is configured
    data: dict[str, Any] = {"providers": [], "active_id": None, "background_id": None}
    if settings.llm.api_key:
        provider = {
            "id": "default",
            "name": "Default (from .env)",
            "base_url": settings.llm.base_url,
            "model": settings.llm.model,
            "api_key": settings.llm.api_key,
            "temperature": settings.llm.temperature,
            "max_tokens": settings.llm.max_tokens,
        }
        data["providers"].append(provider)
        data["active_id"] = "default"
        data["background_id"] = None
        _save_providers(data)
    data.setdefault("background_id", None)
    return data


def _save_providers(data: dict) -> None:
    _ensure_data_dir()
    with open(_PROVIDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ── Preset provider templates ────────────────────────────────────

PRESETS: list[dict[str, Any]] = [
    {
        "id": "preset-openai",
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o",
        "api_key": "",
        "temperature": 0.7,
        "max_tokens": 4096,
    },
    {
        "id": "preset-deepseek",
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "api_key": "",
        "temperature": 0.7,
        "max_tokens": 4096,
    },
    {
        "id": "preset-dashscope",
        "name": "通义千问 (DashScope)",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-turbo",
        "api_key": "",
        "temperature": 0.7,
        "max_tokens": 4096,
    },
    {
        "id": "preset-zhipu",
        "name": "智谱 GLM (Zhipu)",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4",
        "api_key": "",
        "temperature": 0.7,
        "max_tokens": 4096,
    },
    {
        "id": "preset-moonshot",
        "name": "Moonshot (Kimi)",
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-8k",
        "api_key": "",
        "temperature": 0.7,
        "max_tokens": 4096,
    },
    {
        "id": "preset-siliconflow",
        "name": "SiliconFlow",
        "base_url": "https://api.siliconflow.cn/v1",
        "model": "deepseek-ai/DeepSeek-V3",
        "api_key": "",
        "temperature": 0.7,
        "max_tokens": 4096,
    },
    {
        "id": "preset-ollama",
        "name": "Ollama (本地模型)",
        "base_url": "http://127.0.0.1:11434/v1",
        "model": "llama3",
        "api_key": "ollama",
        "temperature": 0.7,
        "max_tokens": 4096,
    },
    {
        "id": "preset-lmstudio",
        "name": "LM Studio (本地)",
        "base_url": "http://127.0.0.1:1234/v1",
        "model": "local-model",
        "api_key": "lm-studio",
        "temperature": 0.7,
        "max_tokens": 4096,
    },
]


# ── Request / Response models ────────────────────────────────────

class ProviderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    base_url: str = Field(min_length=1)
    model: str = Field(min_length=1)
    api_key: str = ""
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1)


class ProviderUpdate(BaseModel):
    name: str | None = None
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1)


class LLMSettingsUpdate(BaseModel):
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)


def _looks_like_ui_error(value: str | None) -> bool:
    text = (value or "").strip().lower()
    return text.startswith("error:") or ("provider " in text and " not found" in text)


# ── Provider CRUD endpoints ──────────────────────────────────────

@router.get("/providers")
async def list_providers() -> Result[dict]:
    """List all configured providers with masked API keys."""
    data = _load_providers()
    safe = []
    for p in data["providers"]:
        entry = {**p}
        key = entry.get("api_key", "")
        entry["api_key_masked"] = (
            f"{key[:6]}...{key[-4:]}" if len(key) > 12 else ("***" if key else "")
        )
        # Don't send raw key in list — send it only in single-get or when editing
        safe.append(entry)
    return Result.ok(data={
        "providers": safe,
        "active_id": data.get("active_id"),
        "background_id": data.get("background_id"),
    })


@router.get("/providers/presets")
async def list_presets() -> Result[list[dict]]:
    """List preset provider templates for quick-add."""
    return Result.ok(data=PRESETS)


@router.get("/providers/{provider_id}")
async def get_provider(provider_id: str) -> Result[dict]:
    """Get a single provider (includes full API key for editing)."""
    data = _load_providers()
    for p in data["providers"]:
        if p["id"] == provider_id:
            return Result.ok(data=p)
    return Result.fail(code=404, message=f"Provider '{provider_id}' not found")


@router.post("/providers")
async def add_provider(provider: ProviderCreate) -> Result[dict]:
    """Add a new LLM provider."""
    if _looks_like_ui_error(provider.api_key):
        return Result.fail(code=400, message="Refusing to save an error message as an API key")
    data = _load_providers()
    new_provider = {"id": uuid.uuid4().hex[:8], **provider.model_dump()}
    data["providers"].append(new_provider)

    # Auto-activate if this is the first provider
    if data["active_id"] is None:
        data["active_id"] = new_provider["id"]
        _apply_provider(new_provider)

    _save_providers(data)
    logger.info("provider_added", name=new_provider["name"], id=new_provider["id"])
    return Result.ok(data=new_provider)


@router.put("/providers/{provider_id}")
async def update_provider(provider_id: str, update: ProviderUpdate) -> Result[dict]:
    """Update an existing provider's settings."""
    data = _load_providers()
    for p in data["providers"]:
        if p["id"] == provider_id:
            for k, v in update.model_dump(exclude_none=True).items():
                if k == "api_key" and _looks_like_ui_error(v):
                    return Result.fail(code=400, message="Refusing to save an error message as an API key")
                p[k] = v
            _save_providers(data)
            if data["active_id"] == provider_id:
                _apply_provider(p)
            return Result.ok(data=p)
    return Result.fail(code=404, message=f"Provider '{provider_id}' not found")


@router.delete("/providers/{provider_id}")
async def delete_provider(provider_id: str) -> Result[None]:
    """Delete a provider. If it's active, auto-switch to another."""
    data = _load_providers()
    original_len = len(data["providers"])
    data["providers"] = [p for p in data["providers"] if p["id"] != provider_id]
    if len(data["providers"]) == original_len:
        return Result.ok(message="Provider already deleted")

    if data["active_id"] == provider_id:
        if data["providers"]:
            data["active_id"] = data["providers"][0]["id"]
            _apply_provider(data["providers"][0])
        else:
            data["active_id"] = None

    _save_providers(data)
    return Result.ok(message="Provider deleted")


@router.post("/providers/{provider_id}/activate")
async def activate_provider(provider_id: str) -> Result[dict]:
    """Set a provider as the active one and reinitialize the LLM client."""
    data = _load_providers()
    for p in data["providers"]:
        if p["id"] == provider_id:
            data["active_id"] = provider_id
            _save_providers(data)
            _apply_provider(p)
            return Result.ok(data=p, message=f"Activated: {p['name']}")
    return Result.fail(code=404, message=f"Provider '{provider_id}' not found")


@router.post("/providers/{provider_id}/activate-background")
async def activate_background_provider(provider_id: str) -> Result[dict]:
    """Set a provider as the low-priority background/sidecar model."""
    data = _load_providers()
    for p in data["providers"]:
        if p["id"] == provider_id:
            data["background_id"] = provider_id
            _save_providers(data)
            _apply_background_provider(p)
            return Result.ok(data=p, message=f"Activated background model: {p['name']}")
    return Result.fail(code=404, message=f"Provider '{provider_id}' not found")


@router.post("/providers/test")
async def test_provider(provider: ProviderCreate) -> Result[dict]:
    """Test connectivity to an LLM provider by sending a minimal completion request."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if provider.api_key:
                headers["Authorization"] = f"Bearer {provider.api_key}"

            resp = await client.post(
                f"{provider.base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json={
                    "model": provider.model,
                    "messages": [{"role": "user", "content": "Hi"}],
                    "max_tokens": 5,
                },
            )
            if resp.status_code == 200:
                return Result.ok(data={"status": "ok", "message": "Connection successful!"})
            else:
                body = resp.text[:300]
                return Result.ok(data={
                    "status": "error",
                    "message": f"HTTP {resp.status_code}: {body}",
                })
    except httpx.ConnectError:
        return Result.ok(data={"status": "error", "message": "Connection refused — is the service running?"})
    except httpx.TimeoutException:
        return Result.ok(data={"status": "error", "message": "Connection timed out (15s)"})
    except Exception as exc:
        return Result.ok(data={"status": "error", "message": str(exc)})


# ── Internal helper ──────────────────────────────────────────────

def _apply_provider(provider: dict) -> None:
    """Push provider settings into the running LLM client."""
    settings.llm.base_url = provider["base_url"]
    settings.llm.api_key = provider.get("api_key", "")
    settings.llm.model = provider["model"]
    settings.llm.temperature = provider.get("temperature", 0.7)
    settings.llm.max_tokens = provider.get("max_tokens", 4096)

    try:
        from app.llm.client import LLMClient

        llm_client = LLMClient()
        llm_client.initialize()
        set_resource("llm_client", llm_client)
        logger.info("llm_client_reinitialized", provider=provider["name"], model=provider["model"])
    except Exception as exc:
        logger.error("llm_client_reinit_failed", error=str(exc))


def _apply_background_provider(provider: dict | None) -> None:
    """Push sidecar provider settings into the running background LLM client."""
    try:
        from app.llm.background_client import build_background_llm_client

        client = build_background_llm_client(provider)
        set_resource("background_llm_client", client)
        try:
            from app.core.lifespan import get_preference_learner

            learner = get_preference_learner()
            if learner is not None and hasattr(learner, "set_llm_client"):
                learner.set_llm_client(client or get_resource("llm_client"))
        except Exception as exc:
            logger.warning("preference_learner_sidecar_update_failed", error=str(exc))
        if provider:
            logger.info("background_llm_client_reinitialized", provider=provider.get("name"), model=provider.get("model"))
    except Exception as exc:
        logger.error("background_llm_client_reinit_failed", error=str(exc))


# ── Legacy endpoints (backward-compatible) ───────────────────────

@router.get("/llm")
async def get_llm_settings() -> Result[dict[str, Any]]:
    """Get current LLM configuration (API key masked)."""
    from app.llm.runtime_config import mask_api_key

    masked = mask_api_key(settings.llm.api_key)
    return Result.ok(data={
        "base_url": settings.llm.base_url,
        "model": settings.llm.model,
        "api_key_masked": masked,
        "temperature": settings.llm.temperature,
        "max_tokens": settings.llm.max_tokens,
        "streaming": settings.llm.streaming,
    })


@router.put("/llm")
async def update_llm_settings(update: LLMSettingsUpdate) -> Result[dict[str, str]]:
    """Update LLM settings at runtime and reinitialize the client."""
    from app.llm.client import LLMClient

    changed: list[str] = []
    if update.base_url is not None:
        settings.llm.base_url = update.base_url
        changed.append("base_url")
    if update.api_key is not None:
        settings.llm.api_key = update.api_key
        changed.append("api_key")
    if update.model is not None:
        settings.llm.model = update.model
        changed.append("model")
    if update.temperature is not None:
        settings.llm.temperature = update.temperature
        changed.append("temperature")

    if changed:
        llm_client = LLMClient()
        llm_client.initialize()
        set_resource("llm_client", llm_client)

    return Result.ok(data={"updated_fields": ", ".join(changed) or "none"})


@router.get("/info")
async def get_service_info() -> Result[dict[str, Any]]:
    """Get service status and capabilities."""
    tool_registry = get_resource("tool_registry")
    rag_engine = get_resource("rag_engine")
    agent_engine = get_resource("agent_engine")

    return Result.ok(data={
        "version": settings.version,
        "env": settings.env,
        "llm_model": settings.llm.model,
        "llm_base_url": settings.llm.base_url,
        "tools_count": tool_registry.tool_count if tool_registry else 0,
        "tools": [t.name for t in tool_registry.list_tools()] if tool_registry else [],
        "rag_available": rag_engine is not None,
        "agent_strategies": (
            list(agent_engine._strategy_executors.keys()) if agent_engine else []
        ),
    })
