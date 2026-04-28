# Phase 8 之前交付核查与补项清单

核查对象：`docs/lsq-worklog/4-28-worklog/worklog` 中技术实现日志。  
核查范围：`4-28plan.md` 中 Phase 0 到 Phase 7，即 Phase 8 之前的内容。  
核查方式：对照 `4-28plan.md`、`原始设计完成度-checklist.md`、技术 worklog、当前代码落点。

> 结论先行：Phase 1 到 Phase 7 大部分已经达到 MVP 交付，但都不是全量完成。主要缺口集中在：LLM 结构化情绪分析、真实 turn_id 关联、日级 snapshot 自动调度、行为采集来源完整性、日程压力连续高压/重排日志、心理趋势前端入口、care trigger 与 proactive 定时联动、roundtable return 接口。

## 一、总体判断

| Phase | 对应内容 | 当前判断 | 是否完整交付 |
|---|---|---|---|
| Phase 0 | 防缩水基建与工作规范 | checklist 和交接说明已建立 | MVP 完成，需持续维护 |
| Phase 1 | 心理 B1 情绪采集层 | 表、保存函数、规则 observation、测试已落地 | MVP 完成，非全量 |
| Phase 2 | 心理 B4 每日心理快照 | 表、聚合模块、接口、测试已落地 | MVP 完成，自动化不足 |
| Phase 3 | 心理 B2 行为采集层 | 表、聊天/前端事件、接口、测试已落地 | MVP 完成，采集源仍不全 |
| Phase 4 | 心理 B3 日程压力观测 | 表、压力信号、测试已落地 | MVP 完成，计划/重排接入不足 |
| Phase 5 | 心理 B5 趋势接口与前端 | `/care/trends` 和前端组件已出现 | MVP 完成，产品入口和解释深度不足 |
| Phase 6 | 心理 B6/B7 触发与反馈 | 触发表、反馈接口、CareCard 已落地 | MVP 完成，联动和策略需补 |
| Phase 7 | 圆桌 Decision 产品化 | decision result、accept、pending action、前端结果卡已落地 | MVP 完成，return/schema 仍缺 |

## 二、Phase 0：防缩水基建与工作规范

对应计划：`4-28plan.md` Phase 0。  
对应文件：

- `docs/lsq-worklog/4-28-worklog/原始设计完成度-checklist.md`
- `docs/lsq-worklog/4-28-worklog/给技术人员的全量实现交接说明.md`

### 已交付

- 已建立 checklist 状态定义：`DONE / MVP / TODO / REWORK / DEFER`。
- 已列出全量设计源文件。
- 已把心理、圆桌、轻量管家、整体计划、速度调优拆成可追踪条目。
- 技术 worklog 基本开始按“完成范围 / 代码文件 / 表 / 接口 / 测试 / 完成度变化 / 剩余缺口”记录。

### 还要补

- checklist 需要在每次实现后同步更新，不能只在 worklog 里写完成度。
- checklist 里部分条目已经被标为 `[MVP]`，但缺少对应代码文件和测试文件引用，建议补一列“佐证文件”。
- 建议新增一个固定 worklog 模板文件，例如：`docs/lsq-worklog/4-28-worklog/worklog-template.md`。

### 下一步补项

- 给 checklist 增加每项的“代码佐证 / 测试佐证 / 最后更新时间”。
- 每次技术人员提交后，要求同步更新 checklist，而不是只新增 worklog。

## 三、Phase 1：心理机制 B1 情绪采集层 MVP

对应计划：Phase 1。  
技术日志：`worklog/StepB1-心理机制情绪采集层MVP-worklog.md`。  
关键代码：

- `shadowlink-ai/app/jarvis/mood_care.py`
- `shadowlink-ai/app/jarvis/persistence.py`
- `shadowlink-ai/tests/unit/jarvis/test_mood_care_observations.py`

### 已交付

- 已新增 `jarvis_emotion_observations` 表。
- 已新增保存函数 `save_emotion_observation()`。
- `mood_care.detect_mood_snapshot()` 的规则结果已可转成 observation payload。
- `persist_mood_care()` 已调用 `save_emotion_observation()`。
- observation 保存结构化字段：primary_emotion、secondary_emotions、valence、arousal、stress_score、fatigue_score、risk_level、confidence、evidence_summary、signals。
- worklog 声称并代码显示不保存用户心理原文全文。
- 已有单元测试文件覆盖情绪 observation。

### 不完整点

- `turn_id` 当前写入为 `None`，没有和实际 `agent_chat_turns` 的用户 turn 严格关联。代码中 `persist_mood_care()` 调用 `save_emotion_observation(turn_id=None)`。
- 当前仍是规则 MVP，没有实现“必要时 LLM 结构化 JSON”。这在 checklist 里也标注为未完成。
- emotion observation 没看到专门的查询/调试接口；目前主要靠测试或内部函数验证。
- 当前情绪分类仍较粗，不能覆盖原设计中的愤怒、开心、兴奋、无助、拖延、自责等完整情绪谱系。

