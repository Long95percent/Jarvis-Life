from __future__ import annotations

from datetime import datetime, timezone

import pytest


def test_build_time_context_uses_profile_timezone():
    from app.jarvis.time_context import build_time_context
    from app.jarvis.user_settings import Location, UserProfile

    profile = UserProfile(location=Location(label="New York", timezone="America/New_York"))
    now_utc = datetime(2026, 1, 15, 15, 30, tzinfo=timezone.utc)

    context = build_time_context(profile=profile, now_utc=now_utc)

    assert context["timezone"] == "America/New_York"
    assert context["location_label"] == "New York"
    assert context["local_date"] == "2026-01-15"
    assert context["local_time"] == "10:30:00"
    assert context["utc_offset"] == "-05:00"


def test_build_time_context_falls_back_to_browser_timezone():
    from app.jarvis.time_context import build_time_context
    from app.jarvis.user_settings import Location, UserProfile

    profile = UserProfile(location=Location(label="", timezone=""))
    now_utc = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)

    context = build_time_context(profile=profile, browser_timezone="Asia/Tokyo", now_utc=now_utc)

    assert context["timezone"] == "Asia/Tokyo"
    assert context["local_date"] == "2026-04-30"
    assert context["local_time"] == "21:00:00"
    assert context["utc_offset"] == "+09:00"


def test_build_time_context_prefers_browser_timezone_for_default_profile():
    from app.jarvis.time_context import build_time_context
    from app.jarvis.user_settings import UserProfile

    profile = UserProfile()
    now_utc = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)

    context = build_time_context(profile=profile, browser_timezone="America/Los_Angeles", now_utc=now_utc)

    assert context["timezone"] == "America/Los_Angeles"
    assert context["local_date"] == "2026-04-30"
    assert context["local_time"] == "05:00:00"
    assert context["utc_offset"] == "-07:00"


def test_build_time_context_uses_manual_profile_timezone_over_browser_timezone():
    from app.jarvis.time_context import build_time_context
    from app.jarvis.user_settings import Location, UserProfile

    profile = UserProfile(location=Location(label="Shanghai", timezone="Asia/Shanghai", timezone_source="manual"))
    now_utc = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)

    context = build_time_context(profile=profile, browser_timezone="America/Los_Angeles", now_utc=now_utc)

    assert context["timezone"] == "Asia/Shanghai"
    assert context["local_time"] == "20:00:00"
    assert context["utc_offset"] == "+08:00"


def test_suggest_location_from_browser_coordinates_prefers_reverse_geocode_label():
    from app.jarvis.time_context import suggest_location_from_browser_coordinates

    suggestion = suggest_location_from_browser_coordinates(
        lat=32.0603,
        lng=118.7969,
        browser_timezone="Asia/Shanghai",
        current_label="Suzhou",
        reverse_geocode=lambda lat, lng: "Nanjing",
    )

    assert suggestion["label"] == "Nanjing"
    assert suggestion["timezone"] == "Asia/Shanghai"
    assert suggestion["timezone_source"] == "browser"
    assert suggestion["label_source"] == "reverse_geocode"


def test_suggest_location_from_browser_coordinates_clears_stale_label_when_unknown():
    from app.jarvis.time_context import suggest_location_from_browser_coordinates

    suggestion = suggest_location_from_browser_coordinates(
        lat=1.23,
        lng=4.56,
        browser_timezone="Asia/Shanghai",
        current_label="Suzhou",
    )

    assert suggestion["label"] == "Current Location (1.2300, 4.5600)"
    assert suggestion["timezone"] == "Asia/Shanghai"
    assert suggestion["label_source"] == "browser"


def test_suggest_location_from_browser_coordinates_reports_label_error():
    from app.jarvis.time_context import suggest_location_from_browser_coordinates

    suggestion = suggest_location_from_browser_coordinates(
        lat=32.0603,
        lng=118.7969,
        browser_timezone="Asia/Shanghai",
        current_label="Current Location",
        label_error="reverse geocode unavailable",
    )

    assert suggestion["label"].startswith("Current Location")
    assert suggestion["label_error"] == "reverse geocode unavailable"


