3.日程安排并没有实际落盘，我点开打开日历-查看所有任务什么都看不到，即使我让它安排了雅思学习计划
问题描述：我发现计划安排只是一个浮于表面的前端
我的要求：用户输入一句话，智能体先判断意图是否要进行日程安排，并自动判断是长期还是短期的哪类，如果是长期就在获取足够的信息后进行长期日程规划，并加上标签（长期还是短时，短时表示今天之内要做的，长期表示今天之外的）、规划周期、以及LLM给的规划安排写入数据库并落盘，同时让用户在打开日历-查看所有任务后能看到所有长期安排、短期安排。同时，日历界面不是有日视图、周视图、月视图吗，要把落盘后的任务和安排展示在这些视图上，视图上可能写不下，但是尽量展现一个标题，用户鼠标移动到上面就可以查看本日应该干什么。一个大任务，本地要记载下来LLM给的安排等基本信息（在那之前要跟LLM说给出任务周期内每天的规划），以每天的任务为一个单位保存到本地数据库，并当那天来到时，只要程序打开，凌晨一点时就把带有当天标记的细分任务推入秘书工作台的待处理列表，（如果程序没打开，就在用户第一次打开时计算，并告诉用户正在初始化）那样n个任务就都可以安排到，那天的所有安排交给秘书去协调。
如果用户当天没有确认完成任务，那就在凌晨1点修改保存在本地的规划安排的时间，并后台发送给LLM，告诉他说此任务时间少了一条但是用户什么都没做，重新安排
同时任务要支持用户自主删除，修改，确认完成

为了完成这个架构，我觉得你需要设计一个合理的多智能体存储系统和信息交换系统

目前链路以及问题所在：

问题拆分：
1. 意图识别：用户自然语言输入后，系统要判断是否是日程/计划需求，并区分短期（日内）与长期（跨天）。
2. 计划生成：短期应生成具体日程；长期应先确认必要信息，再生成任务周期内“每天的规划”。
3. 落盘：不能只显示前端卡片，必须写入本地数据库。
4. 展示：日历日/周/月视图和“查看所有任务”都要来自同一份落盘数据。
5. 运行时调度：当天凌晨 1 点或用户首次打开时，把当天细分任务推入秘书 Maxwell 工作台的待处理列表。
6. 逾期重排：当天未确认完成的细分任务，需要触发 LLM 重排并更新数据库。
7. 用户操作：任务支持删除、修改、确认完成。
8. 多智能体协作：非 Maxwell agent 识别到日程意图时要路由给 Maxwell；Maxwell 负责计划、协调、落盘和后续提醒，其他 agent 只提供上下文或建议。

当前链路：
1. 意图识别已有雏形：`shadowlink-ai/app/api/v1/jarvis_router.py` 的 `_build_schedule_intent(req.message, req.agent_id)` 会用关键词判断日程/长期任务，命中后把请求路由到 Maxwell。
2. `/chat` 中如果 LLM 没有主动调用工具，会有 fallback：短期调用 `jarvis_calendar_add`，长期调用 `jarvis_task_plan_decompose`。这说明当前系统已经试图做“兜底生成”，但这正是问题：它不是完整业务链路，很多情况下只是生成待确认 action 或粗略任务。
3. 工具执行在 `shadowlink-ai/app/jarvis/tool_runtime.py`：写操作工具会先变成 `pending_confirmation`，`/chat` 再把 pending action 保存到 `pending_actions` 表。
4. 用户确认 pending action 后，`jarvis_router.py` 的 `/pending-actions/{pending_id}/confirm`：
   - `calendar.add` 会调用 `/calendar/events` 真实写入日历。
   - `task.plan` 会调用 `save_background_task(...)` 写入 `background_tasks` 表。
