# 原始设计完成度 Checklist

> 用途：这是给后续技术实现使用的“防缩水对照表”。任何实现、worklog、验收都必须回到本表勾选。允许分层实现，但不能把 MVP 当成全量完成。

## 一、状态定义

- `[DONE]`：已按原始设计完整实现，并有代码、接口、前端或测试佐证。
- `[MVP]`：只完成最小闭环，可以演示，但距离原始设计仍有明显缺口。
- `[TODO]`：未开始或只有文档，没有有效实现。
- `[REWORK]`：已有实现方向，但与原始设计不一致，需要重构或迁移。
- `[DEFER]`：明确暂缓，但需要写清楚暂缓原因和恢复条件。

## 二、全量设计源文件

技术人员实现前必须先读：

1. `docs/lsq-worklog/待完成/04-整体架构描述.md`
2. `docs/lsq-worklog/待完成/05-心理关怀模块架构.md`
3. `docs/lsq-worklog/待完成/06-轻量管家团队架构.md`
4. `docs/lsq-worklog/待完成/07-圆桌模式架构.md`
5. `docs/lsq-worklog/待完成/08-智能体回复速度调优任务.md`
6. `docs/ohmori-worklog/2026-04-27-daily-summary.txt`
7. `docs/lsq-worklog/4-28-worklog/4-28plan.md`

## 三、当前已实现基线

### 已完成或 MVP 完成

- `[DONE]` 私聊历史按 `session_id` 恢复，避免只按 `agent_id` 串会话。
- `[DONE]` 跨 Agent 路由时前端本地 history 重复显示问题已修复。
- `[MVP]` `background_task_days` 每日任务、完成按钮、Maxwell 工作台推送、missed 标记。
- `[MVP]` Agent 私下咨询层，非圆桌场景可轻量 consult。
- `[MVP]` Shadow 偏好画像和长期记忆 bounded recall。
- `[MVP]` 主动打扰持久化、状态流转、routine scheduler。
- `[MVP]` 心理机制聊天触发型闭环：Mira 规则识别、`mood.snapshot`、`care.intervention`、`care.followup`、LifeContext 更新、proactive followup、前端卡片。
- `[MVP]` LLM API 轻量稳定化和速度基线文档/脚本方向。

## 四、04 整体架构闭环 Checklist

源文件：`docs/lsq-worklog/待完成/04-整体架构描述.md`

### A. 会话链路

- `[DONE]` 用户首次发送后创建/恢复 `conversation_history`。
- `[DONE]` 用户 turn 写入 `agent_chat_turns`。
- `[DONE]` 历史恢复使用 `session_id + agent_id`。
- `[MVP]` Agent 回复 upsert / 去重，避免一轮出现多条重复气泡。
- `[TODO]` 所有失败场景下也能保证 conversation / user turn 已落盘并可恢复。

### B. 单轮回复链路

- `[MVP]` 工具结果和 care actions 挂到 agent 回复 actions 中。
- `[TODO]` 全面保证第一段草稿不入库、不返回前端。
- `[TODO]` 为所有 action 类型建立统一 schema 和前端渲染边界。

### C. 意图路由链路

- `[MVP]` schedule intent 可路由到 Maxwell。
- `[TODO]` 规则快速命中 + LLM 结构化分类组合机制。
- `[TODO]` 缺字段时只追问，不落盘。
- `[TODO]` 心理、圆桌、长期计划、普通聊天的统一路由策略。

### D. 计划落盘链路

- `[MVP]` `background_tasks + background_task_days` 支持长期任务每日拆解。
- `[REWORK]` 原设计中的 `jarvis_plans / jarvis_plan_days` 尚未决策是否引入。
- `[TODO]` 短期计划、长期计划、手动日历事件统一领域模型。
- `[TODO]` 计划 day 单独完成、修改、延期、重排的完整机制。

### E. 确认与写入链路

