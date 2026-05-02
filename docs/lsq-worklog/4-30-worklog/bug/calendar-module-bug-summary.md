# 日程模块 Bug 梳理

日期：2026-05-01

## 范围

- 前端日程入口：`shadowlink-web/src/components/jarvis/DashboardCards.tsx` 中“打开日历”按钮触发 `onOpenCalendar`。
- 前端日历面板：`shadowlink-web/src/components/jarvis/CalendarPanel.tsx`。
- 前端 API：`shadowlink-web/src/services/jarvisApi.ts` 中 calendar、planner、pending-actions、background-tasks、plans 相关函数。
- 前端 store：`shadowlink-web/src/stores/jarvisStore.ts` 中 `addCalendarEvent`、`updateCalendarEvent`、`deleteCalendarEvent`。
- 后端接口：`shadowlink-ai/app/api/v1/jarvis_router.py` 中 `/calendar/events`、`/planner/calendar-items`、`/pending-actions`、`/background-tasks`、`/plans`、`/plan-days` 等。
- 后端日历适配：`shadowlink-ai/app/mcp/adapters/calendar_adapter.py`。
- 日程相关工具：`shadowlink-ai/app/tools/jarvis_tools.py` 中 `JarvisCalendar*`、`JarvisCheckinScheduleTool`、`JarvisPlanActivitySlotTool` 等。

## 待办文档核对

- 用户指定文件：`docs/lsq-worklog/4-30-worklog/pending-work-and-acceptance-summary.md`。
- 当前检查结果：该路径不存在，无法从该文档核对日程模块待办。
- 建议：如果该文档在其它分支/目录，后续需要补充进仓库或提供实际路径；否则本次只能基于现有代码和可搜索文档梳理 bug。

## P0：点击“打开日历”后整个页面黑屏

### 现象

- 用户点击 Dashboard 卡片中的“打开日历”后，整个页面黑屏。
- 这是前端运行时崩溃的典型表现：React 组件 render/effect 抛出未捕获异常，外层没有错误边界兜底。

### 当前链路

1. `JarvisHome` 维护 `calendarOpen` 状态。
2. `DashboardCards` 点击“打开日历”后调用 `setCalendarOpen(true)`。
3. `CalendarPanel` 挂载并执行 `loadAll()`。
4. `loadAll()` 并发请求：
   - `/planner/calendar-items`
   - `/pending-actions?status=pending`
   - `/background-tasks`
   - `/background-task-days`
   - `/plans`
   - `/plan-days`
5. 数据写入本地 state 后直接渲染日历、待确认安排、后台任务、计划等区域。

### 高概率根因 1：待确认 action 的 `arguments` 非对象时直接崩溃

- 位置：`CalendarPanel.tsx` 的“待确认安排”渲染区域。
- 代码路径中直接读取 `item.arguments.title`、`item.arguments.start`、`item.arguments.end`。
- TypeScript 类型声明 `PendingAction.arguments: Record<string, unknown>` 假定它一定存在，但后端只在 JSON 解析异常时置 `{}`；如果接口返回历史脏数据、`null`、数组、字符串或字段缺失，前端会在 render 阶段抛 `Cannot read properties of null/undefined`，导致页面黑屏。
- 严重性：P0。只要存在一条脏 pending action，打开日历即崩溃。

### 高概率根因 2：多个接口 Promise.all 任一失败会使面板长时间加载且无错误提示

- 位置：`CalendarPanel.tsx` 的 `loadAll()`。
- 当前 `Promise.all([...])` 没有 `catch` 和错误 state。
- 任一接口 500/网络失败时，`finally` 会停止 loading，但用户看不到错误原因；部分 state 保持旧值/空值，可能表现为空白或异常。
- 严重性：P1。会让日程面板不可诊断，且不利于区分“无日程”和“加载失败”。

### 高概率根因 3：日期字段未校验，Invalid Date 可能传染到渲染逻辑

- 位置：`taskDayDate()`、`planDayDate()`、`eventsForDay()`、`formatTime()`、`formFromPending()`。
- 当前直接 `new Date(...)` 并参与排序、比较或格式化。
- 如果后端历史数据中出现空 `plan_date`、非法 `start_time`、非法 ISO 字符串，可能导致：
  - 排序结果异常；
  - 展示 `Invalid Date`；
  - 部分浏览器在 `toISOString()` 或 `Intl` 格式化时抛 `RangeError`。
