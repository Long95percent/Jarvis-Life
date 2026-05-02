# 日程模块待 Debug 清单

日期：2026-05-01

## 背景

本文件用于集中记录日程模块后续需要继续 debug、补齐或重构的内容。当前日程模块已经修复过：

- 点击“打开日历”黑屏问题。
- 长期任务（如“我要考雅思”）重复入库问题。
- 历史重复“雅思备考计划”清库问题。
- 计划与底层 background task 在任务清单中重复展示的问题。

但日程模块仍有若干逻辑未闭环，后续需要逐项处理。

## P0 / P1：核心逻辑未闭环

### 1. 日程面板加载失败不可诊断

- 位置：`shadowlink-web/src/components/jarvis/CalendarPanel.tsx`
- 当前现象：`loadAll()` 使用 `Promise.all` 同时加载多个接口。
- 风险：任一接口失败时，用户无法知道是哪个接口失败，也无法区分“真的没有日程”和“加载失败”。
- 后续方向：
  - 保留真实错误，不用空数组兜底掩盖。
  - 增加可诊断错误状态，显示失败接口、HTTP 状态和建议操作。
  - 考虑将核心日历项与非核心辅助数据分层加载。

### 2. 任务/计划模型仍是双轨结构

- 位置：
  - `shadowlink-ai/app/jarvis/persistence.py`
  - `shadowlink-ai/app/api/v1/jarvis_router.py`
  - `shadowlink-web/src/components/jarvis/CalendarPanel.tsx`
- 当前结构：
  - `background_tasks` / `background_task_days`
  - `jarvis_plans` / `jarvis_plan_days`
- 已修复：前端已避免把已关联计划的 background task 和 plan 并列展示。
- 未闭环：底层数据模型仍是两套，长期看容易再次产生边界混乱。
- 后续方向：
  - 明确 `jarvis_plans` 是长期任务主模型。
  - `background_tasks` 仅作为 Agent 拆解来源/兼容层。
  - 前后端 API 和 UI 逐步围绕主模型收敛。

### 3. 历史重复清理缺少显式管理入口

- 位置：`shadowlink-ai/app/jarvis/persistence.py`
- 当前已有能力：`cleanup_duplicate_background_tasks()`。
- 已执行：本地库已清理历史重复雅思任务。
- 未闭环：没有后端 API 或前端管理入口，只能通过代码/脚本触发。
- 后续方向：
  - 增加受控的维护接口。
  - 在设置或日程管理中增加“扫描并合并重复长期任务”的入口。
  - 执行前展示预览，执行后展示合并报告。

## P1：后端已有能力但前端没有入口

### 4. 计划投影到日历缺少前端按钮

- 后端接口：`POST /plans/{plan_id}/project-calendar`
- 位置：`shadowlink-ai/app/api/v1/jarvis_router.py`
- 当前问题：前端没有“将计划写入日历/重新投影”的明确入口。
- 后续方向：在计划详情中增加投影按钮，并显示已投影数量和冲突提示。

### 5. 计划整体重排缺少前端入口

- 后端接口：`POST /plans/{plan_id}/reschedule`
- 位置：`shadowlink-ai/app/api/v1/jarvis_router.py`
- 当前问题：前端只能单个计划日延期/编辑，不能整体重排。
- 后续方向：
  - 增加“整体重排”入口。
  - 支持选择原因、目标日期范围或自动建议。
  - 重排前展示影响范围。

### 6. 每日维护/自动重排缺少前端入口

- 后端接口：
  - `POST /planner/daily-maintenance`
  - `POST /planner/daily-maintenance/once`
- 当前问题：后端已有维护能力，但用户无法手动触发或查看维护结果。
- 后续方向：
  - 增加“运行今日维护”按钮。
  - 展示 missed 标记、自动重排、推送工作台等结果。

### 7. 逾期标记缺少用户可见流程

- 后端接口：
  - `POST /background-task-days/mark-overdue-missed`
  - `POST /planner/mark-overdue-missed`
- 当前问题：逾期状态可能被后端计算，但前端没有明确说明或手动触发入口。
- 后续方向：
  - 增加逾期扫描入口。
  - 在计划日/任务日上明确展示“已逾期/可重排”。

### 8. Maxwell Workbench 视图未完整实现

- 后端接口：
  - `GET /maxwell/workbench-items`
  - `POST /maxwell/workbench/push-daily-tasks`
- 当前问题：日程面板中没有完整工作台视图。
- 后续方向：
  - 增加工作台 tab 或侧栏。
  - 展示今日推送项、状态、来源计划日。
  - 支持完成/取消/回跳到原计划日。

## P2：功能体验未完善

### 9. 缺少手动创建/编辑长期计划能力

- 当前问题：长期计划主要依赖聊天和 pending action 生成。
- 缺失能力：
  - 手动创建长期计划。
  - 编辑计划标题、目标、时间范围、类型。
  - 修改计划总体状态。
- 后续方向：在任务清单中提供“新建长期计划”和“编辑计划信息”。

### 10. 缺少任务合并/拆分 UI

- 当前已有后端去重和清理逻辑。
- 未实现：用户无法手动选择两个长期任务进行合并，也不能查看合并来源。
- 后续方向：
  - 增加重复任务扫描结果页。
  - 支持用户确认合并。
  - 保留合并日志。

### 11. 冲突处理流程未实现

- 后端 `/planner/calendar-items` 会返回 `conflicts` 和 `free_windows`。
- 当前前端仅显示冲突数量和一个空闲窗口。
- 未实现：
  - 冲突详情列表。
  - 冲突原因解释。
  - 一键移动到可用空闲窗口。
  - 冲突确认/忽略。

### 12. 计划日批量操作缺失

- 当前已有：单日完成、单日延期、单日编辑。
- 未实现：
  - 批量延期。
  - 批量完成/取消。
  - 按周调整计划。
  - 批量重新分配时间段。

### 13. background task 缺少归档/删除入口

- 当前问题：前端可取消 plan，但没有管理底层 background task 的归档/删除入口。
- 风险：长期运行后仍可能积累无用历史任务。
- 后续方向：
  - 明确 background task 是否只读/内部来源。
  - 如果保留可见性，需要提供归档/清理入口。

## 建议处理顺序

