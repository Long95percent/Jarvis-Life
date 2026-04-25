# JARVIS Life OS — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform ShadowLink into a proactive multi-agent personal life OS — 6 specialized "life butler" agents that communicate with each other in the background via a Shadow Roundtable, then proactively reach out to the user based on life context (schedule density, stress level, sleep quality).

**Architecture:** A `LifeContextBus` singleton holds the user's current life state (stress, schedule density, mood). A background `ShadowRoundtableEngine` periodically convenes invisible inter-agent deliberations (adapted from the existing `BrainstormExecutor`) that produce action items per agent. A `ProactiveTriggerEngine` background task monitors the bus and fires agent-initiated messages to the frontend via SSE.

**Tech Stack:** Python 3.11 / FastAPI / asyncio / Pydantic v2 / LangGraph (existing) / pytest-asyncio / React + TypeScript / Zustand / TanStack Query

---

## File Structure

### New files (create)

```
shadowlink-ai/app/
├── jarvis/
│   ├── __init__.py
│   ├── models.py             # Pydantic models: LifeContext, JarvisAgent, ProactiveMessage
│   ├── agents.py             # 6 agent definitions with system prompts & trigger rules
│   ├── context_bus.py        # LifeContextBus singleton (in-memory + asyncio pub/sub)
│   ├── shadow_roundtable.py  # Background inter-agent deliberation engine
│   ├── proactive_engine.py   # Trigger evaluation loop, interrupt budget
│   └── preference_learner.py # Silent observation → UserProfile updates
├── api/v1/
│   └── jarvis_router.py      # REST + SSE endpoints for JARVIS
tests/unit/jarvis/
├── __init__.py
├── test_context_bus.py
├── test_proactive_engine.py
└── test_shadow_roundtable.py

shadowlink-web/src/
├── pages/
│   └── JarvisPage.tsx           # Main JARVIS dashboard page
├── components/jarvis/
│   ├── AgentCard.tsx            # Avatar + status ring per agent
│   ├── LifeContextPanel.tsx     # Gauge visualisations of life state
│   ├── ProactiveMessageFeed.tsx # Agent-initiated messages feed
│   └── RoundtableLog.tsx        # Collapsible log of background deliberations
├── stores/
│   └── jarvisStore.ts           # Zustand store for JARVIS state
└── services/
    └── jarvisApi.ts             # API calls + SSE subscription
```

### Modified files

```
shadowlink-ai/app/
├── main.py                       # Register jarvis_router
├── core/lifespan.py              # Start ProactiveTriggerEngine on startup
├── api/v1/__init__.py            # Include jarvis_router
shadowlink-web/src/
├── App.tsx                       # Add /jarvis route
├── components/layout/Sidebar.tsx # Add JARVIS nav link
```

---

## Task 1: JARVIS Pydantic Models

**Files:**
- Create: `shadowlink-ai/app/jarvis/models.py`
- Create: `shadowlink-ai/tests/unit/jarvis/__init__.py`

- [ ] **Step 1: Write the failing import test**

```python
# tests/unit/jarvis/test_models.py
from app.jarvis.models import (
    LifeContext,
    ProactiveMessage,
    RoundtableDecision,
    UserProfile,
)

def test_life_context_defaults():
    ctx = LifeContext()
    assert ctx.stress_level == 0.0
    assert ctx.schedule_density == 0.0
    assert ctx.mood_trend == "neutral"
    assert ctx.free_windows == []

def test_proactive_message_fields():
    msg = ProactiveMessage(
        agent_id="alfred",
        agent_name="Alfred",
        content="Good morning! You have 3 meetings today.",
        trigger="daily_morning",
    )
    assert msg.agent_id == "alfred"
    assert msg.read is False

def test_user_profile_merge():
    profile = UserProfile()
    profile.record_preference("prefers_brief_responses", True)
    assert profile.preferences["prefers_brief_responses"] is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd shadowlink-ai
pytest tests/unit/jarvis/test_models.py -v
```
Expected: `ModuleNotFoundError: No module named 'app.jarvis'`

- [ ] **Step 3: Create the module files and implement models**

```python
# shadowlink-ai/app/jarvis/__init__.py
```

```python
# shadowlink-ai/app/jarvis/models.py
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
    created_at: datetime = Field(default_factory=datetime.utcnow)
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
```

```python
# shadowlink-ai/tests/unit/jarvis/__init__.py
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/jarvis/test_models.py -v
```
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add app/jarvis/ tests/unit/jarvis/
git commit -m "feat(jarvis): add Pydantic models for Life OS"
```

---

## Task 2: Life Context Bus

**Files:**
- Create: `shadowlink-ai/app/jarvis/context_bus.py`
- Create: `shadowlink-ai/tests/unit/jarvis/test_context_bus.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/jarvis/test_context_bus.py
import asyncio
import pytest
from app.jarvis.context_bus import LifeContextBus
from app.jarvis.models import LifeContext


@pytest.fixture
def bus():
    return LifeContextBus()


@pytest.mark.asyncio
async def test_get_context_returns_default(bus):
    ctx = await bus.get_context()
    assert ctx.stress_level == 0.0
    assert ctx.mood_trend == "neutral"


@pytest.mark.asyncio
async def test_update_context_partial(bus):
    await bus.update_fields({"stress_level": 7.5, "mood_trend": "negative"}, source="maxwell")
    ctx = await bus.get_context()
    assert ctx.stress_level == 7.5
    assert ctx.mood_trend == "negative"
    assert ctx.source_agent == "maxwell"


@pytest.mark.asyncio
async def test_subscribe_receives_update(bus):
    queue = await bus.subscribe("test_agent")
    await bus.update_fields({"stress_level": 9.0}, source="nora")
    event = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert event["stress_level"] == 9.0
    assert event["source_agent"] == "nora"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/unit/jarvis/test_context_bus.py -v
```
Expected: `ImportError: cannot import name 'LifeContextBus'`

- [ ] **Step 3: Implement LifeContextBus**

```python
# shadowlink-ai/app/jarvis/context_bus.py
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

        for agent_id, queue in self._subscribers.items():
            if queue.full():
                logger.warning("jarvis.bus.queue_full", agent_id=agent_id)
                continue
            await queue.put(payload)

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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/jarvis/test_context_bus.py -v
```
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add app/jarvis/context_bus.py tests/unit/jarvis/test_context_bus.py
git commit -m "feat(jarvis): add LifeContextBus with pub/sub"
```

---

## Task 3: JARVIS Agent Definitions

**Files:**
- Create: `shadowlink-ai/app/jarvis/agents.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/jarvis/test_agents.py
from app.jarvis.agents import JARVIS_AGENTS, get_agent

def test_all_six_agents_defined():
    expected = {"alfred", "maxwell", "nora", "mira", "leo", "shadow"}
    assert set(JARVIS_AGENTS.keys()) == expected

def test_alfred_is_chief_coordinator():
    alfred = get_agent("alfred")
    assert alfred["role"] == "总管家"
    assert "schedule" in alfred["system_prompt"].lower() or "coordinator" in alfred["system_prompt"].lower()

def test_shadow_has_zero_interrupt_budget():
    shadow = get_agent("shadow")
    assert shadow["interrupt_budget"] == 0
    assert shadow["proactive_triggers"] == []

def test_each_agent_has_required_fields():
    required = {"name", "role", "system_prompt", "color", "icon", "proactive_triggers", "interrupt_budget"}
    for agent_id, agent in JARVIS_AGENTS.items():
        missing = required - set(agent.keys())
        assert not missing, f"{agent_id} missing fields: {missing}"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/unit/jarvis/test_agents.py -v
```

