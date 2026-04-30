"""Shared local-life discovery service for Jarvis agents.

The service keeps web discovery, filtering, ranking, and cache persistence
outside tool classes so private chat, roundtable, and proactive routines can
reuse the same behavior.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any, Awaitable, Callable

import structlog

from app.jarvis.persistence import list_local_life_items, upsert_local_life_items
from app.jarvis.user_settings import get_settings

logger = structlog.get_logger("jarvis.local_life_search")

WebSearchCallable = Callable[[str, int], Awaitable[list[dict[str, Any]]]]


@dataclass(frozen=True)
class LocalLifeSearchQuery:
    query: str
    category: str | None = None
    radius_m: int = 3000
    window_days: int = 14
    limit: int = 5
    min_date: str | None = None


@dataclass(frozen=True)
class LocalLifeSearchItem:
    source_url: str
    title: str
    item_type: str = "event"
    category: str = "general"
    venue: str | None = None
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    distance_m: int | None = None
    starts_at: str | None = None
    ends_at: str | None = None
    expires_at: str | None = None
    summary: str = ""
    fit_tags: list[str] = field(default_factory=list)
    confidence: float = 0.5
    date_confidence: str = "low"
    location_label: str = ""
    query: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LocalLifeSearchService:
    def __init__(self, web_search: WebSearchCallable | None = None) -> None:
        self._web_search_injected = web_search is not None
        self.web_search = web_search or _default_web_search

    async def search(self, query: LocalLifeSearchQuery, *, now: datetime | None = None) -> list[LocalLifeSearchItem]:
        local_now = now or datetime.now()
        min_day = _coerce_date(query.min_date, local_now.date())
        max_day = min_day + timedelta(days=max(1, query.window_days))
        min_expires_at = datetime.combine(min_day, time.min).isoformat()
        category = _normalize_category(query.category)

        cached = await list_local_life_items(
            min_expires_at=min_expires_at,
            category=category,
            query=query.query,
            limit=query.limit,
        )
        cached_items = _dedupe_and_rank(
            [_item_from_cache(item) for item in cached],
            query=query,
            min_day=min_day,
            max_day=max_day,
        )
        if cached_items:
            return cached_items[:query.limit]

        fetched: list[dict[str, Any]] = []
        search_text = query.query if self._web_search_injected else _build_search_text(query, category)
        try:
            fetched = await self.web_search(search_text, max(query.limit * 2, 8))
        except Exception as exc:
            logger.warning("local_life_search.web_failed", query=query.query, error=str(exc))
            return cached_items[:query.limit]

        normalized = [
            item
            for raw in fetched
            if (item := _normalize_web_result(raw, query=query, category=category, now=local_now, min_day=min_day, max_day=max_day)) is not None
        ]
        normalized = _dedupe_and_rank(normalized, query=query, min_day=min_day, max_day=max_day)[:query.limit]
        if normalized:
            await upsert_local_life_items([item.to_dict() for item in normalized], now_ts=local_now.timestamp())

        merged = {item.source_url: item for item in cached_items + normalized}
        ranked = _dedupe_and_rank(list(merged.values()), query=query, min_day=min_day, max_day=max_day)
        return ranked[:query.limit]


async def list_cached_local_life_opportunities(
    *,
    now: datetime | None = None,
    category: str | None = None,
    radius_m: int = 3000,
    window_days: int = 14,
    limit: int = 5,
) -> list[LocalLifeSearchItem]:
    """Read cached local-life items using the same proximity/time filters as search."""

    local_now = now or datetime.now()
    min_day = local_now.date()
    max_day = min_day + timedelta(days=max(1, window_days))
    min_expires_at = datetime.combine(min_day, time.min).isoformat()
    normalized_category = _normalize_category(category)
    rows = await list_local_life_items(
        min_expires_at=min_expires_at,
        category=normalized_category,
        limit=max(limit * 3, limit),
    )
    query = LocalLifeSearchQuery(
        query="cached_local_life_context",
        category=normalized_category,
        radius_m=radius_m,
        window_days=window_days,
        limit=limit,
        min_date=min_day.isoformat(),
    )
    return _dedupe_and_rank(
        [_item_from_cache(row) for row in rows],
        query=query,
        min_day=min_day,
        max_day=max_day,
    )[:limit]


async def _default_web_search(query: str, max_results: int) -> list[dict[str, Any]]:
    from app.tools.web_search import WebSearchTool

    tool = WebSearchTool()
    raw = await tool._search_ddg(query, max_results)
    return [
        {
            "title": item.get("title") or "",
            "source_url": item.get("url") or "",
            "summary": item.get("snippet") or "",
        }
        for item in raw
    ]


def _build_search_text(query: LocalLifeSearchQuery, category: str | None) -> str:
    loc = get_settings().profile.location
    parts = [query.query.strip()]
    if loc.label:
        parts.append(loc.label)
    parts.extend(["附近", "活动", "截止日期", "本周", "site:peatix.com OR site:timeout.com OR site:meetup.com"])
    if category:
        parts.append(category)
    return " ".join(part for part in parts if part)


def _normalize_web_result(
    raw: dict[str, Any],
    *,
    query: LocalLifeSearchQuery,
    category: str | None,
    now: datetime,
    min_day: date,
    max_day: date,
) -> LocalLifeSearchItem | None:
    source_url = str(raw.get("source_url") or raw.get("url") or raw.get("link") or "").strip()
    title = _clean_text(raw.get("title"))
    if not source_url or not title:
        return None

    summary = _clean_text(raw.get("summary") or raw.get("snippet") or raw.get("description"))
    starts_at = _parse_datetime_text(raw.get("starts_at") or raw.get("start") or raw.get("date") or f"{title} {summary}", now)
    ends_at = _parse_datetime_text(raw.get("ends_at") or raw.get("end"), now)
    expires_at = _parse_datetime_text(raw.get("expires_at") or raw.get("deadline"), now) or ends_at or starts_at
    if expires_at is None:
        return None
    if expires_at.date() < min_day or expires_at.date() > max_day:
        return None

    distance_m = _safe_int(raw.get("distance_m"))
    if distance_m is not None and distance_m > query.radius_m:
        return None

    fit_tags = _fit_tags(raw, category, f"{title} {summary}")
    confidence = _confidence(raw, starts_at=starts_at, expires_at=expires_at, distance_m=distance_m)
    date_confidence = "high" if raw.get("expires_at") or raw.get("starts_at") or raw.get("ends_at") else "medium"
    loc = get_settings().profile.location
    return LocalLifeSearchItem(
        source_url=source_url,
        title=title,
        item_type=str(raw.get("item_type") or raw.get("type") or "event"),
        category=str(raw.get("category") or category or "general"),
        venue=_clean_text(raw.get("venue")) or None,
        address=_clean_text(raw.get("address")) or None,
        lat=_safe_float(raw.get("lat")),
        lng=_safe_float(raw.get("lng")),
        distance_m=distance_m,
        starts_at=starts_at.isoformat() if starts_at else None,
        ends_at=ends_at.isoformat() if ends_at else None,
        expires_at=expires_at.isoformat(),
        summary=summary,
        fit_tags=fit_tags,
        confidence=confidence,
        date_confidence=date_confidence,
        location_label=loc.label or "",
        query=query.query,
    )


def _item_from_cache(row: dict[str, Any]) -> LocalLifeSearchItem:
    return LocalLifeSearchItem(
        source_url=str(row.get("source_url") or ""),
        title=str(row.get("title") or ""),
        item_type=str(row.get("item_type") or "event"),
        category=str(row.get("category") or "general"),
        venue=row.get("venue"),
        address=row.get("address"),
        lat=_safe_float(row.get("lat")),
        lng=_safe_float(row.get("lng")),
        distance_m=_safe_int(row.get("distance_m")),
        starts_at=row.get("starts_at"),
        ends_at=row.get("ends_at"),
        expires_at=row.get("expires_at"),
        summary=str(row.get("summary") or ""),
        fit_tags=list(row.get("fit_tags") or []),
        confidence=float(row.get("confidence") or 0.5),
        date_confidence=str(row.get("date_confidence") or "low"),
        location_label=str(row.get("location_label") or ""),
        query=str(row.get("query") or ""),
    )


def _dedupe_and_rank(
    items: list[LocalLifeSearchItem],
    *,
    query: LocalLifeSearchQuery,
    min_day: date,
    max_day: date,
) -> list[LocalLifeSearchItem]:
    deduped: dict[str, LocalLifeSearchItem] = {}
    for item in items:
        if not item.source_url or not item.title:
            continue
        expires = _parse_iso_datetime(item.expires_at)
        if expires is None or expires.date() < min_day or expires.date() > max_day:
            continue
        if item.distance_m is not None and item.distance_m > query.radius_m:
            continue
        existing = deduped.get(item.source_url)
        if existing is None or item.confidence > existing.confidence:
            deduped[item.source_url] = item

    def rank(item: LocalLifeSearchItem) -> tuple[float, int, str]:
        date_weight = {"high": 0, "medium": 1, "low": 2}.get(item.date_confidence, 2)
        distance = item.distance_m if item.distance_m is not None else 999999
        return (-item.confidence, date_weight, distance, item.expires_at or "")

    return sorted(deduped.values(), key=rank)


def _coerce_date(raw: str | None, fallback: date) -> date:
    if not raw:
        return fallback
    try:
        return datetime.fromisoformat(str(raw)).date()
    except ValueError:
        return fallback


def _parse_datetime_text(raw: Any, now: datetime) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    direct = _parse_iso_datetime(text)
    if direct is not None:
        return direct
    match = re.search(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})", text)
    if match:
        return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)), 23, 59)
    match = re.search(r"(\d{1,2})\s*月\s*(\d{1,2})\s*日", text)
    if match:
        month = int(match.group(1))
        day = int(match.group(2))
        year = now.year
        parsed = datetime(year, month, day, 23, 59)
        if parsed.date() < now.date() - timedelta(days=7):
            parsed = datetime(year + 1, month, day, 23, 59)
        return parsed
    if "今天" in text:
        return datetime.combine(now.date(), time(23, 59))
    if "明天" in text:
        return datetime.combine(now.date() + timedelta(days=1), time(23, 59))
    if "周末" in text or "本周末" in text:
        days_until_saturday = (5 - now.weekday()) % 7
        return datetime.combine(now.date() + timedelta(days=days_until_saturday), time(23, 59))
    return None


def _parse_iso_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        return parsed.replace(tzinfo=None)
    return parsed


def _normalize_category(raw: str | None) -> str | None:
    if not raw:
        return None
    lowered = raw.strip().lower()
    aliases = {
        "food": "food",
        "nutrition": "food",
        "meal": "food",
        "recovery": "recovery",
        "quiet": "recovery",
        "low_effort": "recovery",
        "activity": "activity",
        "event": "activity",
    }
    return aliases.get(lowered, lowered)


def _fit_tags(raw: dict[str, Any], category: str | None, text: str) -> list[str]:
    tags = raw.get("fit_tags") or []
    if not isinstance(tags, list):
        tags = []
    inferred = set(str(tag) for tag in tags)
    if category:
        inferred.add(category)
    lowered = text.lower()
    keyword_tags = {
        "low_effort": ["轻松", "安静", "低刺激", "low", "quiet", "relax"],
        "food": ["市集", "轻食", "餐", "咖啡", "food", "market", "cafe"],
        "social": ["社交", "meetup", "交流"],
        "movement": ["散步", "运动", "瑜伽", "walk", "yoga"],
    }
    for tag, keywords in keyword_tags.items():
        if any(keyword in lowered for keyword in keywords):
            inferred.add(tag)
    return sorted(inferred)


def _confidence(raw: dict[str, Any], *, starts_at: datetime | None, expires_at: datetime | None, distance_m: int | None) -> float:
    score = float(raw.get("confidence") or 0.45)
    if starts_at or expires_at:
        score += 0.25
    if raw.get("venue") or raw.get("address"):
        score += 0.1
    if distance_m is not None:
        score += 0.1
    return min(score, 0.95)


def _clean_text(raw: Any) -> str:
    text = re.sub(r"<[^>]+>", "", str(raw or ""))
    return " ".join(text.split())


def _safe_int(raw: Any) -> int | None:
    if raw is None or raw == "":
        return None
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return None


def _safe_float(raw: Any) -> float | None:
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None
