# 2026-04-28 全量实现分阶段计划

> 这是给技术人员逐步执行的主计划。最终目标是实现 `docs/lsq-worklog/待完成` 中的全量设计，不是只做可演示 MVP。允许分层、分阶段交付，但每个阶段都必须说明对应原始设计、完成度变化、剩余缺口。任何 worklog 都不能把 MVP 写成“模块完成”。

## 0. 执行前必须阅读

技术人员开始前必须按顺序阅读：

1. `docs/lsq-worklog/4-28-worklog/原始设计完成度-checklist.md`
2. `docs/lsq-worklog/4-28-worklog/给技术人员的全量实现交接说明.md`
3. `docs/lsq-worklog/待完成/05-心理关怀模块架构.md`
4. `docs/lsq-worklog/待完成/07-圆桌模式架构.md`
5. `docs/lsq-worklog/待完成/06-轻量管家团队架构.md`
6. `docs/lsq-worklog/待完成/04-整体架构描述.md`
7. `docs/lsq-worklog/待完成/08-智能体回复速度调优任务.md`
8. `docs/ohmori-worklog/2026-04-27-daily-summary.txt`

执行规则：

- 每一步都要回填 `原始设计完成度-checklist.md` 的状态。
- 如果只完成 MVP，worklog 标题必须写 MVP。
- 每次提交必须写清楚“完成了全量设计的哪一层，还差哪几层”。
- 不允许为了赶进度删掉原始设计中的关键链路。
- 所有规划、worklog、验证文档统一使用 `.md`。

## 1. 当前完成度基线

| 模块 | 当前状态 | 当前完成度 | 不能误判 |
|---|---|---:|---|
| LLM API 稳定化 | 已完成轻量稳定化 | 70% | 不是完整配置中心。 |
| 智能体速度基线 | 已完成方案和初步验证文档 | 45% | 还不是持续性能回归体系。 |
| 心理机制 | 已完成聊天触发型 MVP | 25% | 不是完整心理关怀模块。 |
| 圆桌会议 | 有基础 roundtable 能力 | 35% | 不是 decision / brainstorm 产品化圆桌。 |
| 轻量管家团队 | 有 Agent consult 雏形 | 45% | 不是完整总管团队闭环。 |
| 计划领域 | 有 background_task_days MVP | 40% | 不是统一计划领域模型。 |

已完成内容参考：

- `docs/ohmori-worklog/2026-04-27-daily-summary.txt`
- `docs/lsq-worklog/4-28-worklog/Step0-LLM_API轻量稳定化-worklog.md`
- `docs/lsq-worklog/4-28-worklog/Step1-智能体回复速度基线-worklog.md`
- `docs/lsq-worklog/4-28-worklog/Step2-心理机制MVP后端闭环-worklog.md`
- `docs/lsq-worklog/4-28-worklog/Step3-心理机制前端最小展示-worklog.md`

## 2. 最终全量架构目标

### 2.1 整体业务闭环

最终系统必须从“聊天”走到“计划落盘”再到“秘书执行”和“心理/圆桌辅助决策”的完整闭环：

```text
用户私聊
  -> 会话与 turn 落盘
  -> 意图路由
  -> Agent / 总管判断
  -> 心理状态、长期记忆、偏好画像、日程压力上下文装配
  -> 普通回复 / consult / 圆桌 / Maxwell 规划
  -> pending action 确认
  -> calendar / plan day / background task / proactive message 落盘
  -> 前端日历、任务、心理卡片、圆桌结果、Maxwell 工作台展示
  -> 后台 routine、missed、重排、回访继续消费数据
```

### 2.2 心理关怀全量目标

心理模块不是心情弹窗，而是长期状态追踪系统。全量必须包含：