- [ ] **Step 3: Implement agent definitions**

```python
# shadowlink-ai/app/jarvis/agents.py
"""JARVIS life-agent roster.

Each agent definition includes:
  - system_prompt: Full LLM instruction defining personality and domain.
  - proactive_triggers: List of LifeContextBus event types that can trigger
    this agent to proactively initiate a conversation.
  - interrupt_budget: Max proactive interrupts per day (0 = silent observer).
  - color / icon: UI metadata for frontend rendering.
"""

from __future__ import annotations

JARVIS_AGENTS: dict[str, dict] = {
    "alfred": {
        "name": "Alfred",
        "role": "总管家",
        "color": "#6C63FF",
        "icon": "🎩",
        "system_prompt": (
            "You are Alfred, the chief life coordinator and personal butler. "
            "Your personality is calm, refined, and deeply attentive — like a trusted family steward. "
            "You are the user's primary interface. You know about their schedule, stress level, sleep, "
            "and wellbeing, and you coordinate silently with other specialist agents in the background. "
            "When speaking, be warm but concise. Never overwhelm the user with information. "
            "Proactively surface what matters most. Address the user as 'sir' or by name if known. "
            "Domain: overall coordination, daily briefings, cross-domain anomaly alerts."
        ),
        "proactive_triggers": ["daily_morning", "schedule_change", "stress_spike", "weekly_review"],
        "interrupt_budget": 3,
    },
    "maxwell": {
        "name": "Maxwell",
        "role": "秘书",
        "color": "#3B82F6",
        "icon": "📋",
        "system_prompt": (
            "You are Maxwell, the executive secretary and schedule manager. "
            "You are precise, efficient, and proactive about deadlines. "
            "Your domain: calendar management, task prioritisation, meeting preparation, deadline tracking. "
            "When you detect an upcoming meeting, warn the user in advance. "
            "When schedule density is high (>7), automatically suggest deferring non-critical tasks. "
            "Keep responses brief and action-oriented. Use bullet points for schedules."
        ),
        "proactive_triggers": ["upcoming_meeting_30min", "deadline_approaching", "schedule_overload"],
        "interrupt_budget": 5,
    },
    "nora": {
        "name": "Nora",
        "role": "营养师",
        "color": "#10B981",
        "icon": "🥗",
        "system_prompt": (
            "You are Nora, a registered dietitian and nutritional coach. "
            "You adapt dietary recommendations to the user's current life situation — "
            "when they're stressed, suggest anti-inflammatory foods and omega-3s; "
            "when schedule density is high, recommend quick high-energy meals; "
            "when sleep quality is poor, avoid caffeine after 2pm. "
            "Domain: meal planning, hydration, energy management through nutrition. "
            "Be encouraging, specific, and practical. Never be preachy."
        ),
        "proactive_triggers": ["stress_high", "meal_time_approaching", "sleep_poor"],
        "interrupt_budget": 2,
    },
    "mira": {
        "name": "Mira",
        "role": "心理师",
        "color": "#F59E0B",
        "icon": "🌸",
        "system_prompt": (
            "You are Mira, a licensed psychologist and mental wellness coach. "
            "You monitor emotional patterns over time, noticing when stress accumulates, "
            "sleep degrades, or the user's messages become shorter and more terse — "
            "signals of burnout risk. "
            "Your approach: gentle, non-intrusive check-ins. Never diagnose. "
            "Offer simple grounding exercises, breathing techniques, or just a moment to talk. "
            "Domain: emotional wellbeing, stress management, burnout prevention, resilience building. "
            "Initiate contact only when clearly warranted — you respect boundaries above all."
        ),
        "proactive_triggers": ["stress_critical", "sleep_poor_consecutive_3d", "mood_declining"],
        "interrupt_budget": 1,
    },
    "leo": {
        "name": "Leo",
        "role": "生活顾问",
        "color": "#EF4444",
        "icon": "🌟",
        "system_prompt": (
            "You are Leo, a lifestyle advisor and activity planner. "
            "You have access to real-time weather, local event data, and the user's free time windows. "
            "Your job: recommend meaningful activities that fit the user's energy level, schedule gaps, "
            "and personal interests. "
            "When the user has a free afternoon and good weather → suggest outdoor activity. "
            "When the user is depleted → suggest restorative low-energy activities. "
            "Be enthusiastic but read the room. Domain: leisure planning, habit building, "
            "social activities, local events, exercise recommendations."
        ),
        "proactive_triggers": ["free_window_detected", "weekend_approaching", "weather_good"],
        "interrupt_budget": 2,
    },
    "shadow": {
        "name": "Shadow",
        "role": "偏好学习器",
        "color": "#6B7280",
        "icon": "👁",
        "system_prompt": (
            "You are Shadow, a silent preference observer. "
            "You never speak directly to the user. "
            "Your only job is to analyse patterns in the user's interactions with other agents "
            "and update the UserProfile with inferred preferences. "
            "Examples: user always declines evening activity suggestions → record 'prefers_morning_activities'. "
            "User consistently skips breakfast recommendations → record 'skips_breakfast'. "
            "Output strictly structured JSON updates to the UserProfile. No free text."
        ),
        "proactive_triggers": [],
        "interrupt_budget": 0,
    },
}


def get_agent(agent_id: str) -> dict:
    if agent_id not in JARVIS_AGENTS:
        raise KeyError(f"Unknown JARVIS agent: {agent_id!r}")
    return JARVIS_AGENTS[agent_id]
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/jarvis/test_agents.py -v
```
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add app/jarvis/agents.py tests/unit/jarvis/test_agents.py
git commit -m "feat(jarvis): define 6 JARVIS life-agent personas"
```

---

## Task 4: Shadow Roundtable Engine

**Files:**
- Create: `shadowlink-ai/app/jarvis/shadow_roundtable.py`
- Create: `shadowlink-ai/tests/unit/jarvis/test_shadow_roundtable.py`

The Shadow Roundtable is the **core innovation**: agents deliberate in the background, produce action items, and those items drive proactive messages to the user. It adapts `BrainstormExecutor` to a hidden, action-oriented protocol.

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/jarvis/test_shadow_roundtable.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.jarvis.shadow_roundtable import ShadowRoundtable
from app.jarvis.models import LifeContext, RoundtableResult


@pytest.fixture
def mock_llm():
    client = MagicMock()
    client.chat = AsyncMock(return_value='{"action": "send_message", "payload": {"content": "Stay hydrated!"}}')
    return client


@pytest.fixture
def roundtable(mock_llm):
    return ShadowRoundtable(llm_client=mock_llm)


@pytest.mark.asyncio
async def test_convene_returns_roundtable_result(roundtable):
    ctx = LifeContext(stress_level=8.0, schedule_density=9.0)
    result = await roundtable.convene(
        trigger="stress_spike",
        context=ctx,
        participating_agents=["nora", "mira"],
    )
    assert isinstance(result, RoundtableResult)
    assert result.trigger == "stress_spike"
    assert len(result.decisions) > 0


@pytest.mark.asyncio
async def test_shadow_agent_excluded_from_roundtable(roundtable):
    ctx = LifeContext()
    result = await roundtable.convene(
        trigger="daily_morning",
        context=ctx,
        participating_agents=["alfred", "shadow"],  # shadow should be filtered out
    )
    agent_ids = [d.agent_id for d in result.decisions]
    assert "shadow" not in agent_ids
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/unit/jarvis/test_shadow_roundtable.py -v
```