- 严重性：P1/P2，取决于数据污染范围。

### 建议修复

1. 给 `CalendarPanel` 增加局部错误边界或至少增加 `loadError` 状态，避免日历异常拖垮整个 Jarvis 首页。
2. 对外部数据统一做 normalize：
   - `PendingAction.arguments` 不为普通对象时转 `{}`。
   - `calendarItems.items`、`conflicts`、`free_windows` 不为数组时转空数组。
   - `backgroundTasks`、`backgroundTaskDays`、`plans`、`planDays` 不为数组时转空数组。
3. 渲染待确认 action 时不要直接访问 `item.arguments.xxx`，应使用安全函数：`const args = safeRecord(item.arguments)`。
4. 日期解析增加 safe wrapper：非法日期返回 `null`，渲染层显示“时间未设置”，不要让异常进入 render。
5. `loadAll()` 不要用一个 `Promise.all` 决定整个面板成败；可用 `Promise.allSettled`，保证日历事件可用时先显示，失败模块显示局部错误。

## P1：日程面板缺少错误态和空态区分

### 现象

- 接口失败、无数据、数据为空数组时，当前 UI 很容易都显示成“今天暂无日程”或空白。
- 用户无法知道是没有日程，还是后端接口失败。

### 建议修复

- `CalendarPanel` 增加 `loadError`。
- 在面板顶部展示失败模块，例如：`日程数据加载失败：/planner/calendar-items 500`。
- API 层 `jarvisApi` 已有 `errorFromResponse()`，但日历面板没有展示错误。

## P1：打开日历会一次性请求过多数据，任一慢接口拖慢首屏

### 现状

- 打开日历立即请求 planner、pending、background tasks、task days、plans、plan days。
- 日历首屏其实只需要日历事件/计划日/任务日，后台任务详情可以切到“任务”tab 或选中任务时再懒加载。

### 风险

- 首次打开慢。
- 任一非核心接口失败影响整个面板体验。

### 建议修复

- 首屏只加载 `/planner/calendar-items` 和 `/pending-actions`。
- 切到“任务”tab 后再加载 background tasks/plans 详情。
- 或至少改为 `Promise.allSettled`，把非关键数据失败降级为局部提示。

## P2：月视图重复计算导致性能和一致性风险

### 现状

- 月视图每个日期格内多次调用 `eventsForDay()`、`planDaysForDay()`、`taskDaysForDay()`。
- 每次调用都会 filter/sort。

### 风险

- 数据量稍大时打开月视图卡顿。
- 多次计算结果在 render 内重复创建，调试困难。

### 建议修复

- 用 `useMemo` 按日期预分组。
- 渲染时直接取当天数组。

## P2：新增/编辑日程没有校验结束时间晚于开始时间

### 现状

- `payloadFromForm()` 直接把本地日期时间转 ISO。
- `saveForm()` 只校验 title。

### 风险

- 用户可创建 end <= start 的日程。
- 后端/工具层可能出现冲突计算异常或密度计算异常。

### 建议修复

- 前端保存前校验：标题、日期、开始时间、结束时间、结束晚于开始。
- 后端 `CalendarEventRequest` 也应校验，防止 API 直接写入异常数据。

## P2：任务/计划详情对脏数据容错不足

### 现状

- 多处直接使用 `selectedTask.title`、`selectedPlan.title`、`day.plan_date.slice(...)`、`day.start_time.slice(...)`。
- 如果接口返回字段缺失或非字符串，可能出现展示异常或运行时异常。

### 建议修复

- API 返回类型做 runtime normalize。
- 渲染层所有 `.slice()` 前确认类型为 string。
- 对任务/计划详情做 fallback 文案。

## 建议优先级

1. 先修 P0 黑屏：给 `CalendarPanel` 增加安全 normalize、错误边界/错误态，尤其修复 `item.arguments.xxx` 直接访问。
2. 再修 P1：`loadAll()` 改为 `Promise.allSettled` 或拆分核心/非核心加载。
3. 再修 P2：日期校验、月视图性能、表单时间合法性。

