> MVP 计划替代说明：2026-05-01 用户确认先做“短期 / 长期计划自动化规划 + 智能体重排”的基本闭环，因此本完整 proposal 计划暂停执行。当前执行计划改为 `docs/lsq-worklog/4-30-worklog/calendar-module-mvp-implementation-plan.md`。本文档仅作为后续增强参考。
# 日程模块秘书式重排 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把日程模块从“机械日期修改”改成“确定性校验 + 秘书 Skill 生成方案 + 用户选择 + 代码落库”的可用调度系统。

**Architecture:** 后端新增确定性调度 Guard 和 proposal flow，LLM/Maxwell 只返回结构化安排或重排方案，代码负责校验和写库。前端只表达用户意图、展示方案、触发执行，不再直接计算最终调度日期。

**Tech Stack:** FastAPI / Pydantic / pytest / React / TypeScript / existing Jarvis persistence and calendar adapter.

---

## File Structure

### Backend

- Modify: `shadowlink-ai/app/api/v1/jarvis_router.py`
  - 暂时承载 API wiring，新增 proposal 相关 request/response models 和 endpoints。
  - 对现有 `/plan-days/{day_id}/move`、`/plan-days/bulk-update`、`/plans/{plan_id}/reschedule` 增加 P0 guard。

- Create: `shadowlink-ai/app/jarvis/planner_guard.py`
  - 负责确定性校验：过去日期、时间顺序、冲突、重复、空闲窗口可用性。
  - 不调用 LLM，不写库。

- Create: `shadowlink-ai/app/jarvis/secretary_scheduler.py`
  - 负责构建秘书 Skill 输入、调用 LLM、解析严格 JSON、清洗结构化方案。
  - 不写库。

- Create: `shadowlink-ai/app/jarvis/planner_proposals.py`
  - 负责 proposal set 的生成、暂存、读取和执行。
  - 执行前后调用 `planner_guard`。

- Modify: `shadowlink-ai/app/jarvis/planner_maintenance.py`
  - 现有 missed 自动重排已有 LLM 雏形，但直接写库；后续改为复用 `secretary_scheduler` 的结构化输出和 `planner_guard` 校验。

- Modify: `shadowlink-ai/app/jarvis/persistence.py`
  - 如已有通用 agent event 可复用，优先不新增表。
  - 若需要持久化 proposal，先用 `record_agent_event(event_type="planner.proposal_set.created")` 存 payload，避免第一阶段引入复杂迁移。

### Frontend

- Modify: `shadowlink-web/src/services/jarvisApi.ts`
  - 新增 proposal 相关类型和 API client。
  - 机械延期 API 暂不删除，但 UI 不再直接调用。

- Modify: `shadowlink-web/src/components/jarvis/CalendarPanel.tsx`
  - 移除正式 UI 的“忽略冲突”。
  - 延期/批量延期/冲突处理改成“生成秘书方案”。
  - 新增 proposal list 展示和 apply 按钮。

### Tests

- Modify: `shadowlink-ai/tests/unit/jarvis/test_unified_planner.py`
  - 增加 P0 guard 和 proposal flow 单测。

- Modify: `shadowlink-ai/tests/unit/jarvis/test_calendar_frontend_contract.py`
  - 增加前端契约测试：没有忽略冲突、延期不直接 `+1 day` 写库、展示 proposal 操作。

- Create: `shadowlink-ai/tests/unit/jarvis/test_secretary_scheduler.py`
  - 测试 LLM 结构化输出解析、非法 JSON、过去日期、未知 ID、冲突方案过滤。

---

## Task 1: P0 Guard for Past Dates

**Files:**
- Create: `shadowlink-ai/app/jarvis/planner_guard.py`
- Modify: `shadowlink-ai/app/api/v1/jarvis_router.py`
- Test: `shadowlink-ai/tests/unit/jarvis/test_unified_planner.py`

- [ ] **Step 1: Write failing tests for past-date rejection**

Add tests:

```python
def test_plan_day_move_rejects_past_date():
    async def scenario():
        plan = await persistence.save_jarvis_plan(plan_id="plan-past-guard", title="past guard", goal="test")
        day = await persistence.save_jarvis_plan_day(
            plan_id=plan["id"],
            plan_date="2026-05-02",
            title="future day",
            start_time="19:00",
            end_time="20:00",
        )
        with pytest.raises(ValueError, match="past date"):
            validate_plan_day_move(
                {"id": day["id"], "plan_date": "2026-05-02", "start_time": "19:00", "end_time": "20:00"},
                {"plan_date": "2026-04-30", "start_time": "19:00", "end_time": "20:00"},
                today="2026-05-01",
            )
    asyncio.run(scenario())
```

Also add a route-level test if existing integration utilities make it cheap; otherwise keep unit-level guard first.

- [ ] **Step 2: Run failing test**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; Remove-Item Env:SSLKEYLOGFILE -ErrorAction SilentlyContinue; python -m pytest shadowlink-ai\tests\unit\jarvis\test_unified_planner.py::test_plan_day_move_rejects_past_date -q --basetemp=shadowlink-ai\.pytest_calendar_tmp
```

Expected: FAIL because `planner_guard.validate_plan_day_move` does not exist.

- [ ] **Step 3: Implement minimal guard**

Create `shadowlink-ai/app/jarvis/planner_guard.py`:

```python
from __future__ import annotations

from datetime import date
from typing import Any


def _date_key(value: Any) -> str:
    return str(value or "")[:10]


def validate_not_past(plan_date: str, *, today: str) -> None:
    target = _date_key(plan_date)
    current = _date_key(today)
    if not target:
        raise ValueError("missing plan date")
    date.fromisoformat(target)
    date.fromisoformat(current)
    if target < current:
        raise ValueError(f"past date is not allowed: {target} < {current}")


def validate_time_range(start_time: str | None, end_time: str | None) -> None:
    if start_time and end_time and str(start_time)[:5] >= str(end_time)[:5]:
        raise ValueError("start_time must be before end_time")


def validate_plan_day_move(original: dict[str, Any], patch: dict[str, Any], *, today: str) -> None:
    plan_date = _date_key(patch.get("plan_date") or original.get("plan_date"))
    start_time = patch.get("start_time", original.get("start_time"))
    end_time = patch.get("end_time", original.get("end_time"))
    validate_not_past(plan_date, today=today)
    validate_time_range(start_time, end_time)
```

- [ ] **Step 4: Wire guard into existing write endpoints**

In `jarvis_router.py`, before `update_jarvis_plan_day` in:

- `move_plan_day_item`
- `bulk_update_plan_days` when `shift_days` is used
- `reschedule_plan_days`
- `update_plan_day_item` when `plan_date`, `start_time`, or `end_time` is changed

Use local today:

```python
from datetime import date
from app.jarvis.planner_guard import validate_plan_day_move

try:
    validate_plan_day_move(existing_day, patch, today=date.today().isoformat())
except ValueError as exc:
    raise HTTPException(status_code=422, detail={"code": "planner_guard_violation", "message": str(exc)}) from exc
```

If route does not currently load `existing_day`, fetch it before update.

- [ ] **Step 5: Run tests**

Run the new unit test plus existing reschedule tests:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; Remove-Item Env:SSLKEYLOGFILE -ErrorAction SilentlyContinue; python -m pytest shadowlink-ai\tests\unit\jarvis\test_unified_planner.py::test_plan_day_move_rejects_past_date shadowlink-ai\tests\unit\jarvis\test_unified_planner.py::test_reschedule_plan_days_updates_calendar_projection -q --basetemp=shadowlink-ai\.pytest_calendar_tmp
```

Expected: PASS.

---

## Task 2: Remove Ignore Conflict from Formal UI

**Files:**
- Modify: `shadowlink-web/src/components/jarvis/CalendarPanel.tsx`
- Test: `shadowlink-ai/tests/unit/jarvis/test_calendar_frontend_contract.py`

- [ ] **Step 1: Write failing frontend contract test**

Add:

```python
def test_calendar_panel_does_not_offer_ignore_conflict_in_formal_ui() -> None:
    component_path = Path(__file__).parents[4] / "shadowlink-web" / "src" / "components" / "jarvis" / "CalendarPanel.tsx"
    source = component_path.read_text(encoding="utf-8")

    assert "ignoreConflictOnce" not in source
    assert "忽略本次冲突" not in source
    assert "setIgnoredConflictKeys" not in source
```

