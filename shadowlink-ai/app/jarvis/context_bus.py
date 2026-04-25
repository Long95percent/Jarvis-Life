from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import structlog

from app.jarvis.models import LifeContext

logger = structlog.get_logger("jarvis.context_bus")

_MAX_QUEUE_SIZE = 50


class LifeContextBus:
    """In-memory pub/sub bus for life context state.

    Singleton per service instance. Agents read current state via
    get_context() and write via update_fields(). Subscribers receive
    a dict of changed fields + source_agent on every update.
    """

    def __init__(self) -> None:
        self._context = LifeContext()
        self._subscribers: dict[str, asyncio.Queue[dict[str, Any]]] = {}
        self._lock = asyncio.Lock()

    async def get_context(self) -> LifeContext:
        async with self._lock:
            return self._context.model_copy()

    async def update_fields(self, fields: dict[str, Any], source: str = "system") -> None:
        async with self._lock:
            updated = self._context.model_copy(
                update={**fields, "source_agent": source, "last_updated": datetime.utcnow()}
            )
            self._context = updated
            payload = {**fields, "source_agent": source}
            # Snapshot the scalar state we want to persist while still under lock,
            # so the fire-and-forget task below sees consistent values.
            snapshot_fields = {
                "stress_level": updated.stress_level,
                "schedule_density": updated.schedule_density,
                "sleep_quality": updated.sleep_quality,
                "mood_trend": updated.mood_trend,
            }

        for agent_id, queue in self._subscribers.items():
            if queue.full():
                logger.warning("jarvis.bus.queue_full", agent_id=agent_id)
                continue
            await queue.put(payload)

        # Fire-and-forget: persist this state to SQLite. Failures are
        # logged inside snapshot_context — we never want persistence to
        # break bus updates.
        try:
            from app.jarvis.persistence import snapshot_context

            asyncio.create_task(
                snapshot_context(
                    stress_level=snapshot_fields["stress_level"],
                    schedule_density=snapshot_fields["schedule_density"],
                    sleep_quality=snapshot_fields["sleep_quality"],
                    mood_trend=snapshot_fields["mood_trend"],
                    source_agent=source,
                )
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("jarvis.bus.persistence_failed", error=str(exc))

        logger.info("jarvis.bus.updated", source=source, fields=list(fields.keys()))

    async def subscribe(self, agent_id: str) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=_MAX_QUEUE_SIZE)
        self._subscribers[agent_id] = queue
        return queue

    async def unsubscribe(self, agent_id: str) -> None:
        self._subscribers.pop(agent_id, None)


# Module-level singleton — replaced in tests via dependency injection
_default_bus: LifeContextBus | None = None


def get_life_context_bus() -> LifeContextBus:
    global _default_bus
    if _default_bus is None:
        _default_bus = LifeContextBus()
    return _default_bus
