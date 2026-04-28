# Phase 8 及之后剩余缺口清单（排除管家团队）

核查范围：`4-28plan.md` 中 Phase 8 及之后。  
排除范围：Phase 10 轻量管家团队闭环，因为你明确没有让技术人员做管家团队架构升级。  
核查依据：`worklog` 目录、`原始设计完成度-checklist.md`、当前代码接口与文件。

## 一、总体结论

| 阶段 | 模块 | 当前状态 | 还差什么 |
|---|---|---|---|
| Phase 8 | 圆桌 Brainstorm | MVP 已完成 | 缺 return 链路、schema 规范、result_json 正规化、与来源私聊回写。 |
| Phase 9 | 圆桌舞台体验与性能 | MVP 已完成，且策略调整为保留轮流发言 | 缺 roundtable return、错误降级、进度失败态、性能预算；一次生成整轮已按产品策略 DEFER。 |
| Phase 10 | 轻量管家团队 | 本次不要求 | 不纳入本清单。 |
| Phase 11 | 统一计划领域模型 | 基本完成，日志标 96% | 仍需页面验收、心理压力联动验收、旧 background_task 迁移/兼容确认。 |
| Phase 12 | 速度调优持续化 | 只完成早期基线 MVP | 缺前端端到端埋点、持续回归、性能预算、历史对比、改动后自动跑基线。 |

## 二、Phase 8：圆桌 Brainstorm 模式产品化

技术日志：`docs/lsq-worklog/4-28-worklog/worklog/StepC3-圆桌Brainstorm模式-worklog.md`

### 已完成

- Brainstorm 圆桌结束后生成并持久化结构化 `brainstorm_result`。
- `brainstorm_result` 包含 themes、ideas、tensions、followup_questions、save_as_memory。
- 默认只保存 result，不写 calendar、不写 plan。
- 用户点击“保存灵感”后才写 `jarvis_memories`。
- 用户点击“转成计划”后才生成 Maxwell `pending_actions` 待确认计划卡。
- 前端 Brainstorm 结果卡展示主题、想法、张力，并提供保存灵感、继续讨论、转成计划按钮。
- 后端接口已看到：
  - `GET /roundtable/{session_id}/brainstorm-result`
  - `POST /roundtable/{session_id}/save`
  - `POST /roundtable/{session_id}/plan`

### 仍需补齐

1. **return 返回私聊链路**
   - 当前后端 decorator 中没有看到 `POST /roundtable/{session_id}/return`。
   - Brainstorm 保存或讨论结束后，用户应能返回原私聊，并把总结作为一条消息写回来源 session。

2. **result schema 正规化**
   - worklog 说明 Brainstorm MVP 复用 `roundtable_results.options_json` 存 themes、`tradeoffs_json` 存 tensions、`context_json` 存 ideas/followups。
   - 这能跑，但不够全量。建议补正式 `result_json`，完整保存 brainstorm_result。

3. **保存灵感后的二次引用**
   - 已能保存 memory，但后续检索、在私聊/圆桌中引用该灵感的体验没有明确验收。
   - 至少要确认记忆面板可见、后续询问时能被长期记忆召回。

4. **Brainstorm 转计划后的确认链路页面验收**
   - 已生成 pending action，但需要确认页面上能在 Maxwell / 待确认动作中看到，并且不会直接落日程。

## 三、Phase 9：圆桌舞台体验与性能边界

技术日志：`docs/lsq-worklog/4-28-worklog/worklog/StepC4C5-圆桌舞台体验与性能-worklog.md`

### 已完成

- 产品策略已调整：保留角色轮流发言，不做一次请求返回整轮，不做减少上下文。
- 圆桌舞台区分 Decision / Brainstorm 视觉模式。
- 席位、头像、当前发言高亮和 `Speaking` 标识已强化。
- 中心圆桌增加主持总结卡。
- 当前发言气泡做长度控制，完整内容保留在完整记录中。
- 后端为轮流发言增加 timing：context_prepare、agent_turn、result_persist、total_ms。
- 前端顶部显示本轮 timing 总耗时。

### 策略调整说明

以下原计划项不再要求实现，应该在 checklist 中长期标为 `[DEFER]`，且原因是产品策略调整：

- 默认一次 LLM 生成整轮 JSON。
- 禁止按角色逐个串行调用。
- 减少上下文作为默认性能策略。

保留轮流发言后，性能优化方向改为：

- 用户可见进度。
- agent_turn 级 timing。
- 单 Agent 失败降级。
- 错误不中断整场圆桌。
- 必要时做缓存/预取，而不是牺牲轮流发言体验。

### 仍需补齐

1. **return 接口仍缺**
   - 后端 roundtable decorators 中目前有 start、continue、decision-result、brainstorm-result、accept、save、plan。
   - 没有看到 `POST /roundtable/{session_id}/return`。

2. **轮流发言错误降级不完整**
   - 需要每个 agent_turn 有 status/error。
   - 某个 Agent 失败时，主持人应说明并继续。
   - 前端应显示“某角色暂时失败/已跳过”，不能整个圆桌空白或卡死。

3. **进度反馈还可加强**
   - 现在有 Speaking 和 timing，但需要确认是否显示“第几位 / 共几位”“正在生成总结”等明确进度。

4. **roundtable result schema 仍需补强**
   - `user_choice`、`handoff_status`、`result_json` 需要规范。

5. **上下文解释展示不足**
   - Decision 圆桌应显示参考了哪些上下文：心理状态、任务压力、今日任务、日程。
   - 不应暴露敏感心理原文。

## 四、Phase 11：统一计划领域模型补齐

技术日志：`docs/lsq-worklog/4-28-worklog/worklog/StepE-unified-planner-worklog.md`

