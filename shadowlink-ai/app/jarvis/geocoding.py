from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GeocodingResult:
    label: str
    lat: float
    lng: float
    provider: str
    formatted_address: str = ""
    adcode: str = ""

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "label": self.label,
            "lat": self.lat,
            "lng": self.lng,
            "provider": self.provider,
        }
        if self.formatted_address:
            data["formatted_address"] = self.formatted_address
        if self.adcode:
            data["adcode"] = self.adcode
        return data


def _string_value(value: Any) -> str:
    if isinstance(value, list):
        return ""
    return str(value or "").strip()


def _amap_label(component: dict[str, Any], formatted_address: str, fallback: str = "") -> str:
    return (
        _string_value(component.get("city"))
        or _string_value(component.get("district"))
        or _string_value(component.get("province"))
        or formatted_address.strip()
        or fallback.strip()
    )


def parse_amap_reverse_geocode(data: dict[str, Any], *, lat: float, lng: float) -> GeocodingResult | None:
    if str(data.get("status")) != "1":
        return None
    regeocode = data.get("regeocode") or {}
    component = regeocode.get("addressComponent") or {}
    formatted_address = _string_value(regeocode.get("formatted_address"))
    label = _amap_label(component, formatted_address)
    if not label:
        return None
    return GeocodingResult(
        label=label,
        lat=round(float(lat), 6),
        lng=round(float(lng), 6),
        provider="amap",
        formatted_address=formatted_address,
        adcode=_string_value(component.get("adcode")),
    )


def parse_amap_city_geocode(data: dict[str, Any], *, fallback_label: str = "") -> GeocodingResult | None:
    if str(data.get("status")) != "1":
        return None
    geocodes = data.get("geocodes") or []
    if not geocodes:
        return None
    item = geocodes[0] or {}
    location = _string_value(item.get("location"))
    if "," not in location:
        return None
    lng_text, lat_text = location.split(",", 1)
    formatted_address = _string_value(item.get("formatted_address"))
    label = _amap_label(item, formatted_address, fallback_label)
    if not label:
        return None
    return GeocodingResult(
        label=label,
        lat=round(float(lat_text), 6),
        lng=round(float(lng_text), 6),
        provider="amap",
        formatted_address=formatted_address,
        adcode=_string_value(item.get("adcode")),
    )


def pick_osm_geocode_label(data: dict[str, Any], fallback: str = "") -> str:
    address = data.get("address") or {}
    display_name = str(data.get("display_name") or "")
    return (
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("municipality")
        or address.get("city_district")
        or address.get("district")
        or address.get("state_district")
        or address.get("county")
        or address.get("state")
        or data.get("name")
        or (display_name.split(",")[0].strip() if display_name else "")
        or fallback
    )


def parse_osm_reverse_geocode(data: dict[str, Any], *, lat: float, lng: float) -> GeocodingResult | None:
    label = pick_osm_geocode_label(data)
    if not label:
        return None
    return GeocodingResult(label=label, lat=round(float(lat), 6), lng=round(float(lng), 6), provider="osm")


def parse_osm_city_geocode(data: list[dict[str, Any]], *, fallback_label: str = "") -> GeocodingResult | None:
    if not data:
        return None
    item = data[0]
    label = pick_osm_geocode_label(item, fallback=fallback_label)
    if not label:
        return None
    return GeocodingResult(
        label=label,
        lat=round(float(item["lat"]), 6),
        lng=round(float(item["lon"]), 6),
        provider="osm",
    )


async def reverse_geocode(lat: float, lng: float) -> GeocodingResult | None:
    from app.config import settings

    provider = settings.geocoding.provider.strip().lower()
    amap_key = get_amap_api_key()
    errors: list[str] = []
    wants_amap = provider in {"auto", "amap", "gaode"}
    if wants_amap and not amap_key:
        errors.append("amap: key is not configured; set SHADOWLINK_GEOCODING_AMAP_KEY")
    if wants_amap and amap_key:
        try:
            result = await _reverse_geocode_amap(lat, lng, amap_key=amap_key)
            if result:
                return result
        except Exception as exc:
            errors.append(f"amap: {exc}")
            if _is_provider_configuration_error(exc) or (provider in {"amap", "gaode"} and not settings.geocoding.osm_enabled):
                raise RuntimeError("; ".join(errors)) from exc
    if provider in {"auto", "osm"} and settings.geocoding.osm_enabled:
        try:
            return await _reverse_geocode_osm(lat, lng)
        except Exception as exc:
            errors.append(f"osm: {exc}")
    if errors:
        raise RuntimeError("; ".join(errors))
    return None


