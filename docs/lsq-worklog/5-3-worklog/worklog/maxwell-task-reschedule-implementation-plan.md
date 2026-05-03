# Maxwell 单任务重排实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让用户在日/周/月视图点击某个任务后，可以手动修改时间，或点击“延后一天/交给 Maxwell 重排”，由后端 Maxwell 以全局日程视角完成重排。

**Architecture:** 前端只通过 `jarvisScheduleApi` 服务层表达用户意图，不直接 fetch 后端。后端新增一个 Maxwell 编排接口，读取计划日、后台任务日、日历项、冲突和空闲窗口，决定如何移动单日任务或压缩长期计划后续任务量，并写入 Maxwell 工作日志。

**Tech Stack:** React + TypeScript 前端，FastAPI 路由，SQLite persistence，现有 Jarvis planner/Maxwell persistence 服务。

---

## 接口边界

- 前端组件只改 `shadowlink-web/src/components/jarvis/CalendarPanel.tsx`，调用 `jarvisScheduleApi.requestMaxwellReschedule()`。
- 前端服务只改 `shadowlink-web/src/services/jarvisApi.ts`，新增类型和方法。
- 后端只新增 `POST /api/v1/jarvis/maxwell/reschedule-task`，不改变已有接口返回结构。
- 接口文档同步更新 `docs/解耦接口说明/frontend-decoupling-developer-guide.md`。

## 任务分解

### Task 1: 后端编排服务

**Files:**
- Modify: `shadowlink-ai/app/jarvis/persistence.py`
- Modify: `shadowlink-ai/app/api/v1/jarvis_router.py`

- [ ] 新增后端 helper：根据 `item_type + item_id` 找到任务。
- [ ] 新增后端 helper：`postpone_one_day` 时计算目标日期。
- [ ] 对 `plan_day` 调用已有 `move_jarvis_plan_day()` 或 `update_jarvis_plan_day()` 逻辑，保留校验和日历同步。
- [ ] 对 `background_task_day` 调用已有更新逻辑，保持任务日状态正确。
- [ ] 写入 `append_maxwell_workbench_log()`，日志说明 Maxwell 收到用户延期请求、检查全局日程、完成重排。

### Task 2: 后端 API

**Files:**
- Modify: `shadowlink-ai/app/api/v1/jarvis_router.py`

- [ ] 新增请求体：`item_type`, `item_id`, `action`, `reason`。
- [ ] 新增响应体：`changed`, `message`, `work_logs`, `pressure_review`, `warnings`。
- [ ] 路由只做参数接收，核心逻辑放 persistence/service helper，避免 router 变胖。

### Task 3: 前端服务层

**Files:**
- Modify: `shadowlink-web/src/services/jarvisApi.ts`

- [ ] 新增 `MaxwellRescheduleRequest` 类型。
- [ ] 新增 `MaxwellRescheduleResult` 类型。
- [ ] 新增 `jarvisScheduleApi.requestMaxwellReschedule(payload)`。
- [ ] 所有 fetch 仍集中在 service 层。

### Task 4: 前端交互

**Files:**
- Modify: `shadowlink-web/src/components/jarvis/CalendarPanel.tsx`

- [ ] 在 `selectedPlanDay` 详情区域新增“延后一天/交给 Maxwell”按钮。
- [ ] 在 `selectedTaskDay` 详情区域新增“延后一天/交给 Maxwell”按钮。
- [ ] 点击后只调用 `jarvisScheduleApi.requestMaxwellReschedule()`，成功后 `loadAll()` 刷新。
- [ ] 保留已有手动编辑入口，不删除任何已有按钮或显示逻辑。
- [ ] `calendar_event` 暂不接 Maxwell 自动重排，仅保留现有手动修改，避免误动外部日历。

### Task 5: 文档与验证

**Files:**
- Modify: `docs/解耦接口说明/frontend-decoupling-developer-guide.md`

- [ ] 记录新增接口 URL、请求参数、响应字段。
- [ ] 记录前端只能调用 `jarvisScheduleApi.requestMaxwellReschedule()`。
- [ ] 运行 `python -m py_compile app/jarvis/persistence.py app/api/v1/jarvis_router.py`。
- [ ] 运行 `npm.cmd run type-check`。

## 风险控制

- 不改日/周/月视图布局。
- 不让前端计算重排日期和冲突。
- 不改已有 API 返回字段，新增接口独立上线。
- 第一期只支持 `plan_day` 和 `background_task_day`，外部 `calendar_event` 不自动改。