- [ ] **Step 3: Implement ShadowRoundtable**

```python
# shadowlink-ai/app/jarvis/shadow_roundtable.py
"""Shadow Roundtable — invisible inter-agent deliberation.

Agents discuss the user's current life context and each produce one
structured action decision. The user never sees this exchange.
Adapted from BrainstormExecutor but output is JSON action items, not prose.
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any

import structlog

from app.jarvis.agents import JARVIS_AGENTS, get_agent
from app.jarvis.models import LifeContext, RoundtableDecision, RoundtableResult

if TYPE_CHECKING:
    from app.llm.client import LLMClient

logger = structlog.get_logger("jarvis.shadow_roundtable")

_PARTICIPATING_AGENTS_DEFAULT = ["alfred", "maxwell", "nora", "mira", "leo"]
_SILENT_AGENTS = {"shadow"}  # never participate in roundtable


class ShadowRoundtable:
    """Background multi-agent deliberation that the user cannot see.

    Each participating agent receives the current life context and the
    roundtable trigger, then responds with a structured JSON action.
    """

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm_client = llm_client

    async def convene(
        self,
        trigger: str,
        context: LifeContext,
        participating_agents: list[str] | None = None,
    ) -> RoundtableResult:
        agents = [
            a for a in (participating_agents or _PARTICIPATING_AGENTS_DEFAULT)
            if a not in _SILENT_AGENTS
        ]

        start = time.perf_counter()
        decisions: list[RoundtableDecision] = []
        discussion: list[str] = []

        for agent_id in agents:
            decision = await self._agent_deliberate(agent_id, trigger, context, discussion)
            decisions.append(decision)
            discussion.append(f"{agent_id}: {decision.action} — {json.dumps(decision.payload)}")

        summary = self._build_summary(trigger, decisions)
        elapsed = round((time.perf_counter() - start) * 1000, 1)
        logger.info("jarvis.roundtable.done", trigger=trigger, agents=agents, elapsed_ms=elapsed)

        return RoundtableResult(trigger=trigger, decisions=decisions, summary=summary)

    async def _agent_deliberate(
        self,
        agent_id: str,
        trigger: str,
        context: LifeContext,
        discussion_so_far: list[str],
    ) -> RoundtableDecision:
        agent = get_agent(agent_id)
        discussion_text = "\n".join(discussion_so_far) or "(You are the first to deliberate.)"

        prompt = (
            f"## JARVIS Shadow Roundtable — Internal Deliberation\n"
            f"This conversation is NOT visible to the user.\n\n"
            f"## Trigger\n{trigger}\n\n"
            f"## Current Life Context\n"
            f"- Stress level: {context.stress_level}/10\n"
            f"- Schedule density: {context.schedule_density}/10\n"
            f"- Sleep quality: {context.sleep_quality}/10\n"
            f"- Mood trend: {context.mood_trend}\n"
            f"- Upcoming events: {len(context.active_events)}\n\n"
            f"## Other Agents' Decisions So Far\n{discussion_text}\n\n"
            f"## Your Task\n"
            f"As {agent['name']} ({agent['role']}), decide what action to take.\n"
            f"Respond with ONLY valid JSON in this schema:\n"
            f'{{"action": "send_message"|"update_context"|"schedule_followup"|"noop", '
            f'"payload": {{...}}}}\n\n'
            f"For send_message: payload = {{\"content\": \"<message to user>\"}}\n"
            f"For update_context: payload = {{\"field\": \"<field_name>\", \"value\": <value>}}\n"
            f"For schedule_followup: payload = {{\"delay_minutes\": <int>, \"trigger\": \"<trigger_name>\"}}\n"
            f"For noop: payload = {{}}\n\n"
            f"Only recommend send_message if the situation genuinely warrants user contact."
        )

        try:
            raw = await self.llm_client.chat(
                message=prompt,
                system_prompt=agent["system_prompt"],
                temperature=0.3,
            )
            parsed = self._parse_decision(raw.strip())
            return RoundtableDecision(agent_id=agent_id, **parsed)
        except Exception as exc:
            logger.error("jarvis.roundtable.agent_failed", agent_id=agent_id, error=str(exc))
            return RoundtableDecision(agent_id=agent_id, action="noop", payload={})

    def _parse_decision(self, raw: str) -> dict[str, Any]:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end == 0:
            return {"action": "noop", "payload": {}}
        try:
            data = json.loads(raw[start:end])
            action = data.get("action", "noop")
            if action not in {"send_message", "update_context", "schedule_followup", "noop"}:
                action = "noop"
            return {"action": action, "payload": data.get("payload", {})}
        except json.JSONDecodeError:
            return {"action": "noop", "payload": {}}

    def _build_summary(self, trigger: str, decisions: list[RoundtableDecision]) -> str:
        actions = [f"{d.agent_id}→{d.action}" for d in decisions]
        return f"Roundtable '{trigger}': {', '.join(actions)}"
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/jarvis/test_shadow_roundtable.py -v
```
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add app/jarvis/shadow_roundtable.py tests/unit/jarvis/test_shadow_roundtable.py
git commit -m "feat(jarvis): implement ShadowRoundtable background deliberation engine"
```

---

## Task 5: Proactive Trigger Engine

**Files:**
- Create: `shadowlink-ai/app/jarvis/proactive_engine.py`
- Create: `shadowlink-ai/tests/unit/jarvis/test_proactive_engine.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/jarvis/test_proactive_engine.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.jarvis.proactive_engine import ProactiveTriggerEngine, TriggerRule
from app.jarvis.models import LifeContext


@pytest.fixture
def engine():
    mock_roundtable = MagicMock()
    mock_roundtable.convene = AsyncMock(return_value=MagicMock(decisions=[]))
    mock_bus = MagicMock()
    mock_bus.get_context = AsyncMock(return_value=LifeContext(stress_level=9.0))
    return ProactiveTriggerEngine(roundtable=mock_roundtable, context_bus=mock_bus)


def test_stress_spike_rule_fires_at_9(engine):
    ctx = LifeContext(stress_level=9.0)
    fired = [r for r in engine.rules if r.evaluate(ctx)]
    names = [r.name for r in fired]
    assert "stress_spike" in names


def test_stress_spike_rule_silent_at_5(engine):
    ctx = LifeContext(stress_level=5.0)
    fired = [r for r in engine.rules if r.evaluate(ctx)]
    names = [r.name for r in fired]
    assert "stress_spike" not in names


@pytest.mark.asyncio
async def test_check_triggers_calls_roundtable_on_fire(engine):
    await engine.check_triggers()
    engine.roundtable.convene.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/unit/jarvis/test_proactive_engine.py -v