5. 日历事件接口已经存在：`/calendar/events` 支持 list/add/update/delete，底层使用 `app.mcp.adapters.calendar_adapter` 管理事件；前端 `CalendarPanel.tsx` 的日/周/月视图已经用 `eventsForDay(events, day)` 渲染 `events`。
6. 后台任务接口也存在：`/background-tasks` 读取 `background_tasks` 表；前端 `CalendarPanel.tsx` 的“查看所有任务”读取 `tasks` 并展示 `task.milestones / task.subtasks / task.calendar_candidates`。
7. 现有问题在于：长期计划确认后只保存一个大任务 JSON 到 `background_tasks`，没有把“每天的任务”拆成可调度、可完成、可延期的本地实体，也没有同步生成每天的 calendar events，所以日/周/月视图只看 `calendar_events` 时看不到长期计划。
8. `background_tasks` 目前只有 `milestones / subtasks / calendar_candidates` JSON 字段，没有独立的 daily task 表、完成状态、计划日期、逾期重排状态，也没有凌晨 1 点扫描器。
9. 前端“查看所有任务”只展示后台任务列表（后台任务列表也看不到，现在没有任何显示），没有把短期 `calendar_events` 合并进任务清单，也没有对长期任务提供删除、修改、完成的真实接口。
10. 当前确认流程要求用户点 pending action；如果用户说“安排雅思学习计划”后只是看到 agent 回复但没有确认卡片或没有点确认，就不会真正写入 `background_tasks` 或 `calendar_events`，这也要求系统能正确弹出确认卡片。

根因：
1. “日程计划”被拆成了日历事件、pending action、后台任务三个松散模块，缺少统一的计划领域模型。
2. 长期任务只保存大 JSON，不保存按天拆分的可执行任务，所以日历视图和秘书工作台无法消费。
3. 短期/长期判断依赖关键词和 fallback，缺少 LLM 结构化意图输出和必要信息补齐状态机。
4. 没有每日调度器与逾期重排任务，任务不会在当天自动进入秘书待处理列表。
5. 前端任务列表与日历视图的数据源不统一，导致“查看所有任务”和日/周/月视图各看各的。

解决方案（不允许只写兜底代码，必须修改实际业务链路，让它能真实运行）：

实施计划：
1. 建立统一计划领域模型：`plans` 表保存大任务，`plan_days` 表保存每天安排，`workbench_items` 表保存秘书待处理项。
2. 改造 Maxwell 聊天链路：意图识别 -> 信息补齐 -> LLM 结构化规划 -> 保存计划 -> 生成日历投影 -> 返回同一条 agent 回复与确认卡片。
3. 改造日历和任务接口：所有短期日程、长期计划日任务都从后端统一查询。
4. 增加每日调度器：凌晨 1 点扫描当天 plan_days，推送到 Maxwell 工作台；启动补偿处理错过的日期。
5. 增加逾期重排：未完成日任务在次日 1 点调用 LLM 重排剩余周期并更新数据库。
6. 增加用户操作接口：删除、修改、完成计划/日任务，并同步更新日历投影。

具体改造：
1. 数据库设计（`shadowlink-ai/app/jarvis/persistence.py`）：
   - 新增 `jarvis_plans`：`id, title, plan_type(short_term|long_term), status(active|completed|cancelled), source_agent, session_id, original_user_request, goal, start_date, end_date, timezone, planning_cycle, llm_plan_json, created_at, updated_at`。
   - 新增 `jarvis_plan_days`：`id, plan_id, plan_date, title, description, start_time, end_time, status(pending|pushed|completed|missed|rescheduled|cancelled), calendar_event_id, workbench_item_id, sort_order, llm_payload_json, created_at, updated_at`。
   - 新增 `jarvis_workbench_items`：`id, plan_day_id, agent_id(default maxwell), title, description, due_at, status(todo|doing|done|cancelled), pushed_at, created_at, updated_at`。
   - 保留 `background_tasks` 做兼容展示，但长期任务的真实来源迁移到 `jarvis_plans / jarvis_plan_days`。
2. 意图识别（`jarvis_router.py`）：
   - 将 `_build_schedule_intent` 从关键词启发式升级为“规则快速命中 + LLM JSON 分类”：输出 `intent=schedule|none`、`horizon=short_term|long_term`、`confidence`、`missing_fields`、`reason`。
   - 短期定义为计划日期在今天内；长期定义为跨过今天或多日周期。
   - 非 Maxwell agent 命中后只负责路由，Maxwell 接管后继续同一个 session/turn。
3. 信息补齐：
   - 长期计划必须至少拿到 `目标、周期/截止日期、每日可用时长或频率、偏好时间段`。缺字段时 Maxwell 只追问，不写库。
   - 如果用户输入足够，例如“帮我安排 30 天雅思学习计划，每天 2 小时”，直接进入规划。
4. LLM 结构化规划：
   - 新增 Maxwell 专用工具 `jarvis_plan_create`，要求 LLM 返回严格 JSON：`title, plan_type, start_date, end_date, planning_cycle, days:[{date,title,description,start_time,end_time}]`。
   - 禁止只返回自然语言计划；工具层校验每天是否有 `date/title`，长期计划必须覆盖周期内每一天或明确休息日。