1. 先修加载失败诊断，避免后续 debug 缺少错误信息。
2. 再统一任务清单主模型，以 `jarvis_plans` 作为长期任务主视图。
3. 补齐计划投影、整体重排、每日维护、逾期处理等已有后端能力的前端入口。
4. 最后做手动创建计划、任务合并/拆分、冲突处理和批量操作。

## 备注

- 后续修复应继续遵守：不通过兜底代码掩盖根因，不删除已有业务逻辑。
- 每次修复应在本文件或 `calendar-module-bug-summary.md` 中追加对应处理记录。

## 2026-05-01 修复记录：日程面板加载失败不可诊断

### 对应条目
- P0 / P1：日程面板加载失败不可诊断。

### 根因
- 前端日程相关 API 在 HTTP 失败时返回空数组或空 calendar response。
- `CalendarPanel.loadAll()` 无法区分“接口失败”和“确实没有数据”。
- 多接口并发加载时，失败接口没有模块名，后续 debug 很难定位。

### 修复内容
- `jarvisApi` 中日程加载相关 API 失败时改为抛出 `errorFromResponse()`，不再静默返回空数据：
  - `listPendingActions()`
  - `listBackgroundTasks()`
  - `listBackgroundTaskDays()`
  - `listPlans()`
  - `listPlanDays()`
  - `getPlannerCalendar()`
- `CalendarPanel` 新增命名加载步骤：
  - `日历项`
  - `待确认安排`
  - `后台任务`
  - `后台任务日`
  - `长期计划`
  - `计划日`
- 加载失败时展示：`日程数据加载失败：<模块名>：<后端错误>`。
- 错误展示同时覆盖日历 tab 和任务清单 tab，避免用户看到空列表误以为没有数据。

### 修改文件
- `shadowlink-web/src/services/jarvisApi.ts`
- `shadowlink-web/src/components/jarvis/CalendarPanel.tsx`
- `shadowlink-ai/tests/unit/jarvis/test_calendar_frontend_contract.py`

### 验证结果
- `$env:SSLKEYLOGFILE=''; python -m pytest shadowlink-ai\tests\unit\jarvis\test_calendar_frontend_contract.py shadowlink-ai\tests\unit\jarvis\test_calendar_panel_contract.py -q --basetemp=shadowlink-ai\.pytest_calendar_tmp`
  - 结果：`3 passed, 1 warning`。
- `cd shadowlink-web; npm.cmd run type-check`
  - 结果：exit 0。

### 状态
- 该条目已完成第一阶段修复。
- 后续如果要进一步优化，可以把核心日历项与非核心辅助数据拆成分层加载，但不应再静默吞掉接口错误。

## 2026-05-01 修复记录：任务/计划模型双轨导致任务清单边界不清

### 对应条目
- P0 / P1：任务/计划模型仍是双轨结构。

### 根因
- 前端任务清单原先分别请求 `plans` 和 `background_tasks`，再在组件内自行合并/过滤。
- 这种做法把“长期计划主模型”和“Agent 拆解来源/兼容层”混在 UI 层处理，边界不清，容易再次出现重复展示或统计不一致。

### 修复内容
- 后端新增统一任务清单接口：`GET /planner/tasks`。
- 统一规则：
  - `jarvis_plans` 作为长期任务/计划主模型，返回 `item_type=plan`。
  - 已被计划引用的 `background_tasks` 不再作为顶层任务返回。
  - 未关联计划的 legacy/orphan `background_tasks` 仍返回 `item_type=background_task`，避免丢失历史数据。
  - 返回顺序优先展示 plan，再展示 orphan background task。
- 前端 `CalendarPanel` 改为通过 `jarvisApi.listPlannerTasks()` 渲染任务清单。
- 原有 `plans`、`tasks`、`planDays`、`taskDays` 仍保留用于详情和日历渲染，不删除业务逻辑。

### 修改文件
- `shadowlink-ai/app/api/v1/jarvis_router.py`
- `shadowlink-ai/tests/unit/jarvis/test_unified_planner.py`
- `shadowlink-web/src/services/jarvisApi.ts`
- `shadowlink-web/src/components/jarvis/CalendarPanel.tsx`
- `shadowlink-ai/tests/unit/jarvis/test_calendar_frontend_contract.py`

### 回归测试
- 新增 `test_planner_task_items_use_plans_as_primary_model_and_hide_linked_background_tasks`：验证统一任务清单只返回计划主项和未关联 background task，不把同一长期任务拆成两条顶层项。
- 更新前端契约测试：要求 `统一任务清单` 成为日历面板的命名加载步骤。

### 验证结果
- `$env:SSLKEYLOGFILE=''; python -m pytest shadowlink-ai\tests\unit\jarvis\test_unified_planner.py::test_planner_task_items_use_plans_as_primary_model_and_hide_linked_background_tasks shadowlink-ai\tests\unit\jarvis\test_calendar_frontend_contract.py -q --basetemp=shadowlink-ai\.pytest_calendar_tmp`
  - 结果：`3 passed, 1 warning`。
- `cd shadowlink-web; npm.cmd run type-check`
  - 结果：exit 0。

### 状态
- 已完成第一阶段：任务清单读取边界收敛到统一后端接口。
- 后续若继续根治，可逐步把创建、编辑、合并、归档等操作也收敛到统一 planner task API。

## 2026-05-01 修复记录：重复长期任务清理缺少显式管理入口

### 对应条目
- P0 / P1：历史重复清理缺少显式管理入口。

### 根因
- 后端已有 `cleanup_duplicate_background_tasks()`，但只能通过代码/脚本触发。
- 用户无法在日程模块中扫描重复长期任务，也无法受控执行清理。

### 修复内容
- 后端新增预览能力：`preview_duplicate_background_tasks()`。
- 后端新增维护接口：`POST /planner/tasks/cleanup-duplicates?execute=false|true`。
  - `execute=false`：只返回重复组和重复任务数量，不修改数据库。
  - `execute=true`：执行合并清理，并返回删除数量和删除任务 ID。
- 前端 `jarvisApi` 新增 `cleanupDuplicatePlannerTasks()`。
- `CalendarPanel` 的任务清单中新增“重复长期任务检查”：
  - 点击“扫描”先预览重复项。
  - 有重复时显示重复组/重复任务数量。
  - 点击“合并清理”前弹窗确认。
  - 清理后自动刷新任务清单。

