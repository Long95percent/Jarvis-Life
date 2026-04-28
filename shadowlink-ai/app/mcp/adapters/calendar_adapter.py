# shadowlink-ai/app/mcp/adapters/calendar_adapter.py
"""Simple in-process calendar — accepts ICS content or manual event injection.

For demo: events can be added via the JARVIS API directly.
For production: swap _events with Google Calendar API calls.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from app.jarvis.models import CalendarEvent

_events: list[CalendarEvent] = []


def _event_from_row(row: dict[str, Any]) -> CalendarEvent:
    return CalendarEvent(
        id=str(row["id"]),
        title=str(row["title"]),
        start=datetime.fromisoformat(str(row["start"])),
        end=datetime.fromisoformat(str(row["end"])),
        stress_weight=float(row.get("stress_weight") or 1.0),
        location=row.get("location"),
        notes=row.get("notes"),
        source=str(row.get("source") or "user_ui"),
        source_agent=row.get("source_agent"),
        created_reason=row.get("created_reason"),
        status=str(row.get("status") or "confirmed"),
        route_required=bool(row.get("route_required")),
    )


def _persist_event(event: CalendarEvent) -> None:
    from app.jarvis.persistence import save_calendar_event_sync

    save_calendar_event_sync(event)



def add_event(
    title: str,
    start: datetime,
    end: datetime,
    stress_weight: float = 1.0,
    *,
    location: str | None = None,
    notes: str | None = None,
    source: str = "user_ui",
    source_agent: str | None = None,
    created_reason: str | None = None,
    status: str = "confirmed",
    route_required: bool = False,
) -> CalendarEvent:
    event = CalendarEvent(
        title=title,
        start=start,
        end=end,
        stress_weight=stress_weight,
        location=location,
        notes=notes,
        source=source,
        source_agent=source_agent,
        created_reason=created_reason,
        status=status,
        route_required=route_required,
    )
    _events[:] = [existing for existing in _events if existing.id != event.id]
    _events.append(event)
    _persist_event(event)
    return event


def delete_event(event_id: str) -> bool:
    """Remove an event by id. Returns True if deleted, False if not found."""
    global _events
    before = len(_events)
    _events = [e for e in _events if e.id != event_id]
    from app.jarvis.persistence import delete_calendar_event_sync

    persisted = delete_calendar_event_sync(event_id)
    return len(_events) < before or persisted


def update_event(
    event_id: str,
    *,
    title: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    stress_weight: float | None = None,
    location: str | None = None,
    notes: str | None = None,
    source: str | None = None,
    source_agent: str | None = None,
    created_reason: str | None = None,
    status: str | None = None,
    route_required: bool | None = None,
) -> CalendarEvent | None:
    """Mutate an existing event in place. Returns the updated event or None."""
    for e in _events:
        if e.id == event_id:
            if title is not None:
                e.title = title
            if start is not None:
                e.start = start
            if end is not None:
                e.end = end
            if stress_weight is not None:
                e.stress_weight = stress_weight
            if location is not None:
                e.location = location
            if notes is not None:
                e.notes = notes
            if source is not None:
                e.source = source
            if source_agent is not None:
                e.source_agent = source_agent
            if created_reason is not None:
                e.created_reason = created_reason
            if status is not None:
                e.status = status
            if route_required is not None:
                e.route_required = route_required
            _persist_event(e)
            return e
    from app.jarvis.persistence import update_calendar_event_sync
    patch = {
        "title": title,
        "start": start,
        "end": end,
        "stress_weight": stress_weight,
        "location": location,
        "notes": notes,
        "source": source,
        "source_agent": source_agent,
        "created_reason": created_reason,
        "status": status,
        "route_required": route_required,
    }
    row = update_calendar_event_sync(event_id, patch)
    return _event_from_row(row) if row else None


def get_event(event_id: str) -> CalendarEvent | None:
    for e in _events:
        if e.id == event_id:
            return e
    from app.jarvis.persistence import get_calendar_event_sync

    row = get_calendar_event_sync(event_id)
    if row is None:
        return None
    event = _event_from_row(row)
    _events.append(event)
    return event


def get_upcoming_events(hours_ahead: int = 24) -> list[CalendarEvent]:
    now = datetime.utcnow()
    cutoff_dt = now + timedelta(hours=hours_ahead)
    from app.jarvis.persistence import list_upcoming_calendar_events_sync

    rows = list_upcoming_calendar_events_sync(now.isoformat(), cutoff_dt.isoformat())
    return [_event_from_row(row) for row in rows]


def get_events_between(start: datetime, end: datetime) -> list[CalendarEvent]:
    """Return events overlapping a time window, sorted by start time."""
    from app.jarvis.persistence import list_calendar_events_between_sync

    rows = list_calendar_events_between_sync(start.isoformat(), end.isoformat())
    return [_event_from_row(row) for row in rows]


def compute_schedule_density(hours_ahead: int = 24) -> float:
    """Returns 0-10 based on total meeting hours in the next window."""
    events = get_upcoming_events(hours_ahead)
    total_minutes = sum(
        (e.end - e.start).total_seconds() / 60 * e.stress_weight
        for e in events
    )
    return min(10.0, total_minutes / (hours_ahead * 60 / 10))