- `[MVP]` pending action 已有基础确认机制。
- `[TODO]` pending action 持久化字段和修改后确认的统一规则。
- `[TODO]` 短期日程确认后同时写 calendar event 和 plan day。
- `[TODO]` 长期计划确认后批量写 day，并为明确时间段生成 calendar event。

### F. 展示链路

- `[MVP]` 日历、后台任务、Maxwell 工作台已有局部展示。
- `[TODO]` `GET /planner/calendar-items?start=...&end=...` 合并事件和计划 day。
- `[TODO]` 日/周/月视图统一显示普通日历、短期计划、长期计划、后台任务。

### G. 后台调度链路

- `[MVP]` routine scheduler 和 missed 标记已有基础。
- `[TODO]` 每天自动推送今日任务给 Maxwell 的完整调度策略。
- `[TODO]` 未完成任务重排、延期、减负和用户确认机制。

## 五、05 心理关怀模块 Checklist

源文件：`docs/lsq-worklog/待完成/05-心理关怀模块架构.md`

> 产品要求：心理机制最终目标不是“心情建议弹窗”，而是长期状态追踪系统。当前只是 MVP，不能停止在这里。

### A. 情绪采集层

- `[MVP]` Mira 私聊中规则识别低能量、压力、睡眠、回访、高风险关键词。
- `[MVP]` 新增 `jarvis_emotion_observations` 表，已可保存聊天触发型情绪 observation。
- `[MVP]` 保存 `primary_emotion`、`secondary_emotions`、`valence`、`arousal`、`stress_score`、`fatigue_score`、`risk_level`、`confidence`、`evidence_summary`，当前来源为规则 MVP。
- `[MVP]` 已有规则快速判断并写入 observation；`必要时 LLM 结构化 JSON` 仍未实现。
- `[MVP]` observation 只保存 evidence_summary、signals 和结构化指标，不保存用户心理原文全文。
- `[MVP]` 单元测试覆盖低能量、焦虑/压力、睡眠、高风险、无信号五类输入，并验证 observation 不保存原文。

### B. 行为采集层

- `[MVP]` LifeContext 有最近活跃更新。
- `[MVP]` 新增 `jarvis_behavior_observations` 表，已保存聊天触发型行为 observation。
- `[MVP]` 已记录首次活跃、最后活跃、深夜使用、超过 bedtime，并新增前端 heartbeat / 关闭 / visibility 生命周期事件；连续在线目前为心跳信号 MVP。
- `[MVP]` 已接入用户资料中的 bedtime / wake，当前来源为 `JarvisSettings.profile.sleep_schedule`。
- `[MVP]` 深夜使用只作为疲劳/风险信号保存为 behavior observation，不直接诊断。

### C. 日程压力观测层

- `[MVP]` 新增 `jarvis_stress_signals` 表，已保存日程/任务压力 signal。
- `[MVP]` 已读取 `background_task_days`、内存 `calendar_events`、Maxwell workbench、missed tasks；`jarvis_plan_days` 和重排日志仍未接入。
- `[MVP]` 已计算日程密度、missed 任务数量、未完成任务、休息窗口不足、晚间任务过重；连续高压天数仍未实现。
- `[MVP]` 每个压力信号都带可解释 reason 和 `source_refs`。

### D. 每日心理快照层

- `[MVP]` 当前有单轮 `MoodSnapshot` action，但不是日级快照。
- `[MVP]` 新增 `jarvis_mood_snapshots` 表，可保存日级综合状态。
- `[MVP]` 字段包括 date、mood_score、stress_score、energy_score、sleep_risk_score、schedule_pressure_score、dominant_emotions、positive_events、negative_events、risk_flags、summary、confidence、created_at、updated_at。
- `[MVP]` Mira 心理触发后可聚合当天 emotion observations 生成日级 snapshot；behavior observations 已纳入 sleep risk / risk_flags，stress signals 已纳入 schedule pressure / risk_flags，任务完成情况只以 missed/backlog MVP 纳入。
- `[MVP]` 已在 worklog 中明确区分单轮 `mood.snapshot` action 与日级 `jarvis_mood_snapshots`；前端命名仍需后续统一调整。