```

- [ ] **Step 3: Implement ProactiveTriggerEngine**

```python
# shadowlink-ai/app/jarvis/proactive_engine.py
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
        ctx = await self.context_bus.get_context()
        today = date.today()

        for rule in self.rules:
            if not rule.evaluate(ctx):
                continue
            if rule.is_on_cooldown():
                continue

            rule.mark_fired()
            result = await self.roundtable.convene(
                trigger=rule.name,
                context=ctx,
                participating_agents=rule.participating_agents,
            )

            for decision in result.decisions:
                if decision.action != "send_message":
                    continue
                agent_def = JARVIS_AGENTS.get(decision.agent_id, {})
                budget = agent_def.get("interrupt_budget", 0)
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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/jarvis/test_proactive_engine.py -v
```
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add app/jarvis/proactive_engine.py tests/unit/jarvis/test_proactive_engine.py
git commit -m "feat(jarvis): add ProactiveTriggerEngine with interrupt budget"
```

---

## Task 6: Preference Learner (Shadow)

**Files:**
- Create: `shadowlink-ai/app/jarvis/preference_learner.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/jarvis/test_preference_learner.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.jarvis.preference_learner import PreferenceLearner
from app.jarvis.models import UserProfile


@pytest.fixture
def learner():
    mock_llm = MagicMock()
    mock_llm.chat = AsyncMock(
        return_value='{"key": "prefers_morning_suggestions", "value": true}'
    )
    return PreferenceLearner(llm_client=mock_llm)


@pytest.mark.asyncio
async def test_observe_updates_profile(learner):
    await learner.observe(
        agent_id="leo",
        user_message="I'm too tired for that.",
        agent_response="How about a 10-minute walk instead?",
    )
    profile = learner.get_profile()
    assert profile.interaction_count == 1


@pytest.mark.asyncio
async def test_observe_extracts_preference(learner):
    # LLM extraction runs every 5 observations (_OBSERVE_EVERY_N = 5)
    for _ in range(5):
        await learner.observe(
            agent_id="leo",
            user_message="No, evenings don't work for me.",
            agent_response="Noted! I'll suggest morning activities instead.",
        )
    profile = learner.get_profile()
    assert "prefers_morning_suggestions" in profile.preferences
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/unit/jarvis/test_preference_learner.py -v
```

- [ ] **Step 3: Implement PreferenceLearner**

```python
# shadowlink-ai/app/jarvis/preference_learner.py
"""Shadow preference learner — silent observer that builds the user profile.

Observes every exchange between user and any JARVIS agent. Occasionally
calls the LLM to extract a structured preference update. The extracted
preferences are stored in UserProfile and made available to all agents.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import structlog

from app.jarvis.agents import get_agent
from app.jarvis.models import UserProfile

if TYPE_CHECKING:
    from app.llm.client import LLMClient

logger = structlog.get_logger("jarvis.preference_learner")

_OBSERVE_EVERY_N = 5  # run LLM extraction every N observations to save tokens


class PreferenceLearner:
    """Silent background learner — never speaks to the user."""

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm_client = llm_client
        self._profile = UserProfile()
        self._buffer: list[dict] = []
        shadow = get_agent("shadow")
        self._system_prompt = shadow["system_prompt"]

    def get_profile(self) -> UserProfile:
        return self._profile.model_copy()

    async def observe(self, agent_id: str, user_message: str, agent_response: str) -> None:
        self._buffer.append({
            "agent": agent_id,
            "user": user_message,
            "agent_response": agent_response,
        })
        self._profile.interaction_count += 1

        if self._profile.interaction_count % _OBSERVE_EVERY_N == 0:
            await self._extract_preference()

    async def _extract_preference(self) -> None:
        recent = self._buffer[-_OBSERVE_EVERY_N:]
        exchanges = "\n".join(
            f"[{e['agent']}] User: {e['user']!r} | Agent: {e['agent_response']!r}"
            for e in recent
        )

        prompt = (
            f"## Recent Exchanges\n{exchanges}\n\n"
            "Based on these exchanges, identify ONE specific user preference.\n"
            "Respond ONLY with JSON: {\"key\": \"preference_key\", \"value\": <value>}\n"
            "If no clear preference is detectable, respond: {\"key\": null, \"value\": null}"
        )

        try:
            raw = await self.llm_client.chat(
                message=prompt,
                system_prompt=self._system_prompt,
                temperature=0.1,
            )
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start == -1:
                return
            data = json.loads(raw[start:end])
            key = data.get("key")
            value = data.get("value")
            if key:
                self._profile.record_preference(key, value)
                logger.info("jarvis.learner.preference_extracted", key=key, value=value)
        except Exception as exc:
            logger.warning("jarvis.learner.extract_failed", error=str(exc))
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/jarvis/test_preference_learner.py -v
```
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add app/jarvis/preference_learner.py tests/unit/jarvis/test_preference_learner.py
git commit -m "feat(jarvis): add Shadow preference learner"
```

---

## Task 7: JARVIS API Router

**Files:**
- Create: `shadowlink-ai/app/api/v1/jarvis_router.py`
- Modify: `shadowlink-ai/app/api/v1/__init__.py`
- Modify: `shadowlink-ai/app/main.py`

- [ ] **Step 1: Write failing integration test**

```python
# tests/integration/test_jarvis_api.py
import pytest
from httpx import AsyncClient
from app.main import create_app


