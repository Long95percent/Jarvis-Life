from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class TimeWindow(BaseModel):
    start: datetime
    end: datetime
    label: str = ""


class CalendarEvent(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    title: str
    start: datetime
    end: datetime
    stress_weight: float = 1.0  # 0-3, higher = more stressful
    location: str | None = None
    notes: str | None = None
    source: str = "user_ui"
    source_agent: str | None = None
    created_reason: str | None = None
    status: str = "confirmed"  # pending_confirmation | confirmed | completed | postponed | conflict
    route_required: bool = False


class LifeContext(BaseModel):
    stress_level: float = 0.0       # 0-10
    schedule_density: float = 0.0   # 0-10 (meetings/tasks density)
    sleep_quality: float = 7.0      # 0-10
    mood_trend: str = "neutral"     # positive | neutral | negative | unknown
    free_windows: list[TimeWindow] = Field(default_factory=list)
    active_events: list[CalendarEvent] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    source_agent: str = "system"


class ProactiveMessage(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    agent_id: str
    agent_name: str
    content: str
    trigger: str
    priority: str = "normal"
    status: str = "pending"  # pending | delivered | read | dismissed
    created_at: datetime = Field(default_factory=datetime.utcnow)
    delivered_at: datetime | None = None
    read_at: datetime | None = None
    dismissed_at: datetime | None = None
    read: bool = False


class RoundtableDecision(BaseModel):
    """Single agent's decision from a Shadow Roundtable session."""
    agent_id: str
    action: str           # "send_message" | "update_context" | "schedule_followup" | "noop"
    payload: dict[str, Any] = Field(default_factory=dict)


class RoundtableResult(BaseModel):
    trigger: str
    decisions: list[RoundtableDecision]
    summary: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class UserProfile(BaseModel):
    preferences: dict[str, Any] = Field(default_factory=dict)
    interaction_count: int = 0
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    def record_preference(self, key: str, value: Any) -> None:
        self.preferences[key] = value
        self.last_updated = datetime.utcnow()