## 2026-05-01 P0 第一阶段修复记录

### 本次修复

- `CalendarPanel` 新增 `safeRecord()`、`safeArray()`、`errorMessage()`，对后端返回的未知结构做运行时兜底。
- `formFromPending()` 和“待确认安排”渲染不再直接访问 `item.arguments.title/start/end`，改为先 `safeRecord(item.arguments)`。
- `formatTime()` 对非法日期返回“未设置”，避免脏时间字符串在渲染中继续扩散。
- `loadAll()` 增加 `loadError`，并对 planner items、conflicts、free windows、pending actions、tasks、task days、plans、plan days 做数组归一化。
- `loadAll()` 捕获加载异常并在日历主区域显示错误提示，避免接口异常造成无提示空白/黑屏。

### 修改文件

- `shadowlink-web/src/components/jarvis/CalendarPanel.tsx`

### 验证记录

- `cd shadowlink-web; npm.cmd run type-check`：通过，exit 0。

### 剩余事项

- 当前仍是第一阶段防黑屏修复；下一步建议继续把 `loadAll()` 从整体 `Promise.all` 改为 `Promise.allSettled`，做到某个非核心接口失败时其它日程数据仍可显示。

## 2026-05-01 P0 黑屏兜底修复记录

### 背景

- 用户反馈第一阶段后仍存在点击“打开日历”黑屏。
- 这说明日历组件中仍有 render 阶段未捕获异常；仅靠局部数据 normalize 不足以保证主页面不被拖垮。

### 本次修复

- 新增 `CalendarPanelBoundary`，只包裹日历面板。
- 如果日历渲染仍抛异常，显示“日程日历暂时无法打开”错误面板，并保留关闭按钮；主 Jarvis 页面不再整体黑屏。
- 将原业务组件保留为 `CalendarPanelContent`，没有删除日程、任务、计划、pending action、Maxwell workbench 等业务逻辑。
- 新增 `timePrefix()`，替换剩余 `start_time.slice()`、`end_time.slice()`、`plan_date.slice()` 直接调用，避免非字符串时间字段导致 render 崩溃。
- 新增 `formatUnixSeconds()`，避免 plan event 的 `created_at` 非法时 `toISOString()` 抛 `RangeError`。

### 修改文件

- `shadowlink-web/src/components/jarvis/CalendarPanel.tsx`

### 验证记录

- `cd shadowlink-web; npm.cmd run type-check`：通过，exit 0。

### 说明

- 这次是 P0 兜底修复：即使还有未知脏数据，也应降级为日历错误面板，而不是整页黑屏。
- 后续仍建议继续做第二阶段：`loadAll()` 改为 `Promise.allSettled`，让某个非核心接口失败时其它日程数据仍能显示。

## 2026-05-01 日程模块完整性检查记录

### 检查原则

- 本轮只检查代码完整性和业务链路，不删除任何业务逻辑。
- 后续修复应以“防御式修复、保留现有业务能力”为原则，避免用删除复杂逻辑的方式掩盖问题。

### 前端链路检查

- `DashboardCards` 仍通过 `onOpenCalendar` 打开日历入口。
- `JarvisHome` 仍维护 `calendarOpen` 并渲染 `CalendarPanel`。
- `CalendarPanel` 仍保留现有业务能力：
  - 日/周/月视图。
  - 日程事件展示、添加、修改、删除、完成/恢复。
  - 待确认 action 确认、修改、取消。
  - 后台任务清单、每日任务、长期计划、计划日编辑、延期、完成。
  - planner conflicts/free windows 展示。
- `jarvisApi` 中日程相关前端 API 方法存在且与后端路径基本对应：
  - calendar events CRUD。
  - pending actions list/update/confirm/cancel。
  - background tasks / background task days。
  - plans / plan days / planner calendar。
  - maxwell workbench push/list。
- `jarvisStore` 仍保留 `addCalendarEvent`、`updateCalendarEvent`、`deleteCalendarEvent`，并在变更后刷新上下文。

### 后端链路检查