### 必须补的东西

1. **补 turn 关联**
   - `save_chat_turn()` 需要返回用户 turn id，或先保存用户 turn 后再把 id 传给 `persist_mood_care()`。
   - `jarvis_emotion_observations.turn_id` 不能长期为空。

2. **补 LLM 结构化 fallback**
   - 对规则置信度低、复杂表达、多情绪混合场景，调用 LLM 输出结构化 JSON。
   - LLM 输出字段必须贴合原设计：primary_emotion、secondary_emotions、valence、arousal、stress_score、fatigue_score、risk_level、confidence、evidence_summary。

3. **补 emotion observation 查询或调试能力**
   - 可新增内部调试接口，或在 `/care/snapshots` 详情中关联 observation ids。

4. **补更多情绪测试**
   - 愤怒、开心、兴奋、无助、拖延、自责、混合情绪。

## 四、Phase 2：心理机制 B4 每日心理快照层 MVP

对应计划：Phase 2。  
技术日志：`worklog/StepB4-每日心理快照MVP-worklog.md`。  
关键代码：

- `shadowlink-ai/app/jarvis/mood_snapshot.py`
- `shadowlink-ai/app/jarvis/persistence.py`
- `shadowlink-ai/app/api/v1/jarvis_router.py`
- `shadowlink-ai/tests/unit/jarvis/test_mood_snapshots.py`

### 已交付

- 已新增 `jarvis_mood_snapshots` 表。
- 已有 `aggregate_mood_snapshot()` / `build_snapshot_payload()`。
- 聚合输入包含 emotion observations、behavior observations、stress signals。
- 已有 `/care/snapshots` 查询接口。
- snapshot 字段覆盖 mood_score、stress_score、energy_score、sleep_risk_score、schedule_pressure_score、dominant_emotions、positive_events、negative_events、risk_flags、summary、confidence。

### 不完整点

- 日级 snapshot 的自动生成机制不够明确：目前看起来更多依赖接口调用或业务链路触发，没有确认有稳定每日定时或启动时补齐所有缺失日期。
- `positive_events` 当前实现较弱，主要看到 negative/stress 输入，正向事件来源不足。
- 高风险、行为、压力信号进入 snapshot 的解释性还需要产品化验证。
- 前端“今日状态摘要”入口不确定是否已经作为稳定产品入口出现。

### 必须补的东西

1. **补自动聚合调度**
   - 用户启动时补当天 snapshot。
   - 每日固定时间生成前一天 snapshot。
   - 如果缺失历史日期，支持 backfill。

2. **补正向事件来源**
   - 任务完成、用户表达开心/放松、按时休息等应进入 positive_events。

3. **补 snapshot 解释接口或详情**
   - 点击某天能解释来自哪些 emotion / behavior / stress signals。

4. **补前端稳定入口**
   - 不只在调试面板里可见，要有用户能找到的心理状态入口。

## 五、Phase 3：心理机制 B2 行为采集层 MVP

对应计划：Phase 3。  
技术日志：`worklog/StepB2-行为采集层MVP-worklog.md`。  
关键代码：

- `shadowlink-ai/app/jarvis/persistence.py`
- `shadowlink-ai/app/api/v1/jarvis_router.py`
- `shadowlink-web/src/services/jarvisApi.ts`
- `shadowlink-web/src/components/jarvis/AgentChatPanel.tsx`
- `shadowlink-ai/tests/unit/jarvis/test_behavior_observations.py`

### 已交付

- 已新增 `jarvis_behavior_observations` 表。
- 已有 `/care/behavior-events` 和 `/care/behavior-observations`。
- 前端已出现 behavior event API 调用能力。
- checklist 显示已记录首次活跃、最后活跃、深夜使用、超过 bedtime，连续在线目前为 heartbeat MVP。
- 已接入用户资料中的 bedtime/wake。

### 不完整点

- 行为采集来源还不全。当前主要看聊天、前端 heartbeat、visibility/关闭事件，未确认覆盖 Electron 桌面壳、浏览器关闭异常、长时间后台运行等情况。
- 连续在线只是 heartbeat MVP，未形成稳定 session duration / active duration 计算。
- 关闭事件在浏览器中不一定可靠，需要补容错策略。
- 用户禁用心理追踪后的行为采集边界需要重点验证。

### 必须补的东西

1. **补行为事件可靠性策略**
   - heartbeat 丢失、页面异常关闭、刷新、休眠恢复要有兜底。

2. **补连续在线/活跃时长计算**
   - 从 heartbeat 合并为 session activity window。

3. **补隐私开关验证**
   - 关闭 psychological tracking 后，不应继续写入行为观测。

