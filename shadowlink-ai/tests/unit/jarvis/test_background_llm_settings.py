from pathlib import Path

import pytest

from app.api.v1 import settings_router
from app.core.dependencies import get_resource, set_resource
from app.llm.background_client import SidecarLLMClient, get_background_llm_client


@pytest.fixture(autouse=True)
def temp_provider_file(monkeypatch, tmp_path):
    provider_file = tmp_path / "llm_providers.json"
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(settings_router, "_PROVIDERS_FILE", provider_file)
    set_resource("background_llm_client", None)
    yield provider_file
    set_resource("background_llm_client", None)


@pytest.mark.asyncio
async def test_background_provider_can_be_configured_independently():
    primary = await settings_router.add_provider(
        settings_router.ProviderCreate(
            name="Primary",
            base_url="https://primary.example/v1",
            model="primary-model",
            api_key="primary-key",
        )
    )
    sidecar = await settings_router.add_provider(
        settings_router.ProviderCreate(
            name="Sidecar",
            base_url="https://sidecar.example/v1",
            model="small-model",
            api_key="sidecar-key",
            temperature=0.1,
            max_tokens=512,
        )
    )

    await settings_router.activate_provider(primary.data["id"])
    result = await settings_router.activate_background_provider(sidecar.data["id"])
    listed = await settings_router.list_providers()

    assert result.data["id"] == sidecar.data["id"]
    assert listed.data["active_id"] == primary.data["id"]
    assert listed.data["background_id"] == sidecar.data["id"]

    client = get_background_llm_client()
    assert isinstance(client, SidecarLLMClient)
    assert client.model == "small-model"
    assert client.base_url == "https://sidecar.example/v1"
    assert get_resource("background_llm_client") is client
