# Schedule Coordination LangGraph Roundtable Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade only the `schedule_coord` preset roundtable into a LangGraph-backed, human-in-the-loop meeting with per-role streaming bubbles, per-round public minutes, user checkpoints, and final decision results.

**Architecture:** Keep the existing `/roundtable/start`, `/roundtable/continue`, `roundtable_sessions`, `roundtable_results`, private-chat return, and decision accept endpoints. Add a schedule-specific graph executor behind the existing router dispatch; all other scenarios keep the current executor. The graph runs one visible meeting round at a time, streams each role's public speech via SSE, persists turns, emits a round summary checkpoint, then waits for user feedback or finalization.

**Tech Stack:** FastAPI, SSE via `EventSourceResponse`, existing `LLMClient.chat_stream`, LangGraph, SQLite persistence helpers, React `RoundtableStage`, Vitest-free frontend verification through `npm run build`, backend pytest.

---

## Scope

Only `schedule_coord` changes behavior in this plan.

Current `schedule_coord`:
- Scenario id: `schedule_coord`
- Name: `今日日程协调`
- Participants: `maxwell`, `nora`, `mira`, `alfred`
- Current mode: `decision`
- Current behavior: generic sequential `_run_roundtable_round`

New behavior:
- Round 1: Maxwell, Nora, Mira, Alfred speak with streaming bubbles.
- Then the graph emits a public round summary with `minutes`, `consensus`, `disagreements`, `questions_for_user`, and `suggested_next_actions`.
- The graph pauses at a user checkpoint.
- `/roundtable/continue` resumes the same schedule graph with user feedback.
- User can continue discussion or ask to finalize.
- Final result persists through the existing `roundtable_results` table and remains acceptable through `/roundtable/{session_id}/accept`.

Do not migrate `study_energy_decision`, `local_lifestyle`, `emotional_care`, `weekend_recharge`, or `work_brainstorm` in this plan.

---

## Files

Create:
- `shadowlink-ai/app/jarvis/roundtable_graph.py`
  Shared state models, event helpers, and public schema for graph-backed roundtables.
- `shadowlink-ai/app/jarvis/schedule_coord_graph.py`
  Schedule coordination graph executor and schedule-specific prompts.
- `shadowlink-ai/tests/unit/jarvis/test_schedule_coord_graph.py`
  Unit tests for graph state, role order, checkpoint summaries, final result mapping.

Modify:
- `shadowlink-ai/app/api/v1/jarvis_router.py`
  Dispatch `schedule_coord` start/continue to graph executor; preserve old executor for other scenarios.
- `shadowlink-ai/app/jarvis/roundtable_sessions.py`
  Persist user checkpoint feedback as roundtable turns using the existing append path.
- `shadowlink-ai/app/jarvis/persistence.py`
  Add small metadata fields only if needed for round summaries; prefer storing graph state in existing `roundtable_results.context` first.
- `shadowlink-web/src/components/jarvis/RoundtableStage.tsx`
  Support `role_started`, `role_delta`, `role_completed`, `round_summary`, `user_checkpoint`, and `final_result` events.
- `shadowlink-web/src/services/jarvisApi.ts`
  Extend types for round summary and checkpoint payloads if they are exported.

---

## Event Contract

Backend emits these new SSE events for `schedule_coord`:

```json
{"event":"round_started","data":{"session_id":"...","scenario_id":"schedule_coord","round_index":1,"participants":["maxwell","nora","mira","alfred"]}}
```

```json
{"event":"role_started","data":{"agent_id":"maxwell","agent_name":"Maxwell","agent_role":"秘书","round_index":1}}
```

```json
{"event":"role_delta","data":{"agent_id":"maxwell","delta":"今天的关键冲突是...","round_index":1}}
```

```json
{"event":"role_completed","data":{"agent_id":"maxwell","content":"完整公开发言","round_index":1}}
```

```json
{
  "event":"round_summary",
  "data":{
    "round_index":1,
    "minutes":[{"agent_id":"maxwell","summary":"..."}],
    "consensus":["..."],
    "disagreements":["..."],
    "questions_for_user":["你更想保护上午深度工作，还是优先处理会议准备？"],
    "next_round_focus":["根据用户偏好修正日程优先级"]
  }
}
```

