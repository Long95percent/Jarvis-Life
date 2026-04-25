# shadowlink-ai/app/mcp/adapters/weather_adapter.py
"""Open-Meteo weather adapter — no API key required."""

from __future__ import annotations

import httpx
import structlog

logger = structlog.get_logger("mcp.weather")


async def get_current_weather(latitude: float = 35.6762, longitude: float = 139.6503) -> dict:
    """Fetch current weather. Defaults to Tokyo."""
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={latitude}&longitude={longitude}"
        f"&current=temperature_2m,weathercode,windspeed_10m,precipitation"
    )
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            current = data.get("current", {})
            return {
                "temperature_c": current.get("temperature_2m"),
                "weather_code": current.get("weathercode"),
                "wind_kmh": current.get("windspeed_10m"),
                "precipitation_mm": current.get("precipitation"),
                "is_good_weather": current.get("weathercode", 99) <= 3,
            }
    except Exception as exc:
        logger.warning("mcp.weather.fetch_failed", error=str(exc))
        return {"error": str(exc), "is_good_weather": False}
