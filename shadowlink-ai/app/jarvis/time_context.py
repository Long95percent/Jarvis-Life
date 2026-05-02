"""Timezone-aware time context helpers for Jarvis."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.jarvis.user_settings import UserProfile, get_settings

DEFAULT_TIMEZONE = "Asia/Shanghai"


def resolve_timezone(timezone_name: str | None) -> ZoneInfo:
    """Resolve an IANA timezone name into ZoneInfo."""
    normalized = (timezone_name or "").strip() or DEFAULT_TIMEZONE
    try:
        return ZoneInfo(normalized)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Invalid timezone: {normalized}") from exc


def choose_timezone(profile: UserProfile | None = None, browser_timezone: str | None = None) -> str:
    """Choose timezone by priority: manually saved profile, browser-detected, default."""
    saved_timezone = ""
    timezone_source = "auto"
    if profile is not None and profile.location is not None:
        saved_timezone = (profile.location.timezone or "").strip()
        timezone_source = (getattr(profile.location, "timezone_source", "auto") or "auto").strip()
    if saved_timezone and timezone_source == "manual":
        resolve_timezone(saved_timezone)
        return saved_timezone

    detected_timezone = (browser_timezone or "").strip()
    if detected_timezone:
        resolve_timezone(detected_timezone)
        return detected_timezone

    fallback_timezone = saved_timezone or DEFAULT_TIMEZONE
    resolve_timezone(fallback_timezone)
    return fallback_timezone


def _format_utc_offset(dt: datetime) -> str:
    offset = dt.utcoffset()
    if offset is None:
        return "+00:00"
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    absolute_minutes = abs(total_minutes)
    hours, minutes = divmod(absolute_minutes, 60)
    return f"{sign}{hours:02d}:{minutes:02d}"


def suggest_location_from_browser_coordinates(
    *,
    lat: float,
    lng: float,
    browser_timezone: str | None = None,
    current_label: str | None = None,
    reverse_geocode: Any | None = None,
    label_error: str | None = None,
) -> dict[str, Any]:
    """Suggest a profile location after browser geolocation updates coordinates."""
    timezone_name = (browser_timezone or "").strip() or DEFAULT_TIMEZONE
    resolve_timezone(timezone_name)

    label = ""
    if reverse_geocode is not None:
        label = (reverse_geocode(lat, lng) or "").strip()
    label_source = "reverse_geocode" if label else "browser"
    if not label:
        label = f"Current Location ({lat:.4f}, {lng:.4f})"

    result = {
        "lat": round(lat, 6),
        "lng": round(lng, 6),
        "label": label,
        "timezone": timezone_name,
        "timezone_source": "browser",
        "label_source": label_source,
        "previous_label": current_label or "",
    }
    if label_error:
        result["label_error"] = label_error
    return result


def suggest_location_from_city_name(
    *,
    city_name: str,
    browser_timezone: str | None = None,
    geocode: Any | None = None,
) -> dict[str, Any]:
    """Resolve a user-entered city name into profile location fields."""
    city = city_name.strip()
    if not city:
        raise ValueError("City name is required")
    timezone_name = (browser_timezone or "").strip() or DEFAULT_TIMEZONE
    resolve_timezone(timezone_name)
    if geocode is None:
        raise ValueError(f"Unable to resolve city: {city}")

    resolved = geocode(city)
    if not resolved:
        raise ValueError(f"Unable to resolve city: {city}")

    label = str(resolved.get("label") or city).strip() or city
    lat = float(resolved["lat"])
    lng = float(resolved["lng"])
    resolved_timezone = str(resolved.get("timezone") or timezone_name).strip() or timezone_name
    resolve_timezone(resolved_timezone)

    return {
        "lat": round(lat, 6),
        "lng": round(lng, 6),
        "label": label,
        "timezone": resolved_timezone,
        "timezone_source": "manual",
        "label_source": "geocode",
    }


def build_time_context(
    *,
    profile: UserProfile | None = None,
    browser_timezone: str | None = None,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    """Build a stable timezone-aware time payload for API and prompts."""
    effective_profile = profile or get_settings().profile
    timezone_name = choose_timezone(effective_profile, browser_timezone)
    zone = resolve_timezone(timezone_name)
    utc_now = now_utc or datetime.now(timezone.utc)
    if utc_now.tzinfo is None:
        utc_now = utc_now.replace(tzinfo=timezone.utc)
    local_now = utc_now.astimezone(zone)

    location_label = ""
    if effective_profile.location is not None:
        location_label = effective_profile.location.label or ""

    return {
        "timezone": timezone_name,
        "timezone_abbr": local_now.strftime("%Z"),
        "utc_offset": _format_utc_offset(local_now),
        "local_iso": local_now.isoformat(),
        "local_date": local_now.date().isoformat(),
        "local_time": local_now.strftime("%H:%M:%S"),
        "weekday": local_now.strftime("%A"),
        "location_label": location_label,
    }


def build_time_prompt_line(
    *,
    profile: UserProfile | None = None,
    browser_timezone: str | None = None,
    now_utc: datetime | None = None,
) -> str:
    """Build a compact prompt line describing the user's local time."""
    context = build_time_context(profile=profile, browser_timezone=browser_timezone, now_utc=now_utc)
    location = context["location_label"] or "unknown location"
    local_datetime = f"{context['local_date']} {context['local_time']}"
    return (
        f"本地参考时间: {local_datetime} {context['timezone']} "
        f"(UTC{context['utc_offset']}, {context['timezone_abbr']}); 用户位置标签: {location}\n"
    )