- `jarvis_router.py` 中日程相关路由存在：
  - `/pending-actions`
  - `/background-tasks`
  - `/background-task-days`
  - `/maxwell/workbench-items`
  - `/maxwell/workbench/push-daily-tasks`
  - `/planner/calendar-items`
  - `/planner/availability`
  - `/plans`
  - `/plan-days`
  - `/calendar/events`
- `persistence.py` 中日程相关表和读写函数存在：
  - `pending_actions`
  - `background_tasks`
  - `background_task_days`
  - `jarvis_plans`
  - `jarvis_plan_days`
  - `jarvis_agent_events`
  - calendar event save/list/update/delete。
- `calendar_adapter.py` 中内存+持久化桥接仍存在：`add_event`、`delete_event`、`update_event`、`get_event`、`get_upcoming_events`、`get_events_between`、`compute_schedule_density`。
- `jarvis_tools.py` 中日程/任务工具仍存在：
  - `JarvisCalendarUpcomingTool`
  - `JarvisCalendarAddTool`
  - `JarvisCalendarDeleteTool`
  - `JarvisCalendarUpdateTool`
  - `JarvisCalendarFindFreeSlotTool`
  - `JarvisPlanActivitySlotTool`
  - `JarvisCheckinScheduleTool`
  - 以及会议 brief、deadline check、task prioritize、route estimate 等相关工具。

### 验证结果

- `cd shadowlink-web; npm.cmd run type-check`：通过，说明前端当前日程模块引用和类型层面没有缺失。
- 尝试运行部分日程相关后端集成测试时，当前环境遇到 pytest async 插件/临时目录权限问题：
  - `client_with_mock_llm` async fixture 未被插件处理。
  - `.pytest_time_tmp` 删除时 `PermissionError`。
  - 因此本轮不把该失败判定为日程业务代码缺失。

### 完整性结论

- 目前日程模块代码“链路是齐全的”：前端入口、面板、API client、store、后端路由、持久化、calendar adapter、Agent 工具均存在。
- 当前更像是复杂业务链路上的容错与数据质量问题，而不是模块缺失问题。
- 后续修复应优先围绕：
  1. 脏数据安全访问。
  2. 接口局部失败降级。
  3. 日期/时间字段校验。
  4. 前端错误边界和可诊断错误提示。
- 不建议删除日程、任务、计划、Maxwell workbench、pending action 等已有业务逻辑来“简化修复”。

## 2026-05-01 打开日历黑屏根因修复记录

### 用户要求
- 本次不接受兜底式交付，必须深入定位真实根因。
- 修复时不删除日程模块既有业务逻辑。
- 后续所有任务继续按模块留痕，本记录仍写入日程模块 bug 文档。

### 根因定位
- 黑屏触发点不是后端日程数据缺失，也不是通过错误边界可以真正解决的问题。
- `CalendarPanel` 在 `if (!open) return null` 之后仍声明了一个 `useEffect`。
- React 要求每次 render 的 Hook 调用顺序一致；日历面板默认 `open=false` 时会提前 return，点击“打开日历”切到 `open=true` 后才调用后面的 `useEffect`，导致 Hook 顺序变化。
- 该类错误会在 React 渲染阶段直接抛异常，表现为点击“打开日历”后整个页面黑屏。

### 修复内容
- 将 `if (!open) return null` 移到 `CalendarPanel` 内所有 Hook 声明之后。
- 保留日程模块原有业务逻辑：日/周/月视图、pending action、任务、计划、计划变更历史、编辑/延期/完成等逻辑均未删除。
- 移除前序临时错误边界/防御式处理思路，不把“兜底不黑屏”作为最终交付。

### 修改文件
- `shadowlink-web/src/components/jarvis/CalendarPanel.tsx`
- `shadowlink-ai/tests/unit/jarvis/test_calendar_panel_contract.py`

### 回归测试
- 新增 `test_calendar_panel_declares_hooks_before_open_guard`，要求 `if (!open) return null` 之后不得再出现 `useEffect`、`useMemo`、`useState`。
- 该测试先在旧结构下失败，错误指向 `if (!open) return null` 之后仍存在 `useEffect`，确认能复现黑屏根因。
- 修复后该测试通过。