1. 情绪采集层：从聊天内容提取结构化 emotion observation。
2. 行为采集层：记录深夜使用、最后活跃、作息偏离。
3. 日程压力层：读取日程、任务、逾期、重排、休息窗口。
4. 每日心理快照层：聚合成日级 mood snapshot。
5. 长期趋势层：周/月/年趋势接口和前端可视化。
6. 关怀触发层：冷却、打扰预算、分级触发。
7. 关怀交互层：用户反馈、稍后提醒、降频、关闭某类提醒。
8. 安全边界：不诊断、不替代医生，高风险只做安全提示和求助建议。

### 2.3 圆桌会议全量目标

圆桌不是普通多角色聊天。全量必须包含：

1. `decision` 圆桌：帮助用户做选择，输出结构化决策结果。
2. `brainstorm` 圆桌：帮助用户发散，默认不执行、不落计划。
3. 圆桌结果动作：accept、return、save、handoff。
4. 与总管/Maxwell 的执行边界：用户确认后才写日程或计划。
5. 前端舞台感：席位、发言高亮、主持总结卡、结果按钮。
6. 性能边界：默认一次 LLM 生成整轮，不按角色逐个串行请求。

### 2.4 轻量管家团队全量目标

轻量管家不是复杂多 Agent 炫技，而是稳定决策链路：

```text
当前 Agent / 总管
  -> 判断是否需要 consult
  -> 找专业 Agent 获取意见
  -> 汇总 conflicts / aligned actions / followups
  -> 判断是否推荐圆桌或交给 Maxwell
  -> 需要写操作时生成 pending action
  -> 用户确认后执行
```

### 2.5 计划领域全量目标

计划不能只存在 LLM 文本里，也不能只是一段 background task JSON。全量要实现：

1. 短期计划、长期计划、手动日历事件的统一模型。
2. 计划 day 可单独完成、修改、延期、重排。
3. `planner/calendar-items` 合并普通日历和计划 day。
4. Maxwell 工作台消费当天任务。
5. 心理压力层能读取计划负载。

### 2.6 速度调优全量目标

所有新增能力都必须受性能基线约束：

1. 固定 20 条 benchmark prompt。
2. 后端 timing 覆盖 route、memory、consult、LLM、persist、roundtable、planner。
3. 前端记录 send_clicked、response_headers、first_render、final_render。
4. 每次心理、圆桌、consult、记忆召回改动都跑基线。

## 3. 分阶段实施计划

### Phase 0：防缩水基建与工作规范

目标：先建立可追踪机制，避免后续继续 MVP 冒充完成。

对应文件：

- `docs/lsq-worklog/4-28-worklog/原始设计完成度-checklist.md`
- `docs/lsq-worklog/4-28-worklog/给技术人员的全量实现交接说明.md`

任务：

- 确认 checklist 中每个条目的状态：`DONE / MVP / TODO / REWORK / DEFER`。
- 每个 worklog 模板固定包含：对应 checklist、完成范围、代码文件、表、接口、前端、测试、完成度变化、剩余缺口。
- 后续每个技术任务都从 checklist 领取，不允许口头扩缩范围。

验收：

- 技术人员能根据 checklist 明确下一步做什么。
- 任意模块都不能再写模糊的“完成心理模块”。

产出：

- 更新后的 checklist。
- 后续 worklog 模板。

### Phase 1：心理机制 B1 情绪采集层 MVP

优先级：P0  
当前完成度：心理机制 25% -> 35%  
对应原始设计：`05-心理关怀模块架构.md` 的“聊天情绪观测链路”

目标：把当前单轮规则识别升级为可持久追踪的 emotion observation。

后端任务：

- 新增 `jarvis_emotion_observations` 表或等价持久化结构。
- 字段至少包括：`id`、`session_id`、`turn_id/message_id`、`agent_id`、`primary_emotion`、`secondary_emotions`、`valence`、`arousal`、`stress_score`、`fatigue_score`、`risk_level`、`confidence`、`evidence_summary`、`source`、`created_at`。
- 当前 `mood_care.detect_mood_snapshot()` 的结果必须写入 observation。
- 规则识别保留为快速层。
- 复杂或不确定场景允许后续接 LLM 结构化 JSON，但本阶段至少预留接口。
- 不保存用户心理原文全文，只保存摘要和结构化指标。