- [ ] **Step 2: Run failing test**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; Remove-Item Env:SSLKEYLOGFILE -ErrorAction SilentlyContinue; python -m pytest shadowlink-ai\tests\unit\jarvis\test_calendar_frontend_contract.py::test_calendar_panel_does_not_offer_ignore_conflict_in_formal_ui -q --basetemp=shadowlink-ai\.pytest_calendar_tmp
```

Expected: FAIL while ignore conflict code exists.

- [ ] **Step 3: Remove ignore conflict formal flow**

In `CalendarPanel.tsx`:

- Remove `ignoredConflictKeys` state.
- Remove `ignoreConflictOnce()`.
- Remove any filter that hides conflicts after ignore.
- Remove button text `忽略本次冲突`.

Keep conflict display and replace action with disabled or placeholder button `生成解决方案` until Task 5 implements it.

- [ ] **Step 4: Run type-check and test**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; Remove-Item Env:SSLKEYLOGFILE -ErrorAction SilentlyContinue; python -m pytest shadowlink-ai\tests\unit\jarvis\test_calendar_frontend_contract.py::test_calendar_panel_does_not_offer_ignore_conflict_in_formal_ui -q --basetemp=shadowlink-ai\.pytest_calendar_tmp
```

Run:

```powershell
cd shadowlink-web; npm.cmd run type-check
```

Expected: both PASS.

---

## Task 3: Stop Direct Mechanical Postpone in Frontend

**Files:**
- Modify: `shadowlink-web/src/components/jarvis/CalendarPanel.tsx`
- Test: `shadowlink-ai/tests/unit/jarvis/test_calendar_frontend_contract.py`

- [ ] **Step 1: Write failing contract test**

Add:

```python
def test_calendar_panel_does_not_directly_write_plus_one_day_postpone() -> None:
    component_path = Path(__file__).parents[4] / "shadowlink-web" / "src" / "components" / "jarvis" / "CalendarPanel.tsx"
    source = component_path.read_text(encoding="utf-8")

    assert "movePlanDayTomorrow" not in source
    assert "rescheduleSelectedPlanTomorrow" not in source
    assert "shift_days: action === \"postpone\" ? 1" not in source
    assert "让秘书重排" in source
```

- [ ] **Step 2: Run failing test**

Expected: FAIL because current code still has direct postpone functions.

- [ ] **Step 3: Replace UI calls with proposal placeholder**

In `CalendarPanel.tsx`:

- Rename single-day button text from `延期` to `让秘书重排`.
- Replace handler with `requestRescheduleProposalForPlanDays([day.id])`.
- Replace batch postpone handler with `requestRescheduleProposalForPlanDays(selectedPlanDayIds)`.
- Until API exists, function sets message: `正在接入秘书重排方案生成，当前不会直接修改日期。`
- Do not call `jarvisApi.movePlanDay` or `bulkUpdatePlanDays` for postpone.

- [ ] **Step 4: Run type-check and contract test**

Expected: PASS.

---

## Task 4: Secretary Scheduler JSON Parser

**Files:**
- Create: `shadowlink-ai/app/jarvis/secretary_scheduler.py`
- Create: `shadowlink-ai/tests/unit/jarvis/test_secretary_scheduler.py`

- [ ] **Step 1: Write parser tests**

Test valid reschedule response:

```python
def test_parse_secretary_reschedule_response_accepts_valid_schema():
    raw = '{"schema_version":"secretary_reschedule.v1","intent":"reschedule_long_plan","summary":"ok","proposal_set_title":"test","proposals":[{"proposal_id":"balanced","strategy":"balanced","title":"Balanced","summary":"Move one day","changes":[{"change_id":"c1","source_type":"plan_day","source_id":"day-1","action":"move","from":{"date":"2026-05-01","start_time":"19:00","end_time":"20:00"},"to":{"date":"2026-05-02","start_time":"19:00","end_time":"20:00"},"title":"IELTS","description":"study","reason":"user requested postpone"}],"estimated_delay_days":1,"risk_level":"low","requires_goal_shift":false}],"rejected_options":[]}'
    parsed = parse_secretary_reschedule_response(raw)
    assert parsed["schema_version"] == "secretary_reschedule.v1"
    assert parsed["proposals"][0]["proposal_id"] == "balanced"
```