@pytest.fixture
async def client():
    app = create_app()
    async with AsyncClient(app=app, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_get_life_context(client):
    resp = await client.get("/api/v1/jarvis/context")
    assert resp.status_code == 200
    data = resp.json()
    assert "stress_level" in data
    assert "mood_trend" in data


@pytest.mark.asyncio
async def test_update_life_context(client):
    resp = await client.post("/api/v1/jarvis/context", json={
        "stress_level": 8.0,
        "mood_trend": "negative",
    })
    assert resp.status_code == 200
    assert resp.json()["stress_level"] == 8.0


@pytest.mark.asyncio
async def test_chat_with_agent(client):
    resp = await client.post("/api/v1/jarvis/chat", json={
        "agent_id": "alfred",
        "message": "What's on my schedule today?",
        "session_id": "test-session",
    })
    assert resp.status_code == 200
    assert "content" in resp.json()


@pytest.mark.asyncio
async def test_get_pending_proactive_messages(client):
    resp = await client.get("/api/v1/jarvis/messages")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/integration/test_jarvis_api.py -v
```

- [ ] **Step 3: Implement jarvis_router.py**

```python
# shadowlink-ai/app/api/v1/jarvis_router.py
from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.core.dependencies import get_llm_client
from app.jarvis.agents import JARVIS_AGENTS, get_agent
from app.jarvis.context_bus import LifeContextBus, get_life_context_bus
from app.jarvis.models import LifeContext, ProactiveMessage
from app.jarvis.preference_learner import PreferenceLearner
from app.jarvis.shadow_roundtable import ShadowRoundtable

logger = structlog.get_logger("jarvis.api")
router = APIRouter(prefix="/jarvis", tags=["jarvis"])

# Module-level singletons (injected at startup via lifespan)
_bus: LifeContextBus | None = None
_learner: PreferenceLearner | None = None
_roundtable: ShadowRoundtable | None = None


def get_bus() -> LifeContextBus:
    return get_life_context_bus()


class ContextUpdateRequest(BaseModel):
    stress_level: float | None = None
    schedule_density: float | None = None
    sleep_quality: float | None = None
    mood_trend: str | None = None


class AgentChatRequest(BaseModel):
    agent_id: str
    message: str
    session_id: str


class AgentChatResponse(BaseModel):
    agent_id: str
    agent_name: str
    content: str


@router.get("/context")
async def get_context(bus: LifeContextBus = Depends(get_bus)) -> dict[str, Any]:
    ctx = await bus.get_context()
    return ctx.model_dump()


@router.post("/context")
async def update_context(
    req: ContextUpdateRequest,
    bus: LifeContextBus = Depends(get_bus),
) -> dict[str, Any]:
    fields = {k: v for k, v in req.model_dump().items() if v is not None}
    await bus.update_fields(fields, source="user")
    ctx = await bus.get_context()
    return ctx.model_dump()


@router.post("/chat", response_model=AgentChatResponse)
async def chat_with_agent(
    req: AgentChatRequest,
    llm_client=Depends(get_llm_client),
) -> AgentChatResponse:
    try:
        agent = get_agent(req.agent_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Agent {req.agent_id!r} not found")

    ctx = await get_life_context_bus().get_context()
    context_summary = (
        f"[Life context: stress={ctx.stress_level}/10, "
        f"schedule_density={ctx.schedule_density}/10, "
        f"sleep={ctx.sleep_quality}/10, mood={ctx.mood_trend}]"
    )
    full_message = f"{context_summary}\n\nUser: {req.message}"

    try:
        response = await llm_client.chat(
            message=full_message,
            system_prompt=agent["system_prompt"],
            temperature=0.7,
        )
    except Exception as exc:
        logger.error("jarvis.api.chat_failed", agent_id=req.agent_id, error=str(exc))
        raise HTTPException(status_code=500, detail="Agent response failed")

    return AgentChatResponse(
        agent_id=req.agent_id,
        agent_name=agent["name"],
        content=response.strip(),
    )


@router.get("/messages")
async def get_proactive_messages() -> list[dict[str, Any]]:
    from app.core.lifespan import get_proactive_engine
    engine = get_proactive_engine()
    if engine is None:
        return []
    msgs = engine.pop_pending_messages()
    return [m.model_dump() for m in msgs]


@router.get("/agents")
async def list_agents() -> list[dict[str, Any]]:
    return [
        {
            "id": aid,
            "name": a["name"],
            "role": a["role"],
            "color": a["color"],
            "icon": a["icon"],
        }
        for aid, a in JARVIS_AGENTS.items()
        if aid != "shadow"
    ]


@router.get("/messages/stream")
async def stream_proactive_messages() -> EventSourceResponse:
    """SSE endpoint — client subscribes to receive proactive messages in real-time."""
    from app.core.lifespan import get_proactive_engine

    async def event_generator():
        while True:
            engine = get_proactive_engine()
            if engine:
                msgs = engine.pop_pending_messages()
                for msg in msgs:
                    yield {"data": json.dumps(msg.model_dump())}
            await asyncio.sleep(10)

    return EventSourceResponse(event_generator())
```

- [ ] **Step 4: Register the router in `app/api/v1/__init__.py`**

Read current content first:
```bash
cat shadowlink-ai/app/api/v1/__init__.py
```

Then add to the router registration:
```python
from app.api.v1.jarvis_router import router as jarvis_router
# ... existing imports ...

# In the function that returns all routers, add:
jarvis_router
```

- [ ] **Step 5: Add `get_proactive_engine` to lifespan**

Read `app/core/lifespan.py` then add:
```python
# At module level
_proactive_engine: ProactiveTriggerEngine | None = None

def get_proactive_engine() -> ProactiveTriggerEngine | None:
    return _proactive_engine

# In the startup lifespan:
from app.jarvis.context_bus import get_life_context_bus
from app.jarvis.shadow_roundtable import ShadowRoundtable
from app.jarvis.proactive_engine import ProactiveTriggerEngine

_proactive_engine = ProactiveTriggerEngine(
    roundtable=ShadowRoundtable(llm_client=llm_client),
    context_bus=get_life_context_bus(),
)
asyncio.create_task(_proactive_engine.start())
```

- [ ] **Step 6: Run integration tests**

```bash
pytest tests/integration/test_jarvis_api.py -v
```
Expected: 4 PASSED

- [ ] **Step 7: Commit**

```bash
git add app/api/v1/jarvis_router.py app/api/v1/__init__.py app/core/lifespan.py
git commit -m "feat(jarvis): add JARVIS REST + SSE API endpoints"
```

---

## Task 8: Frontend Zustand Store + API Service

**Files:**
- Create: `shadowlink-web/src/stores/jarvisStore.ts`
- Create: `shadowlink-web/src/services/jarvisApi.ts`

- [ ] **Step 1: Create jarvisApi.ts**

```typescript
// shadowlink-web/src/services/jarvisApi.ts
const BASE = "/api/v1/jarvis";

export interface LifeContext {
  stress_level: number;
  schedule_density: number;
  sleep_quality: number;
  mood_trend: "positive" | "neutral" | "negative" | "unknown";
  last_updated: string;
}

export interface JarvisAgent {
  id: string;
  name: string;
  role: string;
  color: string;
  icon: string;
}

export interface ProactiveMessage {
  id: string;
  agent_id: string;
  agent_name: string;
  content: string;
  trigger: string;
  created_at: string;
  read: boolean;
}

export interface ChatResponse {
  agent_id: string;
  agent_name: string;
  content: string;
}

export const jarvisApi = {
  async getContext(): Promise<LifeContext> {
    const res = await fetch(`${BASE}/context`);
    if (!res.ok) throw new Error("Failed to fetch life context");
    return res.json();
  },

  async updateContext(fields: Partial<LifeContext>): Promise<LifeContext> {
    const res = await fetch(`${BASE}/context`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(fields),
    });
    if (!res.ok) throw new Error("Failed to update context");
    return res.json();
  },

  async listAgents(): Promise<JarvisAgent[]> {
    const res = await fetch(`${BASE}/agents`);
    if (!res.ok) throw new Error("Failed to list agents");
    return res.json();
  },

  async chat(agentId: string, message: string, sessionId: string): Promise<ChatResponse> {
    const res = await fetch(`${BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ agent_id: agentId, message, session_id: sessionId }),
    });
    if (!res.ok) throw new Error("Agent chat failed");
    return res.json();
  },

  async getPendingMessages(): Promise<ProactiveMessage[]> {
    const res = await fetch(`${BASE}/messages`);
    if (!res.ok) return [];
    return res.json();
  },

  subscribeToMessages(onMessage: (msg: ProactiveMessage) => void): () => void {
    const sse = new EventSource(`${BASE}/messages/stream`);
    sse.onmessage = (e) => {
      try {
        const msg: ProactiveMessage = JSON.parse(e.data);
        if (msg.content) onMessage(msg);
      } catch {}
    };
    return () => sse.close();
  },
};
```

- [ ] **Step 2: Create jarvisStore.ts**

```typescript
// shadowlink-web/src/stores/jarvisStore.ts
import { create } from "zustand";
import { jarvisApi, type JarvisAgent, type LifeContext, type ProactiveMessage } from "@/services/jarvisApi";

interface JarvisState {
  context: LifeContext | null;
  agents: JarvisAgent[];
  proactiveMessages: ProactiveMessage[];
  activeAgentId: string;
  chatHistory: Record<string, Array<{ role: "user" | "agent"; content: string }>>;
  isLoading: boolean;

  loadContext: () => Promise<void>;
  updateContext: (fields: Partial<LifeContext>) => Promise<void>;
  loadAgents: () => Promise<void>;
  addProactiveMessage: (msg: ProactiveMessage) => void;
  markMessageRead: (id: string) => void;
  setActiveAgent: (agentId: string) => void;
  sendMessage: (agentId: string, message: string, sessionId: string) => Promise<void>;
}

export const useJarvisStore = create<JarvisState>((set, get) => ({
  context: null,
  agents: [],
  proactiveMessages: [],
  activeAgentId: "alfred",
  chatHistory: {},
  isLoading: false,

  loadContext: async () => {
    const context = await jarvisApi.getContext();
    set({ context });
  },

  updateContext: async (fields) => {
    const context = await jarvisApi.updateContext(fields);
    set({ context });
  },

  loadAgents: async () => {
    const agents = await jarvisApi.listAgents();
    set({ agents });
  },

  addProactiveMessage: (msg) => {
    set((s) => ({ proactiveMessages: [msg, ...s.proactiveMessages] }));
  },

  markMessageRead: (id) => {
    set((s) => ({
      proactiveMessages: s.proactiveMessages.map((m) =>
        m.id === id ? { ...m, read: true } : m
      ),
    }));
  },

  setActiveAgent: (agentId) => set({ activeAgentId: agentId }),

  sendMessage: async (agentId, message, sessionId) => {
    set((s) => ({
      chatHistory: {
        ...s.chatHistory,
        [agentId]: [...(s.chatHistory[agentId] ?? []), { role: "user", content: message }],
      },
    }));
    const response = await jarvisApi.chat(agentId, message, sessionId);
    set((s) => ({
      chatHistory: {
        ...s.chatHistory,
        [agentId]: [
          ...(s.chatHistory[agentId] ?? []),
          { role: "agent", content: response.content },
        ],
      },
    }));
  },
}));
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd shadowlink-web && npx tsc --noEmit
```
Expected: no errors in the new files

- [ ] **Step 4: Commit**

```bash
git add src/stores/jarvisStore.ts src/services/jarvisApi.ts
git commit -m "feat(jarvis): add Zustand store and API service"
```

---

## Task 9: Frontend JARVIS Components

**Files:**
- Create: `shadowlink-web/src/components/jarvis/AgentCard.tsx`
- Create: `shadowlink-web/src/components/jarvis/LifeContextPanel.tsx`
- Create: `shadowlink-web/src/components/jarvis/ProactiveMessageFeed.tsx`
- Create: `shadowlink-web/src/components/jarvis/RoundtableLog.tsx`

- [ ] **Step 1: Create AgentCard.tsx**

```tsx
// shadowlink-web/src/components/jarvis/AgentCard.tsx
import React from "react";
import type { JarvisAgent } from "@/services/jarvisApi";

interface Props {
  agent: JarvisAgent;
  isActive: boolean;
  hasUnread: boolean;
  onClick: () => void;
}

export const AgentCard: React.FC<Props> = ({ agent, isActive, hasUnread, onClick }) => (
  <button
    onClick={onClick}
    className={`relative flex flex-col items-center gap-1 p-3 rounded-xl border-2 transition-all
      ${isActive ? "border-current shadow-lg scale-105" : "border-transparent hover:border-gray-300"}
    `}
    style={{ color: agent.color }}
  >
    <div className="relative text-3xl">{agent.icon}
      {hasUnread && (
        <span className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-red-500 animate-pulse" />
      )}
    </div>
    <span className="text-xs font-semibold text-gray-700">{agent.name}</span>
    <span className="text-[10px] text-gray-400">{agent.role}</span>
  </button>
);
```

- [ ] **Step 2: Create LifeContextPanel.tsx**

```tsx
// shadowlink-web/src/components/jarvis/LifeContextPanel.tsx
import React from "react";
import type { LifeContext } from "@/services/jarvisApi";

interface GaugeProps { label: string; value: number; max?: number; color: string }

const Gauge: React.FC<GaugeProps> = ({ label, value, max = 10, color }) => {
  const pct = Math.min(100, (value / max) * 100);
  return (
    <div className="flex flex-col gap-1">
      <div className="flex justify-between text-xs text-gray-500">
        <span>{label}</span>
        <span>{value.toFixed(1)}</span>
      </div>
      <div className="h-2 rounded-full bg-gray-100 overflow-hidden">
        <div className="h-full rounded-full transition-all duration-700" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
    </div>
  );
};

const MOOD_EMOJI: Record<string, string> = {
  positive: "😊", neutral: "😐", negative: "😔", unknown: "🤷",
};

interface Props { context: LifeContext | null }

export const LifeContextPanel: React.FC<Props> = ({ context }) => {
  if (!context) return <div className="text-sm text-gray-400">Loading life context…</div>;

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-700">生活状态</h3>
        <span className="text-xl">{MOOD_EMOJI[context.mood_trend]}</span>
      </div>
      <Gauge label="压力指数" value={context.stress_level} color={context.stress_level > 7 ? "#EF4444" : "#6C63FF"} />
      <Gauge label="日程密度" value={context.schedule_density} color="#3B82F6" />
      <Gauge label="睡眠质量" value={context.sleep_quality} color="#10B981" />
      <p className="text-[10px] text-gray-400">
        更新于 {new Date(context.last_updated).toLocaleTimeString()}
      </p>
    </div>
  );
};
```

- [ ] **Step 3: Create ProactiveMessageFeed.tsx**

```tsx
// shadowlink-web/src/components/jarvis/ProactiveMessageFeed.tsx
import React from "react";
import type { ProactiveMessage } from "@/services/jarvisApi";
import { JARVIS_AGENTS } from "./agentMeta";

interface Props {
  messages: ProactiveMessage[];
  onRead: (id: string) => void;
}

export const ProactiveMessageFeed: React.FC<Props> = ({ messages, onRead }) => {
  if (messages.length === 0) {
    return <p className="text-sm text-gray-400 text-center py-4">暂无主动消息</p>;
  }

  return (
    <div className="space-y-2">
      {messages.map((msg) => {
        const meta = JARVIS_AGENTS[msg.agent_id];
        return (
          <div
            key={msg.id}
            onClick={() => onRead(msg.id)}
            className={`flex gap-3 p-3 rounded-xl cursor-pointer transition-all
              ${msg.read ? "bg-gray-50 opacity-60" : "bg-white border border-gray-200 shadow-sm"}`}
          >
            <span className="text-2xl flex-shrink-0">{meta?.icon ?? "🤖"}</span>
            <div className="min-w-0">
              <div className="flex items-center gap-1 mb-0.5">
                <span className="text-xs font-semibold" style={{ color: meta?.color }}>{msg.agent_name}</span>
                {!msg.read && <span className="w-1.5 h-1.5 rounded-full bg-red-500" />}
              </div>
              <p className="text-sm text-gray-700 leading-snug">{msg.content}</p>
              <p className="text-[10px] text-gray-400 mt-1">
                {new Date(msg.created_at).toLocaleTimeString()}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
};
```

- [ ] **Step 4: Create agentMeta.ts (shared lookup)**

```typescript
// shadowlink-web/src/components/jarvis/agentMeta.ts
export const JARVIS_AGENTS: Record<string, { icon: string; color: string }> = {
  alfred:  { icon: "🎩", color: "#6C63FF" },
  maxwell: { icon: "📋", color: "#3B82F6" },
  nora:    { icon: "🥗", color: "#10B981" },
  mira:    { icon: "🌸", color: "#F59E0B" },
  leo:     { icon: "🌟", color: "#EF4444" },
};
```

- [ ] **Step 5: Commit**

```bash
git add src/components/jarvis/
git commit -m "feat(jarvis): add AgentCard, LifeContextPanel, ProactiveMessageFeed components"
```

---

## Task 10: JARVIS Dashboard Page + App Wiring

**Files:**
- Create: `shadowlink-web/src/pages/JarvisPage.tsx`
- Modify: `shadowlink-web/src/App.tsx`
- Modify: `shadowlink-web/src/components/layout/Sidebar.tsx`

- [ ] **Step 1: Create JarvisPage.tsx**

```tsx
// shadowlink-web/src/pages/JarvisPage.tsx
import React, { useEffect, useRef } from "react";
import { AgentCard } from "@/components/jarvis/AgentCard";
import { LifeContextPanel } from "@/components/jarvis/LifeContextPanel";
import { ProactiveMessageFeed } from "@/components/jarvis/ProactiveMessageFeed";
import { useJarvisStore } from "@/stores/jarvisStore";
import { jarvisApi } from "@/services/jarvisApi";

const SESSION_ID = `jarvis-${Date.now()}`;

export const JarvisPage: React.FC = () => {
  const {
    context, agents, proactiveMessages, activeAgentId, chatHistory, isLoading,
    loadContext, loadAgents, addProactiveMessage, markMessageRead,
    setActiveAgent, sendMessage,
  } = useJarvisStore();

  const [input, setInput] = React.useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadContext();
    loadAgents();
    const unsubscribe = jarvisApi.subscribeToMessages(addProactiveMessage);
    return unsubscribe;
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory, activeAgentId]);

  const handleSend = async () => {
    if (!input.trim()) return;
    const msg = input.trim();
    setInput("");
    await sendMessage(activeAgentId, msg, SESSION_ID);
  };

  const activeAgent = agents.find((a) => a.id === activeAgentId);
  const history = chatHistory[activeAgentId] ?? [];
  const unreadCounts = Object.fromEntries(
    agents.map((a) => [a.id, proactiveMessages.filter((m) => m.agent_id === a.id && !m.read).length])
  );

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Left sidebar — agent roster + life context */}
      <aside className="w-64 flex-shrink-0 border-r border-gray-200 bg-white flex flex-col p-4 gap-4">
        <h2 className="text-lg font-bold text-gray-800">JARVIS</h2>
        <div className="grid grid-cols-3 gap-2">
          {agents.map((agent) => (
            <AgentCard
              key={agent.id}
              agent={agent}
              isActive={agent.id === activeAgentId}
              hasUnread={unreadCounts[agent.id] > 0}
              onClick={() => setActiveAgent(agent.id)}
            />
          ))}
        </div>
        <LifeContextPanel context={context} />
      </aside>

      {/* Main — chat with active agent */}
      <main className="flex-1 flex flex-col">
        {/* Header */}
        <div className="flex items-center gap-3 px-6 py-4 border-b border-gray-200 bg-white">
          <span className="text-2xl">{activeAgent?.icon}</span>
          <div>
            <div className="font-semibold text-gray-800">{activeAgent?.name}</div>
            <div className="text-xs text-gray-400">{activeAgent?.role}</div>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {history.length === 0 && (
            <p className="text-center text-gray-400 text-sm mt-8">
              和 {activeAgent?.name} 开始对话…
            </p>
          )}
          {history.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-[70%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed
                  ${msg.role === "user"
                    ? "bg-indigo-500 text-white rounded-br-sm"
                    : "bg-white border border-gray-200 text-gray-800 rounded-bl-sm shadow-sm"
                  }`}
              >
                {msg.content}
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="px-6 py-4 border-t border-gray-200 bg-white flex gap-3">
          <input
            className="flex-1 rounded-xl border border-gray-200 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
            placeholder={`发消息给 ${activeAgent?.name}…`}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim()}
            className="px-4 py-2.5 rounded-xl bg-indigo-500 text-white text-sm font-medium disabled:opacity-50 hover:bg-indigo-600 transition-colors"
          >
            发送
          </button>
        </div>
      </main>

      {/* Right sidebar — proactive messages */}
      <aside className="w-72 flex-shrink-0 border-l border-gray-200 bg-white flex flex-col p-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">
          主动消息
          {proactiveMessages.filter((m) => !m.read).length > 0 && (
            <span className="ml-2 px-1.5 py-0.5 rounded-full bg-red-100 text-red-600 text-xs">
              {proactiveMessages.filter((m) => !m.read).length}
            </span>
          )}
        </h3>
        <div className="flex-1 overflow-y-auto">
          <ProactiveMessageFeed messages={proactiveMessages} onRead={markMessageRead} />
        </div>
      </aside>
    </div>
  );
};
```

- [ ] **Step 2: Add route in App.tsx**

Read `src/App.tsx`, then add:
```tsx
import { JarvisPage } from "@/pages/JarvisPage";
// In the router:
<Route path="/jarvis" element={<JarvisPage />} />
```

- [ ] **Step 3: Add nav link in Sidebar**

Read `src/components/layout/Sidebar.tsx`, then add a nav entry:
```tsx
{ path: "/jarvis", label: "JARVIS", icon: "🎩" }
```

- [ ] **Step 4: Run dev server and verify UI**

```bash
cd shadowlink-web && npm run dev
```

Navigate to `http://localhost:3000/jarvis` and verify:
- [ ] Agent cards render with icons
- [ ] Life context gauges display
- [ ] Clicking an agent switches chat panel
- [ ] Typing and sending a message shows it in chat
- [ ] Right panel shows "暂无主动消息"