接口任务：

- 可选增加内部查询接口或调试接口，用于验证 observation 是否写入。
- 如果暂不开放前端接口，必须有测试或脚本能查到 observation。

前端任务：

- 现有关怀卡片继续工作，不要求本阶段新增页面。
- 卡片中的 `mood.snapshot` 文案应避免暗示这是“日级 snapshot”，可显示为“本次状态记录”。

测试任务：

- 低能量：“我今天特别累，不想学了”。
- 压力/焦虑：“我压力很大，有点焦虑和自责”。
- 睡眠：“我昨晚失眠了”。
- 高风险：“我有点活不下去了”。
- 无心理信号：“帮我查一下明天安排”。

验收：

- Mira 私聊心理信号会写入 `jarvis_emotion_observations`。
- observation 有结构化分数和摘要。
- 高风险标记为 high，但不输出医疗诊断。
- 原有 `mood.snapshot / care.intervention / care.followup` 仍正常返回。

worklog 要求：

- 文件名：`StepB1-心理机制情绪采集层MVP-worklog.md`
- 必须写：这是 B1 MVP，不是心理机制全量完成。

### Phase 2：心理机制 B4 每日心理快照层 MVP

优先级：P0  
依赖：Phase 1  
当前完成度：心理机制 35% -> 45%  
对应原始设计：`05-心理关怀模块架构.md` 的“每日心理快照链路”

目标：从“单轮状态”升级为“日级综合状态”。

后端任务：

- 新增 `jarvis_mood_snapshots` 表。
- 字段至少包括：`date`、`mood_score`、`stress_score`、`energy_score`、`sleep_risk_score`、`schedule_pressure_score`、`dominant_emotions`、`positive_events`、`negative_events`、`risk_flags`、`summary`、`confidence`、`created_at`、`updated_at`。
- 新增聚合函数：从当天 emotion observations、LifeContext、proactive/care 记录中生成日级 snapshot。
- 初版可在用户启动、Mira 私聊后或定时任务中触发。
- 区分单轮 `mood.snapshot action` 和日级 `jarvis_mood_snapshots`，必要时将前端 action 命名/展示调整为“本次状态记录”。

接口任务：

- 新增 `GET /api/v1/care/snapshots?start=...&end=...` 或放在现有 Jarvis router 下的等价接口。
- 返回日级 snapshot 列表。

前端任务：

- 可先做最小展示：在 Mira 或心理面板中显示“今日状态摘要”。
- 不要求复杂图表，图表放 Phase 5。

测试任务：

- 当天多条 emotion observations 能聚合成一条 snapshot。
- 无数据当天不生成误导性高风险结论。
- 高风险 observation 能进入 risk_flags。

验收：

- 每天至少能生成或查询一条综合 mood snapshot。
- snapshot 不是单轮文本，而是日级聚合。

worklog：`StepB4-每日心理快照MVP-worklog.md`

### Phase 3：心理机制 B2 行为采集层 MVP

优先级：P1  
当前完成度：心理机制 45% -> 55%  
对应原始设计：`05-心理关怀模块架构.md` 的“作息行为观测链路”

目标：心理判断不只看聊天文本，也看使用行为和作息偏离。

后端任务：

- 新增 `jarvis_behavior_observations` 表。
- 字段至少包括：`date`、`observation_type`、`expected_bedtime`、`expected_wake`、`actual_first_active_at`、`actual_last_active_at`、`deviation_minutes`、`duration_minutes`、`source`、`created_at`。
- 复用用户资料中的 bedtime / wake。
- 记录最后活跃、首次活跃、深夜使用、超过 bedtime。
- 当前可先从聊天行为和页面活跃事件推断。

前端任务：

- 如果已有心跳或页面 mount 逻辑，接入 activity tracker。
- 如果没有，先用聊天行为作为最小来源，不阻塞后端表设计。

验收：

- 用户晚于 bedtime 仍活跃时，写入 `late_night_usage` observation。
- 行为观测只作为风险输入，不直接诊断用户。