Test invalid markdown and wrong schema are rejected.

- [ ] **Step 2: Run failing tests**

Expected: FAIL because module does not exist.

- [ ] **Step 3: Implement parser and prompt builder**

Implement:

```python
def parse_secretary_json(raw: str) -> dict[str, Any]
def parse_secretary_reschedule_response(raw: str) -> dict[str, Any]
def build_secretary_reschedule_prompt(context: dict[str, Any]) -> str
```

Rules:

- Strip ```json fences if present.
- Require dict root.
- Require `schema_version == "secretary_reschedule.v1"`.
- Require `proposals` list length 1-3.
- Require every change has `source_id`, `action`, and `to.date` for move/schedule.

- [ ] **Step 4: Run parser tests**

Expected: PASS.

---

## Task 5: Proposal Generation API

**Files:**
- Create: `shadowlink-ai/app/jarvis/planner_proposals.py`
- Modify: `shadowlink-ai/app/api/v1/jarvis_router.py`
- Modify: `shadowlink-web/src/services/jarvisApi.ts`
- Test: `shadowlink-ai/tests/unit/jarvis/test_unified_planner.py`

- [ ] **Step 1: Write backend test for proposal generation**

Add a unit test that seeds a plan and plan day, uses a fake LLM client returning `secretary_reschedule.v1`, calls `generate_reschedule_proposals(...)`, and asserts no DB plan day changed.

Expected behavior:

```python
assert result["proposal_set_id"]
assert len(result["proposals"]) == 1
assert unchanged_day["plan_date"] == "2026-05-01"
```

- [ ] **Step 2: Implement `generate_reschedule_proposals`**

In `planner_proposals.py`:

```python
async def generate_reschedule_proposals(*, intent: str, item_refs: list[dict[str, str]], reason: str, today: str, llm_client: Any) -> dict[str, Any]:
    # load referenced plan days
    # load owning plan and sibling remaining days
    # build context for secretary_scheduler
    # call llm
    # parse response
    # validate each proposal with planner_guard
    # record agent event planner.proposal_set.created
    # return proposal set
```

- [ ] **Step 3: Add API endpoint**

In `jarvis_router.py`:

```python
@router.post("/planner/reschedule-proposals")
async def create_reschedule_proposals(req: RescheduleProposalRequest, llm_client=Depends(get_llm_client)) -> dict[str, Any]:
    return await generate_reschedule_proposals(...)
```

- [ ] **Step 4: Add frontend API client**

In `jarvisApi.ts`, add types:

```ts
export interface PlannerRescheduleProposalSet { proposal_set_id: string; proposals: PlannerRescheduleProposal[]; }
export interface PlannerRescheduleProposal { proposal_id: string; title: string; summary: string; changes: PlannerProposalChange[]; risk_level?: string; }
```

Add method:

```ts
async createRescheduleProposals(payload: { intent: string; item_refs: Array<{ item_type: string; item_id: string }>; reason?: string }): Promise<PlannerRescheduleProposalSet>
```

- [ ] **Step 5: Run tests**

Run backend targeted tests and frontend type-check.

---

## Task 6: Proposal Apply API

**Files:**
- Modify: `shadowlink-ai/app/jarvis/planner_proposals.py`
- Modify: `shadowlink-ai/app/api/v1/jarvis_router.py`
- Modify: `shadowlink-web/src/services/jarvisApi.ts`
- Test: `shadowlink-ai/tests/unit/jarvis/test_unified_planner.py`

- [ ] **Step 1: Write test for applying proposal**

Seed proposal event or call generation first, then apply proposal.

Assert:

- Plan day changed only after apply.
- Calendar projection syncs if `calendar_event_id` exists.
- Applying unknown proposal fails.
- Applying proposal with past date fails.

- [ ] **Step 2: Implement `apply_reschedule_proposal`**

Rules:

- Load proposal set from persistence/agent event.
- Find selected proposal.
- Re-run `planner_guard` on every change.
- Apply changes with `update_jarvis_plan_day`.
- Sync calendar events.
- Record `planner.proposal_set.applied`.

- [ ] **Step 3: Add API endpoint**

```python
@router.post("/planner/reschedule-proposals/{proposal_set_id}/apply")
async def apply_reschedule_proposal_endpoint(proposal_set_id: str, req: ApplyRescheduleProposalRequest) -> dict[str, Any]:
    return await apply_reschedule_proposal(proposal_set_id=proposal_set_id, proposal_id=req.proposal_id)