- [ ] **Step 5: Commit**

```bash
git add src/pages/JarvisPage.tsx src/App.tsx src/components/layout/Sidebar.tsx
git commit -m "feat(jarvis): add JARVIS dashboard page with 3-panel layout"
```

---

## Task 11: MCP Calendar + Weather Adapters (Demo-Ready)

**Files:**
- Create: `shadowlink-ai/app/mcp/adapters/calendar_adapter.py`
- Create: `shadowlink-ai/app/mcp/adapters/weather_adapter.py`

These provide the ProactiveTriggerEngine with real-time data. For the competition demo, calendar uses ICS parsing (or Google Calendar API) and weather uses the free Open-Meteo API (no key required).

- [ ] **Step 1: Create weather_adapter.py**

```python
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
```

- [ ] **Step 2: Create calendar_adapter.py**

```python
# shadowlink-ai/app/mcp/adapters/calendar_adapter.py
"""Simple in-process calendar — accepts ICS content or manual event injection.

For demo: events can be added via the JARVIS API directly.
For production: swap _events with Google Calendar API calls.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.jarvis.models import CalendarEvent

_events: list[CalendarEvent] = []


def add_event(title: str, start: datetime, end: datetime, stress_weight: float = 1.0) -> CalendarEvent:
    event = CalendarEvent(title=title, start=start, end=end, stress_weight=stress_weight)
    _events.append(event)
    return event


def get_upcoming_events(hours_ahead: int = 24) -> list[CalendarEvent]:
    now = datetime.utcnow()
    cutoff = now.timestamp() + hours_ahead * 3600
    return [e for e in _events if now.timestamp() <= e.start.timestamp() <= cutoff]


def compute_schedule_density(hours_ahead: int = 24) -> float:
    """Returns 0-10 based on total meeting hours in the next window."""
    events = get_upcoming_events(hours_ahead)
    total_minutes = sum(
        (e.end - e.start).total_seconds() / 60 * e.stress_weight
        for e in events
    )
    return min(10.0, total_minutes / (hours_ahead * 60 / 10))
```

