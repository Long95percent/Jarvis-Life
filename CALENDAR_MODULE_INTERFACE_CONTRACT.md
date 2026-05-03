# Calendar Module Interface Contract

> Version: `calendar-contract.v1`  
> Date: 2026-05-01  
> Scope: Jarvis / Maxwell calendar, long-term plan, schedule coordination, conflict resolution, reschedule proposal flow  
> Purpose: This document is the boundary contract for future calendar development. Frontend, Agent skills, backend services, and persistence must communicate only through the interfaces defined here.

## 1. Why This Contract Exists

The calendar module currently mixes responsibilities across UI, API router, Agent logic, persistence, and calendar adapter. This caused real product failures:

- Frontend buttons directly changed final dates.
- Conflict resolution could move tasks into the past.
- Conflict UI allowed users to ignore conflicts.
- Long-term plan days polluted task list views.
- LLM-generated reschedule results could be applied directly without a proposal selection layer.
- Frontend and backend shared implicit assumptions instead of stable contracts.

This contract makes the calendar module an isolated scheduling subsystem. Other modules may request scheduling work, but they must not know or mutate internal calendar state directly.

## 2. Core Boundary Rule

No caller outside the calendar module may directly decide final schedule placement.

Allowed:

```text
Frontend / Agent / Other module -> Calendar interface -> proposal or command -> Calendar module validates -> Calendar module writes
```

Forbidden:

```text
Frontend computes final date -> writes plan day
Agent writes DB directly
Other module mutates plan_days/calendar_events
LLM output is applied without deterministic validation
```

## 3. Module Ownership

### 3.1 Calendar Module Owns

- Long-term plans.
- Plan days.
- Calendar projections.
- Schedule conflicts.
- Free windows.
- Reschedule proposals.
- Proposal execution.
- Calendar-related audit events.
- Maxwell workbench schedule push.

### 3.2 Calendar Module Does Not Own

- Chat UI rendering.
- Agent routing policy outside schedule intents.
- User profile location/timezone storage.
- Weather lookup.
- General settings / API key management.
- LLM provider configuration.
- Memory / RAG / mood systems.

These modules can provide context, but cannot directly change schedule state.

## 4. Layered Architecture

```text
[Frontend UI]
    |
    | Calendar HTTP Contract only
    v
[Calendar API Facade]
    |
    | typed commands / queries
    v
[Calendar Application Services]
    |-- PlanService
    |-- PlanDayService
    |-- CalendarProjectionService
    |-- AvailabilityService
    |-- ScheduleProposalService
    |-- ScheduleExecutionService
    |
    v
[Deterministic Planner Guard]
    |
    | validates hard constraints
    v
[Persistence + Calendar Adapter]

[Agent / Maxwell Skill]
    |
    | structured JSON proposals only
    v
[Secretary Scheduler Adapter]
    |
    | parsed and validated by Calendar module
    v
[ScheduleProposalService]
```

## 5. Required Backend Package Boundary

Future implementation should converge to this package layout:

```text
shadowlink-ai/app/jarvis/calendar/
  __init__.py
  contracts.py
  facade.py
  guard.py
  availability.py
  plans.py
  plan_days.py
  projection.py
  proposals.py
  secretary_adapter.py
  repository.py
```

### 5.1 `contracts.py`

Defines all Pydantic models used at module boundaries.

No persistence calls. No LLM calls.

### 5.2 `facade.py`

Single service entry point for API router, Agent tools, and proactive routines.

External callers should use facade functions only.

### 5.3 `guard.py`

Deterministic validation:

- No past dates.
- No invalid time ranges.
- No overlap with fixed items.
- No duplicate same-plan items.
- No unknown item refs.
- No direct LLM trust.

No database writes.

### 5.4 `availability.py`

Builds calendar items, conflicts, and free windows.

Does not mutate state.

### 5.5 `plans.py`

Owns long-term plan CRUD and high-level plan list rules.

Important rule:

- `list_planner_tasks` must show long-term plans as one task.
- It must not expose decomposed plan days as top-level tasks.

### 5.6 `plan_days.py`

