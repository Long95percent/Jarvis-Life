# 日程重复显示与冲突数量异常排查日志
## 2026-05-02 记录1
- 开始排查：用户反馈 LLM 生成 30 日计划后，日/周/月视图重复显示；实际约 31 条日程，月视图显示一百多条冲突。
- 初步动作：检查 AGENTS.md、创建 bug 工作日志目录与日志文件。
- 观察：递归搜索 AGENTS.md 时，仓库内存在若干 pytest 临时目录权限拒绝，暂未见输出的 AGENTS 约束文件。
## 2026-05-02 记录2
- 已确认项目关键路径：`shadowlink-web/src/components/jarvis/CalendarPanel.tsx`、`shadowlink-ai/app/mcp/adapters/calendar_adapter.py`、`shadowlink-ai/app/jarvis/persistence.py`。
- 下一步重点：确认计划生成是否既写入了原始计划，又投影成日程事件，导致视图重复；并检查月视图冲突是否来自跨层重复读取或重复插入。
## 2026-05-02 记录3
- 已定位主要根因：`/planner/calendar-items` 同时返回 `calendar_event` 与带 `calendar_event_id` 的 `plan_day`；计划自动投影后，同一个计划日既作为日历事件显示，又作为计划日显示。
- 冲突数量异常来源：`_build_planner_conflicts_and_free_windows` 对上述双轨项目做两两冲突计算，投影日程会与自己的源计划日互相冲突，并在月视图长区间中放大。
- 前端放大点：`CalendarPanel.tsx` 的日/周/月渲染同时遍历 `eventsForDay(events, ...)` 与 `planDaysForDay(planDays, ...)`，且 `loadAll` 额外加载所有 `jarvisPlanDays`，未过滤已投影项。
- 修复方向：后端 planner calendar 响应对已投影计划日/任务日去重；前端日历视图只渲染未投影计划日，保留任务列表中完整计划管理能力。
## 2026-05-02 记录4
- 已实现修复：后端 `/planner/calendar-items` 对已投影计划日去重，不再把带 `calendar_event_id` 的 `plan_day` 当作独立日历项返回；同时隐藏其源 `background_task_day`，避免 30 天计划出现 `calendar_event + plan_day + background_task_day` 三份。
- 已实现修复：前端 `CalendarPanel.tsx` 日/周/月视图使用 `visiblePlanDays` 与 `visibleTaskDays`，只显示未投影到日历事件的计划/任务日；“查看所有任务”仍保留完整计划管理数据。
- 已补测试：30 天计划自动投影后，合并日历视图只返回 30 个 `calendar_event`，不返回投影源 `plan_day`，且无自冲突；手动日程创建的短期 plan_day 也不在合并视图重复展示。
- 验证结果：`python -m pytest ...` 日程相关 44 条通过；`npm.cmd run type-check` 通过。
- 注意：首次 pytest 被本机 `SSLKEYLOGFILE=D:\sslkey.log` 权限阻断，已在命令中临时清空环境变量后验证。
## 2026-05-02 记录5
- 新问题：用户反馈在投影里删除长期任务后，日/周/月视图的投影日程仍残留；同时需要检查短期任务是否存在同类问题。
- 排查方向：追踪 `deletePlan` / `deletePlanDay` / `cancelPlan` 与 `calendar_event_id` 的同步关系，确认删除任务时是否只标记计划/计划日，而没有软删除对应 `jarvis_calendar_events`。
## 2026-05-02 记录6
- 根因确认：长期任务删除只改了 `background_tasks.status`，没有同步清理其派生 `jarvis_plans`、`jarvis_plan_days` 和 `jarvis_calendar_events`，因此投影残留在日/周/月视图里。
- 已修复：`update_background_task_item` 在 `archived/deleted` 时调用派生计划级联函数，统一把相关计划和计划日标记为 `cancelled/deleted`，并同步投影日历事件状态。
- 短期任务结论：同样受影响；以前只删除后台任务本体会残留投影。已加测试覆盖短期和长期两条链路，确认删除后合并日历视图清空。
- 验证：`python -m pytest shadowlink-ai/tests/unit/jarvis/test_unified_planner.py shadowlink-ai/tests/unit/jarvis/test_calendar_frontend_contract.py shadowlink-ai/tests/unit/jarvis/test_calendar_panel_contract.py shadowlink-ai/tests/unit/jarvis/test_calendar_day_delete_contract.py -q` 通过，共 46 passed；`npm.cmd run type-check` 通过。
## 2026-05-02 记录7
- 新需求：前端删除后，数据库里相关对象也要彻底清除，而不是仅做软删除；目标是避免历史数据越积越多导致内存/数据膨胀。
- 排查方向：确认当前删除链路是否只是 `status='deleted'/'cancelled'`，并识别哪些实体需要真正 `DELETE`（后台任务、计划、计划日、日历事件、工作台项、事件日志是否保留需另定）。
## 2026-05-02 记录8
- 已按用户要求把前端删除语义改为数据库硬删除：删除任务/计划/计划日/日历事件时，不再只保留 `status='deleted'`，而是从对应表中 `DELETE`。
- 新增硬删除链路：后台任务删除会清除 `background_tasks`、`background_task_days`、派生 `jarvis_plans`、`jarvis_plan_days`、投影 `jarvis_calendar_events`、相关 `maxwell_workbench_items` 和相关 `jarvis_agent_events`。
- 计划删除会清除 `jarvis_plans`、`jarvis_plan_days`、投影 `jarvis_calendar_events`、相关工作台项和计划事件日志；单个计划日删除也会同步清除其投影日历事件。
- 语义保留：`archived` 仍是软归档，`cancel` 仍是取消；只有前端“删除”走硬删除。
- 验证：日程相关 pytest 46 passed；前端 `npm.cmd run type-check` 通过。
## 2026-05-02 记录9
- 新问题：用户反馈月视图里删除没有打通；要求日/周/月视图都从数据库投影，所有前端行为必须落到数据库，刷新或切换视图后状态一致。
- 排查方向：检查 `CalendarPanel.tsx` 日/周/月三处渲染是否都绑定 `removeEvent/removePlanDay/removeTaskDay`，以及月视图 compact 按钮是否可触发键盘/右键删除；同时确认删除 API 均为硬删除并 `loadAll()` 重新从数据库读取。
## 2026-05-02 记录10
- 月视图删除问题确认：月视图此前使用 compact 卡片，只支持右键/Delete，没有显式删除按钮，用户难以触发；另外 `background_task_day` 删除仍是软删，未完全落实到数据库硬删除。
- 已修复前端：日/周/月三视图共用 `renderEventButton`、`renderPlanDayButton`、`renderTaskDayButton`，每种卡片都带显式 `×` 删除按钮；compact 月视图也可直接点击删除，删除后调用后端 API 并 `loadAll()` 从数据库重新投影。
- 已修复后端：`background_task_day` 删除改为硬删除，连同其 `jarvis_calendar_events` 投影和 `maxwell_workbench_items` 引用一并清除。
- 链路原则：日/周/月视图均从 `/planner/calendar-items` 与数据库 API 加载；新增、修改、完成、删除均调用后端接口，完成后重新加载数据库状态，不做仅前端内存修改。
- 验证：日程相关 pytest 48 passed；前端 `npm.cmd run type-check` 通过。
## 2026-05-02 记录11
- 新反馈：秘书安排 30 天计划后，日历上仍会重复生成；需要继续定位重复是否来自写入层多次插入、旧投影未清理、后台任务日/计划日双写、或前端额外加载全量数据叠加。
- 排查目标：从 `run_secretary_plan_request`、`_persist_task_plan_result`、`project_plan_day_to_calendar`、`save_jarvis_plan`、`save_background_task_days` 到 `/planner/calendar-items` 全链路确认重复来源，并在写入源头彻底去重。
## 2026-05-02 记录12
- 根因确认：秘书计划服务 `_run_long_plan/_run_short_schedule` 每次都生成新的 `plan_secretary_*_{uuid}`，没有使用稳定业务 identity；重复请求同一个 30 天计划会写入多个 `jarvis_plans`，随后每个计划都会投影 30 条 `jarvis_calendar_events`，因此日历重复。
- 第二层隐患：`save_jarvis_plan(..., days=...)` 重写同一个 plan_id 时只删除旧 `jarvis_plan_days`，没有删除旧计划日关联的 `jarvis_calendar_events`，可能造成旧投影孤儿残留。
- 已修复：秘书服务新增基于 plan_type + 标题/目标/原始请求 + 起止日期的幂等匹配，重复生成同一计划时先硬删除旧计划及旧投影，再复用原 plan_id 写入新结果。
- 已修复：`save_jarvis_plan` 在替换计划日之前会删除旧计划日关联的投影日历事件和工作台引用，防止同一 plan_id 重写时留下孤儿投影。
- 新增测试：同一 IELTS 30 天秘书计划连续生成两次后，数据库只保留 1 个计划、30 条日历事件，且无重复 title/start/end。
- 验证：秘书服务 + 日程相关 pytest 54 passed；前端 `npm.cmd run type-check` 通过。
## 2026-05-02 记录13
- 用户要求：先把所有日程安排历史清理掉，便于重新测试秘书 30 天计划和日/周/月视图投影链路。
- 安全策略：先备份当前 `shadowlink-ai/data/jarvis.db`，再硬清空日程/计划/任务投影相关表，并验证表计数归零。
## 2026-05-02 记录14
- 已备份数据库：`shadowlink-ai/data/jarvis.db.bak-before-calendar-full-reset-20260502-101300`。
- 已硬清空日程历史相关表：`background_tasks`、`background_task_days`、`jarvis_plans`、`jarvis_plan_days`、`jarvis_calendar_events`、`maxwell_workbench_items`、`jarvis_agent_events`。
- 验证结果：上述表计数均为 0；`pending_actions` 未清理，当前仍保留 2 条，避免误删待确认动作以外的上下文。
## 2026-05-02 记录15
- 新报错：用户让 Jarvis 将无锡 5月4日-5月6日旅游安排写入日程时，`run_agent_turn` 报错 `can't compare offset-naive and offset-aware datetimes`。
- 上下文：行程中包含 2026-05-04/05/06 多个本地时间段，意图是批量写入日程；需要定位日程创建/冲突检查中 naive datetime 与 timezone-aware datetime 混用的位置。
## 2026-05-02 记录16
- 根因确认：`run_agent_turn` 在执行 `jarvis_calendar_add` 前会构建 `schedule_guard`。用户旅游安排的工具参数常带 `+08:00`，已有日程也可能是 timezone-aware；`tool_runtime.py` 的 guard 在 `cursor = max(cursor, event.end + buffer)` 等位置把 naive `cursor` 与 aware `event.end` 直接比较，触发 `can't compare offset-naive and offset-aware datetimes`。
- 已修复：新增 `_as_naive_utc`，将工具参数和已有事件统一转换成 naive UTC 后再比较、排序、计算空闲窗口，避免 aware/naive 混用。
- 已补测试：模拟已有 `+08:00` 日程，再让 Maxwell 生成需确认的 `jarvis_calendar_add`，确认 schedule guard 不再崩溃；同时补了旅游日程工具写入测试。
- 验证：`test_tool_runtime.py`、`test_unified_planner.py`、`test_secretary_planning_service.py` 共 39 passed；前端 `npm.cmd run type-check` 通过。