### 修改文件
- `shadowlink-ai/app/jarvis/persistence.py`
- `shadowlink-ai/app/api/v1/jarvis_router.py`
- `shadowlink-ai/tests/unit/jarvis/test_unified_planner.py`
- `shadowlink-web/src/services/jarvisApi.ts`
- `shadowlink-web/src/components/jarvis/CalendarPanel.tsx`
- `shadowlink-ai/tests/unit/jarvis/test_calendar_frontend_contract.py`

### 回归测试
- 新增 `test_cleanup_duplicate_planner_tasks_endpoint_supports_preview_and_execute`：验证预览不改库，执行才删除重复任务。
- 更新前端契约测试：要求 `cleanupDuplicatePlannerTasks()` HTTP 失败时抛出错误，不静默失败。

### 验证结果
- `$env:SSLKEYLOGFILE=''; python -m pytest shadowlink-ai\tests\unit\jarvis\test_unified_planner.py::test_cleanup_duplicate_planner_tasks_endpoint_supports_preview_and_execute shadowlink-ai\tests\unit\jarvis\test_calendar_frontend_contract.py -q --basetemp=shadowlink-ai\.pytest_calendar_tmp`
  - 结果：`3 passed, 1 warning`。
- `cd shadowlink-web; npm.cmd run type-check`
  - 结果：exit 0。

### 状态
- 该条目已完成：重复长期任务清理已从脚本能力变为用户可触发的受控维护流程。

## 2026-05-01 修复记录：计划投影到日历缺少前端按钮

### 对应条目
- P1：后端已有能力但前端没有入口 —— 计划投影到日历缺少前端按钮。

### 边界设计
- 后端继续负责投影业务：`POST /plans/{plan_id}/project-calendar`。
- `jarvisApi` 负责 HTTP 封装和错误传播。
- `CalendarPanel` 只负责触发投影、显示结果、刷新数据，不直接拼业务规则。

### 修复内容
- 前端 API 新增 `projectPlanToCalendar(planId)`。
- 新增 `ProjectPlanCalendarResult` 类型。
- 计划详情顶部新增“写入日历”按钮。
- 投影中显示“写入中…”。
- 成功后显示 `已写入 N 个日历项` 并刷新日程/任务数据。
- 失败后显示 `投影失败：<错误详情>`，不静默吞错。

### 修改文件
- `shadowlink-web/src/services/jarvisApi.ts`
- `shadowlink-web/src/components/jarvis/CalendarPanel.tsx`
- `shadowlink-ai/tests/unit/jarvis/test_calendar_frontend_contract.py`

### 验证结果
- `$env:SSLKEYLOGFILE=''; python -m pytest shadowlink-ai\tests\unit\jarvis\test_calendar_frontend_contract.py -q --basetemp=shadowlink-ai\.pytest_calendar_tmp`
  - 结果：`2 passed, 1 warning`。
- `cd shadowlink-web; npm.cmd run type-check`
  - 结果：exit 0。

### 状态
- 该条目已完成第一阶段：用户可以在计划详情中手动把计划日写入日历。
- 后续可继续增强：投影前预览冲突、投影后跳转到对应日期、重复投影识别提示。

## 2026-05-01 修复记录：计划整体重排缺少前端入口

### 对应条目
- P1：后端已有能力但前端没有入口 —— 计划整体重排缺少前端入口。

### 边界设计
- 后端继续负责重排业务：`POST /plans/{plan_id}/reschedule`。
- `jarvisApi` 只封装 HTTP 调用并向上抛出错误。
- `CalendarPanel` 只负责收集用户明确动作、构造可审计的重排请求、展示结果和刷新数据。

### 修复内容
- 前端 API 新增 `reschedulePlan(planId, payload)`。
- 新增 `PlanRescheduleResult` 类型。
- 计划详情新增“整体顺延一天”按钮。
- 仅对未完成且仍有日期的计划日生成重排请求，避免改动已完成历史。
- 重排前弹窗确认受影响计划日数量。
- 成功后显示 `已重排 N 个计划日` 并刷新日程/任务数据。
- 失败后显示 `重排失败：<错误详情>`，不静默吞错。

### 修改文件
- `shadowlink-web/src/services/jarvisApi.ts`
- `shadowlink-web/src/components/jarvis/CalendarPanel.tsx`
- `shadowlink-ai/tests/unit/jarvis/test_calendar_frontend_contract.py`

### 验证结果
- `$env:SSLKEYLOGFILE=''; python -m pytest shadowlink-ai\tests\unit\jarvis\test_calendar_frontend_contract.py -q --basetemp=shadowlink-ai\.pytest_calendar_tmp`
  - 结果：`2 passed, 1 warning`。
- `cd shadowlink-web; npm.cmd run type-check`
  - 结果：exit 0。

### 状态
- 该条目已完成第一阶段：用户可以在计划详情中手动把未完成计划日整体顺延一天。
- 后续可继续增强：自定义重排日期、冲突预览、只重排选中计划日。

## 2026-05-01 修复记录：每日维护/自动重排缺少前端入口

### 对应条目
- P1：后端已有能力但前端没有入口 —— 每日维护/自动重排缺少前端入口。

### 边界设计
- 后端继续负责维护业务：`POST /planner/daily-maintenance/once`。
- `jarvisApi` 只封装 HTTP 调用、参数和错误传播。
- `CalendarPanel` 只提供用户显式触发入口，展示维护摘要，并在成功后刷新数据。

### 修复内容
- 前端 API 新增 `runPlannerDailyMaintenanceOnce(params)`。
- 新增 `PlannerDailyMaintenanceResult` 类型。
- 任务清单新增“今日计划维护”区块。
- 点击运行前弹窗确认会执行：标记逾期、自动重排、推送今日任务。
- 成功后展示维护摘要：逾期数量、重排数量、推送数量。
- 若当天已运行过，展示“今日维护已运行过”。
- 失败后展示 `维护失败：<错误详情>`，不静默吞错。

### 修改文件
- `shadowlink-web/src/services/jarvisApi.ts`
- `shadowlink-web/src/components/jarvis/CalendarPanel.tsx`
- `shadowlink-ai/tests/unit/jarvis/test_calendar_frontend_contract.py`

