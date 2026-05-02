# 日程 Demo 前端入口走查 Bug 清单

> 日期：2026-05-01  
> 范围：`calendar-module-demo-design.md` 中 Demo 1-4  
> 走查方式：以前端 UI 作为用户入口，对照 `CalendarPanel.tsx`、`AgentChatPanel.tsx`、`jarvisApi.ts` 与后端 API 契约做静态链路走查。当前项目没有 Playwright/Cypress 等浏览器 E2E 脚本，因此本文档先记录可从代码确认的前端入口问题和需要人工复测的风险点。

## 1. 前端入口覆盖情况

| Demo | 用户入口 | 前端入口状态 | 结论 |
|---|---|---|---|
| Demo 1：自然语言长期目标到可执行计划 | 私聊输入长期目标；打开日历；查看所有任务；写入日历 | 私聊、日历面板、任务面板、写入日历按钮都存在 | 可演示，但存在自动写入与“写入日历”按钮语义重复风险 |
| Demo 2：计划维护、延期与批量操作 | 查看所有任务；逾期扫描；今日维护；整体顺延；批量操作 | 按钮和 API 都存在 | 可演示，但批量选择和整体顺延有日期解析/状态边界风险 |
| Demo 3：冲突处理、工作台执行、合并拆分 | 日历冲突区；移动到空闲窗口；Maxwell 工作台；合并/拆分 | 入口存在 | 可演示，但冲突处理策略过粗，合并/拆分交互容易误操作 |
| Demo 4：跨 Agent 路由与秘书 Skill | 非 Maxwell Agent 私聊输入；系统路由 Maxwell；查看计划落库 | 前端能选择 Agent 并发消息 | 路由过程前端可见性不足，评委可能看不到明确 route trace |

## 2. 已确认 Bug / 风险清单

### CAL-DEMO-FE-001：Demo 1 自动写入后仍显示“写入日历”，容易重复操作

- 严重级别：P1
- Demo：Demo 1
- 前端入口：`打开日历 -> 查看所有任务 -> 计划详情 -> 写入日历`
- 现象：长期计划现在已支持自动写入日历，但前端仍保留“写入日历”按钮，且文案仍表达为手动投影。
- 风险：用户/评委可能以为还没写入，重复点击；后端虽然会跳过已有 `calendar_event_id` 的计划日，但前端只显示“已写入 0 个日历项”，体验像失败。
- 期望：如果计划日已全部投影，应显示“已写入日历”或“重新同步日历”，并展示已投影数量/跳过原因。
- 相关文件：`shadowlink-web/src/components/jarvis/CalendarPanel.tsx`
- 建议修复：计划详情统计 `selectedPlanDays` 中 `calendar_event_id` 数量，按钮文案动态化；结果显示 `projected_count + skipped.length`。

### CAL-DEMO-FE-002：Demo 4 路由到 Maxwell 的过程前端可见性不足

- 严重级别：P1
- Demo：Demo 4
- 前端入口：非 Maxwell Agent 私聊输入长期计划需求。
- 现象：前端 `chatHistory` 支持 `routing?: Record<string, unknown>`，但演示视图中没有明确看到“source_agent -> target_agent -> reason”的固定展示区。
- 风险：评委只能从回复文本猜测发生了路由，看不到“Agent 路由”这个核心卖点。
- 期望：Agent 回复卡片下方显示路由摘要，例如：`Alfred -> Maxwell · long_term_planning · reason`。
- 相关文件：`shadowlink-web/src/components/jarvis/AgentChatPanel.tsx`、`shadowlink-web/src/stores/jarvisStore.ts`。
- 建议修复：确认后端返回的 `routing` 字段是否稳定；前端消息气泡展示 route badge。

### CAL-DEMO-FE-003：Demo 2 批量操作选择状态不够清晰，容易误操作

- 严重级别：P2
- Demo：Demo 2
- 前端入口：计划详情 -> 每日计划 -> 多选 -> 批量完成/延期/取消。
- 现象：`togglePlanDaySelection()` 同时设置 `selectedPlanDay` 和 `selectedPlanDayIds`，但 UI 当前选中项、批量选中项、用于拆分的选中项共用同一个选择动作。
- 风险：用户为了查看详情点选计划日时，可能无意加入批量选择；之后批量操作误改多个计划日。
- 期望：查看详情和批量选择分离；批量模式下才显示复选框。
- 相关文件：`shadowlink-web/src/components/jarvis/CalendarPanel.tsx`。
- 建议修复：增加 `bulkSelectMode` 或复选框列；普通点击只设 `selectedPlanDay`，不改 `selectedPlanDayIds`。

### CAL-DEMO-FE-004：Demo 3 冲突处理只移动第一个 plan_day，不支持选择要移动的冲突项

- 严重级别：P2
- Demo：Demo 3
- 前端入口：日历 -> 冲突处理 -> 移动到空闲窗口。
- 现象：`resolveConflictWithFreeWindow()` 使用 `conflict.items.find(item_type === "plan_day")`，自动移动第一个计划日。
- 风险：如果冲突中有多个 plan_day，或者用户想移动另一个事项，前端没有选择权；演示时可能移动了不该移动的任务。
- 期望：冲突卡片展示可移动项列表，用户选择移动哪一个。
- 相关文件：`shadowlink-web/src/components/jarvis/CalendarPanel.tsx`。
- 建议修复：冲突卡片为每个 movable plan_day 单独提供“移动此项到空闲窗口”。

### CAL-DEMO-FE-005：Demo 3 冲突处理函数里重复调用 `loadAll()`

- 严重级别：P3
- Demo：Demo 3
- 前端入口：日历 -> 冲突处理 -> 移动到空闲窗口。
- 现象：`resolveConflictWithFreeWindow()` 成功后连续 `await loadAll(); await loadAll();`。
- 风险：增加一次不必要的全量数据加载，现场演示时变慢；也可能造成状态闪烁。
- 期望：只调用一次 `loadAll()`。
- 相关文件：`shadowlink-web/src/components/jarvis/CalendarPanel.tsx`。
- 建议修复：删除重复调用。