Owns plan day CRUD and status transitions.

It cannot directly run LLM.

### 5.7 `projection.py`

Owns plan day to calendar event projection.

Projection must be idempotent. Re-projecting the same plan day must not duplicate calendar events.

### 5.8 `proposals.py`

Owns proposal generation, storage, and application.

Proposal generation does not write plan days.
Proposal application writes only after guard validation.

### 5.9 `secretary_adapter.py`

Owns Maxwell / LLM prompt building and strict JSON parsing.

It cannot write persistence.
It cannot call frontend APIs.
It only returns typed proposal data.

### 5.10 `repository.py`

Thin persistence wrapper around existing storage.

No business decisions.

## 6. Public HTTP API Groups

All frontend-facing calendar APIs should live under:

```text
/api/v1/jarvis/calendar/*
```

Existing endpoints can remain temporarily, but new development should target the `calendar/*` namespace.

## 7. Shared Types

### 7.1 `CalendarItemRef`

Used by frontend, Agent tools, proposal APIs, and guard.

```json
{
  "item_type": "plan | plan_day | calendar_event | background_task | background_task_day | workbench_item",
  "item_id": "string"
}
```

Rules:

- `item_type` is required.
- `item_id` is required.
- Unknown item types must be rejected.
- External callers must not infer DB table names from item type.

### 7.2 `LocalDate`

```text
YYYY-MM-DD
```

Rules:

- Date-only values are local calendar dates.
- Do not parse date-only strings as UTC.
- Frontend must not use JavaScript `Date` to reinterpret `YYYY-MM-DD` as final schedule logic.
- Backend owns final date validation.

### 7.3 `LocalTime`

```text
HH:MM
```

Rules:

- 24-hour format.
- `start_time < end_time`.
- Timezone conversion happens before entering calendar module.
- Calendar module stores local date/time unless explicitly handling external calendar events.

### 7.4 `ScheduleChange`

```json
{
  "change_id": "string",
  "source": {
    "item_type": "plan_day",
    "item_id": "day-001"
  },
  "action": "schedule | move | cancel | complete | update_metadata",
  "from": {
    "date": "2026-05-01",
    "start_time": "19:00",
    "end_time": "20:30"
  },
  "to": {
    "date": "2026-05-02",
    "start_time": "19:00",
    "end_time": "20:30"
  },
  "title": "雅思听力训练",
  "description": "延期后保持原训练内容",
  "reason": "用户今晚临时有事，次日晚间有完整空闲窗口"
}
```

Rules:

- `from` is required for `move`, optional for `schedule`.
- `to` is required for `schedule` and `move`.
- `cancel` cannot delete history; it changes status only.
- Hard delete is a separate explicit command.

### 7.5 `CalendarError`

All calendar API errors should return this shape:

```json
{
  "detail": {
    "code": "planner_guard_violation",
    "message": "past date is not allowed: 2026-04-30 < 2026-05-01",
    "fields": {
      "item_id": "day-001",
      "field": "plan_date"
    },
    "recoverable": true
  }
}
```

Common codes:

- `planner_guard_violation`
- `past_date_not_allowed`
- `time_range_invalid`
- `schedule_conflict`
- `duplicate_schedule_item`
- `proposal_not_found`
- `proposal_expired`
- `proposal_context_changed`
- `llm_schedule_schema_invalid`
- `unknown_calendar_item_ref`

## 8. Query APIs

### 8.1 List Planner Tasks

```http
GET /api/v1/jarvis/calendar/tasks?status=active&limit=200
```

Response:

```json
{
  "items": [
    {
      "item_type": "plan",
      "id": "plan-ielts-30d",
      "title": "雅思 30 天备考计划",
      "status": "active",
      "goal": "30 天后完成阶段备考",
      "time_horizon": {
        "start_date": "2026-05-01",
        "target_date": "2026-05-30"
      },
      "summary": {
        "total_plan_days": 30,
        "completed_plan_days": 2,
        "next_plan_date": "2026-05-03"
      }
    }
  ]
}
```

Contract:

- Long-term plans appear once.
- Decomposed plan days must not appear as top-level task items.
- Frontend may display summary counts but must fetch plan days separately.

