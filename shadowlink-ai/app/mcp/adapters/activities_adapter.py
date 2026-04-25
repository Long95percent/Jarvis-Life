"""Nearby activities adapter — queries OpenStreetMap Overpass API.

Returns points of interest (parks, cafes, restaurants, gyms, museums)
within a radius of the user's location. No API key required.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx
import structlog

logger = structlog.get_logger("mcp.activities")

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Category -> (OSM key, value) mapping. Keep small for demo (<= 5 categories).
_CATEGORY_QUERIES: dict[str, tuple[str, str]] = {
    "park":       ("leisure", "park"),
    "cafe":       ("amenity", "cafe"),
    "restaurant": ("amenity", "restaurant"),
    "gym":        ("leisure", "fitness_centre"),
    "museum":     ("tourism", "museum"),
}


@dataclass
class Activity:
    name: str
    category: str
    lat: float
    lng: float
    distance_m: int  # approximate distance from center
    address: str | None = None


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    from math import radians, sin, cos, asin, sqrt
    rlat1, rlat2 = radians(lat1), radians(lat2)
    dlat, dlng = radians(lat2 - lat1), radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(rlat1) * cos(rlat2) * sin(dlng / 2) ** 2
    return 6371000 * 2 * asin(sqrt(a))


async def fetch_nearby_activities(
    *,
    lat: float = 35.6762,
    lng: float = 139.6503,
    radius_m: int = 2000,
    categories: list[str] | None = None,
    limit: int = 20,
) -> list[Activity]:
    """Query Overpass for points of interest near (lat, lng)."""
    cats = categories or list(_CATEGORY_QUERIES.keys())
    # Build one combined Overpass query
    clauses: list[str] = []
    for cat in cats:
        if cat not in _CATEGORY_QUERIES:
            continue
        key, value = _CATEGORY_QUERIES[cat]
        clauses.append(f'node["{key}"="{value}"](around:{radius_m},{lat},{lng});')
    if not clauses:
        return []

    query = f"[out:json][timeout:10];({''.join(clauses)});out body;"

    results: list[Activity] = []
    try:
        # Overpass expects the query either as ?data= on GET or as
        # URL-encoded `data=...` on POST. Some mirrors reject unusual
        # Accept headers (-> 406), so we pin a permissive one.
        headers = {
            "Accept": "*/*",
            "User-Agent": "shadowlink-jarvis/0.1",
        }
        async with httpx.AsyncClient(timeout=12.0, headers=headers) as client:
            resp = await client.post(
                _OVERPASS_URL,
                content=f"data={query}",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            data = resp.json()
            for elem in data.get("elements", []):
                tags = elem.get("tags", {})
                name = tags.get("name") or tags.get("name:en") or tags.get("amenity") or ""
                if not name:
                    continue
                # Determine category by tag match
                cat_found = "other"
                for cat, (key, value) in _CATEGORY_QUERIES.items():
                    if tags.get(key) == value:
                        cat_found = cat
                        break
                p_lat = elem.get("lat")
                p_lng = elem.get("lon")
                if p_lat is None or p_lng is None:
                    continue
                addr_parts = [
                    tags.get("addr:housenumber"),
                    tags.get("addr:street"),
                    tags.get("addr:city"),
                ]
                address = ", ".join([a for a in addr_parts if a]) or None
                results.append(Activity(
                    name=name,
                    category=cat_found,
                    lat=p_lat,
                    lng=p_lng,
                    distance_m=int(_haversine_m(lat, lng, p_lat, p_lng)),
                    address=address,
                ))
    except Exception as exc:
        logger.warning("mcp.activities.fetch_failed", error=str(exc))
        return []

    results.sort(key=lambda a: a.distance_m)
    return results[:limit]