### CAL-DEMO-FE-006：Demo 2 整体顺延仍用 `new Date(`${day.plan_date}T00:00:00`)`，与已修复的本地日期工具不一致

- 严重级别：P2
- Demo：Demo 2
- 前端入口：计划详情 -> 整体顺延一天。
- 现象：`rescheduleSelectedPlanTomorrow()` 直接用 `new Date(`${day.plan_date}T00:00:00`)` 加一天；此前已经为本地日期边界新增 `localDateFromKey()`，但这里没有复用。
- 风险：不同浏览器/时区下可能再次出现日期边界问题。
- 期望：所有 `plan_date` 的 date-key 运算都走统一本地日期工具。
- 相关文件：`shadowlink-web/src/components/jarvis/CalendarPanel.tsx`。
- 建议修复：用 `localDateFromKey(day.plan_date)` 代替直接 `new Date(...)`。

### CAL-DEMO-FE-007：Demo 1 / Demo 4 长期计划生成完成后前端不会自动打开日历或定位到新计划

- 严重级别：P2
- Demo：Demo 1、Demo 4
- 前端入口：私聊输入长期目标。
- 现象：聊天完成后，用户需要手动打开日历、进入“查看所有任务”、再在列表中找新计划。
- 风险：演示链路不够顺，评委看不到“刚生成的计划在哪里”。
- 期望：Agent action 中如果返回 `plan`/`persisted`，前端显示“打开新计划”按钮，点击后打开 CalendarPanel 并选中新计划。
- 相关文件：`AgentChatPanel.tsx`、`CalendarPanel.tsx`、`jarvisStore.ts`。
- 建议修复：在 chat action 渲染区识别 `type=task.plan && persisted`，暴露跳转入口。

### CAL-DEMO-FE-008：Demo 2 今日维护按钮每次都弹确认，现场演示节奏偏慢

- 严重级别：P3
- Demo：Demo 2
- 前端入口：Maxwell 工作台 -> 今日计划维护 -> 运行。
- 现象：`runDailyMaintenanceOnce()` 强制 `confirm()`。
- 风险：评委演示时多一步浏览器确认弹窗，打断节奏；且 confirm 文案无法展示更多上下文。
- 期望：改为面板内二次确认或“运行维护”按钮旁展示说明。
- 相关文件：`CalendarPanel.tsx`。
- 建议修复：后续 UI 优化，不影响核心功能。

### CAL-DEMO-FE-009：Demo 3 合并按钮文案有歧义

- 严重级别：P3
- Demo：Demo 3
- 前端入口：计划详情 -> 任务合并/拆分。
- 现象：选择“合并目标”后按钮文案是“合并到当前计划”，但实际调用是把当前计划 `sourcePlan` 合并到选择的 `target`。
- 风险：用户可能理解反了，误把当前计划并入另一个计划。
- 期望：按钮文案改为“将当前计划合并到所选计划”。
- 相关文件：`CalendarPanel.tsx`。
- 建议修复：只改文案即可。

### CAL-DEMO-FE-010：重复日程 409 在前端只显示原始错误，不够友好

- 严重级别：P2
- Demo：Demo 1、Demo 3、日程确认场景
- 前端入口：确认秘书日程 / 手动新增日程。
- 现象：后端现在返回 `duplicate_calendar_event`，但前端 `errorMessage()` 可能只显示通用 HTTP 错误文本或 JSON 字符串。
- 风险：用户不知道是“同名重复日程被拦截”，以为系统失败。
- 期望：前端识别 `detail.code === duplicate_calendar_event`，展示“已存在同名日程：xxx，不再重复安排”。
- 相关文件：`jarvisApi.ts`、`AgentChatPanel.tsx`、`CalendarPanel.tsx`。
- 建议修复：增强 `errorFromResponse()` / `errorMessage()` 对结构化 detail 的解析。

## 3. 需要人工从浏览器复测的关键脚本

### Demo 1 复测脚本
1. 选择 Maxwell 或从 Alfred 输入：`我 3 个月后要考雅思，目标 7 分。帮我安排一个每天都能执行的学习计划，平时晚上有空，周末可以多学一点。`
2. 打开日历。
3. 进入“查看所有任务”。
4. 检查顶层是否只显示一个“雅思备考计划”。
5. 点开计划，检查每日计划数量和日期连续性。
6. 检查是否已经投影到日历；如果点击“写入日历”，观察文案是否合理。

### Demo 2 复测脚本
1. 准备一个包含昨天/今天/明天计划日的长期计划。
2. 运行“逾期计划扫描”。
3. 运行“今日计划维护”。
4. 执行“整体顺延一天”。
5. 多选计划日执行批量完成/延期/取消。
6. 检查是否误选、误改、日期错位。

### Demo 3 复测脚本
1. 创建一个固定会议。
2. 创建或移动计划日到同一时间段。
3. 打开日历，看冲突卡片。
4. 点击“移动到空闲窗口”。
5. 检查移动的是不是用户期望的那一个计划日。
6. 检查 Maxwell 工作台是否能推送今日任务。
7. 测试合并/拆分计划的文案是否会误导。

### Demo 4 复测脚本
1. 先选择非 Maxwell Agent，例如 Alfred/Athena。
2. 输入：`我准备三个月后考雅思，目标 7 分。帮我安排每天学习计划，如果有几天没完成，要能自动顺延并提醒我。`
3. 检查聊天回复是否明确体现路由到 Maxwell。
4. 检查前端是否显示 route trace / route badge。
5. 打开日历，查看是否生成顶层计划和每日计划日。

## 4. 建议修复顺序

1. P1：`CAL-DEMO-FE-001`，解决自动写入后按钮/文案重复，避免 Demo 1 现场误判失败。
2. P1：`CAL-DEMO-FE-002`，增强 Agent 路由可见性，这是 Agent 项目的核心展示点。
3. P2：`CAL-DEMO-FE-010`，让重复日程拦截对用户友好可解释。
4. P2：`CAL-DEMO-FE-006`，统一日期 key 运算，避免日程日期问题复发。
5. P2：`CAL-DEMO-FE-003` / `CAL-DEMO-FE-004`，优化批量选择和冲突移动交互。
6. P3：`CAL-DEMO-FE-005` / `CAL-DEMO-FE-008` / `CAL-DEMO-FE-009`，处理性能小问题和演示文案。