### E. 长期趋势层

- `[MVP]` 新增 `GET /care/trends?range=week|month|year`，支持 week/month/year。
- `[MVP]` 返回 mood、stress、energy、sleep risk、schedule pressure 时间序列，来源为后端 `jarvis_mood_snapshots`。
- `[MVP]` 前端新增真实可用“心理趋势中心”，支持周/月柱状、全年热力网格、指标切换。
- `[MVP]` 点击某一天可查看 snapshot summary、stress signals、late-night behavior 等解释；已提供追踪开关与心理数据清除入口。

### F. 关怀触发层

- `[MVP]` 中/高风险或请求回访时写 proactive message。
- `[MVP]` 已实现连续 3 天高压力、连续晚睡、任务过载、高风险关键词触发规则；用户主动求助触发仍沿用 B1 关怀 action，未并入统一 trigger rule。
- `[MVP]` 已实现 cooldown 和 daily care budget；用户选择“太频繁/不需要”后触发降频。
- `[MVP]` 已实现中/高风险文案分级；低风险陪伴仍主要停留在 mood snapshot 记录。
- `[MVP]` proactive message 已关联 care trigger / intervention，并保存 evidence_ids / source_refs。

### G. 关怀交互层

- `[MVP]` 前端展示关怀卡片，支持“稍后提醒 / 我已处理 / 不用了”。
- `[MVP]` “稍后提醒”已接真实 snooze/update 接口，会暂时隐藏 proactive message。
- `[MVP]` 用户反馈已支持：有帮助、太频繁、不需要此类提醒、稍后提醒、我已处理。
- `[MVP]` 已根据 too_frequent / not_needed 调整后续触发频率。
- `[MVP]` 已抽出独立 `CareCard` 组件，并用于私聊 action 与 proactive feed。

### H. 安全边界

- `[MVP]` 高风险关键词触发安全提示。
- `[MVP]` 危机分级已有 low/medium/high，明确自伤意图/紧急风险更细分仍待后续。
- `[MVP]` 高风险场景不做医疗诊断，只提示联系可信任的人和当地紧急渠道。
- `[MVP]` 自动化测试已覆盖高风险安全边界文案。

## 六、06 轻量管家团队 Checklist

源文件：`docs/lsq-worklog/待完成/06-轻量管家团队架构.md`

### A. 总管判断层

- `[MVP]` Agent consult 模块已存在。
- `[TODO]` 明确当前 Agent 何时直接回复、何时 consult、何时推荐圆桌、何时交给 Maxwell。
- `[TODO]` 跨领域、心理+日程冲突、长期计划、风险场景的触发规则。

### B. 专业 Agent 咨询层

- `[MVP]` 可咨询其他 Agent。
- `[TODO]` 固定 consult 输出 schema：specialists、summary、aligned_actions、conflicts、followups、handoff_target。
- `[TODO]` consult 超时和失败降级策略。
- `[TODO]` 不允许 consult 结果直接写库。

### C. Committer / 执行边界

- `[TODO]` 明确哪些动作只回复，哪些生成 pending action，哪些禁止自动执行。
- `[TODO]` Maxwell / Committer 只在用户确认后写 calendar/task/memory 敏感动作。
- `[TODO]` 所有写动作都能追溯到用户确认。

### D. 前端呈现

- `[TODO]` 展示“参考了哪些 Agent 意见”。
- `[TODO]` 默认不把每个 consult 都变成一条聊天气泡。
- `[TODO]` 最终只出现一条清晰回复和必要 action card。

## 七、07 圆桌模式 Checklist

源文件：`docs/lsq-worklog/待完成/07-圆桌模式架构.md`

### A. 数据结构