### 验证结果
- `$env:SSLKEYLOGFILE=''; python -m pytest shadowlink-ai\tests\unit\jarvis\test_calendar_panel_contract.py -q --basetemp=shadowlink-ai\.pytest_calendar_tmp`
  - 结果：`1 passed, 1 warning`
  - warning：当前 pytest 配置存在既有 `asyncio_mode` 未识别提示。
- `cd shadowlink-web; npm.cmd run type-check`
  - 结果：exit 0。

### 后续原则
- 日程模块后续 bug 修复优先定位真实触发点和数据/组件契约，不用 ErrorBoundary、try/catch、空数组兜底等方式掩盖根因。

## 2026-05-01 长期任务重复入库与任务清单混乱修复记录

### 用户反馈
- 示例：“我要考雅思”应被识别为一个长期任务并持续拆解。
- 当前“查看所有任务”中出现多个“雅思备考计划”，任务仓库存储和展示都显得混乱。
- 要求重点分析日程/任务管理逻辑并修复不合理点。

### 根因分析
- `jarvis_task_plan_decompose` 每次生成随机 `task_id`，同一长期目标多次确认会变成多个顶层 `background_tasks`。
- `confirm_pending_action_item()` 原先直接按传入 `task_id` upsert，缺少“同一长期目标”的身份识别与复用。
- 雅思这类长期目标在不同入口可能被标成 `future_project` 或 `recurring_plan`，导致同一目标进一步分裂。
- 前端“查看所有任务”同时展示 `jarvis_plans` 与其来源 `background_tasks`，同一计划可能以“计划”和“后台任务”两种顶层对象出现。
- 本地 `jarvis.db` 检查确认：已有多条 `雅思备考计划` 顶层任务，属于真实数据层重复，不是单纯 UI 展示错觉。

### 修复内容
- 后端新增任务身份规范化与查询：按标题/目标/原始请求 + 规范化任务类型识别同一长期任务。
- 确认 `task.plan` 时，先查找同类 active 任务；存在则复用原 `task_id` 并更新每日拆解，不再创建新的顶层任务。
- 将 `future_project`、`recurring_plan` 在长期目标入库时统一归并为 `long_project`。
- `list_background_tasks()` 增加列表层去重，兼容历史已存在的重复长期任务，避免旧数据继续污染任务清单。
- 前端任务清单中，如果某个 `background_task` 已被 `jarvis_plan.source_background_task_id` 引用，则只展示计划，不再把底层任务并列展示为另一个顶层条目。

### 修改文件
- `shadowlink-ai/app/jarvis/persistence.py`
- `shadowlink-ai/app/api/v1/jarvis_router.py`
- `shadowlink-ai/tests/unit/jarvis/test_unified_planner.py`
- `shadowlink-web/src/components/jarvis/CalendarPanel.tsx`

### 回归测试
- 新增 `test_duplicate_long_term_goal_confirmation_updates_existing_task_and_plan`：同一“雅思备考计划”确认两次后，只保留 1 个 active 顶层任务和 1 个计划，第二次拆解会更新计划日。
- 新增 `test_background_task_listing_collapses_existing_duplicate_long_term_tasks`：历史遗留的 `future_project`、`recurring_plan`、`long_project` 同名长期任务在列表层折叠为 1 个。

### 验证结果
- `$env:SSLKEYLOGFILE=''; python -m pytest shadowlink-ai\tests\unit\jarvis\test_unified_planner.py::test_duplicate_long_term_goal_confirmation_updates_existing_task_and_plan shadowlink-ai\tests\unit\jarvis\test_unified_planner.py::test_background_task_listing_collapses_existing_duplicate_long_term_tasks shadowlink-ai\tests\unit\jarvis\test_unified_planner.py::test_task_plan_confirmation_writes_unified_plan_days -q --basetemp=shadowlink-ai\.pytest_calendar_tmp`
  - 结果：`3 passed, 20 warnings`
  - warnings：既有 pytest `asyncio_mode` 配置提示，以及既有 `datetime.utcnow` deprecation。
- `cd shadowlink-web; npm.cmd run type-check`
  - 结果：exit 0。
- 使用当前本地 `jarvis.db` 调用 `persistence.list_background_tasks(limit=20)` 验证，历史雅思重复项已在列表层折叠。

### 后续建议
- 后续若要彻底清理历史库，可再做一个显式“合并重复长期任务”的维护脚本；本次没有直接删除历史数据，避免破坏已有计划日、日历投影和工作台关联。

