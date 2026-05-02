from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import settings


_DATA_DIR = Path(settings.data_dir)
_API_KEYS_FILE = _DATA_DIR / "api_keys.json"

EXTERNAL_API_KEYS: dict[str, str] = {
    "amap": "高德地图",
}


def _ensure_data_dir() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_external_api_keys() -> dict[str, str]:
    _ensure_data_dir()
    if not _API_KEYS_FILE.exists():
        return {}
    try:
        with open(_API_KEYS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        keys = data.get("keys", {}) if isinstance(data, dict) else {}
        return {str(k): str(v) for k, v in keys.items() if str(v).strip()}
    except (json.JSONDecodeError, OSError):
        return {}


def save_external_api_keys(keys: dict[str, str]) -> None:
    _ensure_data_dir()
    with open(_API_KEYS_FILE, "w", encoding="utf-8") as f:
        json.dump({"keys": keys}, f, indent=2, ensure_ascii=False)


def mask_api_key(api_key: str) -> str:
    if len(api_key) > 12:
        return f"{api_key[:6]}...{api_key[-4:]}"
    return "***" if api_key else ""


def external_api_key_entry(key_id: str, api_key: str = "") -> dict[str, Any]:
    return {
        "id": key_id,
        "name": EXTERNAL_API_KEYS[key_id],
        "has_key": bool(api_key),
        "api_key_masked": mask_api_key(api_key),
    }


def get_external_api_key_value(key_id: str) -> str:
    if key_id not in EXTERNAL_API_KEYS:
        return ""
    return load_external_api_keys().get(key_id, "")


def save_external_api_key_value(key_id: str, api_key: str) -> dict[str, Any]:
    if key_id not in EXTERNAL_API_KEYS:
        raise KeyError(key_id)
    keys = load_external_api_keys()
    keys[key_id] = api_key
    save_external_api_keys(keys)
    return external_api_key_entry(key_id, api_key)


def delete_external_api_key_value(key_id: str) -> None:
    keys = load_external_api_keys()
    if key_id in keys:
        del keys[key_id]
        save_external_api_keys(keys)