## 5. 走查边界

- 本次没有启动浏览器执行真实点击，因为项目当前没有配置前端 E2E 自动化框架。
- 本次没有修改业务代码，只整理从前端入口可确认的 Demo 风险和 bug。
- 后续修复时应逐项处理，每修一个都补充对应前端契约测试或后端单测。

## 2026-05-01 20:55 - 修复 Demo 1 投影按钮重复语义

### 已修复内容
- 长期计划详情中的“写入日历”按钮改为派生状态：
  - 如果全部计划日已投影，显示“已写入日历”；
  - 如果部分计划日已投影，显示“补写入日历”；
  - 如果尚未投影，显示“写入日历”。
- 按钮文案和可点击状态由 `selectedPlanDays` 的派生摘要控制，不再依赖业务返回的模糊结果，避免前端和后端职责混在一起。

### 验证结果
- `shadowlink-ai/tests/unit/jarvis/test_calendar_frontend_contract.py::test_calendar_panel_project_button_reflects_projection_state`
- `shadowlink-web` `npm.cmd run type-check`

### 仍可继续优化
- 计划详情里“写入日历”按钮现在不会再误导，但如果要给评委演示“自动投影 + 重新同步”的区别，还可以增加一个专门的“同步状态”徽标。

## 2026-05-01 21:10 - 修复重复日程错误前端提示

### 已修复内容
- `jarvisApi.errorFromResponse()` 增加 `duplicate_calendar_event` 结构化错误解析。
- 当前端收到后端 409 重复日程错误时，展示用户可理解的提示：`已存在同名日程：xxx。为避免重复安排，本次没有写入。`
- `deleteCalendarEvent()` / `updateCalendarEvent()` 也改为复用统一错误解析，避免继续散落 `new Error(HTTP status)`。

### 解耦说明
- 重复判断仍由后端业务层负责；前端只负责把结构化错误转换成可理解文案。
- 没有把重复判断逻辑复制到前端，避免前后端规则不一致。

### 验证结果
- `shadowlink-ai/tests/unit/jarvis/test_calendar_frontend_contract.py::test_frontend_formats_duplicate_calendar_event_errors`
- `shadowlink-ai/tests/unit/jarvis/test_unified_planner.py::test_calendar_add_rejects_duplicate_title_even_when_time_differs`
- `shadowlink-web` `npm.cmd run type-check`

## 2026-05-01 21:20 - 修复计划日顺延日期 key 运算残留

### 已修复内容
- `movePlanDayTomorrow()` 不再使用 `new Date(`${day.plan_date}T00:00:00`)`，改为 `localDateFromKey(day.plan_date)`。
- `rescheduleSelectedPlanTomorrow()` 整体顺延也统一使用 `localDateFromKey(day.plan_date)`。
- 这样单个延期和整体顺延都复用同一个本地 date-key 解析入口，避免日期错位问题再次散落出现。

### 解耦说明
- 前端只负责本地 date-key 的 UI 运算；后端仍负责实际 plan day 更新和日历同步。
- 没有在多个函数里各自手写日期解析规则。

### 验证结果
- `shadowlink-ai/tests/unit/jarvis/test_calendar_frontend_contract.py::test_calendar_panel_uses_local_date_key_for_plan_day_shifts`
- `shadowlink-web` `npm.cmd run type-check`

## 2026-05-01 21:35 - 修复计划日详情点击与批量选择耦合

对应问题：`CAL-DEMO-FE-003`

根因：
- 每日计划列表的整行 `onClick` 直接调用 `togglePlanDaySelection(day)`，导致“查看详情”和“加入批量选择”共用同一个交互入口。
- 用户只是点击计划日查看详情时，也会悄悄加入 `selectedPlanDayIds`，后续批量延期/完成/取消容易误操作。

修复：
- 新增 `bulkPlanDaySelectMode`，批量操作必须显式点击“批量选择”进入。
- 新增 `selectPlanDayForDetail()`，普通点击只更新详情态，不再修改批量选择集合。
- 保留 `togglePlanDaySelection()` 只服务复选框，批量模式退出和批量操作完成后清空选择。
- UI 文案明确提示“普通点击查看详情，批量模式下勾选计划日”，避免演示和真实使用时混淆。

解耦边界：
- 前端只负责交互状态隔离和用户确认。
- 后端 `bulkUpdatePlanDays` 仍负责实际计划日状态/日期变更，不把批量业务规则挪到前端。

验证：
- `python -m pytest shadowlink-ai\tests\unit\jarvis\test_calendar_frontend_contract.py::test_calendar_panel_separates_plan_day_detail_click_from_bulk_selection -q --basetemp=shadowlink-ai\.pytest_calendar_tmp`
  - 结果：`1 passed, 1 warning`
  - 运行时临时设置：`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`，并移除 `SSLKEYLOGFILE`。
- `cd shadowlink-web; npm.cmd run type-check`
  - 结果：通过，exit code 0。

## 2026-05-01 21:55 - 日程模块从功能修补升级为秘书式重排重构

背景：
- 用户反馈当前效果很差：冲突重排会改到过去日期、冲突可以忽略、延期只是机械改日期、秘书没有承担日程协调职责。
- 该问题不是单个前端交互 bug，而是当前日程模块调度模型不合理。

确认方向：
- 冲突时采用“先给建议”：秘书生成 2-3 个可选方案，用户选择后执行。
- LLM/秘书负责生成方案和解释差异；确定性代码负责过去日期、冲突、重复、空闲窗口等硬约束。
- 前端不再直接决定最终重排日期，只表达用户意图并展示方案。

新增设计文档：
- `docs/lsq-worklog/4-30-worklog/calendar-module-reschedule-redesign.md`