def test_suggest_location_from_browser_coordinates_is_global_not_china_specific():
    from app.jarvis.time_context import suggest_location_from_browser_coordinates

    suggestion = suggest_location_from_browser_coordinates(
        lat=48.8566,
        lng=2.3522,
        browser_timezone="Europe/Paris",
        current_label="Tokyo",
    )

    assert suggestion["label"] == "Current Location (48.8566, 2.3522)"
    assert suggestion["timezone"] == "Europe/Paris"
    assert suggestion["timezone_source"] == "browser"
    assert suggestion["label_source"] == "browser"


def test_suggest_location_from_city_name_uses_geocode_result():
    from app.jarvis.time_context import suggest_location_from_city_name

    suggestion = suggest_location_from_city_name(
        city_name="Nanjing",
        browser_timezone="Asia/Shanghai",
        geocode=lambda city: {"label": "Nanjing", "lat": 32.0603, "lng": 118.7969},
    )

    assert suggestion["label"] == "Nanjing"
    assert suggestion["lat"] == 32.0603
    assert suggestion["lng"] == 118.7969
    assert suggestion["timezone"] == "Asia/Shanghai"
    assert suggestion["label_source"] == "geocode"


def test_suggest_location_from_city_name_marks_browser_timezone_as_manual_city_choice():
    from app.jarvis.time_context import build_time_context, suggest_location_from_city_name
    from app.jarvis.user_settings import Location, UserProfile

    suggestion = suggest_location_from_city_name(
        city_name="Nanjing",
        browser_timezone="Asia/Shanghai",
        geocode=lambda city: {"label": "Nanjing", "lat": 32.0603, "lng": 118.7969},
    )
    profile = UserProfile(location=Location(**suggestion))
    now_utc = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)

    context = build_time_context(profile=profile, browser_timezone="Europe/Paris", now_utc=now_utc)

    assert suggestion["timezone"] == "Asia/Shanghai"
    assert suggestion["timezone_source"] == "manual"
    assert context["timezone"] == "Asia/Shanghai"
    assert context["local_time"] == "20:00:00"


def test_suggest_location_from_city_name_rejects_unresolved_city():
    from app.jarvis.time_context import suggest_location_from_city_name

    with pytest.raises(ValueError, match="Unable to resolve city"):
        suggest_location_from_city_name(
            city_name="Not A Real City",
            browser_timezone="Europe/Paris",
            geocode=lambda city: None,
        )


def test_build_time_context_falls_back_when_saved_auto_timezone_is_invalid():
    from app.jarvis.time_context import build_time_context
    from app.jarvis.user_settings import Location, UserProfile

    profile = UserProfile(location=Location(label="Legacy", timezone="Not/AZone", timezone_source="auto"))
    now_utc = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)

    context = build_time_context(profile=profile, browser_timezone="Europe/Paris", now_utc=now_utc)

    assert context["timezone"] == "Europe/Paris"
    assert context["local_time"] == "14:00:00"


def test_build_time_context_rejects_invalid_manual_profile_timezone():
    from app.jarvis.time_context import build_time_context
    from app.jarvis.user_settings import Location, UserProfile

    profile = UserProfile(location=Location(label="Legacy", timezone="Not/AZone", timezone_source="manual"))

    with pytest.raises(ValueError, match="Invalid timezone"):
        build_time_context(profile=profile, browser_timezone="Europe/Paris")


def test_build_time_context_rejects_invalid_timezone():
    from app.jarvis.time_context import resolve_timezone

    with pytest.raises(ValueError, match="Invalid timezone"):
        resolve_timezone("Mars/Olympus")


def test_build_time_prompt_line_contains_stable_time_details():
    from app.jarvis.time_context import build_time_prompt_line
    from app.jarvis.user_settings import Location, UserProfile

    profile = UserProfile(location=Location(label="Shanghai", timezone="Asia/Shanghai"))
    now_utc = datetime(2026, 4, 30, 0, 5, 6, tzinfo=timezone.utc)

    line = build_time_prompt_line(profile=profile, now_utc=now_utc)

    assert "本地参考时间: 2026-04-30 08:05:06" in line
    assert "Asia/Shanghai" in line
    assert "+08:00" in line
    assert "用户位置标签: Shanghai" in line
    assert "鏈" not in line
    assert "鐢" not in line
