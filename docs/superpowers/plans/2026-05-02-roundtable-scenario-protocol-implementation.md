# Roundtable Scenario Protocol Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the six preset roundtable scenarios scenario-specific meeting protocols without breaking the shared roundtable runtime, then verify the new logic with focused unit tests.

**Architecture:** Add one shared protocol registry for all roundtable scenarios, then teach each scenario executor to read its protocol for phase order, role instructions, tool policy, and final result contract. Keep the shared `RoundtableGraphState`, SSE events, tool decision runtime, and persistence paths unchanged.

**Tech Stack:** Python 3.11, FastAPI, pytest, langgraph, existing `app.jarvis` runtime helpers.

---

### Task 1: Add scenario protocol registry and coverage tests

**Files:**
- Create: `shadowlink-ai/app/jarvis/roundtable_protocols.py`
- Create: `shadowlink-ai/tests/unit/jarvis/test_roundtable_protocols.py`

- [ ] **Step 1: Write the failing test**

```python
from app.jarvis.roundtable_protocols import get_roundtable_protocol


def test_all_scenarios_have_protocols():
    scenarios = [
        "schedule_coord",
        "study_energy_decision",
        "local_lifestyle",
        "emotional_care",
        "weekend_recharge",
        "work_brainstorm",
    ]

    protocols = [get_roundtable_protocol(s) for s in scenarios]

    assert [p.scenario_id for p in protocols] == scenarios
    assert [p.mode for p in protocols] == ["decision", "decision", "brainstorm", "brainstorm", "brainstorm", "brainstorm"]
    assert protocols[0].phases[0].id == "context_scan"
    assert protocols[1].phases[-1].id == "decision"
    assert protocols[5].phases[0].id == "frame_problem"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd shadowlink-ai && .venv311/bin/python -m pytest tests/unit/jarvis/test_roundtable_protocols.py -q`

Expected: FAIL with `ModuleNotFoundError` or missing symbol error for `roundtable_protocols`.

- [ ] **Step 3: Write minimal implementation**

```python
from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class RoundtableProtocolPhase:
    id: str
    title: str
    owner_agent: str | None
    objective: str
    role_instructions: dict[str, str]


@dataclass(frozen=True)
class ScenarioProtocol:
    scenario_id: str
    mode: Literal["decision", "brainstorm"]
    phases: list[RoundtableProtocolPhase]
    tool_policy: dict[str, Any]
    result_contract: dict[str, Any]
    safety_rules: list[str]
    handoff_target: str


def get_roundtable_protocol(scenario_id: str) -> ScenarioProtocol:
    try:
        return _SCENARIO_PROTOCOLS[scenario_id]
    except KeyError as exc:
        raise KeyError(f"Unknown roundtable scenario: {scenario_id!r}") from exc
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd shadowlink-ai && .venv311/bin/python -m pytest tests/unit/jarvis/test_roundtable_protocols.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add shadowlink-ai/app/jarvis/roundtable_protocols.py shadowlink-ai/tests/unit/jarvis/test_roundtable_protocols.py
git commit -m "feat(jarvis): add roundtable scenario protocol registry"
```

### Task 2: Wire protocols into the six scenario executors

**Files:**
- Modify: `shadowlink-ai/app/jarvis/schedule_coord_graph.py`
- Modify: `shadowlink-ai/app/jarvis/study_energy_decision_graph.py`
- Modify: `shadowlink-ai/app/jarvis/local_lifestyle_graph.py`
- Modify: `shadowlink-ai/app/jarvis/emotional_care_graph.py`
- Modify: `shadowlink-ai/app/jarvis/weekend_recharge_graph.py`
- Modify: `shadowlink-ai/app/jarvis/work_brainstorm_graph.py`
- Modify: `shadowlink-ai/tests/unit/jarvis/test_schedule_coord_graph.py`
- Modify: `shadowlink-ai/tests/unit/jarvis/test_study_energy_decision_graph.py`
- Modify: `shadowlink-ai/tests/unit/jarvis/test_local_lifestyle_graph.py`
- Modify: `shadowlink-ai/tests/unit/jarvis/test_emotional_care_graph.py`
- Modify: `shadowlink-ai/tests/unit/jarvis/test_weekend_recharge_graph.py`
- Modify: `shadowlink-ai/tests/unit/jarvis/test_work_brainstorm_graph.py`

- [ ] **Step 1: Write the failing tests**

```python
class PromptRecorderLLM:
    def __init__(self, response: str):
        self.response = response
        self.messages: list[str] = []

    async def chat_stream(self, message: str, **kwargs):
        self.messages.append(message)
        yield "ok"

    async def chat(self, message: str, **kwargs):
        self.messages.append(message)
        return self.response


def test_schedule_coord_prompt_uses_protocol_phase():
    llm = PromptRecorderLLM(
        json.dumps(
            {
                "minutes": [],
                "consensus": [],
                "disagreements": [],
                "questions_for_user": [],
                "next_round_focus": [],
            }
        )
    )

    executor = ScheduleCoordGraphExecutor(llm_client=llm)
    asyncio.run(
        executor.start_round(
            session_id="rt-protocol-schedule",
            user_goal="帮我协调今天日程",
            context={"calendar_events": []},
        ).__anext__()
    )

    assert any("context_scan" in message for message in llm.messages)
    assert any("schedule conflict" in message or "冲突" in message for message in llm.messages)


def test_work_brainstorm_prompt_uses_workshop_protocol():
    llm = PromptRecorderLLM(
        json.dumps(
            {
                "minutes": [],
                "consensus": [],
                "disagreements": [],
                "questions_for_user": [],
                "next_round_focus": [],
            }
        )
    )

    executor = WorkBrainstormGraphExecutor(llm_client=llm)
    asyncio.run(
        executor.start_round(
            session_id="rt-protocol-work",
            user_goal="帮我头脑风暴一个 demo",
            context={"previous_discussion": ""},
        ).__anext__()
    )

    assert any("frame_problem" in message for message in llm.messages)
    assert any("validation_plan" in message for message in llm.messages)
```