```json
{"event":"user_checkpoint","data":{"round_index":1,"allowed_actions":["continue","comment","finalize","redirect"]}}
```

```json
{"event":"final_result","data":{"mode":"decision","summary":"...","recommended_option":"...","actions":[...]}}
```

Existing events remain valid:
- `phase_change`
- `agent_degraded`
- `roundtable_timing`
- `decision_result`
- `done`

---

## Task 1: Backend Graph State And Event Models

**Files:**
- Create: `shadowlink-ai/app/jarvis/roundtable_graph.py`
- Test: `shadowlink-ai/tests/unit/jarvis/test_schedule_coord_graph.py`

- [ ] **Step 1: Write failing tests for shared models**

Add to `tests/unit/jarvis/test_schedule_coord_graph.py`:

```python
from app.jarvis.roundtable_graph import (
    RoundtableGraphState,
    RoundtableRoleOutput,
    RoundtableRoundSummary,
    round_event,
)


def test_roundtable_graph_state_defaults_to_first_round():
    state = RoundtableGraphState(
        session_id="rt-schedule-1",
        scenario_id="schedule_coord",
        user_goal="帮我协调今天日程",
        participants=["maxwell", "nora", "mira", "alfred"],
    )

    assert state.round_index == 1
    assert state.status == "running"
    assert state.role_outputs == []
    assert state.user_feedback_history == []


def test_round_event_serializes_payload_as_json_string():
    event = round_event("round_started", {"session_id": "rt-schedule-1", "round_index": 1})

    assert event["event"] == "round_started"
    assert '"round_index": 1' in event["data"]
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
cd shadowlink-ai
.venv311/bin/python -m pytest tests/unit/jarvis/test_schedule_coord_graph.py -q
```

Expected: import failure because `app.jarvis.roundtable_graph` does not exist.

- [ ] **Step 3: Implement shared models**

Create `app/jarvis/roundtable_graph.py`:

```python
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal


GraphStatus = Literal["running", "waiting_for_user", "finalized", "failed"]


@dataclass
class RoundtableRoleOutput:
    agent_id: str
    agent_name: str
    role: str
    content: str
    round_index: int
    summary: str = ""
    concerns: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


@dataclass
class RoundtableRoundSummary:
    round_index: int
    minutes: list[dict[str, Any]] = field(default_factory=list)
    consensus: list[str] = field(default_factory=list)
    disagreements: list[str] = field(default_factory=list)
    questions_for_user: list[str] = field(default_factory=list)
    next_round_focus: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "round_index": self.round_index,
            "minutes": self.minutes,
            "consensus": self.consensus,
            "disagreements": self.disagreements,
            "questions_for_user": self.questions_for_user,
            "next_round_focus": self.next_round_focus,
        }


@dataclass
class RoundtableGraphState:
    session_id: str
    scenario_id: str
    user_goal: str
    participants: list[str]
    round_index: int = 1
    context: dict[str, Any] = field(default_factory=dict)
    user_feedback_history: list[str] = field(default_factory=list)
    role_outputs: list[RoundtableRoleOutput] = field(default_factory=list)
    round_summaries: list[RoundtableRoundSummary] = field(default_factory=list)
    final_result: dict[str, Any] | None = None
    status: GraphStatus = "running"


def round_event(event: str, payload: dict[str, Any]) -> dict[str, str]:
    return {"event": event, "data": json.dumps(payload, ensure_ascii=False)}
```

- [ ] **Step 4: Verify tests pass**

Run:

```bash
cd shadowlink-ai
.venv311/bin/python -m pytest tests/unit/jarvis/test_schedule_coord_graph.py -q
```

Expected: tests pass.

---

## Task 2: Schedule Coordination Graph Executor

**Files:**
- Create: `shadowlink-ai/app/jarvis/schedule_coord_graph.py`
- Modify: `shadowlink-ai/tests/unit/jarvis/test_schedule_coord_graph.py`

- [ ] **Step 1: Write failing tests for role order and checkpoint emission**

Append:

```python
import json
import pytest

from app.jarvis.schedule_coord_graph import ScheduleCoordGraphExecutor


class FakeStreamingLLM:
    async def chat_stream(self, *, message: str, system_prompt: str, temperature: float = 0.7, **kwargs):
        if "Maxwell" in system_prompt:
            chunks = ["Maxwell sees ", "two time conflicts."]
        elif "Nora" in system_prompt:
            chunks = ["Nora suggests ", "stable meals."]
        elif "Mira" in system_prompt:
            chunks = ["Mira protects ", "recovery boundaries."]
        else:
            chunks = ["Alfred summarizes ", "the coordinated plan."]
        for chunk in chunks:
            yield chunk

    async def chat(self, *, message: str, system_prompt: str, temperature: float = 0.7, **kwargs):
        return (
            '{"minutes":[{"agent_id":"maxwell","summary":"conflicts"}],'
            '"consensus":["protect buffers"],'
            '"disagreements":["morning focus vs meeting prep"],'
            '"questions_for_user":["Which priority matters more?"],'
            '"next_round_focus":["revise priority order"]}'
        )


@pytest.mark.asyncio
async def test_schedule_coord_graph_streams_roles_then_checkpoint():
    executor = ScheduleCoordGraphExecutor(llm_client=FakeStreamingLLM())
    events = []

    async for event in executor.start_round(
        session_id="rt-schedule-1",
        user_goal="帮我协调今天日程",
        context={"calendar_events": [], "today_tasks": []},
    ):
        events.append(event)

    names = [event["event"] for event in events]
    assert names[0] == "round_started"
    assert names.count("role_started") == 4
    assert names.count("role_delta") >= 4
    assert names.count("role_completed") == 4
    assert "round_summary" in names
    assert names[-1] == "user_checkpoint"
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
cd shadowlink-ai
.venv311/bin/python -m pytest tests/unit/jarvis/test_schedule_coord_graph.py::test_schedule_coord_graph_streams_roles_then_checkpoint -q
```

Expected: import failure because `schedule_coord_graph.py` does not exist.

- [ ] **Step 3: Implement minimal executor**

Create `app/jarvis/schedule_coord_graph.py` with:

```python
from __future__ import annotations

import json
from typing import Any, AsyncIterator

from app.jarvis.agents import get_agent
from app.jarvis.roundtable_graph import (
    RoundtableGraphState,
    RoundtableRoleOutput,
    RoundtableRoundSummary,
    round_event,
)

SCHEDULE_COORD_PARTICIPANTS = ["maxwell", "nora", "mira", "alfred"]


class ScheduleCoordGraphExecutor:
    def __init__(self, llm_client: Any) -> None:
        self.llm_client = llm_client

    async def start_round(
        self,
        *,
        session_id: str,
        user_goal: str,
        context: dict[str, Any],
        round_index: int = 1,
        feedback_history: list[str] | None = None,
    ) -> AsyncIterator[dict[str, str]]:
        state = RoundtableGraphState(
            session_id=session_id,
            scenario_id="schedule_coord",
            user_goal=user_goal,
            participants=list(SCHEDULE_COORD_PARTICIPANTS),
            round_index=round_index,
            context=context,
            user_feedback_history=feedback_history or [],
        )
        yield round_event("round_started", {
            "session_id": session_id,
            "scenario_id": "schedule_coord",
            "round_index": round_index,
            "participants": state.participants,
        })

        for agent_id in state.participants:
            output = await self._stream_role(state, agent_id)
            state.role_outputs.append(output)
            yield round_event("role_completed", {
                "agent_id": output.agent_id,
                "agent_name": output.agent_name,
                "content": output.content,
                "round_index": round_index,
            })

        summary = await self._summarize_round(state)
        state.round_summaries.append(summary)
        state.status = "waiting_for_user"
        yield round_event("round_summary", summary.to_dict())
        yield round_event("user_checkpoint", {
            "round_index": round_index,
            "allowed_actions": ["continue", "comment", "finalize", "redirect"],
        })

    async def _stream_role(self, state: RoundtableGraphState, agent_id: str) -> RoundtableRoleOutput:
        agent = get_agent(agent_id)
        yield_started = getattr(self, "_yield_started", None)
        content_parts: list[str] = []
        prompt = self._role_prompt(state, agent_id)
        self._pending_events = getattr(self, "_pending_events", [])
        self._pending_events.append(round_event("role_started", {
            "agent_id": agent_id,
            "agent_name": agent["name"],
            "agent_role": agent["role"],
            "round_index": state.round_index,
        }))
        async for delta in self.llm_client.chat_stream(
            message=prompt,
            system_prompt=agent["system_prompt"],
            temperature=0.35,
        ):
            content_parts.append(delta)
            self._pending_events.append(round_event("role_delta", {
                "agent_id": agent_id,
                "delta": delta,
                "round_index": state.round_index,
            }))
        return RoundtableRoleOutput(
            agent_id=agent_id,
            agent_name=agent["name"],
            role=agent["role"],
            content="".join(content_parts).strip(),
            round_index=state.round_index,
        )

    def _role_prompt(self, state: RoundtableGraphState, agent_id: str) -> str:
        feedback = "\n".join(state.user_feedback_history) or "无"
        previous = "\n".join(f"{item.agent_name}: {item.content}" for item in state.role_outputs) or "无"
        role_tasks = {
            "maxwell": "评估今日时间窗口、冲突、缓冲和执行顺序。",
            "nora": "评估饮食、补水、咖啡因和身体能量对日程的影响。",
            "mira": "评估压力、恢复边界、过载风险和情绪负担。",
            "alfred": "综合各方，指出共识、分歧和需要用户判断的问题。",
        }
        return (
            "## 今日日程协调圆桌\n"
            f"用户诉求: {state.user_goal}\n\n"
            f"上下文: {json.dumps(state.context, ensure_ascii=False, default=str)[:3000]}\n\n"
            f"用户上一轮反馈: {feedback}\n\n"
            f"前面角色发言: {previous}\n\n"
            f"你的职责: {role_tasks.get(agent_id, '从你的角色视角给出建议。')}\n"
            "请输出面向用户可公开展示的会议发言，3-5 句，不要展示隐藏推理链。"
        )

    async def _summarize_round(self, state: RoundtableGraphState) -> RoundtableRoundSummary:
        prompt = (
            "请把今日日程协调圆桌本轮讨论整理成严格 JSON，字段为 "
            "minutes, consensus, disagreements, questions_for_user, next_round_focus。\n\n"
            + "\n\n".join(f"{item.agent_id}: {item.content}" for item in state.role_outputs)
        )
        raw = await self.llm_client.chat(message=prompt, system_prompt=get_agent("alfred")["system_prompt"], temperature=0.2)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {}
        return RoundtableRoundSummary(
            round_index=state.round_index,
            minutes=data.get("minutes") if isinstance(data.get("minutes"), list) else [],
            consensus=data.get("consensus") if isinstance(data.get("consensus"), list) else [],
            disagreements=data.get("disagreements") if isinstance(data.get("disagreements"), list) else [],
            questions_for_user=data.get("questions_for_user") if isinstance(data.get("questions_for_user"), list) else [],
            next_round_focus=data.get("next_round_focus") if isinstance(data.get("next_round_focus"), list) else [],
        )
```

Then adjust `start_round` so `_pending_events` are yielded immediately after `_stream_role` returns. The implementation must not leave `role_started`/`role_delta` buffered until after completion; tests should assert event order. If the first pass uses this simple pending list, refactor before marking the task complete.

- [ ] **Step 4: Refactor streaming helper to yield events correctly**

Replace `_stream_role` with an async generator returning deltas and final content through the parent loop:

```python
async def _run_role(self, state: RoundtableGraphState, agent_id: str) -> AsyncIterator[dict[str, str]]:
    agent = get_agent(agent_id)
    content_parts: list[str] = []
    yield round_event("role_started", {...})
    async for delta in self.llm_client.chat_stream(...):
        content_parts.append(delta)
        yield round_event("role_delta", {...})
    content = "".join(content_parts).strip()
    state.role_outputs.append(RoundtableRoleOutput(...))
    yield round_event("role_completed", {...})
```

Update `start_round`:

```python
for agent_id in state.participants:
    async for event in self._run_role(state, agent_id):
        yield event
```

- [ ] **Step 5: Verify tests pass**

Run:

```bash
cd shadowlink-ai
.venv311/bin/python -m pytest tests/unit/jarvis/test_schedule_coord_graph.py -q
```

Expected: tests pass.

---

## Task 3: Router Dispatch For `schedule_coord`

**Files:**
- Modify: `shadowlink-ai/app/api/v1/jarvis_router.py`
- Test: `shadowlink-ai/tests/unit/jarvis/test_schedule_coord_graph.py`

- [ ] **Step 1: Write failing router test**

Add:

```python
import asyncio

from app.api.v1 import jarvis_router


def test_schedule_coord_uses_graph_dispatch(monkeypatch):
    called = {"value": False}

    async def fake_stream(*args, **kwargs):
        called["value"] = True
        yield {"event": "user_checkpoint", "data": "{}"}

    monkeypatch.setattr(jarvis_router, "_run_schedule_coord_graph_round", fake_stream)

    async def collect():
        events = []
        async for event in jarvis_router._run_graph_or_legacy_round(
            llm_client=None,
            session_id="rt-schedule-dispatch",
            scenario_id="schedule_coord",
            scenario_name="今日日程协调",
            scenario_icon="📅",
            participants=["maxwell", "nora", "mira", "alfred"],
            opening_prompt="",
            profile_prefix="",
            context_prefix="",
            phase_label="open",
            mode="decision",
            initial_user_input="帮我协调今天",
            decision_context={"date": "2026-04-30"},
        ):
            events.append(event)
        return events

    events = asyncio.run(collect())

    assert called["value"] is True
    assert events[-1]["event"] == "user_checkpoint"
```

- [ ] **Step 2: Run and verify failure**

Run:

```bash
cd shadowlink-ai
.venv311/bin/python -m pytest tests/unit/jarvis/test_schedule_coord_graph.py::test_schedule_coord_uses_graph_dispatch -q
```

Expected: `_run_graph_or_legacy_round` does not exist.

- [ ] **Step 3: Add dispatch wrapper**

In `jarvis_router.py`, add:

```python
async def _run_graph_or_legacy_round(**kwargs):
    if kwargs.get("scenario_id") == "schedule_coord":
        async for event in _run_schedule_coord_graph_round(**kwargs):
            yield event
        return
    async for event in _run_roundtable_round(**kwargs):
        yield event
```

Add:

```python
async def _run_schedule_coord_graph_round(**kwargs):
    from app.jarvis.schedule_coord_graph import ScheduleCoordGraphExecutor

    executor = ScheduleCoordGraphExecutor(llm_client=kwargs["llm_client"])
    async for event in executor.start_round(
        session_id=kwargs["session_id"],
        user_goal=kwargs.get("initial_user_input") or "",
        context=kwargs.get("decision_context") or {},
    ):
        yield event
```

Update `start_roundtable` and `continue_roundtable` call sites to call `_run_graph_or_legacy_round` instead of `_run_roundtable_round`.

- [ ] **Step 4: Verify dispatch test passes**

Run:

```bash
cd shadowlink-ai
.venv311/bin/python -m pytest tests/unit/jarvis/test_schedule_coord_graph.py::test_schedule_coord_uses_graph_dispatch -q
```

Expected: pass.

---

## Task 4: User Checkpoint Resume And Finalize Semantics

**Files:**
- Modify: `shadowlink-ai/app/api/v1/jarvis_router.py`
- Modify: `shadowlink-ai/app/jarvis/schedule_coord_graph.py`
- Test: `shadowlink-ai/tests/unit/jarvis/test_schedule_coord_graph.py`

- [ ] **Step 1: Extend continue request behavior without changing request schema**

Use existing `RoundtableContinueRequest.user_message`.

Interpret:
- Message starts with `/finalize` or equals `finalize` / `收敛` / `直接结论`: finalize.
- Otherwise: treat as user feedback and run next graph round.

No new endpoint for first version.

- [ ] **Step 2: Write failing tests**

Add:

```python
@pytest.mark.asyncio
async def test_schedule_coord_continue_feedback_runs_next_round():
    executor = ScheduleCoordGraphExecutor(llm_client=FakeStreamingLLM())
    events = []

    async for event in executor.continue_round(
        session_id="rt-schedule-1",
        user_goal="帮我协调今天日程",
        context={"calendar_events": []},
        feedback_history=["我更想保护上午深度工作"],
        round_index=2,
    ):
        events.append(event)

    payload = json.loads(events[0]["data"])
    assert events[0]["event"] == "round_started"
    assert payload["round_index"] == 2
    assert events[-1]["event"] == "user_checkpoint"


@pytest.mark.asyncio
async def test_schedule_coord_finalize_emits_final_result():
    executor = ScheduleCoordGraphExecutor(llm_client=FakeStreamingLLM())
    events = []

    async for event in executor.finalize(
        session_id="rt-schedule-1",
        user_goal="帮我协调今天日程",
        context={"date": "2026-04-30"},
        feedback_history=["直接收敛"],
    ):
        events.append(event)

    names = [event["event"] for event in events]
    assert "final_result" in names
    assert "decision_result" in names
    assert names[-1] == "done"
```

- [ ] **Step 3: Implement `continue_round` and `finalize`**

In `ScheduleCoordGraphExecutor`:

```python
async def continue_round(...):
    async for event in self.start_round(...):
        yield event

async def finalize(...):
    result = await self._build_final_result(...)
    yield round_event("final_result", result)
    yield round_event("decision_result", result)
    yield round_event("done", {"phase": "round_complete", "session_id": session_id, "scenario_id": "schedule_coord"})
```

`_build_final_result` must produce existing decision fields:

```python
{
    "id": f"rt_result_{session_id}",
    "session_id": session_id,
    "mode": "decision",
    "status": "draft",
    "summary": "...",
    "options": [...],
    "recommended_option": "...",
    "tradeoffs": [...],
    "actions": [...],
    "handoff_target": "maxwell",
    "context": {...},
}
```

- [ ] **Step 4: Persist final result**

In router helper `_run_schedule_coord_graph_round`, when receiving `decision_result`, call existing `save_roundtable_result` before yielding it, matching `_run_roundtable_round`.

- [ ] **Step 5: Verify tests**

Run:

```bash
cd shadowlink-ai
.venv311/bin/python -m pytest tests/unit/jarvis/test_schedule_coord_graph.py tests/unit/jarvis/test_roundtable_decision.py -q
```

Expected: pass.

---

## Task 5: Frontend Streaming Bubble And Round Summary UI

**Files:**
- Modify: `shadowlink-web/src/components/jarvis/RoundtableStage.tsx`
- Modify: `shadowlink-web/src/services/jarvisApi.ts` if exported types are needed

- [ ] **Step 1: Add frontend state types**

In `RoundtableStage.tsx`, add:

```ts
interface RoundSummaryPayload {
  round_index: number;
  minutes: Array<{ agent_id: string; summary: string }>;
  consensus: string[];
  disagreements: string[];
  questions_for_user: string[];
  next_round_focus: string[];
}

interface RoleDeltaPayload {
  agent_id: string;
  delta: string;
  round_index: number;
}
```

Add state:

```ts
const [roundSummaries, setRoundSummaries] = useState<RoundSummaryPayload[]>([]);
const [waitingForCheckpoint, setWaitingForCheckpoint] = useState(false);
```

- [ ] **Step 2: Handle new events**

In `handleFrame`:

```ts
if (event === "round_started") {
  setWaitingForCheckpoint(false);
  setCurrentContent("");
  setActiveAgentId(null);
  return;
}

if (event === "role_started") {
  const payload = data as SpeakPayload;
  setActiveAgentId(payload.agent_id);
  setCurrentContent("");
  setUserBubble(null);
  return;
}

if (event === "role_delta") {
  const payload = data as RoleDeltaPayload;
  setActiveAgentId(payload.agent_id);
  setCurrentContent((prev) => prev + payload.delta);
  return;
}

if (event === "role_completed") {
  const payload = data as TokenPayload;
  setTranscript((prev) => [...prev, {/* same agent transcript shape */}]);
  setTimeout(() => {
    setActiveAgentId((current) => current === payload.agent_id ? null : current);
    setCurrentContent("");
  }, 450);
  return;
}

if (event === "round_summary") {
  setRoundSummaries((prev) => [...prev, data as RoundSummaryPayload]);
  return;
}

if (event === "user_checkpoint") {
  setWaitingForCheckpoint(true);
  setStatus("idle");
  setPhase("等待你的判断");
  return;
}
```