后续修复原则：
- 不再围绕单个按钮做兜底修补。
- 优先做 P0 止血：禁止过去日期写入、移除正式 UI 的忽略冲突、延期不再直接 `+1 day` 写库。
- 后续逐步实现统一 Deterministic Planner Guard、proposal 生成/执行 API、Maxwell 秘书方案生成、前端方案选择体验。

## 2026-05-01 22:15 - 补充秘书 Skill 结构化调度设计与实施计划

用户补充：
- 秘书 Skill 需要判断当天日程情况，返回特定格式的日程安排，再由代码写库。
- 重排也需要请求 LLM，让它基于长期任务整体安排返回延期一天后的特定格式，再由代码写库。
- 智能体交互设计需要认真设计，不能只是机械执行按钮命令。

已补充设计：
- `docs/lsq-worklog/4-30-worklog/calendar-module-reschedule-redesign.md`
  - 新增“秘书 Skill 与智能体交互设计”。
  - 明确 Agent 路由、Skill 输入格式、`secretary_schedule.v1` 当天安排输出、`secretary_reschedule.v1` 重排方案输出。
  - 明确 LLM 只生成结构化安排/方案，代码负责校验、暂存、用户选择和写库。

新增实施计划：
- `docs/lsq-worklog/4-30-worklog/calendar-module-reschedule-implementation-plan.md`
  - Task 1：P0 过去日期 Guard。
  - Task 2：移除正式 UI 的忽略冲突。
  - Task 3：停止前端机械延期写库。
  - Task 4：秘书结构化 JSON parser。
  - Task 5：proposal 生成 API。
  - Task 6：proposal 执行 API。
  - Task 7：前端 proposal 体验。
  - Task 8：当天日程 Skill flow。
  - Task 9：持续留痕和指标记录。

执行原则：
- 先止血，再接智能。
- 不让 LLM 直接写数据库。
- 不让前端直接计算最终调度日期。
- 每一步都按 TDD 补测试，并继续写入日程模块现有留痕文档。

## 2026-05-01 22:35 - 根目录新增日程模块接口协议文档

背景：
- 在落地日程重排计划前，用户要求先把日程相关部分解耦，写好日程接口层。
- 目标是让日程模块与其它模块以及前端彻底解耦，避免继续出现前端直接算日期、Agent 直接写库、LLM 输出直接落库等问题。

新增文档：
- `CALENDAR_MODULE_INTERFACE_CONTRACT.md`

文档内容：
- 明确 Calendar Module 的所有权边界：计划、计划日、日历投影、冲突、空闲窗口、proposal、执行、审计。
- 明确非所有权边界：聊天 UI、Agent 路由、时间地点、天气、设置、LLM Provider、RAG/Memory/Mood。
- 设计未来后端包结构：`contracts.py`、`facade.py`、`guard.py`、`availability.py`、`plans.py`、`plan_days.py`、`projection.py`、`proposals.py`、`secretary_adapter.py`、`repository.py`。
- 统一 API namespace：后续新接口收敛到 `/api/v1/jarvis/calendar/*`。
- 定义共享类型：`CalendarItemRef`、`LocalDate`、`LocalTime`、`ScheduleChange`、`CalendarError`。
- 定义 Query APIs、Command APIs、Proposal APIs、Secretary Skill Contract、Frontend Contract、Agent/Tool Contract、Persistence Contract。
- 定义迁移策略和解耦验收清单。

关键约束：
- 前端不能计算最终重排日期。
- Agent/Skill 不能直接写日程持久化。
- LLM 输出不能直接落库，必须先转 proposal 并经过 Guard。
- Proposal 生成不写状态，Proposal apply 重新校验后才写库。
- 正式 UI 不能有“忽略冲突”。
- 所有写路径必须拒绝过去日期。

## 2026-05-01 22:55 - 执行接口解耦计划 Task 1：P0 过去日期 Guard

对应计划：
- `docs/lsq-worklog/4-30-worklog/calendar-module-reschedule-implementation-plan.md`
- Task 1: P0 Guard for Past Dates

本次改动：
- 新增 `shadowlink-ai/app/jarvis/planner_guard.py`。
- 新增确定性校验函数：
  - `validate_not_past()`：拒绝今天之前的计划日期。
  - `validate_time_range()`：拒绝开始时间不早于结束时间。
  - `validate_plan_day_move()`：统一校验计划日移动/重排 patch。
- 将旧写入口接入 Guard：
  - `PATCH /plan-days/{day_id}`
  - `POST /plan-days/{day_id}/move`
  - `POST /plan-days/bulk-update`
  - `POST /plans/{plan_id}/reschedule`
- Guard 失败统一返回 422，错误 code 为 `planner_guard_violation`。

解耦意义：
- 过去日期、时间顺序这类硬约束从前端和零散业务逻辑中抽出，收敛到后端确定性 Guard。
- 旧接口还保留兼容，但写入前必须通过统一 Guard，避免旧路径继续绕过新边界。
- 这一步不引入 LLM，不做 proposal，只先止血，符合“先解耦、再落地智能重排”的顺序。

验证：
- `python -m pytest shadowlink-ai\tests\unit\jarvis\test_unified_planner.py::test_plan_day_move_rejects_past_date shadowlink-ai\tests\unit\jarvis\test_unified_planner.py::test_move_plan_day_item_rejects_past_date_before_persisting shadowlink-ai\tests\unit\jarvis\test_unified_planner.py::test_reschedule_plan_days_updates_calendar_projection -q --basetemp=shadowlink-ai\.pytest_calendar_tmp`
  - 结果：`3 passed, 5 warnings`
  - 运行时临时设置：`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`，并移除 `SSLKEYLOGFILE`。

## 2026-05-01 23:20 - 日程模块实施计划收缩为 MVP

背景：
- 用户确认当前不需要过重的完整 proposal / Calendar Facade 架构。
- 当前目标是先实现基本可用的短期计划、长期计划、智能体重排闭环。
- 重点是靠 Maxwell / 秘书智能体生成结构化计划，代码校验后写库。