5. 落盘业务链路：
   - 短期：确认后写 `calendar_events`，同时写一条 `jarvis_plans(plan_type=short_term)` 和一条 `jarvis_plan_days`，便于“查看所有任务”也能看到。
   - 长期：确认后写 `jarvis_plans`，批量写 `jarvis_plan_days`，并为每个有具体时间段的 day 生成或关联 `calendar_events`。
   - `background_tasks` 可由 `jarvis_plans` 同步生成兼容记录，但 UI 应逐步切到新接口。
6. 日历展示：
   - 新增接口 `GET /planner/calendar-items?start=...&end=...`，返回普通 `calendar_events` + `jarvis_plan_days` 的合并结果，字段统一为 `id,title,start,end,type,plan_id,status,tooltip`。
   - `CalendarPanel.tsx` 的日/周/月视图改用该接口；渲染标题，`title` 或 tooltip 展示当天完整安排。
   - 月视图只显示前 3 项，超过显示 `+N 项`，现有逻辑可以保留。
7. “查看所有任务”展示：
   - 新增接口 `GET /planner/tasks`，返回长期计划、短期日程、当天待办的统一列表。
   - `CalendarPanel.tsx` 的 tasks tab 不再只读 `background_tasks`，而是展示 `jarvis_plans`，点开后显示 `jarvis_plan_days`。
8. 秘书工作台推送：
   - 新增后端调度器 `planner_scheduler`：程序运行时每天 Asia/Shanghai 凌晨 1 点执行。
   - 扫描 `jarvis_plan_days where plan_date=today and status='pending'`，生成 `jarvis_workbench_items(agent_id='maxwell')`，更新 day 状态为 `pushed`。
   - 程序启动时执行补偿扫描：如果上次运行时间早于今天 1 点，则立即初始化今天任务，并通过 `/messages` 或工作台接口告诉用户“正在初始化今日安排”。
9. 逾期重排：
   - 每天 1 点先扫描昨天及更早 `status in ('pending','pushed')` 且未完成的 day，标记 `missed`。
   - 调用 Maxwell/LLM 重排工具，传入“剩余周期少了一天、用户未完成任何内容、原计划 JSON、剩余 day 列表”。
   - LLM 返回新的剩余日计划后，更新未来 `jarvis_plan_days` 和对应 `calendar_events`，并记录 `rescheduled_from_day_id` 或重排日志。
10. 用户操作接口：
   - `PATCH /planner/plans/{plan_id}` 修改标题、周期、状态。
   - `DELETE /planner/plans/{plan_id}` 软删除计划，并取消未来 day 和关联 calendar events。
   - `PATCH /planner/days/{day_id}` 修改某天标题、描述、时间，并同步 calendar event。
   - `POST /planner/days/{day_id}/complete` 标记完成，并同步 workbench item 状态。
   - `POST /planner/days/{day_id}/reschedule` 用户手动延期某天任务。
11. 多智能体存储与信息交换：
   - 统一事件表 `jarvis_agent_events`：记录 `event_type(plan.created/day.pushed/day.completed/day.missed/plan.rescheduled)、source_agent、target_agent、session_id、payload_json、created_at`。
   - Maxwell 订阅计划类事件，Mira/Leo 等 agent 只写上下文建议或触发协作，不直接改计划表。
   - 所有 agent 对任务状态的修改必须通过 planner service，不允许直接写 calendar/background 表。
12. 验证：
   - 输入“帮我安排今天晚上 8 点学习雅思” -> Maxwell 判断短期 -> 生成待确认日程 -> 确认后日历日/周/月视图和查看所有任务都能看到。
   - 输入“帮我安排 30 天雅思学习计划，每天 2 小时” -> Maxwell 判断长期 -> 生成每天计划 -> 确认后 `jarvis_plans` 和 `jarvis_plan_days` 有记录，日历视图展示每天标题。
   - 次日 1 点或启动补偿后，当天 day 进入 Maxwell 工作台待处理列表。
   - 未完成的昨天任务被标记 missed，LLM 重排后未来计划更新。
   - 用户能删除、修改、确认完成任务，刷新后仍从数据库恢复。




从这里开始是全量的设计，如果觉得过多可以删减，但最好保留亮眼的地方以及能力不要下降太多



日程模块