### 已完成

从代码和日志看，统一计划领域已经大幅推进：

- 新增或已存在 `jarvis_plans`、`jarvis_plan_days`、`jarvis_agent_events`。
- 有 `GET /planner/calendar-items`。
- 有 planner daily maintenance 接口：
  - `POST /planner/daily-maintenance`
  - `POST /planner/daily-maintenance/once`
- 有 mark overdue missed。
- 有 plan reschedule / calendar sync / Maxwell workbench push 链路。
- 测试 `test_unified_planner.py` 存在，worklog 记录 `12 passed`。
- 日志声称 Planner domain 从 93% 到 96%。

### 仍需补齐

1. **用户页面验收不足**
   - 代码和测试较完整，但还需要从页面确认：计划 day 是否显示在日历、任务列表、Maxwell 工作台。

2. **旧 background_task_days 迁移/兼容说明**
   - 需要明确旧数据是否迁移到 `jarvis_plan_days`，还是双轨并存。
   - 如果双轨并存，页面合并展示规则要写清楚。

3. **心理压力联动验收**
   - stress signals 是否已优先读取 `jarvis_plan_days`，并在心理趋势/圆桌 decision 中体现，需要页面验证。

4. **计划修改/延期/重排的前端入口**
   - 后端有 reschedule 等能力，但用户是否能在页面直接操作还要确认。

5. **自动 maintenance 的可见反馈**
   - 自动 missed -> LLM/Maxwell 重排 -> proactive message 是否能被用户看到，需要页面验收。

## 五、Phase 12：速度调优持续化

当前没有看到新的 Phase 12 专门 worklog。早期 Step1 已完成基线 MVP，但 Phase 12 全量仍缺。

### 已完成

- 有 `shadowlink-ai/scripts/jarvis_perf/baseline_prompts.json`。
- 有 `shadowlink-ai/scripts/jarvis_perf/run_baseline.py`。
- Jarvis chat 已有 timing spans。
- Roundtable 已有 timing spans。

### 仍需补齐

1. **前端端到端埋点缺失**
   - 未搜到 `send_clicked`、`response_headers`、`first_render`、`final_render` 或 `performance.mark/measure`。
   - 需要在前端记录从点击发送到首渲染/最终渲染的耗时。

2. **持续回归机制缺失**
   - 目前有脚本，但没有看到每次心理、圆桌、计划改动后自动跑基线的流程。

3. **历史对比输出不足**
   - 需要 JSON/CSV 历史结果保存和对比。

4. **性能预算缺失**
   - 未看到明确预算，例如普通私聊、Mira 心理、Decision 圆桌、Brainstorm 圆桌、planner maintenance 的目标耗时。

5. **优化项未完成**
   - 规则优先路由。
   - 长期记忆 Top-K 召回和摘要注入验证。
   - Agent consult 限流/异步/降级。注意：管家团队升级不做，但如果 consult 仍在主链路，应至少限流防慢。
   - 高频列表分页、缓存、索引检查。

## 六、排除项：Phase 10 管家团队

你明确没有让技术人员做管家团队架构升级，所以本次不要求补 Phase 10。

不过如果某些功能当前依赖 consult 主链路，为了稳定性仍建议只做最小防护：

- consult 超时不阻塞主回复。
- consult 失败有降级。
- consult 不自动写库。

这属于稳定性保护，不算管家团队架构升级。

## 七、建议下一步执行顺序

### P0：今天最该补

1. **圆桌 return 接口与返回私聊链路**
   - 补 `POST /roundtable/{session_id}/return`。
   - 前端“返回私聊”按钮真正调用接口。
   - 原私聊出现圆桌总结消息。

2. **圆桌轮流发言错误降级**
   - 单 Agent 失败不中断全场。
   - SSE 发 `agent_error` 或等价事件。
   - 前端显示跳过/失败说明。

3. **Phase 12 前端端到端埋点**
   - 记录 send_clicked、response_headers、first_render、final_render。
   - 至少在 console 或 dev 面板可见。

### P1：接着补

1. `roundtable_results` schema 规范化：result_json、user_choice、handoff_status。
2. Brainstorm 保存灵感后的记忆面板可见和后续召回验证。
3. 统一计划领域页面验收：日历、任务列表、Maxwell 工作台、自动 maintenance 消息。
4. 心理压力读取 `jarvis_plan_days` 的页面可见验证。

### P2：后续补

1. Phase 12 历史 CSV/JSON 对比和性能预算。
2. `/roundtable/{id}/run` 接口策略最终决策：实现或从设计中移除。
3. 圆桌上下文解释展示深化。
4. 旧 background_task_days 到 jarvis_plan_days 的迁移说明和工具。

## 八、给技术人员的话

可以直接发：

```text
我这边不要求你做 Phase 10 管家团队架构升级。其它 Phase 8 以后基本都跑了，但还差几个关键收口：

P0：
1. 补 /roundtable/{session_id}/return，返回原私聊并写入圆桌总结。
2. 补圆桌轮流发言错误降级：单 Agent 失败不中断全场，前端可见失败/跳过说明。
3. 补前端端到端耗时埋点：send_clicked、response_headers、first_render、final_render。

P1：
1. 规范 roundtable_results schema：result_json、user_choice、handoff_status。
2. 验证 Brainstorm 保存灵感后在记忆面板可见并可后续召回。
3. 做统一计划领域的页面验收：planner/calendar-items、日历、任务列表、Maxwell 工作台、maintenance proactive message。
4. 验证心理压力已读取 jarvis_plan_days。

注意：圆桌继续保留角色轮流发言模式，不要改成一次请求返回整轮。
```