- [ ] **Step 3: Render round summary cards**

Below the stage body, render the latest summary:

```tsx
{roundSummaries.length > 0 && (
  <div className="round-summary-panel">
    <h3>第 {latest.round_index} 轮纪要</h3>
    <section>纪要...</section>
    <section>共识...</section>
    <section>分歧...</section>
    <section>需要你判断...</section>
  </div>
)}
```

Use existing visual style; do not add nested cards inside cards.

- [ ] **Step 4: Add checkpoint controls**

Near the existing user input:

```tsx
<button onClick={() => setUserDraft("继续讨论")}>继续讨论</button>
<button onClick={() => setUserDraft("直接收敛")}>直接收敛</button>
```

Keep free text input so the user can add feedback.

- [ ] **Step 5: Build frontend**

Run:

```bash
cd shadowlink-web
npm run build
```

Expected: build passes.

---

## Task 6: Persistence, Acceptance, And Regression

**Files:**
- Modify: `shadowlink-ai/app/api/v1/jarvis_router.py`
- Test: `shadowlink-ai/tests/unit/jarvis/test_schedule_coord_graph.py`
- Test: `shadowlink-ai/tests/integration/test_jarvis_api.py`

- [ ] **Step 1: Add persistence test for final decision**

Add:

```python
def test_schedule_coord_final_result_can_be_accepted():
    # Save a graph-produced decision result with handoff_target=maxwell.
    # Call accept_roundtable_decision.
    # Assert it creates pending calendar.add and direct_calendar_mutation is False.
```

Use the existing pattern in `tests/unit/jarvis/test_roundtable_decision.py::test_accept_decision_creates_pending_action_without_calendar_mutation`.

- [ ] **Step 2: Ensure round summaries persist in result context**

When finalizing, put:

```python
"round_summaries": [summary.to_dict() for summary in state.round_summaries],
"user_feedback_history": feedback_history,
"graph_executor": "schedule_coord_langgraph_v1"
```

inside `context`.

- [ ] **Step 3: Verify focused backend tests**

Run:

```bash
cd shadowlink-ai
.venv311/bin/python -m pytest \
  tests/unit/jarvis/test_schedule_coord_graph.py \
  tests/unit/jarvis/test_roundtable_decision.py \
  tests/integration/test_jarvis_api.py -q
```

Expected: pass.

- [ ] **Step 4: Verify wider Jarvis tests**

Run:

```bash
cd shadowlink-ai
.venv311/bin/python -m pytest tests/unit/jarvis -q
```

Expected: pass. Existing `snapshot_context()` pending task warnings may still appear; treat them as existing warnings unless tests fail.

- [ ] **Step 5: Compile and diff checks**

Run:

```bash
cd shadowlink-ai
.venv311/bin/python -m compileall -q app/jarvis/roundtable_graph.py app/jarvis/schedule_coord_graph.py app/api/v1/jarvis_router.py tests/unit/jarvis/test_schedule_coord_graph.py
```

Run:

```bash
cd ..
git diff --check
```

Expected: no output from both commands.

---

## Non-Goals

- Do not migrate `study_energy_decision` yet.
- Do not migrate `local_lifestyle` yet.
- Do not redesign all roundtable frontend visuals.
- Do not expose hidden chain-of-thought.
- Do not allow schedule graph to directly mutate calendar.
- Do not remove legacy `_run_roundtable_round`; other scenarios still use it.

---

## Acceptance Criteria

- User can open the existing `今日日程协调` scene card.
- Maxwell, Nora, Mira, and Alfred each show a live speech bubble while speaking.
- Each role bubble disappears after that role completes.
- After one round, the UI shows public minutes, consensus, disagreements, and questions for the user.
- User can add feedback and continue to another round.
- User can ask to finalize and receive a persisted `decision_result`.
- Accepting the final result creates a pending confirmation action, not a direct calendar mutation.
- Other five scenario cards keep their current behavior.
- Backend and frontend verification commands pass.