### 8.2 Get Plan Detail

```http
GET /api/v1/jarvis/calendar/plans/{plan_id}
```

Response:

```json
{
  "plan": {
    "id": "plan-ielts-30d",
    "title": "雅思 30 天备考计划",
    "status": "active",
    "plan_type": "long_term",
    "goal": "30 天后完成阶段备考",
    "source_agent": "maxwell"
  },
  "days": [],
  "projection_summary": {
    "schedulable_count": 30,
    "projected_count": 12,
    "unprojected_count": 18,
    "is_fully_projected": false
  }
}
```

### 8.3 List Calendar Items

```http
GET /api/v1/jarvis/calendar/items?start=2026-05-01T00:00:00%2B08:00&end=2026-05-08T00:00:00%2B08:00
```

Response:

```json
{
  "start": "2026-05-01T00:00:00+08:00",
  "end": "2026-05-08T00:00:00+08:00",
  "items": [],
  "conflicts": [],
  "free_windows": []
}
```

Contract:

- API must normalize offset-aware and offset-naive datetimes internally.
- Response item dates are local dates.
- Frontend must not recompute conflicts.

### 8.4 Get Availability

```http
GET /api/v1/jarvis/calendar/availability?start=...&end=...
```

Response:

```json
{
  "conflicts": [],
  "free_windows": []
}
```

Contract:

- Read-only.
- No writes.
- Used by UI and secretary context builders.

## 9. Command APIs

### 9.1 Create Plan

```http
POST /api/v1/jarvis/calendar/plans
```

Request:

```json
{
  "title": "雅思 30 天备考计划",
  "plan_type": "long_term",
  "goal": "30 天后完成阶段备考",
  "original_user_request": "我要考雅思，未来 30 天帮我安排",
  "time_horizon": {
    "start_date": "2026-05-01",
    "target_date": "2026-05-30"
  }
}
```

Contract:

- Creates plan header only unless `days` are explicitly provided by an internal service.
- Frontend manual create should not generate plan days itself.

### 9.2 Update Plan Metadata

```http
PATCH /api/v1/jarvis/calendar/plans/{plan_id}
```

Allowed fields:

- `title`
- `goal`
- `status`
- `time_horizon`
- `raw_payload`

Not allowed:

- Direct plan day rewrite.
- Direct calendar event mutation.

### 9.3 Delete Plan

```http
DELETE /api/v1/jarvis/calendar/plans/{plan_id}
```

Contract:

- Hard delete requires explicit user action.
- Must cascade or mark related plan days consistently.
- Must sync projected calendar events.
- Must record audit event.

### 9.2.1 Calendar Event Update Sync

When the frontend edits an existing calendar event through `PUT /api/v1/jarvis/calendar/events/{event_id}`:
- The persisted calendar event record must be updated in the database.
- If the event is backed by a `jarvis_plan_day` via `calendar_event_id`, the backing plan day must be updated in the database in the same request flow.
- Calendar projections must be refreshed from the updated database state, not from stale in-memory state.
- This update path must not depend on LLM output.
- The response may include the synced `plan_day` for frontend refresh purposes, but the write authority remains the backend database.

Frontend handoff notes:
- Current `CalendarPanel.tsx` changes are only for local/demo display. The production frontend may be replaced by another developer's implementation.
- The replacement frontend should call the existing update endpoint directly through the calendar service boundary; it must not call LLM or simulate writes locally.
- After a successful update, the frontend should re-query calendar/planner items from the backend instead of mutating only local state.
- Day, week, and month views should use the same selected-event detail/edit flow so all edits go through the same backend write path.
- The frontend should not show unrelated pending actions automatically when opening the calendar; pending actions belong in an explicit confirmation surface.

### 9.4 Project Plan to Calendar

```http
POST /api/v1/jarvis/calendar/plans/{plan_id}/project
```

Response:

```json
{
  "projected_count": 10,
  "skipped": [
    {
      "item_id": "day-001",
      "reason": "already_projected"
    }
  ]
}
```

Contract:

- Idempotent.
- Must not duplicate calendar events.
- Must skip completed/cancelled/deleted days.
- Must use guard before creating calendar event.

## 10. Proposal APIs

Proposal flow is the only allowed path for intelligent reschedule, conflict resolution, and complex postpone.

### 10.1 Generate Reschedule Proposals

```http
POST /api/v1/jarvis/calendar/proposals/reschedule
```

Request:

```json
{
  "intent": "postpone_items | resolve_conflict | reschedule_long_plan | plan_today",
  "item_refs": [
    {
      "item_type": "plan_day",
      "item_id": "day-001"
    }
  ],
  "reason": "今晚临时有事，帮我延期一天并重新安排",
  "policy": {
    "requested_shift_days": 1,
    "scope": "remaining_plan_days",
    "preserve_completed_history": true,
    "prefer_same_time_of_day": true,
    "allow_weekend_compensation": true,
    "allow_goal_date_shift": false
  },
  "timezone": "Asia/Shanghai"
}
```

Response:

```json
{
  "proposal_set_id": "proposal-set-001",
  "schema_version": "calendar_proposal_set.v1",
  "status": "pending",
  "expires_at": 1770000000,
  "summary": "基于延期一天，生成 3 个可执行方案。",
  "proposals": [
    {
      "proposal_id": "balanced",
      "strategy": "balanced",
      "title": "均衡方案：整体顺延一天，周末补一部分",
      "summary": "保持每天学习节奏，目标日期不变，周末增加 30 分钟。",
      "changes": [],
      "estimated_delay_days": 1,
      "risk_level": "low",
      "requires_goal_shift": false,
      "guard_status": "valid"
    }
  ],
  "rejected_proposals": []
}
```

Contract:

- Must not write plan days or calendar events.
- Must collect calendar context server-side.
- Must call secretary adapter only if deterministic rules need intelligent choice.
- Must validate every returned proposal before exposing it.
- Invalid proposals may be returned in `rejected_proposals`, not as executable options.

### 10.2 Apply Proposal

```http
POST /api/v1/jarvis/calendar/proposals/{proposal_set_id}/apply
```

Request:

```json
{
  "proposal_id": "balanced"
}
```

Response:

```json
{
  "applied": true,
  "proposal_set_id": "proposal-set-001",
  "proposal_id": "balanced",
  "changed_count": 3,
  "changed": [],
  "calendar_events": []
}
```

Contract:

- Must reload current state.
- Must re-run guard.
- If context changed and proposal is no longer valid, reject with `proposal_context_changed`.
- Must record audit event.
- Must be idempotent for already-applied proposal sets.

### 10.3 Cancel Proposal Set

```http
POST /api/v1/jarvis/calendar/proposals/{proposal_set_id}/cancel
```

Contract:

- Cancels pending proposal set.
- Does not modify schedule state.

## 11. Secretary Skill Contract

The secretary skill is not an API endpoint. It is an internal adapter contract between Calendar Application Services and Maxwell / LLM.

### 11.1 Skill Input

```json
{
  "request_id": "uuid",
  "intent": "plan_today | create_long_plan | resolve_conflict | postpone_items | reschedule_long_plan",
  "today": "2026-05-01",
  "timezone": "Asia/Shanghai",
  "user_request": "今晚临时有事，把雅思计划延期一天并重新安排",
  "target_plan": {},
  "plan_days": [],
  "calendar_items": [],
  "free_windows": [],
  "constraints": {
    "no_past_dates": true,
    "no_overlap_with_fixed_events": true,
    "no_duplicate_titles_in_same_plan": true,
    "preserve_completed_history": true,
    "must_return_strict_json": true
  }
}
```

Only Calendar Application Services may construct this input.

### 11.2 Today Schedule Output

```json
{
  "schema_version": "secretary_schedule.v1",
  "intent": "plan_today",
  "summary": "今天保留会议，安排 2 个学习窗口。",
  "schedule_items": [],
  "unchanged_items": [],
  "warnings": []
}
```

Contract:

- Code writes only `schedule_items` after validation.
- `unchanged_items` and `warnings` are display-only.
- Wrong schema is rejected.