```

- [ ] **Step 4: Add frontend API client**

Add:

```ts
async applyRescheduleProposal(proposalSetId: string, proposalId: string): Promise<PlannerApplyProposalResult>
```

- [ ] **Step 5: Run tests**

Expected: proposal generation does not write; apply writes after validation.

---

## Task 7: Frontend Proposal Experience

**Files:**
- Modify: `shadowlink-web/src/components/jarvis/CalendarPanel.tsx`
- Test: `shadowlink-ai/tests/unit/jarvis/test_calendar_frontend_contract.py`

- [ ] **Step 1: Write contract test**

Assert:

```python
assert "createRescheduleProposals" in source
assert "applyRescheduleProposal" in source
assert "方案" in source
assert "让秘书重排" in source
assert "忽略本次冲突" not in source
```

- [ ] **Step 2: Implement UI state**

Add states:

```ts
const [proposalSet, setProposalSet] = useState<PlannerRescheduleProposalSet | null>(null);
const [proposalLoading, setProposalLoading] = useState(false);
const [applyingProposalId, setApplyingProposalId] = useState<string | null>(null);
```

- [ ] **Step 3: Wire buttons**

- Single day `让秘书重排` calls `createRescheduleProposals` with one plan day.
- Batch postpone calls same API with selected IDs.
- Conflict card calls same API with conflict item refs.

- [ ] **Step 4: Render proposal cards**

Each card shows:

- title
- summary
- changed item count
- estimated delay days
- risk level
- apply button

- [ ] **Step 5: Apply proposal**

Call `applyRescheduleProposal`, then `loadAll()` and clear proposal state.

- [ ] **Step 6: Run type-check and contract tests**

Expected: PASS.

---

## Task 8: Daily Schedule Skill Flow

**Files:**
- Modify: `shadowlink-ai/app/jarvis/secretary_scheduler.py`
- Modify: `shadowlink-ai/app/jarvis/planner_maintenance.py`
- Test: `shadowlink-ai/tests/unit/jarvis/test_secretary_scheduler.py`

- [ ] **Step 1: Add parser test for `secretary_schedule.v1`**

Use valid JSON with `schedule_items`, `unchanged_items`, and `warnings`.

- [ ] **Step 2: Implement schedule parser**

Add:

```python
def parse_secretary_schedule_response(raw: str) -> dict[str, Any]
def build_secretary_today_schedule_prompt(context: dict[str, Any]) -> str
```

- [ ] **Step 3: Integrate with daily maintenance carefully**

Do not replace all maintenance at once. First use parser for Maxwell workbench push or a new helper that previews today schedule.

- [ ] **Step 4: Tests**

Verify parser accepts valid schedule and rejects:

- wrong schema
- schedule item with past date
- missing source_id

---

## Task 9: Worklog and Demo Metrics

**Files:**
- Modify: `docs/lsq-worklog/4-30-worklog/calendar-module-reschedule-redesign.md`
- Modify: `docs/lsq-worklog/4-30-worklog/bug/calendar-demo-frontend-e2e-bug-list.md`

- [ ] **Step 1: Append implementation result after each completed task**

Use the same calendar module files. Do not create separate bug files for each task.

- [ ] **Step 2: Track metrics**

For each implementation stage, record:

- past-date violation tests
- conflict write prevention tests
- duplicate write prevention tests
- proposal generation tests
- frontend type-check

---

## Execution Order

1. Task 1: P0 past-date guard.
2. Task 2: remove ignore conflict.
3. Task 3: stop direct mechanical postpone.
4. Task 4: secretary JSON parser.
5. Task 5: proposal generation API.
6. Task 6: proposal apply API.
7. Task 7: frontend proposal experience.
8. Task 8: daily schedule skill flow.
9. Task 9: update logs and metrics continuously.

Do not skip Tasks 1-3. They stop the currently harmful behavior before introducing new intelligence.

