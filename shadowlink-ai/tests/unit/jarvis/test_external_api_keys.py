from pathlib import Path
from uuid import uuid4

from app.api.v1 import settings_router
from app.jarvis import api_key_store


def test_external_api_key_save_list_delete(monkeypatch):
    data_dir = Path("shadowlink-ai/.test_api_keys") / uuid4().hex
    api_keys_file = data_dir / "api_keys.json"
    monkeypatch.setattr(api_key_store, "_DATA_DIR", data_dir)
    monkeypatch.setattr(api_key_store, "_API_KEYS_FILE", api_keys_file)

    saved = settings_router.save_external_api_key(
        "amap",
        settings_router.ExternalApiKeyUpdate(api_key="amap-secret-123456"),
    )
    listed = settings_router.list_external_api_keys()

    assert saved.data == {
        "id": "amap",
        "name": "高德地图",
        "has_key": True,
        "api_key_masked": "amap-s...3456",
    }
    assert listed.data["keys"][0]["id"] == "amap"
    assert listed.data["keys"][0]["has_key"] is True
    assert "amap-secret-123456" not in str(listed.data)
    assert settings_router.get_external_api_key_value("amap") == "amap-secret-123456"

    deleted = settings_router.delete_external_api_key("amap")
    listed_after_delete = settings_router.list_external_api_keys()

    assert deleted.success is True
    assert listed_after_delete.data["keys"][0]["has_key"] is False
    assert settings_router.get_external_api_key_value("amap") == ""


def test_geocoding_reads_saved_amap_key_without_router_import(monkeypatch):
    from app.jarvis.geocoding import get_amap_api_key

    data_dir = Path("shadowlink-ai/.test_api_keys") / uuid4().hex
    monkeypatch.setattr(api_key_store, "_DATA_DIR", data_dir)
    monkeypatch.setattr(api_key_store, "_API_KEYS_FILE", data_dir / "api_keys.json")

    api_key_store.save_external_api_key_value("amap", "saved-amap-key")

    assert get_amap_api_key() == "saved-amap-key"
