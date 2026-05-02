import pytest
import asyncio


def test_amap_reverse_geocode_parses_city_label_and_coordinates():
    from app.jarvis.geocoding import parse_amap_reverse_geocode

    result = parse_amap_reverse_geocode(
        {
            "status": "1",
            "regeocode": {
                "formatted_address": "江苏省南京市玄武区珠江路",
                "addressComponent": {
                    "province": "江苏省",
                    "city": "南京市",
                    "district": "玄武区",
                    "adcode": "320102",
                },
            },
        },
        lat=32.0603,
        lng=118.7969,
    )

    assert result is not None
    assert result.label == "南京市"
    assert result.lat == 32.0603
    assert result.lng == 118.7969
    assert result.provider == "amap"
    assert result.adcode == "320102"


def test_amap_city_geocode_parses_city_coordinates_and_label():
    from app.jarvis.geocoding import parse_amap_city_geocode

    result = parse_amap_city_geocode(
        {
            "status": "1",
            "geocodes": [
                {
                    "formatted_address": "江苏省南京市",
                    "province": "江苏省",
                    "city": "南京市",
                    "district": [],
                    "adcode": "320100",
                    "location": "118.796877,32.060255",
                }
            ],
        },
        fallback_label="南京",
    )

    assert result is not None
    assert result.label == "南京市"
    assert result.lat == pytest.approx(32.060255)
    assert result.lng == pytest.approx(118.796877)
    assert result.provider == "amap"


def test_osm_label_parser_remains_available_as_fallback():
    from app.jarvis.geocoding import pick_osm_geocode_label

    assert pick_osm_geocode_label({"address": {"city_district": "Xuanwu District"}}) == "Xuanwu District"
    assert pick_osm_geocode_label({"display_name": "Nanjing, Jiangsu, China"}) == "Nanjing"


def test_geocoding_settings_accepts_legacy_amap_key_env(monkeypatch):
    from app.config import _GeocodingSettings

    monkeypatch.delenv("SHADOWLINK_GEOCODING_AMAP_KEY", raising=False)
    monkeypatch.setenv("SHADOWLINK_AMAP_KEY", "legacy-key")

    settings = _GeocodingSettings()

    assert settings.amap_key == "legacy-key"


def test_reverse_geocode_reports_missing_amap_key(monkeypatch):
    from app.jarvis import geocoding
    from app.jarvis import api_key_store

    class _FakeGeocodingSettings:
        provider = "amap"
        amap_key = ""
        timeout_seconds = 5.0
        osm_enabled = False

    class _FakeSettings:
        geocoding = _FakeGeocodingSettings()

    monkeypatch.setattr("app.config.settings", _FakeSettings())
    monkeypatch.setattr(api_key_store, "_DATA_DIR", None)
    monkeypatch.setattr(api_key_store, "_API_KEYS_FILE", None)
    monkeypatch.setattr(api_key_store, "get_external_api_key_value", lambda key_id: "")

    with pytest.raises(RuntimeError, match="SHADOWLINK_GEOCODING_AMAP_KEY"):
        asyncio.run(geocoding.reverse_geocode(32.0603, 118.7969))


def test_reverse_geocode_reports_amap_api_error(monkeypatch):
    from app.jarvis import geocoding

    class _FakeGeocodingSettings:
        provider = "auto"
        amap_key = "env-key"
        timeout_seconds = 5.0
        osm_enabled = True

    class _FakeSettings:
        geocoding = _FakeGeocodingSettings()

    async def fail_amap(*args, **kwargs):
        raise RuntimeError("AMap error 10009: USERKEY_PLAT_NOMATCH")

    async def fail_osm(*args, **kwargs):
        raise RuntimeError("OSM unavailable")

    monkeypatch.setattr("app.config.settings", _FakeSettings())
    monkeypatch.setattr(geocoding, "get_amap_api_key", lambda: "saved-key")
    monkeypatch.setattr(geocoding, "_reverse_geocode_amap", fail_amap)
    monkeypatch.setattr(geocoding, "_reverse_geocode_osm", fail_osm)

    with pytest.raises(RuntimeError, match="USERKEY_PLAT_NOMATCH"):
        asyncio.run(geocoding.reverse_geocode(32.0603, 118.7969))