### 验证结果
- `$env:SSLKEYLOGFILE=''; python -m pytest shadowlink-ai\tests\unit\jarvis\test_calendar_frontend_contract.py -q --basetemp=shadowlink-ai\.pytest_calendar_tmp`
  - 结果：`2 passed, 1 warning`。
- `cd shadowlink-web; npm.cmd run type-check`
  - 结果：exit 0。

### 状态
- 该条目已完成第一阶段：用户可以在日程模块中手动运行一次今日计划维护。
- 后续可继续增强：维护前预览、展示具体被重排/推送的计划日、支持指定维护日期。

## 2026-05-01 修复记录：逾期标记缺少用户可见流程

### 对应条目
- P1：后端已有能力但前端没有入口 —— 逾期标记缺少用户可见流程。

### 根因
- 后端已有统一接口 `POST /planner/mark-overdue-missed`，会同时标记 legacy background task days 和新 `jarvis_plan_days`。
- 前端旧方法仍命名为 `markOverdueBackgroundTaskDaysMissed()`，类型只描述 `task_days`，与后端实际返回的 `background_task_days` / `plan_days` 不一致。
- `CalendarPanel` 没有独立的逾期扫描入口，用户无法明确知道哪些未完成计划被标记为 missed。

### 修复内容
- 前端 API 新增 `PlannerOverdueMissedResult`，对齐后端统一返回结构。
- 前端 API 新增 `markOverduePlannerDaysMissed(today?)`，调用 `/planner/mark-overdue-missed`。
- 旧 `markOverdueBackgroundTaskDaysMissed()` 改为兼容代理到统一方法，避免继续分裂逻辑。
- 任务清单新增“逾期计划扫描”区块。
- 点击扫描前弹窗确认，只标记今天之前未完成的任务日/计划日。
- 成功后展示总逾期数、长期任务日数量、计划日数量，并刷新日程/任务数据。
- 失败后展示 `扫描失败：<错误详情>`，不静默吞错。

### 修改文件
- `shadowlink-web/src/services/jarvisApi.ts`
- `shadowlink-web/src/components/jarvis/CalendarPanel.tsx`
- `shadowlink-ai/tests/unit/jarvis/test_calendar_frontend_contract.py`

### 验证结果
- `$env:SSLKEYLOGFILE=''; python -m pytest shadowlink-ai\tests\unit\jarvis\test_calendar_frontend_contract.py -q --basetemp=shadowlink-ai\.pytest_calendar_tmp`
  - 结果：`3 passed, 1 warning`。
- `cd shadowlink-web; npm.cmd run type-check`
  - 结果：exit 0。

### 状态
- 该条目已完成第一阶段：用户可以在日程模块中显式扫描并标记逾期计划。
- 后续可继续增强：展开展示本次被标记的具体条目、对逾期项提供一键重排入口。

## 2026-05-01 修复记录：Maxwell Workbench 视图未完整实现

### 对应条目
- P1：后端已有能力但前端没有入口 —— Maxwell Workbench 视图未完整实现。

### 根因
- 后端已有 `GET /maxwell/workbench-items` 和 `POST /maxwell/workbench/push-daily-tasks`。
- 前端已有 `listMaxwellWorkbenchItems()` / `pushDailyTasksToMaxwellWorkbench()`，但列表 API HTTP 失败时返回空数组，导致真实错误被误显示为“暂无数据”。
- `CalendarPanel` 没有独立工作台 tab，用户看不到已推送给 Maxwell 的执行项，也无法从日程面板主动推送今日任务。

### 修复内容
- `MaxwellWorkbenchItem` 类型补充 `plan_day_id`、`plan_id`、`plan_date` 字段，覆盖新 planner 投影来源。
- `listMaxwellWorkbenchItems()` 改为 HTTP 失败时抛错，不再返回空数组。
- `PanelTab` 新增 `workbench`。
- `loadAll()` 加载 Maxwell 工作台数据，并通过 `loadStep("Maxwell 工作台", ...)` 保留失败诊断。
- 日程面板顶部新增“Maxwell 工作台”tab。
- 工作台视图展示标题、描述、状态、计划日期、截止时间、来源和 Agent。
- 工作台视图新增“推送今日任务”按钮，调用 `pushDailyTasksToMaxwellWorkbench()` 后刷新数据。
- 推送失败展示 `推送失败：<错误详情>`，不静默吞错。

### 修改文件
- `shadowlink-web/src/services/jarvisApi.ts`
- `shadowlink-web/src/components/jarvis/CalendarPanel.tsx`
- `shadowlink-ai/tests/unit/jarvis/test_calendar_frontend_contract.py`

### 验证结果
- `$env:SSLKEYLOGFILE=''; python -m pytest shadowlink-ai\tests\unit\jarvis\test_calendar_frontend_contract.py -q --basetemp=shadowlink-ai\.pytest_calendar_tmp`
  - 结果：`4 passed, 1 warning`。
- `cd shadowlink-web; npm.cmd run type-check`
  - 结果：exit 0。

### 状态
- 该条目已完成第一阶段：用户可以在日程面板中查看 Maxwell 工作台，并主动推送今日任务。
- 后续可继续增强：工作台项状态修改、按日期/状态筛选、跳转关联计划日。

## 2026-05-01 修复记录：缺少手动创建/编辑长期计划能力

### 对应条目
- P2：缺少手动创建/编辑长期计划能力。

### 根因
- 长期计划主记录主要来自聊天和 pending action 确认流程。
- 后端只有列表、取消、投影、重排和计划日编辑能力，缺少面向 UI 的计划主记录创建/编辑接口。
- 前端任务清单无法手动新建计划，也无法编辑计划标题、目标、原始需求和目标日期。

### 边界设计
- `jarvis_plans` 仍是长期计划主模型。
- 手动创建/编辑只修改计划主记录，不自动生成或删除计划日，避免和 Agent 拆解逻辑耦合。
- 计划日拆解、批量生成和日历投影仍由既有 Maxwell/后端流程负责。