- [ ] **Step 2: Run test to verify it fails**

Run:
`cd shadowlink-ai && .venv311/bin/python -m pytest tests/unit/jarvis/test_schedule_coord_graph.py tests/unit/jarvis/test_study_energy_decision_graph.py tests/unit/jarvis/test_local_lifestyle_graph.py tests/unit/jarvis/test_emotional_care_graph.py tests/unit/jarvis/test_weekend_recharge_graph.py tests/unit/jarvis/test_work_brainstorm_graph.py -q`

Expected: FAIL because executors do not yet read protocol objects or emit phase-specific prompts.

- [ ] **Step 3: Write minimal implementation**

```python
from app.jarvis.roundtable_protocols import get_roundtable_protocol


protocol = get_roundtable_protocol("schedule_coord")
phase = protocol.phases[min(state.round_index - 1, len(protocol.phases) - 1)]
prompt = (
    f"## {phase.title}\n"
    f"phase_id: {phase.id}\n"
    f"objective: {phase.objective}\n"
    f"role_instruction: {phase.role_instructions.get(agent_id, '')}\n"
    f"previous_roles: {previous}\n"
    f"feedback_history: {feedback}\n"
)
```

- [ ] **Step 4: Run test to verify it passes**

Run:
`cd shadowlink-ai && .venv311/bin/python -m pytest tests/unit/jarvis/test_schedule_coord_graph.py tests/unit/jarvis/test_study_energy_decision_graph.py tests/unit/jarvis/test_local_lifestyle_graph.py tests/unit/jarvis/test_emotional_care_graph.py tests/unit/jarvis/test_weekend_recharge_graph.py tests/unit/jarvis/test_work_brainstorm_graph.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add shadowlink-ai/app/jarvis/*_graph.py shadowlink-ai/tests/unit/jarvis/test_*_graph.py
git commit -m "feat(jarvis): apply scenario protocols to roundtable executors"
```

### Task 3: Keep roundtable API contract aligned with protocol behavior

**Files:**
- Modify: `docs/解耦接口说明/roundtable-api-contract.md`
- Modify: `docs/解耦接口说明/frontend-decoupling-developer-guide.md`

- [ ] **Step 1: Write the failing test**

```python
def test_contract_mentions_scenario_protocols():
    text = Path("docs/解耦接口说明/roundtable-api-contract.md").read_text(encoding="utf-8")
    assert "ScenarioProtocol" in text
    assert "crossfire" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd shadowlink-ai && .venv311/bin/python -m pytest tests/unit/jarvis/test_roundtable_protocols.py -q`

Expected: FAIL until the docs mention the new protocol layer.

- [ ] **Step 3: Write minimal implementation**

```md
- 六个场景使用 `ScenarioProtocol`。
- `crossfire` 作为场景级阶段约束写入协议说明。
- `work_brainstorm` 继续保持 brainstorm mode，但拥有自己的 workshop 阶段。
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd shadowlink-ai && .venv311/bin/python -m pytest tests/unit/jarvis/test_roundtable_protocols.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add docs/解耦接口说明/roundtable-api-contract.md docs/解耦接口说明/frontend-decoupling-developer-guide.md
git commit -m "docs: align roundtable contract with scenario protocols"
```

### Task 4: Run detailed logic tests and lock in behavior

**Files:**
- Modify: `shadowlink-ai/tests/unit/jarvis/test_roundtable_protocols.py`
- Modify: `shadowlink-ai/tests/unit/jarvis/test_roundtable_decision.py`
- Modify: `shadowlink-ai/tests/unit/jarvis/test_intent_router.py`

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.parametrize(
    "scenario_id, expected_mode, expected_handoff",
    [
        ("schedule_coord", "decision", "maxwell"),
        ("study_energy_decision", "decision", "maxwell"),
        ("local_lifestyle", "brainstorm", "maxwell"),
        ("emotional_care", "brainstorm", "mira"),
        ("weekend_recharge", "brainstorm", "maxwell"),
        ("work_brainstorm", "brainstorm", "maxwell"),
    ],
)
def test_every_protocol_has_expected_mode_and_handoff(scenario_id, expected_mode, expected_handoff):
    protocol = get_roundtable_protocol(scenario_id)
    assert protocol.mode == expected_mode
    assert protocol.handoff_target == expected_handoff
    assert len(protocol.phases) >= 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd shadowlink-ai && .venv311/bin/python -m pytest tests/unit/jarvis/test_roundtable_protocols.py -q`

Expected: FAIL if any scenario protocol is missing or misclassified.

- [ ] **Step 3: Write minimal implementation**

```python
# Keep the existing behavior:
# - decision mode for schedule_coord and study_energy_decision
# - brainstorm mode for the other four
# - no direct calendar mutation from roundtable acceptance
# - every scenario still yields a round summary and user checkpoint before finalize
```

- [ ] **Step 4: Run test to verify it passes**

Run:
`cd shadowlink-ai && .venv311/bin/python -m pytest tests/unit/jarvis/test_roundtable_protocols.py tests/unit/jarvis/test_roundtable_decision.py tests/unit/jarvis/test_intent_router.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add shadowlink-ai/tests/unit/jarvis/test_roundtable_protocols.py shadowlink-ai/tests/unit/jarvis/test_roundtable_decision.py shadowlink-ai/tests/unit/jarvis/test_intent_router.py
git commit -m "test(jarvis): lock roundtable scenario protocol behavior"
```
