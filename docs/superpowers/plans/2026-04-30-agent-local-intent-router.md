# Agent Local Intent Router Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic agent-local intent and slot router that plans current-agent tool use before the normal LLM tool prompt.

**Architecture:** Create `app.jarvis.intent_router` with a small `AgentIntentDecision` dataclass and `plan_agent_intent()` function. Integrate it into `chat_with_agent()` after local time context is available, execute planned tools through the existing `execute_tool_calls()` path, and inject planned intent/tool results into the primary agent prompt.

**Tech Stack:** Python 3.11, FastAPI, pytest, existing Jarvis tool runtime and private chat pipeline.

---

## File Structure

- Create `shadowlink-ai/app/jarvis/intent_router.py`
  - Owns intent catalogs, slot extraction, and planned tool-call decisions.
- Create `shadowlink-ai/tests/unit/jarvis/test_intent_router.py`
  - Unit tests for per-agent intent and slot extraction.
- Modify `shadowlink-ai/app/api/v1/jarvis_router.py`
  - Executes planned tool calls before final LLM response.
  - Injects intent context and tool result summaries into prompt.
- Modify `shadowlink-ai/tests/unit/jarvis/test_agent_intent_pipeline.py`
  - Pipeline tests for planned tool execution and pending confirmation behavior.

---

### Task 1: Intent Router Unit Tests

**Files:**
- Create: `shadowlink-ai/tests/unit/jarvis/test_intent_router.py`
- Test: `shadowlink-ai/tests/unit/jarvis/test_intent_router.py`

- [ ] **Step 1: Add failing router tests**