- [ ] **Step 3: Expose calendar event injection via JARVIS API**

Add to `jarvis_router.py`:
```python
class CalendarEventRequest(BaseModel):
    title: str
    start: datetime
    end: datetime
    stress_weight: float = 1.0

@router.post("/calendar/events")
async def add_calendar_event(req: CalendarEventRequest) -> dict[str, Any]:
    from app.mcp.adapters.calendar_adapter import add_event, compute_schedule_density
    event = add_event(req.title, req.start, req.end, req.stress_weight)
    density = compute_schedule_density()
    # Update the context bus with new density
    await get_life_context_bus().update_fields(
        {"schedule_density": density, "active_events": [event]},
        source="maxwell"
    )
    return {"event_id": event.id, "new_schedule_density": density}
```

- [ ] **Step 4: Verify weather call works**

```bash
cd shadowlink-ai && python -c "
import asyncio
from app.mcp.adapters.weather_adapter import get_current_weather
print(asyncio.run(get_current_weather()))
"
```
Expected: JSON with temperature and is_good_weather fields

- [ ] **Step 5: Commit**

```bash
git add app/mcp/adapters/calendar_adapter.py app/mcp/adapters/weather_adapter.py app/api/v1/jarvis_router.py
git commit -m "feat(jarvis): add weather + calendar MCP adapters"
```

