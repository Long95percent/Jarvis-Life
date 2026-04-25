"""Unified local-life aggregator.

Pulls weather + calendar + news + nearby activities, attaches
freshness metadata, and writes normalized signals into LifeContextBus
so agents can see them at prompt time.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import structlog

from app.jarvis.context_bus import get_life_context_bus
from app.jarvis.user_settings import get_settings as get_user_settings

logger = structlog.get_logger("jarvis.local_life")


@dataclass
class LocalLifeSnapshot:
    weather: dict[str, Any] = field(default_factory=dict)
    activities: list[dict[str, Any]] = field(default_factory=list)
    news: list[dict[str, Any]] = field(default_factory=list)
    upcoming_events: list[dict[str, Any]] = field(default_factory=list)
    schedule_density: float = 0.0
    fetched_at: float = field(default_factory=time.time)
    sources: dict[str, str] = field(default_factory=dict)


# ── In-memory cache (short TTL). Demo-friendly. ─────────
_cache: LocalLifeSnapshot | None = None
_cache_ttl_seconds = 600  # 10 minutes


def _cache_valid() -> bool:
    return _cache is not None and (time.time() - _cache.fetched_at) < _cache_ttl_seconds


async def refresh_local_life(force: bool = False) -> LocalLifeSnapshot:
    """Fetch all sources and push a snapshot into the LifeContextBus."""
    global _cache
    if not force and _cache_valid():
        return _cache  # type: ignore[return-value]

    snapshot = LocalLifeSnapshot()
    profile = get_user_settings().profile
    loc = profile.location

    # ── Weather ─────────────────────────────
    try:
        from app.mcp.adapters import weather_adapter
        weather = await weather_adapter.get_current_weather(
            latitude=loc.lat, longitude=loc.lng
        )
        snapshot.weather = weather
        snapshot.sources["weather"] = "open-meteo"
    except Exception as exc:
        logger.warning("local_life.weather_failed", error=str(exc))

    # ── Calendar (internal) ─────────────────
    events_for_ctx: list = []
    try:
        from app.mcp.adapters.calendar_adapter import (
            compute_schedule_density,
            get_upcoming_events,
        )
        upcoming = get_upcoming_events(hours_ahead=24)
        events_for_ctx = upcoming  # list[CalendarEvent]
        snapshot.upcoming_events = [
            {
                "id": e.id,
                "title": e.title,
                "start": e.start.isoformat(),
                "end": e.end.isoformat(),
                "stress_weight": e.stress_weight,
            }
            for e in upcoming
        ]
        snapshot.schedule_density = compute_schedule_density()
        snapshot.sources["calendar"] = "in-memory"
    except Exception as exc:
        logger.warning("local_life.calendar_failed", error=str(exc))

    # ── Activities ──────────────────────────
    try:
        from app.mcp.adapters import activities_adapter
        acts = await activities_adapter.fetch_nearby_activities(
            lat=loc.lat, lng=loc.lng, limit=10
        )
        snapshot.activities = [
            {
                "name": a.name,
                "category": a.category,
                "distance_m": a.distance_m,
                "lat": a.lat,
                "lng": a.lng,
                "address": a.address,
            }
            for a in acts
        ]
        snapshot.sources["activities"] = "overpass"
    except Exception as exc:
        logger.warning("local_life.activities_failed", error=str(exc))

    # ── News ────────────────────────────────
    try:
        from app.mcp.adapters import news_adapter
        items = await news_adapter.fetch_news(limit=8)
        snapshot.news = [
            {
                "title": i.title,
                "link": i.link,
                "source": i.source,
                "published": i.published,
                "summary": i.summary,
            }
            for i in items
        ]
        snapshot.sources["news"] = "rss"
    except Exception as exc:
        logger.warning("local_life.news_failed", error=str(exc))

    # ── Push back into LifeContextBus so agents can use it ─────
    # We don't (yet) change LifeContext shape; stash into active_events
    # by reusing calendar events we just fetched + update schedule_density.
    bus = get_life_context_bus()
    update_payload: dict[str, Any] = {"schedule_density": snapshot.schedule_density}
    if events_for_ctx:
        update_payload["active_events"] = events_for_ctx
    try:
        await bus.update_fields(update_payload, source="local_life_aggregator")
    except Exception as exc:
        logger.warning("local_life.bus_update_failed", error=str(exc))

    _cache = snapshot
    logger.info(
        "local_life.refresh_complete",
        sources=list(snapshot.sources.keys()),
        weather_ok="weather" in snapshot.sources,
        news_count=len(snapshot.news),
        activities_count=len(snapshot.activities),
    )
    return snapshot


def get_cached_snapshot() -> LocalLifeSnapshot | None:
    return _cache if _cache_valid() else None