## 2026-05-01 历史重复长期任务清库记录

### 用户要求
- 清理历史记录，不能只靠列表折叠隐藏重复。
- 确保任务/计划逻辑从根本上清晰，不再混乱。

### 清理前审计
- 当前本地库：`shadowlink-ai/data/jarvis.db`。
- `background_tasks` 中存在 7 条 `雅思备考计划` active 顶层任务。
- 这些重复项分布在 `future_project` 和 `recurring_plan` 两种类型下。
- 关联表审计结果：当前本地库中 `background_task_days`、`jarvis_plans`、`jarvis_plan_days`、`maxwell_workbench_items`、`jarvis_calendar_events` 均为 0，因此本次真实清理不会迁移实际子记录；但代码实现仍支持迁移这些关联。

### 新增清理能力
- 新增 `cleanup_duplicate_background_tasks()`。
- 合并规则：按规范化后的任务身份 `(长期任务类型, 标题/目标/原始请求)` 分组。
- canonical 选择：同组内按 `updated_at DESC, created_at DESC` 排序，保留最新 active 任务。
- 关联迁移：重复任务删除前，将 `background_task_days.task_id` 和 `jarvis_plans.source_background_task_id` 迁移到 canonical 任务。
- 类型归一：canonical 任务统一为 `long_project`，避免 `future_project`/`recurring_plan` 再把同一长期目标拆成多类。

### 真实库清理执行
- 清理前已备份：`shadowlink-ai/data/jarvis.db.bak-calendar-cleanup-20260501`。
- 执行结果：合并 1 组长期任务。
- 保留 canonical：`task_2c022b89f41342cfa1a716cf9dacf734`。
- 删除重复任务 6 条：
  - `task_107ae79a98cd4546ac41ef6e7d1905f8`
  - `task_2601cfbbe4e84f99b83252469426d55e`
  - `task_bb2df93bfc6e457da9ae2003a1a7d91a`
  - `task_e1849070f1084b97bb5c22710ecad3cc`
  - `task_94b73143f7a249cb8eeac402b25939f0`
  - `task_0a2af4845b5a489780dffbfa5d81554c`

### 清理后状态
- `background_tasks` 当前剩余 1 条记录。
- 剩余任务：`雅思备考计划`，类型已统一为 `long_project`。
- 按 `title/task_type/status` 聚合检查，无重复组。

### 修改文件
- `shadowlink-ai/app/jarvis/persistence.py`
- `shadowlink-ai/tests/unit/jarvis/test_unified_planner.py`
- `shadowlink-ai/data/jarvis.db`
- `shadowlink-ai/data/jarvis.db.bak-calendar-cleanup-20260501`

### 回归测试
- 新增 `test_cleanup_duplicate_long_term_tasks_merges_rows_and_relations`：验证历史重复长期任务会合并为 1 个，并迁移 background task days 和 plans 的关联。

### 验证结果
- `$env:SSLKEYLOGFILE=''; python -m pytest shadowlink-ai\tests\unit\jarvis\test_unified_planner.py::test_cleanup_duplicate_long_term_tasks_merges_rows_and_relations shadowlink-ai\tests\unit\jarvis\test_unified_planner.py::test_duplicate_long_term_goal_confirmation_updates_existing_task_and_plan shadowlink-ai\tests\unit\jarvis\test_unified_planner.py::test_background_task_listing_collapses_existing_duplicate_long_term_tasks shadowlink-ai\tests\unit\jarvis\test_unified_planner.py::test_task_plan_confirmation_writes_unified_plan_days -q --basetemp=shadowlink-ai\.pytest_calendar_tmp`
  - 结果：`4 passed, 20 warnings`。
- `cd shadowlink-web; npm.cmd run type-check`
  - 结果：exit 0。
- 真实库清理后 SQL 检查：`background_tasks = 1`，无重复聚合组。

### 结论
- 后续新建长期目标：确认链路会复用同类 active 任务，不再产生重复顶层任务。
- 历史重复数据：已从真实库删除，保留一个 canonical 长期任务。
- 展示层：已避免把计划和其底层 background task 并列展示，任务清单逻辑更清晰。
