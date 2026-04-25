"""Proactive Trigger Engine — monitors LifeContextBus and fires agent actions.

Runs as a background asyncio task. Every POLL_INTERVAL seconds it evaluates
trigger rules against the current life context. When a rule fires, it convenes
a ShadowRoundtable with relevant agents and executes resulting decisions.

Interrupt budget: each agent has a daily max number of proactive interrupts.
This prevents the system from becoming annoying.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import TYPE_CHECKING, Callable

import structlog

from app.jarvis.agents import JARVIS_AGENTS
from app.jarvis.models import LifeContext, ProactiveMessage

if TYPE_CHECKING:
    from app.jarvis.context_bus import LifeContextBus
    from app.jarvis.shadow_roundtable import ShadowRoundtable

logger = structlog.get_logger("jarvis.proactive_engine")

POLL_INTERVAL = 300  # seconds (5 minutes)


@dataclass
class TriggerRule:
    name: str
    evaluate: Callable[[LifeContext], bool]
    participating_agents: list[str]
    cooldown_minutes: int = 60
    _last_fired: datetime | None = field(default=None, repr=False)

    def is_on_cooldown(self) -> bool:
        if self._last_fired is None:
            return False
        elapsed = (datetime.utcnow() - self._last_fired).total_seconds() / 60
        return elapsed < self.cooldown_minutes

    def mark_fired(self) -> None:
        self._last_fired = datetime.utcnow()


class ProactiveTriggerEngine:
    """Evaluates trigger rules and convenes Shadow Roundtables."""

    def __init__(self, roundtable: ShadowRoundtable, context_bus: LifeContextBus) -> None:
        self.roundtable = roundtable
        self.context_bus = context_bus
        self._interrupt_counts: dict[str, dict[date, int]] = defaultdict(lambda: defaultdict(int))
        self._pending_messages: list[ProactiveMessage] = []
        self._running = False
        self.rules = self._build_rules()

    def _build_rules(self) -> list[TriggerRule]:
        return [
            TriggerRule(
                name="stress_spike",
                evaluate=lambda ctx: ctx.stress_level >= 8.0,
                participating_agents=["alfred", "nora", "mira"],
                cooldown_minutes=120,
            ),
            TriggerRule(
                name="schedule_overload",
                evaluate=lambda ctx: ctx.schedule_density >= 8.0,
                participating_agents=["alfred", "maxwell", "nora"],
                cooldown_minutes=240,
            ),
            TriggerRule(
                name="sleep_poor",
                evaluate=lambda ctx: ctx.sleep_quality <= 4.0,
                participating_agents=["nora", "mira", "leo"],
                cooldown_minutes=480,
            ),
            TriggerRule(
                name="free_window_detected",
                evaluate=lambda ctx: len(ctx.free_windows) > 0 and ctx.stress_level < 5.0,
                participating_agents=["leo"],
                cooldown_minutes=360,
            ),
            TriggerRule(
                name="mood_declining",
                evaluate=lambda ctx: ctx.mood_trend == "negative",
                participating_agents=["mira", "alfred"],
                cooldown_minutes=180,
            ),
        ]

    async def check_triggers(self) -> None:
        from app.jarvis.user_settings import get_enabled_agents, get_settings

        ctx = await self.context_bus.get_context()
        today = date.today()
        agent_cfg = get_settings().agents

        for rule in self.rules:
            if not rule.evaluate(ctx):
                continue
            if rule.is_on_cooldown():
                continue

            # Respect user's agent enable/disable toggles from settings.
            # Agents the user has turned off are excluded from this rule's roster.
            enabled_participants = get_enabled_agents(list(rule.participating_agents))
            if not enabled_participants:
                logger.info(
                    "jarvis.engine.all_participants_disabled",
                    trigger=rule.name,
                    configured=list(rule.participating_agents),
                )
                continue

            rule.mark_fired()
            result = await self.roundtable.convene(
                trigger=rule.name,
                context=ctx,
                participating_agents=enabled_participants,
            )

            for decision in result.decisions:
                if decision.action != "send_message":
                    continue
                agent_def = JARVIS_AGENTS.get(decision.agent_id, {})
                # Interrupt budget: prefer user-configured value over agent default
                user_budget = agent_cfg.get(decision.agent_id)
                budget = user_budget.interrupt_budget if user_budget else agent_def.get("interrupt_budget", 0)
                used = self._interrupt_counts[decision.agent_id][today]
                if used >= budget:
                    logger.info(
                        "jarvis.engine.budget_exhausted",
                        agent_id=decision.agent_id,
                        used=used,
                        budget=budget,
                    )
                    continue

                self._interrupt_counts[decision.agent_id][today] += 1
                msg = ProactiveMessage(
                    agent_id=decision.agent_id,
                    agent_name=agent_def.get("name", decision.agent_id),
                    content=decision.payload.get("content", ""),
                    trigger=rule.name,
                )
                self._pending_messages.append(msg)
                logger.info("jarvis.engine.message_queued", agent_id=decision.agent_id, trigger=rule.name)

    def pop_pending_messages(self) -> list[ProactiveMessage]:
        msgs, self._pending_messages = self._pending_messages, []
        return msgs

    async def start(self) -> None:
        self._running = True
        logger.info("jarvis.engine.started", poll_interval=POLL_INTERVAL)
        while self._running:
            try:
                await self.check_triggers()
            except Exception as exc:
                logger.error("jarvis.engine.error", error=str(exc))
            await asyncio.sleep(POLL_INTERVAL)

    def stop(self) -> None:
        self._running = False