### 11.3 Reschedule Output

```json
{
  "schema_version": "secretary_reschedule.v1",
  "intent": "reschedule_long_plan",
  "summary": "基于延期一天，给出 3 个可执行方案。",
  "proposal_set_title": "雅思计划延期一天后的重排方案",
  "proposals": [],
  "rejected_options": []
}
```

Contract:

- LLM output is never applied directly.
- Calendar module converts it into proposal set.
- Guard validates before frontend sees it.
- Guard validates again before apply.

## 12. Frontend Contract

Frontend may:

- Query tasks, plans, days, calendar items, availability.
- Ask calendar module to create proposals.
- Display proposals.
- Ask calendar module to apply selected proposal.
- Trigger explicit delete/cancel/complete commands.

Frontend must not:

- Compute final reschedule dates.
- Directly call move endpoints for intelligent postpone.
- Hide conflicts by local ignore state.
- Write plan days based on raw LLM output.
- Duplicate backend conflict or repeat detection logic.

Required UI behavior:

- Conflict card shows “生成解决方案”, not “忽略冲突”.
- Postpone button says “让秘书重排”.
- Proposal cards show impact, risk, delay, and apply button.
- Long-term plan appears once in task list.
- Decomposed plan days are visible only in plan detail, today view, calendar projection, and workbench.

## 13. Agent / Tool Contract

Agent tools may call calendar facade commands, not persistence.

Allowed tool intents:

- `calendar.create_plan_request`
- `calendar.generate_reschedule_proposals`
- `calendar.apply_proposal`
- `calendar.list_today_schedule`
- `calendar.push_today_to_workbench`

Agent tools must not:

- Call `update_jarvis_plan_day` directly.
- Create calendar events directly.
- Apply LLM output directly.
- Skip proposal flow for conflicts or reschedule.

## 14. Persistence Contract

Persistence stores facts, not decisions.

Calendar services decide:

- Whether a date is valid.
- Whether an item conflicts.
- Whether a proposal is executable.
- Whether projection should happen.

Persistence only provides:

- Save/get/list/update primitives.
- Audit event recording.
- Transaction-safe writes when available.

## 15. Migration Strategy

### Stage 1: Compatibility Facade

Create calendar facade and route new APIs to existing functions internally.

Do not break current frontend immediately.

### Stage 2: Guard Centralization

Move hard constraints into `guard.py` and call from all write paths.

### Stage 3: Proposal Flow

Introduce proposal generation/apply APIs.

Update frontend to use proposal APIs for postpone/conflict/reschedule.

### Stage 4: Namespace Migration

Move frontend from legacy endpoints to `/calendar/*` endpoints.

Legacy endpoints remain as thin compatibility wrappers until no caller uses them.

### Stage 5: Remove Legacy Direct Reschedule

Deprecate or restrict direct `/plans/{plan_id}/reschedule` and `/plan-days/{day_id}/move` for intelligent operations.

They may remain only for admin/manual exact edits, protected by guard.

## 16. Acceptance Checklist

The calendar module is considered decoupled only when all items are true:

- Frontend imports calendar types from one service boundary.
- Frontend does not compute final reschedule dates.
- Agent skills do not write calendar persistence directly.
- LLM outputs are parsed by secretary adapter and validated by guard.
- All calendar writes go through Calendar Application Services.
- Proposal generation never writes schedule state.
- Proposal apply always re-validates current state.
- Long-term plans appear once in task list.
- Decomposed days do not pollute top-level tasks.
- Conflict ignore is absent from formal UI.
- Past-date writes are rejected from every write path.

## 17. Development Rules Going Forward

1. New calendar behavior must first update this contract.
2. New frontend calendar features must use `/api/v1/jarvis/calendar/*` or facade-compatible methods.
3. New Agent calendar features must use calendar facade/tool intents.
4. New LLM scheduling behavior must define strict JSON schema before implementation.
5. Any direct persistence write from outside calendar services is a boundary violation.
6. Any frontend date arithmetic that determines final schedule placement is a boundary violation.
7. Any ability to ignore a conflict in normal UI is a product violation.