worklog：`StepB2-行为采集层MVP-worklog.md`

### Phase 4：心理机制 B3 日程压力观测层 MVP

优先级：P1  
当前完成度：心理机制 55% -> 65%  
对应原始设计：`05-心理关怀模块架构.md` 的“日程压力观测链路”

目标：让心理模块理解“用户为什么压力高”。

后端任务：

- 新增 `jarvis_stress_signals` 表。
- 读取 `background_task_days`、`calendar_events`、`maxwell_workbench_items`、missed tasks。
- 字段至少包括：`date`、`signal_type`、`severity`、`score`、`reason`、`source_refs`、`created_at`。
- 计算日程密度、连续高压天数、逾期任务数量、未完成数量、休息窗口不足、夜间任务过重。
- 每个 signal 必须有可解释 reason。

接口任务：

- 可并入 snapshot 生成，不一定单独开放前端接口。
- 调试或测试必须能验证 signal 生成。

验收：

- 当日任务过多或逾期多时，生成 pressure signal。
- Mira 可以解释“今天压力偏高是因为任务密度/逾期/休息不足”。
- 圆桌 decision 能读取这些压力信号。

worklog：`StepB3-日程压力观测层MVP-worklog.md`

### Phase 5：心理机制 B5 趋势接口与前端心理中心

优先级：P1  
当前完成度：心理机制 65% -> 75%  
对应原始设计：`05-心理关怀模块架构.md` 的“长期趋势链路”

目标：让用户看到周/月/年的心情、压力、能量趋势。

后端任务：

- 新增 `GET /care/trends?range=week|month|year` 或等价接口。
- 返回 mood、stress、energy、sleep risk、schedule pressure 的时间序列。
- 支持点击某天查看解释：dominant emotions、stress signals、late night usage、任务压力。

前端任务：

- 新增心理趋势入口，可以放在 Jarvis 侧栏、Mira 页面或设置页。
- 初版可以是折线图或日历热力图。
- 点击某一天展开“这天为什么压力高”。

验收：

- 能查看最近一周/一月的 mood/stress/energy 趋势。
- 前端趋势来自后端 snapshot，不是临时猜测。

worklog：`StepB5-心理趋势接口与前端MVP-worklog.md`

### Phase 6：心理机制 B6/B7 关怀触发与反馈闭环

优先级：P1  
当前完成度：心理机制 75% -> 85%  
对应原始设计：关怀触发层、关怀交互层、安全边界

目标：从“检测到就提醒”升级为有冷却、有预算、有用户反馈的温和关怀。

后端任务：

- 设计 care trigger rules：连续高压力、连续晚睡、任务过载、主动求助、高风险关键词。
- 增加 cooldown 和 daily budget。
- proactive message 关联 snapshot / signal。
- 新增用户反馈字段或表：helpful、too_frequent、not_needed、snoozed_until。
- “稍后提醒”接真实 snooze/update 接口。

前端任务：

- 抽出 `CareCard` 组件。
- 按钮扩展为：有帮助、太频繁、稍后提醒、不需要这类提醒、我已处理。
- 用户操作必须回写后端。

安全要求：

- 高风险不做诊断。
- 高风险优先提示联系可信任的人和当地紧急渠道。
- 不允许用激进、吓人或过度承诺的文案。

验收：

- 同一天不会无限重复关怀提醒。
- 用户选择“太频繁”后，后续提醒降频。
- 高风险文案符合安全边界。

worklog：`StepB6B7-关怀触发与反馈闭环-worklog.md`

### Phase 7：圆桌 C1/C2 Decision 模式产品化

优先级：P0  
当前完成度：圆桌 35% -> 55%  
对应原始设计：`07-圆桌模式架构.md` 的 decision 场景

目标：完成可执行的策略决策圆桌。

后端任务：