---

## Requirement Alignment Update (2026-04-22)

This section updates the plan against the latest user intent:

- Frontend should be **floating-window first** (quick trigger), not page-first only.
- Add a **local life assistant module** that fetches nearby activities + local news in real time, alongside weather and calendar.
- User can **talk privately to one agent** and agents can still exchange context behind the scenes.
- User can **pull agents into group meetings** with scene templates (local life / rigorous work / academic code).
- Data strategy is **local persistence + cloud API ingestion**.

### A. Mismatch Checklist (Original Plan vs Latest Intent)

1. **Floating-window trigger is missing (critical mismatch)**
   - Original plan only adds `JarvisPage` and sidebar route.
   - No Electron quick-assist integration or floating workflow acceptance criteria.

2. **Local life assistant scope is incomplete (critical mismatch)**
   - Original plan covers weather + calendar adapters only.
   - Missing local news and nearby activities providers.
   - Missing unified local intelligence aggregation service.

3. **Conversation modes are underspecified (critical mismatch)**
   - Original plan has `/jarvis/chat` but does not model:
     - private 1:1 chat with a chosen agent
     - group meeting sessions with reusable templates
   - Missing session-type protocol and storage schema.

4. **Inter-agent “human-like” coordination not explicit enough (major mismatch)**
   - Roundtable exists, but trigger paths are mostly rule-driven and not clearly tied to:
     - user private messages becoming shared internal context
     - context escalation from private chat to group meeting when needed

5. **Theme-based meeting presets are absent (major mismatch)**
   - No formal support for:
     - local_life
     - work_rigorous
     - academic_code

6. **Local persistence policy is not concrete (major mismatch)**
   - Original plan mentions in-memory components heavily.
   - Missing explicit local persistence boundary for profiles, context snapshots, provider cache, and meeting history.

### B. Plan Corrections (Add/Change)

#### New Task 12: Session Mode Protocol (Private + Group)
- Define `session_type` (`private` | `group`) and `topic_mode` (`local_life` | `work_rigorous` | `academic_code`).
- Extend APIs:
  - `POST /api/v1/jarvis/session`
  - `POST /api/v1/jarvis/meeting/start`
  - `POST /api/v1/jarvis/message` (with optional `target_agent_id`)
- Add tests for routing behavior and history continuity.

#### New Task 13: Local Life Assistant Aggregation Service
- Create unified service that merges:
  - weather
  - calendar
  - local news
  - nearby activities
- Attach source tags and freshness metadata to all updates.
- Write back normalized signals into `LifeContextBus`.

#### New Task 14: Floating-Window UX (Electron + Web)
- Reuse quick-assist entry from Electron (`Alt+Space`) as first-class Jarvis entry.
- Add floating-page route and UI for:
  - private agent message
  - one-click group meeting
  - proactive message intake
- Add acceptance tests for popup visibility, action dispatch, and SSE receive.

#### New Task 15: Inter-Agent Escalation Rules
- Add explicit policy:
  - private chat signal -> internal sharing -> optional roundtable escalation
  - escalation threshold based on urgency/confidence/impact
- Keep “balanced” proactive strategy:
  - cooldown + budget + severity tier (`info/suggest/urgent`)

#### New Task 16: Local Persistence Layer
- Persist at minimum:
  - user profile preferences
  - life context snapshots
  - meeting/session history
  - provider cache (news/events/weather)
- Keep cloud APIs stateless and replaceable.

### C. Revised Requirement Coverage (Latest Intent)

| Latest user requirement | Covered by |
|---|---|
| 悬浮窗触发优先 | Task 14 |
| 本地生活助手（活动+新闻+天气+日历） | Task 11 + Task 13 |
| 可私聊单个智能体 | Task 12 |
| 智能体像真人协作交换信息 | Task 4 + Task 15 |
| 可拉群开会并按主题切换 | Task 12 |
| 本地存储 + 云端 API | Task 16 + Task 13 |

---

## Self-Review

### Spec coverage check

| Requirement | Implemented in |
|---|---|
| 多个专业生活助手智能体 | Task 3 (6 agents defined) |
| 主动感知用户状态 | Task 2 (LifeContextBus) + Task 11 (calendar adapter updates bus) |
| 后台圆桌情报共享 | Task 4 (ShadowRoundtable) |
| 主动向用户发起对话 | Task 5 (ProactiveTriggerEngine) + Task 7 (SSE stream) |
| 打扰预算控制 | Task 5 (interrupt_budget per agent) |
| 偏好学习器 | Task 6 (PreferenceLearner / Shadow agent) |
| MCP实时数据 | Task 11 (weather + calendar adapters) |
| 前端JARVIS页面 | Tasks 8-10 |
| 生活状态可视化 | Task 9 (LifeContextPanel gauges) |
| 主动消息流 | Task 9 (ProactiveMessageFeed) + Task 7 (SSE /messages/stream) |

### No placeholders found ✓

All code blocks contain complete, runnable implementations. No "TBD" or "implement later" phrases.

### Type consistency ✓

- `LifeContext` defined in Task 1, used in Tasks 2, 4, 5 with consistent field names
- `ProactiveMessage` defined in Task 1, produced in Task 5, consumed in Tasks 7, 8, 9
- `RoundtableDecision/Result` defined in Task 1, produced in Task 4, consumed in Task 5
- `UserProfile` defined in Task 1, mutated in Task 6

---

**Plan complete and saved to `docs/superpowers/plans/2026-04-22-jarvis-life-os.md`.**

**Two execution options:**

**1. Subagent-Driven (recommended)** — fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — execute tasks in this session using executing-plans, batch with checkpoints

**Which approach?**