### 修复内容
- 后端新增 `PlanCreateRequest` / `PlanUpdateRequest`。
- 后端新增 `POST /plans`：创建 `source_agent=user_ui` 的手动长期计划。
- 后端新增 `PATCH /plans/{plan_id}`：编辑计划主记录。
- 持久层新增 `update_jarvis_plan()`，只允许更新计划主表字段，并记录 `plan.updated` 事件。
- 前端 API 新增 `PlanWritePayload`、`createPlan()`、`updatePlan()`。
- 任务清单新增“新建长期计划”按钮。
- 计划详情新增“编辑计划信息”按钮。
- 表单支持标题、目标说明、原始需求、目标日期。
- 保存失败显示 `保存失败：<错误详情>`，不静默吞错。

### 修改文件
- `shadowlink-ai/app/jarvis/persistence.py`
- `shadowlink-ai/app/api/v1/jarvis_router.py`
- `shadowlink-ai/tests/unit/jarvis/test_unified_planner.py`
- `shadowlink-ai/tests/unit/jarvis/test_calendar_frontend_contract.py`
- `shadowlink-web/src/services/jarvisApi.ts`
- `shadowlink-web/src/components/jarvis/CalendarPanel.tsx`

### 验证结果
- `$env:SSLKEYLOGFILE=''; python -m pytest shadowlink-ai\tests\unit\jarvis\test_unified_planner.py::test_manual_plan_create_and_update_only_changes_plan_header shadowlink-ai\tests\unit\jarvis\test_calendar_frontend_contract.py -q --basetemp=shadowlink-ai\.pytest_calendar_tmp`
  - 结果：`6 passed, 1 warning`。
- `cd shadowlink-web; npm.cmd run type-check`
  - 结果：exit 0。

### 状态
- 该条目已完成第一阶段：用户可以手动创建长期计划，并编辑计划主信息。
- 后续可继续增强：手动添加计划日、从表单触发 Maxwell 拆解、计划模板。

## 2026-05-01 修复记录：缺少任务合并/拆分 UI

### 对应条目
- P2：缺少任务合并/拆分 UI。

### 根因
- 之前只有重复任务自动清理入口，用户无法手动选择两个计划进行合并。
- `jarvis_plans` 和 `jarvis_plan_days` 缺少受控的“迁移计划日”接口，前端不能安全地表达合并/拆分意图。
- 计划变更历史已有 `jarvis_agent_events`，但合并/拆分动作没有对应事件留痕。

### 边界设计
- 合并/拆分的实际数据迁移放在后端持久层完成。
- 前端只选择源计划、目标计划或要拆分的计划日，不直接操作数据库结构。
- 合并只移动 `jarvis_plan_days` 并把源计划标记为 `merged`，不删除源计划。
- 拆分只把选中的计划日移动到新计划，不重新拆解、不删除其它计划日。
- 所有操作写入 `jarvis_agent_events`，保留合并/拆分日志。

### 修复内容
- 持久层新增 `merge_jarvis_plans()`：移动源计划下计划日到目标计划，源计划状态改为 `merged`，记录 `plan.merged`。
- 持久层新增 `split_jarvis_plan()`：创建新计划并移动指定计划日，记录 `plan.split` 和 `plan.split.source`。
- 后端新增 `PlanMergeRequest` / `PlanSplitRequest`。
- 后端新增 `POST /plans/merge` 和 `POST /plans/{plan_id}/split`。
- 前端 API 新增 `mergePlans()` / `splitPlan()`。
- 计划详情新增“任务合并/拆分”区域：
  - 可选择另一个计划作为合并目标。
  - 可选中当前计划日并拆分为新计划。
- 合并/拆分前均弹窗确认，失败显示具体错误。

### 修改文件
- `shadowlink-ai/app/jarvis/persistence.py`
- `shadowlink-ai/app/api/v1/jarvis_router.py`
- `shadowlink-ai/tests/unit/jarvis/test_unified_planner.py`
- `shadowlink-ai/tests/unit/jarvis/test_calendar_frontend_contract.py`
- `shadowlink-web/src/services/jarvisApi.ts`
- `shadowlink-web/src/components/jarvis/CalendarPanel.tsx`

### 验证结果
- `$env:SSLKEYLOGFILE=''; python -m pytest shadowlink-ai\tests\unit\jarvis\test_unified_planner.py::test_manual_plan_merge_and_split_move_plan_days_with_events shadowlink-ai\tests\unit\jarvis\test_calendar_frontend_contract.py -q --basetemp=shadowlink-ai\.pytest_calendar_tmp`
  - 结果：`7 passed, 1 warning`。
- `cd shadowlink-web; npm.cmd run type-check`
  - 结果：exit 0。

### 状态
- 该条目已完成第一阶段：用户可以手动合并计划，或把选中的计划日拆分到新计划。
- 后续可继续增强：多选计划日拆分、合并前差异预览、合并来源可视化。

## 2026-05-01 修复记录：冲突处理流程未实现

### 对应条目
- P2：冲突处理流程未实现。

### 根因
- 后端 `/planner/calendar-items` 已返回 `conflicts` 和 `free_windows`。
- 前端此前只显示冲突数量和一个空闲窗口，用户看不到冲突详情、冲突原因，也不能直接处理。
- 已有 `movePlanDay()` 可以移动计划日，但没有和冲突结果连接起来。

### 边界设计
- 后端继续负责冲突检测和空闲窗口计算。
- 前端只展示冲突详情，并通过已有 `movePlanDay()` 发起明确的计划日移动。
- 当前第一阶段只移动冲突中的 `plan_day` 到第一个足够长的空闲窗口；不自动移动日历事件或 background task day，避免跨模型副作用。
- “忽略本次冲突”只影响当前前端会话提示，不写库、不改变业务数据。

### 修复内容
- 日历视图新增“冲突处理”详情区。
- 展示冲突时间段、冲突原因、冲突项标题和来源类型。
- 新增“移动到空闲窗口”按钮：
  - 查找冲突中的计划日。
  - 计算冲突时长。
  - 查找足够长的空闲窗口。
  - 调用 `movePlanDay()` 移动计划日，并刷新数据。
- 新增“忽略本次冲突”按钮：只隐藏当前冲突提示。
- 失败场景显示具体原因，例如无可移动计划日、无足够空闲窗口或接口错误。