- `[MVP]` 已有基础 `roundtable_sessions / roundtable_turns` 能力。
- `[MVP]` `roundtable_sessions` 已补齐 `mode=decision|brainstorm`、source_session_id、source_agent_id、status；title/user_prompt 仍主要在 conversation_history 与 turns 中间接保存。
- `[MVP]` 已保存 source_session_id、source_agent_id、status；独立 title/user_prompt 字段仍待后续统一 schema。
- `[MVP]` 新增 `roundtable_results`，保存 decision 结构、context、handoff_target、pending_action_id；user_choice/handoff_status 目前以 status/pending_action_id MVP 表达。

### B. Decision 圆桌

- `[MVP]` 已输出并持久化 `decision_result`：summary、options、recommended_option、tradeoffs、actions、handoff_target。
- `[MVP]` Decision 启动前已预取心理 snapshot、压力信号、今日任务、日程事件、Maxwell workbench 和 MVP RAG 摘要。
- `[MVP]` Decision prompt 已明确讨论阶段默认不调用工具；仍待 Phase 9 改成一次 LLM 生成整轮 JSON。
- `[MVP]` 用户接受后由 Maxwell 生成 `pending_actions` 待确认卡，不直接改 calendar。

### C. Brainstorm 圆桌

- `[MVP]` 已输出并持久化 `brainstorm_result`：themes、ideas、tensions、followup_questions、save_as_memory。
- `[MVP]` Brainstorm 结束默认只保存 result，不落计划、不改日程。
- `[MVP]` 用户主动选择“保存灵感”才写 `jarvis_memories`；主动选择“转成计划”才生成 Maxwell `pending_actions`。

### D. 接口

- `[MVP]` 已有 `/roundtable/start`、`/roundtable/continue` 基础接口。
- `[TODO]` `POST /roundtable/{id}/run`。
- `[MVP]` `POST /roundtable/{id}/accept` 已生成 Maxwell pending action；`return/save` 仍待后续。
- `[TODO]` `POST /roundtable/{id}/return`。
- `[MVP]` `POST /roundtable/{id}/save` 已支持 Brainstorm 保存灵感到 memory。
- `[MVP]` `POST /roundtable/{id}/plan` 已支持 Brainstorm 转 Maxwell 待确认计划卡。

### E. 前端舞台体验

- `[MVP]` 席位、头像、当前发言高亮、模式化中心主持总结卡已完成；后续仍可深化舞台动效。
- `[MVP]` decision 结果卡已展示推荐项、利弊、下一步动作，并提供接受建议、返回私聊、让 Maxwell 执行按钮。
- `[MVP]` brainstorm 结果卡已展示主题、想法、冲突/张力，并提供保存灵感、继续讨论、转成计划按钮。
- `[MVP]` 当前发言气泡已做展示长度控制，完整内容保留在完整记录中。

### F. 性能策略

- `[DEFER]` 默认一次 LLM 生成整轮 JSON：产品计划已调整，保留角色轮流发言，不执行一次返回整轮。
- `[DEFER]` 禁止按角色逐个串行调用作为默认路径：产品计划已调整，轮流发言是目标体验。
- `[DEFER]` 上下文准备阶段和讨论生成阶段分离/减少上下文：用户要求暂不做减少上下文，后续如有性能瓶颈再恢复。

## 八、08 速度调优 Checklist

源文件：`docs/lsq-worklog/待完成/08-智能体回复速度调优任务.md`

### A. 基准测试

- `[MVP]` 已有 Step1 速度基线验证文档。
- `[TODO]` 固定 20 条 prompt 正式入库。
- `[TODO]` 每次心理、圆桌、consult、记忆召回改动后都跑基线。
- `[TODO]` 输出 JSON/CSV 历史对比。

### B. 后端 timing

- `[MVP]` Jarvis chat 已有 timing spans。
- `[MVP]` Jarvis chat 与 roundtable 已有 timing spans；consult、planner、proactive 全链路 timing 仍待后续。
- `[TODO]` 设定性能预算和告警阈值。

