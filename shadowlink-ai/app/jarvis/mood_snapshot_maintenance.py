"""Automatic daily mood snapshot maintenance and backfill."""

from __future__ import annotations

from datetime import date as Date, datetime, timedelta
from typing import Any


async def ensure_mood_snapshots(
    *,
    today: str | None = None,
    backfill_days: int = 3,
    include_today: bool = True,
) -> dict[str, Any]:
    """Create missing recent mood snapshots without requiring API reads.

    The function is intentionally idempotent: existing snapshots are not
    regenerated unless the target date is today, because today's evidence can
    still be accumulating during active use.
    """
    from app.jarvis.mood_snapshot import aggregate_mood_snapshot
    from app.jarvis.persistence import list_mood_snapshots
    from app.jarvis.user_settings import is_psychological_tracking_enabled

    if not is_psychological_tracking_enabled():
        return {"skipped": True, "reason": "psychological_tracking_disabled", "created": [], "checked": []}

    target_today = Date.fromisoformat((today or datetime.utcnow().date().isoformat())[:10])
    start_day = target_today - timedelta(days=max(0, backfill_days - 1))
    existing = await list_mood_snapshots(start=start_day.isoformat(), end=target_today.isoformat(), limit=max(10, backfill_days + 2))
    existing_dates = {str(item.get("date"))[:10] for item in existing}
    checked: list[str] = []
    created: list[dict[str, Any]] = []

    for offset in range(backfill_days):
        day = (start_day + timedelta(days=offset)).isoformat()
        if day == target_today.isoformat() and not include_today:
            continue
        checked.append(day)
        if day in existing_dates and day != target_today.isoformat():
            continue
        snapshot = await aggregate_mood_snapshot(day)
        if snapshot is not None:
            created.append(snapshot)

    return {"skipped": False, "today": target_today.isoformat(), "checked": checked, "created": created}