```python
from datetime import datetime

from app.jarvis.intent_router import plan_agent_intent


NOW = datetime(2026, 4, 30, 10, 0, 0)


def test_maxwell_complete_calendar_create_extracts_slots():
    decision = plan_agent_intent("maxwell", "明天下午 3 点提醒我复习英语 1 小时", local_now=NOW)

    assert decision.intent == "calendar_create"
    assert decision.tool_name == "jarvis_calendar_add"
    assert decision.next_action == "pending_confirmation"
    assert decision.slots["title"] == "复习英语"
    assert decision.slots["start"].startswith("2026-05-01T15:00:00")
    assert decision.slots["end"].startswith("2026-05-01T16:00:00")
    assert decision.missing_slots == []


def test_maxwell_calendar_create_missing_time_asks_slots():
    decision = plan_agent_intent("maxwell", "帮我安排复习英语", local_now=NOW)

    assert decision.intent == "calendar_create"
    assert decision.tool_name == "jarvis_calendar_add"
    assert decision.next_action == "ask_missing_slots"
    assert "start" in decision.missing_slots
    assert "end" in decision.missing_slots


def test_maxwell_long_term_study_plan_decomposes_task():
    decision = plan_agent_intent("maxwell", "我想一个月内准备完雅思第一轮", local_now=NOW)

    assert decision.intent == "task_decompose"
    assert decision.tool_name == "jarvis_task_plan_decompose"
    assert decision.next_action == "call_tool"
    assert decision.slots["user_request"] == "我想一个月内准备完雅思第一轮"


def test_nora_meal_plan_extracts_dinner_and_recovery_goal():
    decision = plan_agent_intent("nora", "今晚很累，吃什么比较撑得住？", local_now=NOW)

    assert decision.intent == "meal_plan"
    assert decision.tool_name == "jarvis_meal_plan"
    assert decision.next_action == "call_tool"
    assert decision.slots["meals"] == ["dinner"]
    assert decision.slots["goal"] == "stress_recovery"


def test_nora_caffeine_guard_defaults_to_coffee():
    decision = plan_agent_intent("nora", "咖啡现在还能喝吗？", local_now=NOW)

    assert decision.intent == "caffeine_guard"
    assert decision.tool_name == "jarvis_caffeine_cutoff_guard"
    assert decision.next_action == "call_tool"
    assert decision.slots["beverage_name"] == "coffee"


def test_nora_nutrition_lookup_missing_food_name_asks():
    decision = plan_agent_intent("nora", "帮我查一下这个营养怎么样", local_now=NOW)

    assert decision.intent == "nutrition_lookup"
    assert decision.next_action == "ask_missing_slots"
    assert decision.missing_slots == ["food_name"]


def test_mira_anxiety_maps_to_breathing_protocol():
    decision = plan_agent_intent("mira", "我焦虑得有点喘不过气", local_now=NOW)

    assert decision.intent == "breathing_protocol"
    assert decision.tool_name == "jarvis_breathing_protocol"
    assert decision.next_action == "call_tool"
    assert decision.slots["goal"] == "calm_down"


def test_mira_checkin_schedule_extracts_tomorrow_delay():
    decision = plan_agent_intent("mira", "明天回访一下我的状态", local_now=NOW)

    assert decision.intent == "checkin_schedule"
    assert decision.tool_name == "jarvis_checkin_schedule"
    assert decision.next_action == "pending_confirmation"
    assert decision.slots["delay_hours"] == 24


def test_leo_weekend_activity_maps_to_local_activities():
    decision = plan_agent_intent("leo", "周末有什么低负担活动推荐？", local_now=NOW)

    assert decision.intent == "local_activities"
    assert decision.tool_name == "jarvis_local_activities"
    assert decision.next_action == "call_tool"


def test_leo_plan_activity_slot_missing_time_asks():
    decision = plan_agent_intent("leo", "把散步安排进日程", local_now=NOW)

    assert decision.intent == "plan_activity_slot"
    assert decision.tool_name == "jarvis_plan_activity_slot"
    assert decision.next_action == "ask_missing_slots"
    assert "start" in decision.missing_slots


def test_tool_outside_agent_whitelist_is_not_planned():
    decision = plan_agent_intent("mira", "今晚吃什么比较好？", local_now=NOW)

    assert decision.intent == "chat_only"
    assert decision.tool_name is None


def test_small_talk_is_chat_only():
    decision = plan_agent_intent("nora", "你好呀，今天还不错", local_now=NOW)

    assert decision.intent == "chat_only"
    assert decision.next_action == "chat_only"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd /Users/ohmorimotoki/Downloads/Jarvis\ Life\ v3/shadowlink-ai
.venv311/bin/python -m pytest tests/unit/jarvis/test_intent_router.py -q
```

Expected: FAIL because `app.jarvis.intent_router` does not exist.

---

### Task 2: Implement `intent_router.py`

**Files:**
- Create: `shadowlink-ai/app/jarvis/intent_router.py`
- Test: `shadowlink-ai/tests/unit/jarvis/test_intent_router.py`

- [ ] **Step 1: Add minimal router implementation**

Implement:

- `AgentIntentDecision`
- `plan_agent_intent(agent_id, message, local_now=None)`
- whitelist guard via `get_allowed_tool_names()`
- lightweight Chinese time parsing for today/tomorrow/tonight/afternoon hour
- per-agent rules from the spec

- [ ] **Step 2: Run router tests**

Run:

```bash
cd /Users/ohmorimotoki/Downloads/Jarvis\ Life\ v3/shadowlink-ai
.venv311/bin/python -m pytest tests/unit/jarvis/test_intent_router.py -q
```

Expected: PASS.

- [ ] **Step 3: Commit router**

```bash
git add shadowlink-ai/app/jarvis/intent_router.py shadowlink-ai/tests/unit/jarvis/test_intent_router.py
git commit -m "feat: add agent local intent router"
```

---

### Task 3: Pipeline Tests For Planned Tool Execution

**Files:**
- Create: `shadowlink-ai/tests/unit/jarvis/test_agent_intent_pipeline.py`
- Test: `shadowlink-ai/tests/unit/jarvis/test_agent_intent_pipeline.py`

- [ ] **Step 1: Add fake registry and fake LLM pipeline tests**

Add tests that:

- register a fake `jarvis_meal_plan` handler
- assert Nora planned meal tool executes before final reply
- register fake `jarvis_calendar_add` with `requires_confirmation=True`
- assert Maxwell calendar intent returns a pending `calendar.add` action and keeps `agent_id=maxwell`
- assert small talk executes no planned tools

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd /Users/ohmorimotoki/Downloads/Jarvis\ Life\ v3/shadowlink-ai
.venv311/bin/python -m pytest tests/unit/jarvis/test_agent_intent_pipeline.py -q
```

Expected: FAIL because `chat_with_agent()` does not execute planned intent tools yet.

---

### Task 4: Integrate Router Into `chat_with_agent()`

**Files:**
- Modify: `shadowlink-ai/app/api/v1/jarvis_router.py`
- Test: `shadowlink-ai/tests/unit/jarvis/test_agent_intent_pipeline.py`

- [ ] **Step 1: Import and call intent router**

After `local_now` is available, call:

```python
from app.jarvis.intent_router import format_intent_prompt_prefix, plan_agent_intent

intent_decision = plan_agent_intent(routed_agent_id, req.message, local_now=local_now)
```

- [ ] **Step 2: Execute planned tools when applicable**

Before `run_agent_turn()`, if `intent_decision.next_action in {"call_tool", "pending_confirmation"}` and `tool_name` exists, call:

```python
planned_tool_results = await execute_tool_calls(
    routed_agent_id,
    [{"tool_name": intent_decision.tool_name, "arguments": intent_decision.slots}],
)
```

- [ ] **Step 3: Inject planned intent context**

Add a prompt prefix containing:

- intent name
- planned tool
- missing slots instruction, if any
- formatted tool results, if any

If planned tool results exist, instruct the LLM to answer naturally from those results and not emit duplicate tool blocks.

- [ ] **Step 4: Merge planned tool results with LLM-emitted tool results**

After `run_agent_turn()`, combine:

```python
all_tool_results = [*planned_tool_results, *tool_results]
action_results = [*care_actions, *consult_result.actions, *to_action_results(all_tool_results)]
```

- [ ] **Step 5: Run pipeline tests**

Run:

```bash
cd /Users/ohmorimotoki/Downloads/Jarvis\ Life\ v3/shadowlink-ai
.venv311/bin/python -m pytest tests/unit/jarvis/test_agent_intent_pipeline.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit integration**

```bash
git add shadowlink-ai/app/api/v1/jarvis_router.py shadowlink-ai/tests/unit/jarvis/test_agent_intent_pipeline.py
git commit -m "feat: execute planned agent intent tools"
```

---

### Task 5: Full Verification

**Files:**
- Verify only unless fixes are required.

- [ ] **Step 1: Run focused tests**

```bash
cd /Users/ohmorimotoki/Downloads/Jarvis\ Life\ v3/shadowlink-ai
.venv311/bin/python -m pytest tests/unit/jarvis/test_intent_router.py tests/unit/jarvis/test_agent_intent_pipeline.py tests/unit/jarvis/test_agent_consultation.py -q
```

Expected: PASS.

- [ ] **Step 2: Run nearby Jarvis tests**

```bash
cd /Users/ohmorimotoki/Downloads/Jarvis\ Life\ v3/shadowlink-ai
.venv311/bin/python -m pytest tests/unit/jarvis/test_intent_router.py tests/unit/jarvis/test_agent_intent_pipeline.py tests/unit/jarvis/test_agent_consultation.py tests/unit/jarvis/test_persistence.py tests/unit/jarvis/test_escalation.py -q
```

Expected: PASS.

- [ ] **Step 3: Run frontend build**

```bash
cd /Users/ohmorimotoki/Downloads/Jarvis\ Life\ v3/shadowlink-web
npm run build
```

Expected: PASS.

- [ ] **Step 4: Inspect git status**

```bash
git -C /Users/ohmorimotoki/Downloads/Jarvis\ Life\ v3 status --short --branch
```

Expected: clean working tree.