### C. 前端端到端

- `[TODO]` 记录 send_clicked、response_headers、first_render、final_render。
- `[TODO]` 检查历史恢复、feed、日历面板是否重复刷新。

### D. 优化策略

- `[TODO]` 规则优先路由，LLM 分类只处理不确定场景。
- `[TODO]` 长期记忆 Top-K 召回和摘要注入。
- `[TODO]` Agent consult 限流和异步/降级。
- `[TODO]` 圆桌一次生成整轮。
- `[TODO]` 高频列表分页、缓存、索引检查。

## 九、验收规则

技术人员提交任一模块时，必须提供：

- 对应 checklist 条目编号。
- 修改的代码文件。
- 新增或变更的数据表 / 接口 / 前端组件。
- 自动化测试或可复现手动验证步骤。
- 本次从 `[TODO]` 到 `[MVP]` 或 `[DONE]` 的状态变化。
- 明确剩余未完成项。

如果只完成 MVP，worklog 标题和正文必须写清楚“MVP”，不能写“完成心理模块 / 完成圆桌模块”。





## Phase 11 Unified Planner Closure - 2026-04-28

- `[DONE]` Unified planner domain is now implemented with `jarvis_plans`, `jarvis_plan_days`, and `jarvis_agent_events`.
- `[DONE]` `task.plan` confirmation writes legacy `background_tasks/background_task_days` and unified plan/day records.
- `[DONE]` `calendar.add` confirmation and manual `POST /calendar/events` create short-term plan/day records.
- `[DONE]` Timed long-term plan days are projected to calendar events and linked by `calendar_event_id`; duplicate projection is skipped.
- `[DONE]` `GET /planner/calendar-items` merges calendar events, unified plan days, and legacy background task days.
- `[DONE]` Plan days support complete, update, move/reschedule, missed marking, and plan cancellation with calendar sync.
- `[DONE]` Maxwell workbench push now consumes both legacy background task days and `jarvis_plan_days`.
- `[DONE]` Schedule pressure reads `jarvis_plan_days` and reports source refs from the unified planner.
- `[DONE]` Tests added in `test_unified_planner.py`; validation passed with `10 passed` for unified planner + stress tests.
- `[NEXT]` Automatic LLM replanning after missed days and planner timing spans are deferred to later phases, not Phase 11 blockers.


## Phase 11 Missed Auto Reschedule Closure - 2026-04-28

- `[DONE]` Overdue planner maintenance now marks missed days, groups them by plan, and calls Maxwell/LLM to regenerate future plan day content.
- `[DONE]` LLM reschedule is constrained to future unfinished plan days only; missed/completed history is preserved.
- `[DONE]` LLM failure has deterministic fallback reschedule, so the chain remains usable without provider availability.
- `[DONE]` Rescheduled future days sync existing calendar events and write `plan.rescheduled` events.
- `[DONE]` Maxwell proactive message is created after automatic reschedule so the user can see what changed.
- `[DONE]` Daily routine calls planner maintenance once per local date after 01:00; manual API endpoints are also available.
- `[DONE]` Tests cover LLM reschedule and idempotent daily maintenance.


## Phase 11 Calendar Persistence Closure - 2026-04-28

- `[DONE]` Calendar events are persisted in SQLite via `jarvis_calendar_events`.
- `[DONE]` Calendar adapter reads/writes persistent events; in-memory list is no longer the only source of truth.
- `[DONE]` Planner calendar query reports conflicts and free windows.
- `[DONE]` Auto missed reschedule creates a care/proactive reminder telling the user the plan was unfinished and already rescheduled.
- `[DONE]` Frontend normal Calendar/Tasks page exposes conflict summary, plan day edit, and plan audit history.
- `[DONE]` Tests cover persistent calendar events and conflict/free-window output.