4. **补 Electron/桌面端来源评估**
   - 如果未来桌面端为主，需要把打开/关闭程序时间接入。

## 六、Phase 4：心理机制 B3 日程压力观测层 MVP

对应计划：Phase 4。  
技术日志：`worklog/StepB3-日程压力观测层MVP-worklog.md`。  
关键代码：

- `shadowlink-ai/app/jarvis/persistence.py`
- `shadowlink-ai/tests/unit/jarvis/test_stress_observations.py`

### 已交付

- 已新增 `jarvis_stress_signals` 表。
- 已能读取 `background_task_days`、内存 `calendar_events`、Maxwell workbench、missed tasks。
- 已计算任务密度、missed 数量、未完成任务、休息窗口不足、晚间任务过重等 MVP 压力 signal。
- 每条 signal 有 reason 和 source_refs。

### 不完整点

- 未接入 `jarvis_plan_days`，因为统一计划模型还未完成。
- 未接入重排日志，因此无法评估“计划反复重排导致压力”。
- 连续高压天数仍未实现。
- `calendar_events` 如果仍是内存来源，长期可靠性不足。

### 必须补的东西

1. **补连续高压天数**
   - 基于 mood snapshots 或 stress signals 计算连续 N 天高压。

2. **补计划重排信号**
   - 需要计划领域增加重排日志后接入。

3. **补统一计划表接入**
   - Phase 11 引入 `jarvis_plan_days` 后，stress signals 必须读取它。

4. **补压力解释前端展示**
   - 用户要能看到“压力高是因为任务密度/逾期/休息不足”。

## 七、Phase 5：心理机制 B5 趋势接口与前端心理中心

对应计划：Phase 5。  
技术日志：`worklog/StepB5-心理趋势接口与前端MVP-worklog.md`。  
关键代码：

- `shadowlink-ai/app/jarvis/care_trends.py`
- `shadowlink-ai/app/api/v1/jarvis_router.py`
- `shadowlink-web/src/components/jarvis/CareTrendsPanel.tsx`
- `shadowlink-web/src/services/jarvisApi.ts`
- `shadowlink-ai/tests/unit/jarvis/test_care_trends.py`

### 已交付

- 已有 `/care/trends?range=...` 接口。
- 已有 `CareTrendsPanel` 前端组件。
- 后端 trends 返回 week/month/year 范围时间序列能力。
- 代码中有 day-level details/explanations 聚合迹象。

### 不完整点

- 前端心理中心入口是否稳定暴露不明确，可能只是组件存在。
- 趋势图/热力图的产品体验需要确认，不应只停留在简单列表或调试面板。
- 点击某一天解释压力来源需要实测验证。
- 年度数据量、空数据、用户关闭追踪后的展示状态需要验证。

### 必须补的东西

1. **补稳定入口**
   - 在 Jarvis 侧栏、Mira 页面或设置页明确放置心理趋势入口。

2. **补 day detail 交互**
   - 点击某天展开 emotion / behavior / stress 来源。

3. **补空状态和隐私状态**
   - 关闭追踪时显示“心理追踪已关闭”，不能显示伪数据。

4. **补前端截图/路演验证**
   - worklog 需记录用户从哪里进入、看到什么。

## 八、Phase 6：心理机制 B6/B7 关怀触发与反馈闭环

对应计划：Phase 6。  
技术日志：`worklog/StepB6B7-关怀触发与反馈闭环-worklog.md`。  
关键代码：

- `shadowlink-ai/app/jarvis/care_triggers.py`
- `shadowlink-ai/app/jarvis/persistence.py`
- `shadowlink-ai/app/api/v1/jarvis_router.py`
- `shadowlink-web/src/components/jarvis/CareCard.tsx`
- `shadowlink-web/src/services/jarvisApi.ts`
- `shadowlink-ai/tests/unit/jarvis/test_care_triggers.py`

### 已交付

- 已新增 `jarvis_care_triggers`、`jarvis_care_interventions`。
- `proactive_messages` 已有 `snoozed_until`。
- 已有 `care_feedback` 接口：`/messages/{message_id}/care-feedback`。
- 已有 snooze / helpful / too_frequent / not_needed / handled 等反馈。
- 已有 cooldown 和 daily budget 的 MVP 逻辑。
- 已抽出 `CareCard`。

### 不完整点

- `evaluate_care_triggers()` 是否接入后台 routine scheduler / proactive engine 不明确。也就是说，规则可能存在，但不一定会定时自动运行。
- care trigger 与 snapshot/signal 的关联虽然有 evidence_ids，但前端解释是否展示还不明确。
- `too_frequent` / `not_needed` 降频逻辑当前看起来是 7 天内负反馈影响 daily_budget，仍比较粗。
- `CareCard` 和 `AgentChatPanel` 之间似乎存在重复调用反馈的风险：`CareCard` 内部调用 `jarvisApi.sendCareFeedback()`，同时 `onFeedback` 也会触发 `AgentChatPanel.updateCareAction()`，而后者也调用 `sendCareFeedback()`。需要确认是否会双发请求。