### 修改文件
- `shadowlink-web/src/components/jarvis/CalendarPanel.tsx`
- `shadowlink-ai/tests/unit/jarvis/test_calendar_frontend_contract.py`

### 验证结果
- `$env:SSLKEYLOGFILE=''; python -m pytest shadowlink-ai\tests\unit\jarvis\test_calendar_frontend_contract.py -q --basetemp=shadowlink-ai\.pytest_calendar_tmp`
  - 结果：`7 passed, 1 warning`。
- `cd shadowlink-web; npm.cmd run type-check`
  - 结果：exit 0。

### 状态
- 该条目已完成第一阶段：用户可以查看冲突详情，并将冲突中的计划日移动到空闲窗口或忽略本次提示。
- 后续可继续增强：支持手动选择空闲窗口、处理日历事件冲突、写入忽略记录。

## 2026-05-01 修复记录：计划日批量操作缺失

### 对应条目
- P2：计划日批量操作缺失。

### 根因
- 后端只有单个计划日的完成、移动、编辑接口。
- 前端计划详情只能逐条完成或延期，不能批量选择多个计划日处理。
- 批量动作缺少统一事件记录，后续难以追踪是谁一次性改了哪些计划日。

### 边界设计
- 后端新增统一批量入口，负责逐个调用计划日更新逻辑并同步相关日历事件。
- 前端只负责选择计划日和触发批量动作，不直接拼数据库更新。
- 本阶段支持批量延期一天、批量完成、批量取消；批量重新分配具体时间段留到后续增强。

### 修复内容
- 后端新增 `PlanDayBulkUpdateRequest`。
- 后端新增 `POST /plan-days/bulk-update`。
- 批量接口支持：
  - `status`：批量更新状态。
  - `shift_days`：批量平移计划日期。
  - `reason`：记录批量操作原因。
- 批量接口对每个计划日记录 `plan_day.bulk_updated` 事件，并按计划额外记录聚合事件。
- 前端 API 新增 `bulkUpdatePlanDays()`。
- 计划详情的每日计划区新增“计划日批量操作”。
- 支持多选计划日，并提供“批量延期 / 批量完成 / 批量取消”按钮。
- 操作前弹窗确认，失败显示具体错误。

### 修改文件
- `shadowlink-ai/app/api/v1/jarvis_router.py`
- `shadowlink-ai/tests/unit/jarvis/test_unified_planner.py`
- `shadowlink-ai/tests/unit/jarvis/test_calendar_frontend_contract.py`
- `shadowlink-web/src/services/jarvisApi.ts`
- `shadowlink-web/src/components/jarvis/CalendarPanel.tsx`

### 验证结果
- `$env:SSLKEYLOGFILE=''; python -m pytest shadowlink-ai\tests\unit\jarvis\test_unified_planner.py::test_plan_day_bulk_update_changes_multiple_days_and_records_events shadowlink-ai\tests\unit\jarvis\test_calendar_frontend_contract.py -q --basetemp=shadowlink-ai\.pytest_calendar_tmp`
  - 结果：`9 passed, 1 warning`。
- `cd shadowlink-web; npm.cmd run type-check`
  - 结果：exit 0。

### 状态
- 该条目已完成第一阶段：用户可以选择多个计划日并批量延期、完成或取消。
- 后续可继续增强：批量指定日期/时间段、按筛选条件全选、批量投影到日历。

## 2026-05-01 修复记录：background task 缺少归档/删除入口

### 对应条目
- P2：background task 缺少归档/删除入口。

### 根因
- 统一任务清单中仍会保留未关联计划的 legacy/orphan `background_tasks`，避免历史任务丢失。
- 前端没有对这些 legacy task 的归档/删除入口，用户无法清理旧任务。
- 直接物理删除会破坏历史记录和潜在关联，因此需要软状态更新。

### 边界设计
- 后端新增 background task 主记录更新接口，只允许更新受控字段。
- “归档”和“删除”均为软状态更新：`archived` / `deleted`。
- 默认 `list_background_tasks()` 不再返回 `archived` / `deleted`，但按 status 查询仍可查回。
- 前端只在 legacy/orphan background task 详情中提供入口，不影响 `jarvis_plans` 主模型。

### 修复内容
- 持久层新增 `update_background_task()`。
- 后端新增 `BackgroundTaskUpdateRequest`。
- 后端新增 `PATCH /background-tasks/{task_id}`。
- `list_background_tasks(status=None)` 默认排除 `archived` / `deleted`。
- 前端 API 新增 `updateBackgroundTask()`。
- legacy task 详情新增“归档历史任务”和“删除历史任务”按钮。
- 操作前弹窗确认，并明确说明保留历史记录、仅从默认任务清单隐藏。

### 修改文件
- `shadowlink-ai/app/jarvis/persistence.py`
- `shadowlink-ai/app/api/v1/jarvis_router.py`
- `shadowlink-ai/tests/unit/jarvis/test_unified_planner.py`
- `shadowlink-ai/tests/unit/jarvis/test_calendar_frontend_contract.py`
- `shadowlink-web/src/services/jarvisApi.ts`
- `shadowlink-web/src/components/jarvis/CalendarPanel.tsx`

### 验证结果
- `$env:SSLKEYLOGFILE=''; python -m pytest shadowlink-ai\tests\unit\jarvis\test_unified_planner.py::test_background_task_archive_and_delete_are_soft_status_updates shadowlink-ai\tests\unit\jarvis\test_calendar_frontend_contract.py -q --basetemp=shadowlink-ai\.pytest_calendar_tmp`
  - 结果：`10 passed, 1 warning`。
- `cd shadowlink-web; npm.cmd run type-check`
  - 结果：exit 0。

### 状态
- 该条目已完成第一阶段：用户可以归档或软删除 legacy/orphan background task，避免任务清单继续混乱。
- 后续可继续增强：单独的归档视图、恢复归档任务、按状态筛选历史任务。

## 2026-05-01 19:45 - 修复 30 天长期计划写入不完整与今日日期错位

### 用户反馈
- 用户说“我要考雅思，未来 30 天”，再要求写入日程后，只看到 5/1 和 5/2 的日程，没有完整 30 天安排。
- 前端“今日日程”会错误显示 5/2 的日程，说明日期区分仍然混乱。
- 用户不希望长期计划生成 30 天确认卡再逐项确认，倾向取消长期计划确认卡；已写入后用户可以自行修改。