- `roundtable_sessions` 增加或确认 `mode=decision|brainstorm`、source_session_id、source_agent_id、status。
- 新增或补齐 `roundtable_results`。
- `decision` 输出结构：`summary`、`options`、`recommended_option`、`tradeoffs`、`actions`、`handoff_target`。
- 启动前预取心理 snapshot、日程压力、今日任务、必要 RAG 摘要。
- 圆桌讨论阶段默认不调用工具。
- 用户 accept 后交给 Maxwell / Committer 生成 pending action。

前端任务：

- decision 圆桌结果展示推荐选项、利弊、下一步动作。
- 按钮：接受建议、返回私聊、让 Maxwell 执行。

验收：

- 用户从 Mira 私聊进入“我很累但还有学习任务，要不要继续？”圆桌。
- 圆桌综合 Mira/Maxwell/Athena 输出结构化建议。
- 用户接受后生成待确认日程调整卡，而不是直接改日程。

worklog：`StepC2-圆桌Decision结构化与Handoff-worklog.md`

### Phase 8：圆桌 C3 Brainstorm 模式产品化

优先级：P1  
当前完成度：圆桌 55% -> 70%  
对应原始设计：`07-圆桌模式架构.md` 的 brainstorm 场景

目标：自由头脑风暴只发散，不默认执行。

后端任务：

- `brainstorm` 输出结构：`themes`、`ideas`、`tensions`、`followup_questions`、`save_as_memory`。
- 默认不写 calendar、不写 plan。
- 用户选择“保存灵感”才写 memory。
- 用户选择“转成计划”才交给 Maxwell。

前端任务：

- brainstorm 结果展示主题、想法、冲突、追问。
- 按钮：保存灵感、继续讨论、转成计划。

验收：

- 用户能用圆桌发散想法。
- 不会未经确认生成计划或改日程。

worklog：`StepC3-圆桌Brainstorm模式-worklog.md`

### Phase 9：圆桌 C4/C5 舞台体验与性能边界

优先级：P1  
当前完成度：圆桌 70% -> 80%  
目标：让圆桌既有角色感，又不拖慢。

前端任务：

- 席位、头像、当前发言高亮。
- 主持总结卡。
- 角色发言长度限制，避免文本墙。
- 区分 decision 和 brainstorm 的视觉和按钮。

性能任务：

- 计划调整：保留角色轮流发言，不改成一次 LLM 生成整轮 JSON。
- 计划调整：角色逐个发言是产品目标体验，不作为性能问题移除。
- 计划调整：暂不做减少上下文或上下文拆分，避免破坏讨论质量。
- 加 timing span：context_prepare、agent_turn、result_persist，用于解释轮流发言耗时。

验收：

- 圆桌有明确模式感和舞台感。
- 响应速度可被 timing 解释。

worklog：`StepC4C5-圆桌舞台体验与性能-worklog.md`

### Phase 10：轻量管家团队闭环

优先级：P1  
当前完成度：轻量管家 45% -> 75%  
对应原始设计：`06-轻量管家团队架构.md`

目标：让 consult、圆桌、Maxwell、确认机制形成稳定团队链路。

后端任务：

- 明确触发策略：直接回复、consult、推荐圆桌、交给 Maxwell。
- 固定 consult 输出 schema：`specialists`、`summary`、`aligned_actions`、`conflicts`、`followups`、`handoff_target`。
- 增加 consult 超时、失败降级。
- Committer 边界：写 calendar/task/memory 需要 pending confirmation。
- 所有写动作可追溯到用户确认。

前端任务：

- 展示“参考了哪些 Agent 意见”。
- 不把每个 consult 都变成独立聊天气泡。
- 最终只出现一条清晰回复和必要 action card。

验收：

- 用户说“我状态很差但还要推进考试计划”，系统能 consult Mira + Maxwell + Athena。
- 输出一条清晰回复，并在需要时生成 pending action。

worklog：`StepD-轻量管家团队闭环-worklog.md`

### Phase 11：计划领域模型补齐

优先级：P1  
当前完成度：计划领域 40% -> 75%  
对应原始设计：`04-整体架构描述.md`

目标：把计划从 background task MVP 升级为统一计划领域。

决策任务：