### 必须补的东西

1. **补自动触发接入**
   - 将 `evaluate_care_triggers()` 接入 proactive engine / routine scheduler。

2. **检查并修复 CareCard 双请求风险**
   - 反馈请求应只由父组件或子组件其中一方发送。

3. **补触发解释展示**
   - 告诉用户为什么收到这次关怀：连续高压、晚睡、任务过载等。

4. **补更细粒度偏好降频**
   - 不只是全局 daily_budget，还要按 trigger_type 降频。

## 九、Phase 7：圆桌 C1/C2 Decision 模式产品化

对应计划：Phase 7。  
技术日志：`worklog/StepC2-圆桌Decision结构化与Handoff-worklog.md`。  
关键代码：

- `shadowlink-ai/app/api/v1/jarvis_router.py`
- `shadowlink-ai/app/jarvis/persistence.py`
- `shadowlink-ai/app/jarvis/roundtable_sessions.py`
- `shadowlink-web/src/components/jarvis/RoundtableStage.tsx`
- `shadowlink-ai/tests/unit/jarvis/test_roundtable_decision.py`

### 已交付

- 已新增/补齐 `roundtable_results`。
- 已有 `_build_decision_result()`。
- 已有 `/roundtable/{session_id}/accept`。
- Decision 结果包含 summary、options、recommended_option、tradeoffs、actions、handoff_target。
- accept 后生成 Maxwell pending action，不直接改日程。
- 前端有 Decision 结果卡和接受/执行按钮。
- 启动前预取心理 snapshot、压力信号、今日任务、日程事件、Maxwell workbench、MVP RAG 摘要。

### 不完整点

- `roundtable_results.user_choice / handoff_status` 目前由 status / pending_action_id MVP 表达，schema 仍不完整。
- `POST /roundtable/{id}/return` 仍未产品化。
- `POST /roundtable/{id}/run` 未实现。
- title / user_prompt 独立字段仍不完整，部分靠 conversation_history / turns 间接保存。
- Decision 仍未实现“默认一次 LLM 生成整轮 JSON”，但后续 Phase 9 已按产品决策 defer。若保留轮流发言，需要明确这是新的产品决策。

### 必须补的东西

1. **补 return 接口**
   - 用户从圆桌返回原私聊，把总结作为一条普通消息带回原会话。

2. **补结果 schema**
   - roundtable_results 增加或规范 user_choice、handoff_status，而不是长期用 status/pending_action_id 代替。

3. **补 run 接口决策**
   - 如果不做 `/run`，需要在 plan/checklist 明确移除或合并到 start/continue，不能一直 TODO。

4. **补来源字段**
   - roundtable session 需要稳定保存 title、user_prompt、source_session_id、source_agent_id。

## 十、Phase 8 状态提示（不属于“之前”，但已看到日志）

虽然用户要求核查 Phase 8 之前，但当前 worklog 中已经有 `StepC3-圆桌Brainstorm模式-worklog.md`，并且代码出现 brainstorm result、save、plan 接口。

初步判断：Phase 8 Brainstorm MVP 已交付，但仍有缺口：

- `return` 接口仍未产品化。
- `POST /roundtable/{id}/run` 仍未实现或未决策。
- Brainstorm 的 themes/ideas/tensions 当前可能复用 `roundtable_results` 的 options/tradeoffs 字段，后续建议规范 result_json。
- 保存灵感和转计划需要确认不会直接写 calendar/plan，只生成 memory 或 pending action。

如果需要，可以下一轮单独做 `Phase8-9 圆桌核查补项清单.md`。

## 十一、建议立即安排的补项顺序

### P0 必补

1. Phase 1：emotion observation 补真实 `turn_id` 关联。
2. Phase 6：检查并修复 `CareCard` 反馈双请求风险。
3. Phase 6：把 `evaluate_care_triggers()` 接入后台 proactive/routine 自动触发。
4. Phase 7：补 `/roundtable/{id}/return`。

### P1 必补

1. Phase 2：补 mood snapshot 自动调度和 backfill。
2. Phase 4：补连续高压天数和重排日志接入。
3. Phase 5：补前端心理趋势稳定入口和 day detail 展示。
4. Phase 7：规范 `roundtable_results` 的 user_choice / handoff_status / result_json。

### P2 后续补

1. Phase 1：补 LLM 结构化情绪 fallback。
2. Phase 3：补 Electron/桌面端行为事件。
3. Phase 6：按 trigger_type 做更细粒度降频。
4. Phase 7：决策 `/run` 接口是否保留或合并到现有接口。