async def geocode_city(city: str) -> GeocodingResult | None:
    from app.config import settings

    provider = settings.geocoding.provider.strip().lower()
    amap_key = get_amap_api_key()
    errors: list[str] = []
    wants_amap = provider in {"auto", "amap", "gaode"}
    if wants_amap and not amap_key:
        errors.append("amap: key is not configured; set SHADOWLINK_GEOCODING_AMAP_KEY")
    if wants_amap and amap_key:
        try:
            result = await _geocode_city_amap(city, amap_key=amap_key)
            if result:
                return result
        except Exception as exc:
            errors.append(f"amap: {exc}")
            if _is_provider_configuration_error(exc) or (provider in {"amap", "gaode"} and not settings.geocoding.osm_enabled):
                raise RuntimeError("; ".join(errors)) from exc
    if provider in {"auto", "osm"} and settings.geocoding.osm_enabled:
        try:
            return await _geocode_city_osm(city)
        except Exception as exc:
            errors.append(f"osm: {exc}")
    if errors:
        raise RuntimeError("; ".join(errors))
    return None


def get_amap_api_key() -> str:
    from app.config import settings

    try:
        from app.jarvis.api_key_store import get_external_api_key_value

        saved_key = get_external_api_key_value("amap")
        if saved_key:
            return saved_key
    except Exception:
        pass
    return settings.geocoding.amap_key


def _raise_for_amap_payload(data: dict[str, Any]) -> None:
    if str(data.get("status")) == "1":
        return
    info = str(data.get("info") or "UNKNOWN")
    infocode = str(data.get("infocode") or "")
    suffix = f" {infocode}" if infocode else ""
    raise RuntimeError(f"AMap error{suffix}: {info}")


def _is_provider_configuration_error(exc: Exception) -> bool:
    text = str(exc)
    return "AMap error" in text and any(code in text for code in {"10001", "10002", "10003", "10007", "10009"})


async def _reverse_geocode_amap(lat: float, lng: float, *, amap_key: str) -> GeocodingResult | None:
    import httpx

    from app.config import settings

    async with httpx.AsyncClient(timeout=settings.geocoding.timeout_seconds) as client:
        resp = await client.get(
            "https://restapi.amap.com/v3/geocode/regeo",
            params={
                "key": amap_key,
                "location": f"{lng},{lat}",
                "extensions": "base",
                "output": "json",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        _raise_for_amap_payload(data)
        return parse_amap_reverse_geocode(data, lat=lat, lng=lng)


async def _geocode_city_amap(city: str, *, amap_key: str) -> GeocodingResult | None:
    import httpx

    from app.config import settings

    async with httpx.AsyncClient(timeout=settings.geocoding.timeout_seconds) as client:
        resp = await client.get(
            "https://restapi.amap.com/v3/geocode/geo",
            params={"key": amap_key, "address": city, "output": "json"},
        )
        resp.raise_for_status()
        data = resp.json()
        _raise_for_amap_payload(data)
        return parse_amap_city_geocode(data, fallback_label=city)


async def _reverse_geocode_osm(lat: float, lng: float) -> GeocodingResult | None:
    import httpx

    from app.config import settings

    headers = {"User-Agent": "Jarvis-Life/0.1 location settings"}
    async with httpx.AsyncClient(
        timeout=settings.geocoding.timeout_seconds, headers=headers, follow_redirects=True
    ) as client:
        resp = await client.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"format": "jsonv2", "lat": lat, "lon": lng, "zoom": 10, "addressdetails": 1},
        )
        resp.raise_for_status()
        return parse_osm_reverse_geocode(resp.json(), lat=lat, lng=lng)


async def _geocode_city_osm(city: str) -> GeocodingResult | None:
    import httpx

    from app.config import settings

    headers = {"User-Agent": "Jarvis-Life/0.1 location settings"}
    async with httpx.AsyncClient(
        timeout=settings.geocoding.timeout_seconds, headers=headers, follow_redirects=True
    ) as client:
        resp = await client.get(
            "https://nominatim.openstreetmap.org/search",
            params={"format": "jsonv2", "q": city, "limit": 1, "addressdetails": 1},
        )
        resp.raise_for_status()
        return parse_osm_city_geocode(resp.json(), fallback_label=city)