新增 MVP 计划：
- `docs/lsq-worklog/4-30-worklog/calendar-module-mvp-implementation-plan.md`

旧计划状态：
- `docs/lsq-worklog/4-30-worklog/calendar-module-reschedule-implementation-plan.md`
- 已在文档开头标注暂停执行，仅作为后续增强参考。

MVP 范围：
- 保留已完成的 P0 Guard。
- 新增秘书 JSON parser：`secretary_schedule.v1`、`secretary_long_plan.v1`、`secretary_reschedule.v1`。
- 新增秘书规划服务：短期计划、长期计划、重排统一处理。
- 新增 MVP API：`POST /api/v1/jarvis/planner/secretary-plan`。
- 前端接入该 API，先打通“让秘书重排”和基本计划创建闭环。

暂不做：
- 完整 proposal set 生命周期。
- 三方案 A/B/C UI。
- 完整 `/api/v1/jarvis/calendar/*` namespace 迁移。
- 完整 Calendar Facade 包拆分。
- 复杂审计和指标系统。

验收重点：
- 短期自然语言计划能写入。
- 长期自然语言计划能写入。
- 长期计划在所有任务里只显示一个主任务。
- 每日计划在详情、今日、日历中显示。
- 重排由 Maxwell 结构化输出驱动，不是前端 `+1 day`。
- 写库前必须经过 Guard。

## 2026-05-01 23:35 - 执行 MVP Task 2：秘书 JSON Parser

对应计划：
- `docs/lsq-worklog/4-30-worklog/calendar-module-mvp-implementation-plan.md`
- Task 2：秘书 JSON Parser

本次改动：
- 新增 `shadowlink-ai/app/jarvis/secretary_scheduler.py`。
- 新增 `shadowlink-ai/tests/unit/jarvis/test_secretary_scheduler.py`。
- 支持解析三种 MVP schema：
  - `secretary_schedule.v1`：短期 / 单日计划。
  - `secretary_long_plan.v1`：长期计划 + 每日计划。
  - `secretary_reschedule.v1`：重排后的后续计划。