- 判断继续扩展 `background_tasks + background_task_days`，还是引入 `jarvis_plans + jarvis_plan_days`。
- 如果引入新表，写迁移策略，不能破坏当前 daily task MVP。

后端任务：

- 实现或设计 `planner/calendar-items`，合并 calendar events、plan days、background task days。
- 短期计划、长期计划、手动日历事件统一确认规则。
- 计划 day 支持完成、修改、延期、重排。
- 心理压力层可以读取计划负载。

前端任务：

- 日历视图展示普通事件和计划 day。
- 任务列表展示 background task days / plan days 的状态。
- Maxwell 工作台消费当天任务。

验收：

- 30 天计划能拆成每日可执行项。
- 每日项能显示、完成、延期、重排。
- 心理模块能读取任务压力。

worklog：`StepE-统一计划领域模型-worklog.md`

### Phase 12：速度调优持续化

优先级：P1  
当前完成度：速度基线 45% -> 80%  
对应原始设计：`08-智能体回复速度调优任务.md`

目标：所有新增能力都有可测性能预算。

任务：

- 固定 20 条 benchmark prompt，纳入日常回归。
- 每次心理、圆桌、consult、记忆召回改动后跑基线。
- 后端 timing 覆盖 route、memory、consult、LLM、persist、proactive、roundtable、planner。
- 前端记录 send_clicked、response_headers、first_render、final_render。
- 输出 JSON/CSV 历史对比。
- 优化：规则优先路由、Top-K 记忆裁剪、consult 限流、圆桌一次生成、分页和索引。

验收：

- 能指出最慢 3 个 span。
- 能比较优化前后。
- 新增心理和圆桌能力后不出现无法定位的整体变慢。

worklog：`StepF-速度调优持续化-worklog.md`

## 4. 技术人员每步交付格式

每完成一个 Phase，必须新增 worklog：

```text
docs/lsq-worklog/4-28-worklog/StepX-xxx-worklog.md
```

worklog 必须包含：

1. 对应原始设计文件。
2. 对应 checklist 条目。
3. 本次完成范围。
4. 修改代码文件。
5. 新增或修改数据表。
6. 新增或修改接口。
7. 前端影响。
8. 测试与验证。
9. 完成度变化。
10. 距离全量设计还差什么。

如果某阶段只完成 MVP，必须写：

```text
本阶段是 MVP，不是全量完成。
```

## 5. 防缩水验收硬规则

- 不允许只做关键词规则就说完成心理分析。
- 不允许只做前端卡片就说完成心理机制。
- 不允许只做单轮 `mood.snapshot` action 就说完成每日心理快照。
- 不允许只做 proactive message 就说完成长期关怀触发。
- 不允许只做 `/roundtable/start` 和 `/continue` 就说完成圆桌模式。
- 不允许只做 consult prompt 就说完成轻量管家团队。
- 不允许只做 background task day 就说完成统一计划领域。
- 不允许为了速度优化移除心理、记忆、圆桌的关键能力。
- 不允许高风险心理场景输出医疗诊断。
- 每次验收必须对照 `原始设计完成度-checklist.md` 更新状态。

## 6. 下一步立即执行

下一步直接交给技术人员：

```text
请执行 Phase 1：心理机制 B1 情绪采集层 MVP。

先阅读：
1. docs/lsq-worklog/4-28-worklog/4-28plan.md
2. docs/lsq-worklog/4-28-worklog/原始设计完成度-checklist.md
3. docs/lsq-worklog/待完成/05-心理关怀模块架构.md

实现要求：
- 新增 jarvis_emotion_observations 持久化。
- 将 mood_care.detect_mood_snapshot() 的结果写入 observation。
- observation 不保存用户心理原文全文，只保存 evidence_summary 和结构化指标。
- 保持当前 mood.snapshot / care.intervention / care.followup 前端卡片不坏。
- 补低能量、压力、睡眠、高风险、无信号五类测试或验证。
- 写 StepB1-心理机制情绪采集层MVP-worklog.md。

注意：这是 B1 MVP，不是心理机制全量完成。
```