### 根因分析
- `jarvis_task_plan_decompose` 虽然能根据“30 天”生成 `daily_plan`，但工具仍声明 `requires_confirmation=True`，并且工具说明和 Maxwell prompt 都引导“确认后再写入”。这使长期计划链路依赖 pending action/确认卡，容易只确认或投影少量候选时间块。
- 聊天链路只负责把工具结果转换成 action/pending action，没有在 `task.plan` 工具成功后立即将完整 `daily_plan` 持久化到 `background_task_days`、`jarvis_plan_days` 和日历投影。
- 计划工具默认起始日期使用 `datetime.utcnow().date()`，在本地日期和 UTC 日期跨日时容易造成“今天/明天”边界混乱。
- 前端对 `YYYY-MM-DD` 日期字符串使用 `new Date(value)` 解析时存在 UTC/本地日期边界风险；计划日/后台任务日必须按本地 date key 比较，而不是按 UTC date string 隐式转换。

### 修复策略
- 长期计划不再走确认卡：用户明确要求“安排/写入未来 30 天计划”时，由 Maxwell 的 `task.plan` skill 自动落库并投影完整计划日。
- 保留旧 pending action 确认接口的兼容能力，但抽出统一持久化函数，避免自动写入和手动确认两套业务逻辑分叉。
- 日期边界以本地日期 key 为准：意图路由给计划工具传入本地 `target_start`，计划工具无起点时使用 `Asia/Shanghai` 本地日期，前端 `YYYY-MM-DD` 显示和筛选按本地日期构造。

### 修改内容
- `shadowlink-ai/app/tools/jarvis_tools.py`
  - `JarvisTaskPlanDecomposeTool.requires_confirmation` 改为 `False`。
  - 工具描述改为自动持久化为可编辑每日执行项。
  - `_build_daily_plan()` 无 `target_start` 时使用 `Asia/Shanghai` 本地日期，避免 UTC 跨日错位。
- `shadowlink-ai/app/api/v1/jarvis_router.py`
  - 新增 `_persist_task_plan_result()`，统一保存 background task、background task days、jarvis plan、jarvis plan days，并投影完整日历项。
  - 新增 `_persist_task_plan_actions()`，聊天工具结果中出现 `task.plan` 时自动写入完整计划。
  - 旧 `/pending-actions/{pending_id}/confirm` 的 `task.plan` 分支复用统一持久化函数。
  - 更新聊天规则：长期计划/明确多日写入自动生成可编辑日程；仅高风险单次修改/删除保留确认卡。
- `shadowlink-ai/app/jarvis/tool_runtime.py`
  - `to_action_results()` 不再把 `jarvis_task_plan_decompose` 转成 pending confirmation action。
- `shadowlink-ai/app/jarvis/agents.py`
  - Maxwell prompt 改为完整写入可编辑计划，不要求用户逐日确认。
- `shadowlink-ai/app/jarvis/intent_router.py`
  - task decompose / learning plan 路由槽位增加本地 `target_start`。
- `shadowlink-web/src/components/jarvis/CalendarPanel.tsx`
  - 新增 `localDateFromKey()`。
  - `formatDate()` 对 `YYYY-MM-DD` 使用本地日期解析。
  - `taskDayDate()` / `planDayDate()` 仅取 `plan_date` 的前 10 位并按本地日期时间构造，避免 5/2 错显示到 5/1。

### 测试补充
- `shadowlink-ai/tests/unit/jarvis/test_agents.py`
  - 新增 30 天雅思计划推断测试：确保生成 30 个 daily_plan，日期为 2026-05-01 到 2026-05-30，并确认 task plan 工具不再需要确认。
- `shadowlink-ai/tests/unit/jarvis/test_unified_planner.py`
  - 新增自动持久化测试：30 天 daily_plan 自动写入 30 个 task days、30 个 plan days，并投影 30 个日历项。

### 状态
- 待验证：运行后端定向单测与前端 type-check。

### 验证结果
- `$env:SSLKEYLOGFILE=''; python -m pytest shadowlink-ai\tests\unit\jarvis\test_agents.py shadowlink-ai\tests\unit\jarvis\test_unified_planner.py -q --basetemp=shadowlink-ai\.pytest_calendar_tmp`
  - 结果：`28 passed, 140 warnings`。
  - warnings 主要是当前环境未加载 `pytest-asyncio` 配置提示，以及既有 `datetime.utcnow/utcfromtimestamp` deprecation。
- `cd shadowlink-web; npm.cmd run type-check`
  - 结果：exit 0。

### 完成状态
- 30 天雅思计划会生成并自动写入完整 30 个计划日。
- 自动持久化会同步生成 `background_task_days`、`jarvis_plan_days` 和对应日历投影。
- 长期计划不再依赖确认卡。
- 前端按本地日期 key 展示计划日，避免 5/2 错显示到今日。

## 2026-05-01 20:05 - 查看所有任务支持删除，并只展示顶层任务

### 用户反馈
- “查看所有任务”里需要能删除任务，而不是只能取消。
- 长程任务如“30 天准备雅思”会拆分为每日计划日并写入数据库/日历/今日日程，但“查看所有任务”不应显示 5/1、5/2 等拆分后的短程计划日，只应显示顶层长程任务本身。

### 根因分析
- 顶层 `jarvis_plans` 只有 `/plans/{plan_id}/cancel`，前端详情区只有取消按钮，没有删除入口。
- legacy `background_tasks` 已有 `deleted` 软状态，但 `jarvis_plans` 缺少对应 delete 语义，导致用户无法从统一任务清单移除顶层计划。
- 默认计划日查询没有排除 `deleted`，删除计划后若只改主记录，拆分计划日仍可能出现在日历/今日等视图。
- “查看所有任务”的正确语义应是顶层任务清单：`jarvis_plans` + 未关联计划的 legacy `background_tasks`，不应混入 `jarvis_plan_days` 或 `background_task_days`。