- Parser 只负责严格 JSON 解析和基础字段校验，不写库、不调 LLM。
- 明确拒绝 Markdown fenced JSON，避免 LLM 输出 ```json 包裹内容后被误当成可执行结果。
- 校验基础字段：schema、intent、summary、plan、days/items、date、title、start_time、end_time、reschedule day id。

解耦意义：
- Maxwell / LLM 以后只能通过结构化 JSON 与日程模块交互。
- LLM 输出不会直接进入数据库，必须先过 parser，再进入后续 Guard 和 service。
- 短期计划、长期计划、重排使用三个明确 schema，避免前后端和 Agent 之间继续靠隐式字段约定。

验证：
- `python -m pytest shadowlink-ai\tests\unit\jarvis\test_secretary_scheduler.py -q --basetemp=shadowlink-ai\.pytest_calendar_tmp`
  - 结果：`8 passed, 1 warning`
- `python -m pytest shadowlink-ai\tests\unit\jarvis\test_unified_planner.py::test_plan_day_move_rejects_past_date shadowlink-ai\tests\unit\jarvis\test_unified_planner.py::test_move_plan_day_item_rejects_past_date_before_persisting -q --basetemp=shadowlink-ai\.pytest_calendar_tmp`
  - 结果：`2 passed, 1 warning`
- 运行时临时设置：`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`，并移除 `SSLKEYLOGFILE`。

## 2026-05-01 23:55 - 执行 MVP Task 3：秘书规划服务

对应计划：
- `docs/lsq-worklog/4-30-worklog/calendar-module-mvp-implementation-plan.md`
- Task 3：秘书规划服务

本次改动：
- 新增 `shadowlink-ai/app/jarvis/secretary_planning_service.py`。
- 新增 `shadowlink-ai/tests/unit/jarvis/test_secretary_planning_service.py`。
- 新增统一服务函数 `run_secretary_plan_request()`，支持三个 MVP intent：
  - `short_schedule`：Maxwell 返回 `secretary_schedule.v1` 后写入 short_term plan + plan_day。
  - `long_plan`：Maxwell 返回 `secretary_long_plan.v1` 后写入一个 long_term plan + 多个 plan_days。
  - `reschedule_plan`：Maxwell 返回 `secretary_reschedule.v1` 后更新已有 plan_days。
- 写库前统一调用 `planner_guard.validate_plan_day_move()`，拒绝过去日期和无效时间范围。
- 当前阶段 `auto_project_calendar` 参数已保留，但服务先返回空 `calendar_events`，日历投影接入留到 API / 前端闭环阶段处理。

解耦意义：
- LLM 仍只返回严格 JSON，不直接写库。
- Parser、Guard、Persistence 三层已经串起来，但职责分离：
  - `secretary_scheduler.py`：只解析和校验结构。
  - `planner_guard.py`：只做硬约束。
  - `secretary_planning_service.py`：负责编排和写库。
- 长期计划只写一个 plan，多天内容写入 plan_days，避免再次污染所有任务列表。

验证：
- `python -m pytest shadowlink-ai\tests\unit\jarvis\test_secretary_planning_service.py -q --basetemp=shadowlink-ai\.pytest_calendar_tmp`
  - 结果：`4 passed, 1 warning`
- `python -m pytest shadowlink-ai\tests\unit\jarvis\test_secretary_scheduler.py shadowlink-ai\tests\unit\jarvis\test_unified_planner.py::test_plan_day_move_rejects_past_date shadowlink-ai\tests\unit\jarvis\test_unified_planner.py::test_move_plan_day_item_rejects_past_date_before_persisting -q --basetemp=shadowlink-ai\.pytest_calendar_tmp`
  - 结果：`10 passed, 1 warning`
- 运行时临时设置：`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`，并移除 `SSLKEYLOGFILE`。

## 2026-05-01 00:10 - 执行 MVP Task 4：秘书规划 API 入口

对应计划：
- `docs/lsq-worklog/4-30-worklog/calendar-module-mvp-implementation-plan.md`
- Task 4：API 入口

本次改动：
- 在 `shadowlink-ai/app/api/v1/jarvis_router.py` 新增 `SecretaryPlanRequest`。
- 新增 API：`POST /api/v1/jarvis/planner/secretary-plan`。
- API 接入 `run_secretary_plan_request()`，支持 MVP 三类 intent：
  - `short_schedule`
  - `long_plan`
  - `reschedule_plan`
- API 支持参数：`intent`、`message`、`today`、`plan_id`、`plan_day_ids`、`timezone`、`auto_project_calendar`。
- 服务层 `ValueError` 转为 422，错误 code 为 `secretary_plan_failed`。
- 新增集成测试 `test_secretary_plan_endpoint_creates_long_plan`，验证 API 能通过 fake Maxwell JSON 创建长期计划和计划日。

解耦意义：
- 前端和 Agent 后续可以调用一个统一 MVP 入口，不再各自拼不同写库逻辑。
- LLM 仍由后端依赖注入，前端不直接接触 LLM 输出。
- API 只负责编排请求和错误转换，具体解析、Guard、写库仍在服务层。

验证：
- `python -m pytest shadowlink-ai\tests\integration\test_jarvis_api.py::test_secretary_plan_endpoint_creates_long_plan -q --basetemp=shadowlink-ai\.pytest_calendar_tmp`
  - 结果：`1 passed, 21 warnings`
  - warnings 主要来自当前环境未加载 pytest-asyncio 后文件内既有 async marks 提示。
- `python -m pytest shadowlink-ai\tests\unit\jarvis\test_secretary_planning_service.py shadowlink-ai\tests\unit\jarvis\test_secretary_scheduler.py shadowlink-ai\tests\unit\jarvis\test_unified_planner.py::test_plan_day_move_rejects_past_date shadowlink-ai\tests\unit\jarvis\test_unified_planner.py::test_move_plan_day_item_rejects_past_date_before_persisting -q --basetemp=shadowlink-ai\.pytest_calendar_tmp`
  - 结果：`14 passed, 1 warning`
- 运行时临时移除 `SSLKEYLOGFILE`。

## 2026-05-01 00:35 - 执行 MVP Task 5：前端接入秘书规划 API

对应计划：
- `docs/lsq-worklog/4-30-worklog/calendar-module-mvp-implementation-plan.md`
- Task 5：前端接入 MVP API

本次改动：
- `shadowlink-web/src/services/jarvisApi.ts`
  - 新增 `SecretaryPlanRequest`。
  - 新增 `SecretaryPlanResult`。
  - 新增 `jarvisApi.createSecretaryPlan()`，调用 `POST /api/v1/jarvis/planner/secretary-plan`。
- `shadowlink-web/src/components/jarvis/CalendarPanel.tsx`
  - 新增 `requestSecretaryReschedule()`。
  - 单个计划日“延期到明天”改为“让秘书重排”。
  - 长期计划“整体顺延一天”改为“让秘书重排”。
  - 每日计划列表中的单个延期按钮改为“让秘书重排”。
  - 批量延期不再发送 `shift_days: 1`，改为把选中计划日提交给秘书重排。
- `shadowlink-ai/tests/unit/jarvis/test_calendar_frontend_contract.py`
  - 新增契约测试，要求前端使用 `createSecretaryPlan()` 和 `/planner/secretary-plan`。
  - 更新旧日期顺延测试：现在要求前端不再计算 `+1 day` 重排。

解耦意义：
- 前端不再直接决定最终重排日期。
- 前端只表达“让秘书重排”的意图，并把 plan / plan_day refs 交给后端。
- 后端通过 Maxwell JSON + parser + Guard + service 决定最终写库。
- 旧的机械 `shift_days` 批量延期路径不再由正式 UI 调用。

验证：
- `cd shadowlink-web; npm.cmd run type-check`
  - 结果：通过。
- `python -m pytest shadowlink-ai\tests\unit\jarvis\test_calendar_frontend_contract.py::test_calendar_panel_uses_secretary_plan_api_for_reschedule_intent shadowlink-ai\tests\unit\jarvis\test_calendar_frontend_contract.py::test_calendar_panel_separates_plan_day_detail_click_from_bulk_selection shadowlink-ai\tests\unit\jarvis\test_calendar_frontend_contract.py::test_calendar_panel_no_longer_computes_plus_one_day_reschedules -q --basetemp=shadowlink-ai\.pytest_calendar_tmp`
  - 结果：`3 passed, 1 warning`
- `python -m pytest shadowlink-ai\tests\integration\test_jarvis_api.py::test_secretary_plan_endpoint_creates_long_plan -q --basetemp=shadowlink-ai\.pytest_calendar_tmp`
  - 结果：`1 passed, 21 warnings`
- `python -m pytest shadowlink-ai\tests\unit\jarvis\test_secretary_planning_service.py shadowlink-ai\tests\unit\jarvis\test_secretary_scheduler.py -q --basetemp=shadowlink-ai\.pytest_calendar_tmp`
  - 结果：`12 passed, 1 warning`

## 2026-05-02 续：日程 MVP Task 6 Demo 验证闭环

### 本轮目标
- 继续日程模块 MVP 改造后的 demo 验证，不新增任务文件，沿用日程模块 bug/验收留痕。
- 覆盖短期计划、长期计划、智能重排三条最小端到端 API 链路。

### 修复内容
- `shadowlink-ai/tests/integration/test_jarvis_api.py` 补充 `asyncio` 导入。
- 根因：新增的重排 demo 集成测试需要用 `asyncio.run()` 预置已有长期计划数据，但测试文件未导入 `asyncio`，导致测试在进入业务断言前失败。
- 处理方式：仅修复测试依赖导入，不改动日程业务逻辑。

### 验证结果
- MVP demo 集成测试：`3 passed, 21 warnings`
  - `test_secretary_plan_endpoint_creates_short_schedule`
  - `test_secretary_plan_endpoint_creates_long_plan`
  - `test_secretary_plan_endpoint_reschedules_existing_plan`
- 后端关键回归：`27 passed, 1 warning`
  - `test_secretary_scheduler.py`
  - `test_secretary_planning_service.py`
  - `test_calendar_frontend_contract.py`
- 前端类型检查：`npm.cmd run type-check`，exit 0。

### 当前状态
- 短期计划 API、长期计划 API、秘书智能重排 API 的 MVP 验证已打通。
- 前端日程面板的重排入口已改为调用秘书规划接口，不再由前端机械计算最终日期。
- LLM 仍只负责返回结构化 JSON，后端负责解析、Guard 校验和写库。

### 后续建议
- 下一步应继续围绕真实前端入口验证：自然语言输入 → Agent/秘书 skill → 结构化计划 → 后端写库 → 今日日程/日历投影展示。
- 若要继续增强，应优先补自动日历投影和重复任务拦截的业务验收，而不是扩大接口数量。

## 2026-05-02 续：日程 MVP 真实业务链路接通

### 本轮目标
- 不只验证 `/planner/secretary-plan` API，而是让真实 Maxwell/秘书 skill 能把“写入日程”的用户请求交给秘书规划服务。
- 让 demo 可交付：计划写库后同时生成日历投影，前端日历/今日日程有数据可展示。

### 关键修复
- 新增 `shadowlink-ai/app/jarvis/planner_calendar_projection.py`。
  - 负责 plan_day → calendar_event 的投影。
  - 负责 plan_day 更新后同步已有 calendar_event。
  - 让投影逻辑从 API router 中解耦出来，避免秘书服务反向依赖 FastAPI 路由。
- `secretary_planning_service.py` 接入自动投影。
  - 短期计划：保存 short_term plan + plan_day 后自动投影到 calendar_event。
  - 长期计划：保存 long_term plan + 多个 plan_day 后可自动投影。
  - 重排：已有日历投影会同步更新；没有投影的 plan_day 会按需要补投影。
- `jarvis_router.py` 中旧的内联投影函数改为薄包装，统一复用 planner calendar projection service。
- `JarvisTaskPlanDecomposeTool` 增加真实写入分支。
  - 当用户请求包含“写入日程 / 加入日程 / 帮我安排 / 安排学习计划”等明确落库意图时，调用 `run_secretary_plan_request()`。
  - Maxwell/秘书 skill 不直接写库，只交给 secretary planning service；service 负责 JSON 解析、Guard 校验、写库和投影。
  - 没有 LLM resource 时保留旧本地拆解路径，避免破坏既有测试和离线演示。

### 新增验证
- `test_secretary_short_schedule_auto_projects_calendar_event`
  - 证明秘书短期计划写库后会生成 calendar_event，并把 `calendar_event_id` 写回 plan_day。
- `test_task_plan_tool_writes_schedule_through_secretary_service`
  - 证明真实 Maxwell skill 对“写入日程”请求会走秘书规划服务并落库。

### 验证结果
- 关键后端回归：`29 passed, 1 warning`
  - `test_secretary_scheduler.py`
  - `test_secretary_planning_service.py`
  - `test_calendar_frontend_contract.py`
  - `test_agents.py::test_task_plan_tool_writes_schedule_through_secretary_service`
- 三条 MVP API demo：`3 passed, 24 warnings`
  - 短期计划
  - 长期计划
  - 智能重排
- 前端类型检查：`npm.cmd run type-check`，exit 0。

### 当前可交付链路
- 用户自然语言请求：例如“我要考雅思，未来 30 天帮我安排学习计划并写入日程”。
- Maxwell/秘书 skill：`jarvis_task_plan_decompose` 识别明确写入意图。
- 秘书规划服务：调用 LLM，要求返回严格 JSON。
- 后端服务：解析 JSON、Guard 校验日期/时间、写入 plan 和 plan_day。
- 日历投影服务：把有具体日期时间的 plan_day 投影成 calendar_event。
- 前端：继续通过任务、今日安排、日历项接口刷新展示。

### 仍需关注
- 真实线上 LLM 输出必须严格遵守 secretary JSON schema；如果模型返回 markdown 或字段缺失，会被 parser 拒绝，这是符合 MVP 设计的硬边界。
- 后续若继续增强，优先做重复任务拦截与真实前端手工验收，而不是新增复杂 proposal 架构。

## 2026-05-02 续：秘书聊天停在 `<tool_calls>` 的 demo bug 修复

### 用户复现场景
- 输入：`明天下午三点提醒我和产品同学开一个路演复盘会，提前半小时准备材料。`
- 现象：秘书回复“让我先检查一下明天下午的日程情况”，随后直接把模型工具标签展示出来：
  - `<tool_calls>`
  - `<tool_call name="jarvis_calendar_upcoming">...</tool_call>`
- 问题：聊天没有继续执行工具，也没有生成最终自然语言回复，demo 链路中断。

### 根因定位
- `tool_runtime.strip_tool_blocks()` 只支持项目自定义格式：
  - `<jarvis-tool>{"tool_name":"...","arguments":{...}}</jarvis-tool>`
- 实际 LLM 输出了另一种常见 XML 工具格式：
  - `<tool_calls><tool_call name="...">{...}</tool_call></tool_calls>`
- 因此 runtime 没有识别到工具调用，把整段 `<tool_calls>` 当普通文本返回给前端。
- 同时 `jarvis_calendar_upcoming` 只支持 `hours_ahead/limit`，不支持模型实际给出的 `start/end` 时间窗口参数。即使解析成功，也会因为参数不匹配导致工具执行失败。

### 修复内容
- `shadowlink-ai/app/jarvis/tool_runtime.py`
  - 新增 `<tool_calls>/<tool_call name="...">` 格式解析。
  - 清理最终展示文本中的 `<tool_calls>` 块，避免工具标签泄漏到前端。
  - `run_agent_turn()` 现在能识别该格式、执行工具、再发起二次 LLM 回复。
- `shadowlink-ai/app/tools/jarvis_tools.py`
  - `JarvisCalendarUpcomingTool` 增加 `start/end` 参数。
  - 如果提供明确窗口，调用 `get_events_between(start, end)`；否则保持原来的 `hours_ahead` 行为。
- 新增/更新测试：
  - `test_tool_runtime.py::test_strip_tool_like_blocks_accepts_model_tool_calls_xml`
  - `test_tool_runtime.py::test_run_agent_turn_executes_model_tool_calls_xml`
  - `test_agents.py::test_calendar_upcoming_tool_accepts_explicit_time_window`

### 验证结果
- 日程/工具链路回归：`9 passed, 1 warning`
  - tool runtime XML 工具解析
  - `jarvis_calendar_upcoming` 显式时间窗口
  - Maxwell → secretary planning service 写入链路
  - secretary planning service 回归
- 前端类型检查：`npm.cmd run type-check`，exit 0。

### 当前状态
- 这类模型输出 `<tool_calls>` 的情况不会再停在标签文本上。
- 工具会被执行，执行结果会进入二次 LLM 回复，让秘书继续自然说明下一步。
- 明天下午 14:00-16:00 这类明确窗口查询可以正常走 `jarvis_calendar_upcoming(start,end)`。

### 后续建议
- 这个修复解决“工具调用不继续”的断点。
- 该 demo 的完整写入体验还需要继续验收：查完无冲突后，秘书是否会继续调用写入日程/提醒的工具；如仍只检查不写入，需要继续优化 Maxwell 的日程写入策略，而不是再改解析器。

## 2026-05-02 续：秘书聊天等待态增加“正在...”步骤展示

### 用户反馈
- 日程 demo 中，秘书处理请求时长时间处于等待状态。
- 用户看不到系统在做什么，体验像卡死。
- 期望显示每一步正在做什么，最好是“正在...”形式。

### 方案选择
- MVP 阶段先做前端可见进度，不改后端协议。
- 原因：当前 `/chat` 完成前不会持续返回后端阶段事件；直接改 SSE/流式协议成本更高，且容易影响现有聊天链路。
- 本轮先在聊天面板本地显示清晰阶段：让用户知道系统正在分析、查上下文、调工具、整理回复。

### 实现内容
- `shadowlink-web/src/components/jarvis/AgentChatPanel.tsx`
  - 新增 `CHAT_PROGRESS_STEPS`：
    - `正在理解你的请求…`
    - `正在判断是否需要查看日程或调用工具…`
    - `正在检查相关上下文和日程冲突…`
    - `正在让秘书整理执行结果…`
    - `正在生成最终回复…`
  - 发送消息后启动本地计时器，每 1.8 秒推进一个阶段。
  - 请求结束后清理计时器并重置阶段。
  - 原来的三点 loading 气泡替换为可读步骤列表，已完成步骤显示 `✓`，当前步骤显示 `…`。
- `shadowlink-ai/tests/unit/jarvis/test_chat_frontend_progress_contract.py`
  - 增加前端契约测试，防止以后退回无信息的三点等待。

### 验证结果
- 前端契约测试：`1 passed, 1 warning`
- 前端类型检查：`npm.cmd run type-check`，exit 0。

### 当前效果
- 用户发送日程/提醒 demo 后，不再只看到空白等待或三点气泡。
- 页面会持续显示类似：
  - 正在理解你的请求…
  - 正在判断是否需要查看日程或调用工具…
  - 正在检查相关上下文和日程冲突…
  - 正在让秘书整理执行结果…
  - 正在生成最终回复…

### 后续增强建议
- 若后续要更真实，可以把后端 `timing_spans` 或 SSE 进度事件接入前端，用真实阶段替换本地预估阶段。
- 当前版本优先解决 demo 等待期间“用户看不到系统在干什么”的交付问题。

## 2026-05-02 续：清理历史日程数据 + 日视图删除入口

### 用户需求
- 先删除之前所有日程记录，避免 demo 测试数据混乱。
- 修改前端：用户可以在日视图里用 Delete 删除视图项，或者右击选择删除。

### 数据清理
- 操作前已备份当前数据库：`shadowlink-ai/data/jarvis.db.bak-calendar-reset-<timestamp>`。
- 已清空日程/计划相关测试数据表：
  - `pending_actions`: 45 → 0
  - `background_task_days`: 30 → 0
  - `background_tasks`: 2 → 0
  - `jarvis_plan_days`: 47 → 0
  - `jarvis_plans`: 16 → 0
  - `jarvis_calendar_events`: 77 → 0
  - `jarvis_agent_events`: 109 → 0
  - `maxwell_workbench_items`: 0 → 0
- 清理后再次确认上述表均为 0。

### 后端修复
- `shadowlink-ai/app/api/v1/jarvis_router.py`
  - 新增 `DELETE /api/v1/jarvis/plan-days/{day_id}`。
  - 新增 `DELETE /api/v1/jarvis/background-task-days/{day_id}`。
  - 删除采用软删除：状态更新为 `deleted`，避免直接物理删除破坏业务链路。
  - 如果计划日/任务日已有日历投影，会同步把对应 calendar event 状态置为 `deleted`。

### 前端修复
- `shadowlink-web/src/services/jarvisApi.ts`
  - 新增 `deletePlanDay(dayId)`。
  - 新增 `deleteBackgroundTaskDay(dayId)`。
- `shadowlink-web/src/components/jarvis/CalendarPanel.tsx`
  - 日视图中的普通日历项、计划日、背景任务日都支持：
    - 聚焦后按 `Delete` / `Backspace` 删除。
    - 右键触发删除确认。
  - 日视图非 compact 项增加 `右键/Delete 删除` 提示。
  - 右侧详情面板中，计划日和背景任务日也新增删除按钮。

### 验证结果
- 前端删除交互契约测试：`2 passed, 1 warning`
- 前端类型检查：`npm.cmd run type-check`，exit 0。

### 当前状态
- 测试用历史日程记录已清空。
- 日视图已经支持对三类展示项进行删除：普通日历事件、长期计划拆分出的计划日、旧背景任务日。
- 删除使用软删除，符合当前日程模块“不破坏业务逻辑、不直接删链路”的安全原则。