### 修复策略
- 为 `jarvis_plans` 增加软删除能力：主计划状态改为 `deleted`，未完成计划日同步改为 `deleted`，关联日历投影同步为 `deleted`。
- 默认 `list_jarvis_plans()` 隐藏 `deleted`，按 `status=deleted` 仍可查回，保留审计历史。
- 默认 `list_jarvis_plan_days()` 隐藏 `deleted`，避免删除后的拆分计划日继续显示在日历/今日视图。
- 前端“查看所有任务”计划详情新增“删除任务”按钮，和“取消任务”区分：取消代表不再执行，删除代表从默认清单/日历隐藏。

### 修改内容
- `shadowlink-ai/app/jarvis/persistence.py`
  - `list_jarvis_plans(status=None)` 默认排除 `deleted`。
  - `list_jarvis_plan_days(status=None)` 默认排除 `deleted`。
  - 新增 `delete_jarvis_plan()`，软删除主计划和未完成计划日，并记录 `plan.deleted` 事件。
- `shadowlink-ai/app/api/v1/jarvis_router.py`
  - 新增 `DELETE /plans/{plan_id}`。
  - `_sync_plan_day_calendar_event()` 支持把计划日 `deleted` 同步为日历事件 `deleted`。
- `shadowlink-web/src/services/jarvisApi.ts`
  - 新增 `deletePlan()`。
- `shadowlink-web/src/components/jarvis/CalendarPanel.tsx`
  - 顶层计划详情新增“删除任务”按钮。
  - “取消任务”和“删除任务”分离展示。
- `shadowlink-ai/tests/unit/jarvis/test_unified_planner.py`
  - 新增删除计划隐藏任务并删除日历投影测试。
  - 新增统一任务清单不暴露拆分计划日测试。
- `shadowlink-ai/tests/unit/jarvis/test_calendar_frontend_contract.py`
  - 新增前端删除按钮和 `deletePlan` API 契约测试。

### 状态
- 待验证：后端定向单测与前端 type-check。

### 验证结果
- `$env:SSLKEYLOGFILE=''; python -m pytest shadowlink-ai\tests\unit\jarvis\test_unified_planner.py shadowlink-ai\tests\unit\jarvis\test_calendar_frontend_contract.py -q --basetemp=shadowlink-ai\.pytest_calendar_tmp`
  - 结果：`32 passed, 141 warnings`。
  - warnings 主要是当前环境 `pytest-asyncio` 配置提示和既有 `datetime.utcnow/utcfromtimestamp` deprecation。
- `cd shadowlink-web; npm.cmd run type-check`
  - 结果：exit 0。

### 完成状态
- “查看所有任务”里的顶层计划支持“删除任务”。
- 删除计划后，该计划默认不再出现在“查看所有任务”。
- 删除计划后，未完成拆分计划日默认不再出现在日历/今日视图。
- 长程任务拆分出的每日计划日不会作为独立任务出现在“查看所有任务”；列表只保留顶层长程计划和未关联计划的 legacy background task。

## 2026-05-01 20:30 - 修复确认日程后日历加载时区崩溃，并增加非 LLM 重复日程检查

### 用户反馈
- 点击确认秘书安排的日程后，打开日历报错：`can't compare offset-naive and offset-aware datetimes`。
- 今天的任务因此安排失败。
- 秘书在写入日程前需要确认是否已有重复日程；即使时间不同，只要是重复事项也不能安排上去。
- 不能所有重复判断都请求 LLM，因为这会增加耗时。

### 根因分析
- 前端确认卡写入的 `start/end` 可能带时区，例如 `+08:00` 或 `Z`，持久化后成为 offset-aware datetime。
- `jarvis_plan_days` / `background_task_days` 用 `plan_date + start_time/end_time` 组合，本身是 offset-naive datetime。
- `/planner/calendar-items` 在 `_build_planner_conflicts_and_free_windows()` 中直接比较 aware 与 naive datetime，导致 Python 抛出异常。
- 重复日程问题不适合默认走 LLM：重复判断是确定性规则，应该放在业务层快速执行，LLM 只负责理解用户意图和解释结果。

### 设计方案
- 时区修复：在 planner availability / conflicts 计算入口统一把 datetime 转为本地 naive datetime，只用于内部排序、冲突和空闲窗口计算；API 输出仍保留原始 ISO 字段。
- 重复检查：采用 deterministic duplicate guard。
  - 规范化标题：去空格、去常见标点、小写。
  - 在写入日程前查询前后 30 天已有日程。
  - 如果同名且未删除/未取消，则拒绝写入。
  - 即使时间不同也拒绝，满足“重复的不能安排上去”。
  - `planner_projection` 来源跳过该检查，避免长期计划中每天同名学习块被误判为重复；长期计划的重复控制由 plan/plan_day 模型负责。

### 修改内容
- `shadowlink-ai/app/api/v1/jarvis_router.py`
  - 新增 `_as_naive_local()`，统一 planner 内部比较时间。
  - `_build_planner_conflicts_and_free_windows()` 对窗口和 item 时间统一 normalize，修复 aware/naive 比较崩溃。
  - 新增 `_normalize_event_title()`、`_calendar_event_time_overlap()`、`_find_duplicate_calendar_events()`。
  - `add_calendar_event()` 写入前执行重复检查；发现重复返回 HTTP 409，detail.code 为 `duplicate_calendar_event`。
- `shadowlink-ai/tests/unit/jarvis/test_unified_planner.py`
  - 新增确认日程带时区后 `/planner/calendar-items` 不崩溃测试。
  - 新增同名日程即使时间不同也拒绝写入测试。

### 验证结果
- `$env:SSLKEYLOGFILE=''; python -m pytest shadowlink-ai\tests\unit\jarvis\test_unified_planner.py shadowlink-ai\tests\unit\jarvis\test_calendar_frontend_contract.py -q --basetemp=shadowlink-ai\.pytest_calendar_tmp`
  - 结果：`34 passed, 147 warnings`。
  - warnings 主要是当前环境 `pytest-asyncio` 配置提示和既有 `datetime.utcnow/utcfromtimestamp` deprecation。
- `cd shadowlink-web; npm.cmd run type-check`
  - 结果：exit 0。

### 完成状态
- 带时区的确认日程不会再导致日历加载失败。
- 同名重复日程会在后端写入前被快速拦截，不请求 LLM。
- 长期计划每日投影不会被同名重复检查误伤。
