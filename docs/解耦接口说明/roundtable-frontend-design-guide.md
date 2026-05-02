# 圆桌前端设计指南

**适用范围：** 本文只覆盖 Jarvis 圆桌环节的前端设计。圆桌已经按独立全栈模块解耦，前端实现应围绕后端已经提供的圆桌能力设计界面与交互，不要只照现有 `RoundtableStage.tsx` 的视觉结构补丁式开发。

**后端主入口：**

- `shadowlink-ai/app/api/v1/jarvis/roundtable/router.py`
- `shadowlink-ai/app/api/v1/jarvis_router.py`
- `shadowlink-ai/app/jarvis/roundtable_protocols.py`
- `shadowlink-ai/app/jarvis/*_graph.py`

**前端当前入口：**

- `shadowlink-web/src/components/jarvis/RoundtableStage.tsx`
- `shadowlink-web/src/components/jarvis/roundtableStageLogic.ts`
- `shadowlink-web/src/services/jarvisApi.ts`
- `shadowlink-web/src/components/jarvis/JarvisHome.tsx`
- `shadowlink-web/src/components/jarvis/ScenarioGrid.tsx`

---

## 1. 产品定位

圆桌不是普通聊天弹窗，而是一个“多角色会议工作台”：

1. 用户从私聊、场景入口或历史会话进入圆桌。
2. 后端按场景协议组织多角色发言。
3. 用户可以在每一轮后继续补充、改方向、要求收敛。
4. 圆桌生成两类最终结果：`decision` 或 `brainstorm`。
5. 用户明确点击后，结果才能进入后续业务链路：待确认动作、记忆、Maxwell 计划、回到原私聊。

前端需要表达的核心边界：

- 圆桌可以读取上下文、讨论、生成建议和生成待确认动作。
- 圆桌不能表现成“已经直接修改日历/计划/关怀数据”。
- 所有写入型后续动作都必须有用户点击和明确状态反馈。
- `done` 只代表本轮讨论结束，不代表结果已经被接受、保存或返回私聊。

---

## 2. 圆桌用户流程

### 2.1 进入圆桌

入口来源：

| 来源 | 前端责任 |
| --- | --- |
| 场景卡片 | 从 `jarvisScenarioApi.listScenarios()` 渲染场景，点击后创建 `session_id` 并打开圆桌。 |
| 私聊升级 | 带入 `source_session_id`、`source_agent_id`、`scenario_id`、`user_input`，用于结束后回写私聊。 |
| 历史会话 | 通过 conversation history 或 session id 恢复会话，先拉取 turns，再拉取最新结果。 |

进入时必须准备：

- `scenario_id`
- `session_id`
- `user_input`
- 可选 `mode_id`
- 可选 `source_session_id`
- 可选 `source_agent_id`

### 2.2 直播会议

前端需要展示：

- 当前场景名称、图标和模式。
- 参与角色列表。
- 当前发言角色。
- 当前阶段、轮次、进度。
- 流式发言内容。
- 完整记录入口。
- 降级提示。
- 后端发来的阶段增强信息。

会议中用户不能重复提交：

- `status === "streaming"` 时禁用输入和路线按钮。
- 正在请求 `accept/save/plan/return` 时禁用对应按钮。

### 2.3 每轮结束后的用户判断

后端会发：

- `round_summary`
- `user_checkpoint`
- `scenario_state.next_routes`

前端需要提供：

- 本轮纪要面板：角色纪要、共识、分歧、需要用户判断的问题。
- 用户输入框：继续补充、纠偏或要求收敛。
- 下一轮路线按钮：只把 `prompt` 填进输入框，不能自动发送，不能直接跳阶段。
- 收敛提示：用户可以输入 `finalize`、`收敛`、`给我结论` 等触发后端 finalize。

### 2.4 最终结果后的操作

如果是 `decision`：

- 展示决策摘要、推荐选项、备选方案、取舍、待确认动作说明。
- 提供“接受决策”按钮。
- 提供“带回私聊继续”按钮。
- 接受后展示 pending action，而不是展示“已改日程”。

如果是 `brainstorm`：

- 展示总结、主题、想法、张力、追问。
- 提供“保存为灵感记忆”按钮。
- 提供“转给 Maxwell 生成待确认计划”按钮。
- 提供“带回私聊继续”按钮。
- 保存或转计划后展示记忆或 pending action 状态。

---

## 3. 场景矩阵

| 场景 ID | 模式 | 参与者 | 前端必须支持的界面 |
| --- | --- | --- | --- |
| `schedule_coord` | `decision` | Maxwell, Nora, Mira, Alfred | 日程冲突、保护时间块、推荐方案、待确认日程动作。 |
| `study_energy_decision` | `decision` | Mira, Maxwell, Athena, Alfred | 能量门控、最低学习块、恢复边界、改期选项、待确认安排。 |
| `local_lifestyle` | `brainstorm` | Leo, Maxwell, Nora, Alfred | 本地活动候选、事实补全、评分、排序、计划候选、下一轮路线。 |
| `emotional_care` | `brainstorm` | Mira, Nora, Leo, Alfred | 安全边界、情绪承接、身体支持、低刺激动作、非诊断提示。 |
| `weekend_recharge` | `brainstorm` | Leo, Nora, Mira, Alfred | 周末节奏、活动块、恢复留白、能量预算、可选待确认计划。 |
| `work_brainstorm` | `brainstorm` | Moderator, Explorer, Critic, Synthesizer | 问题框定、想法池、分组、风险矩阵、选中概念、最小验证步骤。 |

模式判断不能写成“场景名包含某个词”。当前后端规则是：

- `decision`：`schedule_coord`、`study_energy_decision`
- `brainstorm`：其它四个预设场景

前端已有 `initialRoundtableModeForScenario()`，后续扩展场景时应同步这个映射。

---

## 4. 后端接口与前端责任

| 后端能力 | 路径 | 前端 UI/逻辑 |
| --- | --- | --- |
| 启动圆桌 | `POST /api/v1/jarvis/roundtable/start` | SSE 读取；初始化阶段、参与者、发言流、结果。 |
| 继续圆桌 | `POST /api/v1/jarvis/roundtable/continue` | 追加用户 turn，禁用输入，接续 SSE。 |
| 获取历史 turns | `GET /api/v1/jarvis/sessions/{session_id}/turns` | 恢复会话时先展示历史记录，避免重复启动。 |
| 获取决策结果 | `GET /api/v1/jarvis/roundtable/{session_id}/decision-result` | 历史恢复或刷新后补回决策卡。 |
| 获取脑暴结果 | `GET /api/v1/jarvis/roundtable/{session_id}/brainstorm-result` | 历史恢复或刷新后补回脑暴卡。 |
| 接受决策 | `POST /api/v1/jarvis/roundtable/{session_id}/accept` | 展示 pending action；文案必须说明未直接改日程。 |
| 保存脑暴 | `POST /api/v1/jarvis/roundtable/{session_id}/save` | 展示保存的 memory；按钮进入 saved 状态。 |
| 脑暴转计划 | `POST /api/v1/jarvis/roundtable/{session_id}/plan` | 展示 Maxwell pending action；文案必须说明未直接创建计划。 |
| 返回私聊 | `POST /api/v1/jarvis/roundtable/{session_id}/return` | 写回来源私聊后调用上层 `onReturnToPrivateChat(agentId, sessionId)`。 |

SSE 目前可以在 `RoundtableStage.tsx` 内直接 `fetch`，因为普通 service 不能直接替代 reader 流处理。其它非 SSE 操作应通过 `jarvisApi` 或后续拆出的 `roundtableApi`。

---

## 5. SSE 事件设计

### 5.1 通用事件

| 事件 | 关键字段 | 前端行为 |
| --- | --- | --- |
| `phase_change` | `phase`, `scenario_id`, `scenario_name`, `participants`, `session_id`, `round_count`, `mode` | 更新顶部状态、模式、轮次、参与者。 |
| `round_started` | `round_index`, `participants` | 重置当前内容，开启进度条。 |
| `role_started` | `agent_id`, `agent_name`, `agent_role`, `round_index` | 高亮当前角色，清空当前流式内容。 |
| `role_delta` | `agent_id`, `delta`, `round_index` | 把 delta 拼到当前发言气泡。 |
| `role_completed` | `content`, `tool_results`, `action_results` | 写入 transcript；显示工具数量和待确认动作数量。 |
| `agent_speak` | legacy agent payload | 兼容旧顺序发言。 |
| `token` | legacy complete content | 兼容旧顺序发言。 |
| `round_summary` | `minutes`, `consensus`, `disagreements`, `questions_for_user`, `next_round_focus` | 展示本轮纪要和用户判断点。 |
| `user_checkpoint` | `allowed_actions` | 设置等待用户输入状态。 |
| `agent_degraded` | `error`, `fallback_content`, `continue_next_agent` | 展示降级提示，不中断整个页面。 |
| `decision_result` | decision result | 展示决策结果卡。 |
| `brainstorm_result` | brainstorm result | 展示脑暴结果卡。 |
| `roundtable_timing` | `total_ms`, `strategy`, `mode` | 可展示调试/性能信息。 |
| `done` | `phase`, `session_id` | 结束本轮 streaming，等待用户下一步。 |

### 5.2 场景增强事件

| 事件 | 关键字段 | 前端行为 |
| --- | --- | --- |
| `scenario_stage` | `stage_id`, `stage_title`, `owner_agent`, `objective`, `artifact_keys` | 展示当前协议阶段、阶段轨迹和阶段目标。 |
| `scenario_state` | `artifacts`, `next_routes`, `state_type` | 展示场景专属中间产物和下一轮路线按钮。 |

`scenario_state.next_routes` 的按钮逻辑：

1. 渲染为简短操作按钮。
2. 点击只填充输入框。
3. 用户再次点击发送后才调用 `/continue`。
4. 前端不能把 `target_stage` 当成本地跳转指令。

### 5.3 工具与待确认动作计数

`role_completed.tool_results.length` 可以作为“工具结果数量”展示。

`role_completed.action_results.length` 不能直接作为待确认数量。只有下面条件成立才算待确认：

```ts
action.pending_confirmation === true
```

前端已有 `pendingActionCount()`，后续不要改回简单 length 统计。

---

## 6. 后端上下文能力对应的前端设计

### 6.1 文档读取

后端支持在圆桌 start/continue 中识别 `document_read`，读取本地文本类文件并注入临时文档上下文。

支持扩展名：

- `.txt`
- `.md` / `.markdown`
- `.py`
- `.json`
- `.csv`
- `.log`
- `.yaml` / `.yml`
- `.ts` / `.tsx`
- `.js` / `.jsx`
- `.java`

前端设计建议：

- 在用户提示中允许自然语言提文件名，例如“读一下 ohmorilog5-2”。
- 如果后续后端把 `document_context.status` 显式流出，前端应支持 `attached`、`not_found`、`ambiguous`、`truncated` 四类提示。
- 在最终结果的 context 面板里可以展示“本轮使用了临时文档上下文”，但不要泄露过长全文。

### 6.2 意图识别与工具上下文

圆桌会复用私聊意图识别：

| 状态 | 后端行为 | 前端表现 |
| --- | --- | --- |
| `chat_only` | 不调用工具 | 普通讨论。 |
| `document_read` | 文档上下文注入 | 可显示文档已附加。 |
| `ask_missing_slots` | 缺槽位注入上下文 | 纪要或输入区强调“需要补充信息”。 |
| `tool_executed` | 只读/分析工具结果注入 | 可显示工具已参与判断。 |
| `pending_confirmation` | 写操作变成待确认动作 | 显示 pending action，不显示已执行。 |

特别规则：

- `jarvis_task_plan_decompose` 在私聊里可能直接生成计划；在圆桌里必须被延迟为 pending action。
- 前端文案必须用“生成待确认计划/安排”，不要写“已创建计划/已写入日程”。

---

## 7. 结果卡设计

### 7.1 Decision Result Card

适用场景：

- `schedule_coord`
- `study_energy_decision`

后端字段：

- `summary`
- `options`
- `recommended_option`
- `tradeoffs`
- `actions`
- `handoff_target`
- `context`
- `pending_action_id`
- `status`
- `handoff_status`

前端组件结构：

1. 决策摘要：1 段主结论。
2. 推荐方案：突出 `recommended_option`。
3. 备选方案：列表展示 `options`。
4. 取舍：展示每个方案的 `pros` / `cons`。
5. 后续动作：展示 `actions`，标注“需要确认”。
6. 上下文依据：从 `context.context_explanation` 或场景 context 中提取。
7. 操作区：
   - `接受决策`
   - `带回私聊继续`

接受后状态：

- 显示 `pending_action.title`。
- 显示 `direct_calendar_mutation === false`。
- 文案：“已生成待确认动作，请在待确认卡中最终确认。”

### 7.2 Brainstorm Result Card

适用场景：

- `local_lifestyle`
- `emotional_care`
- `weekend_recharge`
- `work_brainstorm`

后端字段：

- `summary`
- `themes`
- `ideas`
- `tensions`
- `followup_questions`
- `c_artifacts`
- `ranked_activities`
- `risks`
- `minimum_validation_steps`
- `save_as_memory`
- `handoff_target`
- `status`
- `handoff_status`

前端组件结构：

1. 脑暴摘要。
2. 主题列表。
3. 想法列表，保留 `source_agent`。
4. 张力/风险。
5. 追问。
6. 场景专属区域。
7. 操作区：
   - `保存为灵感`
   - `转给 Maxwell 计划`
   - `带回私聊继续`

保存后状态：

- 显示 memory id 或“已保存为灵感记忆”。
- 显示 `direct_plan_mutation === false` 和 `direct_calendar_mutation === false` 的语义。

转计划后状态：

- 显示 Maxwell pending action。
- 文案：“已生成待确认计划动作，未直接创建计划。”

---

## 8. 场景专属前端能力

### 8.1 `schedule_coord`

后端语义字段：

- `calendar_adjustment_candidates`
- `protected_blocks`
- `pending_actions`
- `round_summaries`

前端应设计：

- 今日冲突/压力摘要。
- 保护时间块列表。
- 候选调整方案。
- Maxwell 待确认动作区域。
- “接受后只生成待确认日程动作”的提示。

### 8.2 `study_energy_decision`

后端语义字段：

- `continue_or_recover_decision`
- `minimum_study_block`
- `recovery_boundary`
- `reschedule_option`

前端应设计：

- 能量门控状态。
- 最低学习块。
- 恢复边界。
- 改期选择。
- 不诊断、不制造自责压力的提示文案。

### 8.3 `local_lifestyle`

后端 C 方案产物：

- `user_constraints`
- `candidate_pool`
- `candidate_facts`
- `scorecards`
- `rejected_candidates`
- `ranked_activities`
- `plan_candidate`
- `next_routes`

前端应设计：

- 活动候选池。
- 候选事实表：地点、时间、距离、来源、缺失信息。
- 评分卡：时间适配、体力负担、恢复友好度。
- 被拒绝候选和拒绝原因。
- 排序结果。
- 计划候选：只显示“可生成待确认安排”，不要直接写日程。
- 下一轮路线：换室内、只有一小时、安排第一项。

### 8.4 `emotional_care`

后端语义字段：

- `care_summary`
- `low_barrier_actions`
- `safety_note`
- `what_to_avoid`

前端应设计：

- 轻恢复清单。
- 低门槛动作列表。
- 安全提醒区域。
- “避免做什么”区域。
- 不提供强计划按钮，不默认转 Maxwell。
- 文案不应写成医疗诊断或治疗建议。

### 8.5 `weekend_recharge`

后端语义字段：

- `weekend_rhythm`
- `activity_blocks`
- `blank_blocks`
- `energy_budget`
- `optional_pending_plan`

前端应设计：

- 周末节奏视图。
- 活动块和留白块并列展示。
- 能量预算提示。
- 至少一个留白窗口的强调。
- 可选“转待确认计划”，但不能表现为已经排满周末。

### 8.6 `work_brainstorm`

后端 C 方案产物：

- `problem_frame`
- `idea_pool`
- `clusters`
- `critique_matrix`
- `selected_concepts`
- `validation_plan`
- `minimum_validation_steps`
- `risks`
- `next_routes`

前端应设计：

- 问题框定卡。
- 想法池。
- 想法分组。
- 批判审视/风险矩阵。
- 选中概念。
- 最小验证步骤。
- 下一轮路线：继续发散、压缩范围、形成验证。

---

## 9. 历史恢复设计

圆桌会话会被持久化：

- session 记录：`scenario_id`、`scenario_name`、`participants`、`mode`、`source_session_id`、`source_agent_id`、`status`。
- turns：用户和 agent 的完整 transcript。
- result：最新 decision 或 brainstorm result。

前端恢复顺序：

1. 调 `getRoundtableTurns(sessionId)`。
2. 如果 turns 非空，先渲染历史 transcript。
3. 按模式尝试拉取 result：
   - `getRoundtableDecisionResult(sessionId)`
   - `getRoundtableBrainstormResult(sessionId)`
4. 如果 result 404，不报错，只表示还没有最终结果。
5. 设置状态为可继续输入。
6. 继续输入时仍调用 `/roundtable/continue`。

不要在恢复历史后再次调用 `/roundtable/start`，否则会重复创建/覆盖会话语义。

---

## 10. 返回私聊设计

返回私聊必须满足：

- 只有带 `source_session_id` 的圆桌才能回到原私聊。
- 后端会把圆桌总结作为 agent turn 写回来源私聊。
- 返回接口会返回：
  - `source_session_id`
  - `source_agent_id`
  - `return_turn_id`
  - `summary`
  - `result`

前端行为：

1. 用户点击“带回私聊继续”。
2. 调 `returnRoundtableToPrivateChat(sessionId, payload)`。
3. 成功后显示短提示。
4. 调用上层 `onReturnToPrivateChat(source_agent_id, source_session_id)`。
5. 如果后端返回 400，显示“这个圆桌不是从私聊发起，不能直接返回；请先保存结果或关闭圆桌。”

---

## 11. 错误与空状态

| 情况 | 前端处理 |
| --- | --- |
| start HTTP error | 显示错误状态，保留关闭按钮。 |
| continue 404 | 提示会话不存在，需要重新进入圆桌。 |
| continue 400 empty message | 输入框不发送空内容；如果后端仍返回，展示错误。 |
| result 404 | 历史恢复时静默忽略；用户主动点结果刷新时提示未生成结果。 |
| accept/save/plan 400 模式不匹配 | 显示后端错误，不切换本地状态。 |
| return 400 无来源私聊 | 提示无法返回原私聊。 |
| agent_degraded | 展示降级提示，允许后续角色继续。 |
| SSE 中断 | 标记错误，允许用户重试继续。 |

---

## 12. 视觉与交互规范

圆桌是操作型工作台，不是落地页。前端设计应保持：

- 信息密度高但层级清楚。
- 当前发言、阶段、纪要、结果、操作按钮分区明确。
- 不使用营销页式大 hero。
- 不把“讨论中”和“结果卡”混在同一个不可扫描区域。
- 不用“已完成日程修改”“已创建计划”这类越过后端边界的文案。
- 按模式区分色彩和按钮文案，但不要做成单一色系页面。
- 长文本必须可折叠或截断，完整内容放 transcript。
- 移动端优先保留：状态栏、当前发言、输入框、结果操作；阶段图和纪要可折叠。

建议页面结构：

1. 顶部状态栏：场景、模式、轮次、状态、关闭。
2. 主会议区：角色布局、当前发言、用户气泡。
3. 侧栏一：阶段协议和场景产物。
4. 侧栏二：本轮纪要和用户判断点。
5. 底部输入区：自由输入、路线按钮、发送。
6. 结果层：decision 或 brainstorm 专属卡片。
7. 历史层：完整 transcript 抽屉。

---

## 13. 文件职责建议

当前 `RoundtableStage.tsx` 已经承担过多职责。后续前端开发可以按下面方式拆，但不需要一次性大重构：

| 文件 | 职责 |
| --- | --- |
| `RoundtableStage.tsx` | 容器、状态编排、SSE 生命周期。 |
| `roundtableStageLogic.ts` | 模式映射、pending action 计数、route button 解析等纯函数。 |
| `RoundtableTranscript.tsx` | transcript 展示、当前发言展示。 |
| `RoundtableScenarioPanel.tsx` | `scenario_stage`、`scenario_state`、C artifacts 展示。 |
| `RoundtableSummaryPanel.tsx` | `round_summary`、checkpoint、下一轮提示。 |
| `RoundtableDecisionCard.tsx` | decision result UI 和 accept 操作。 |
| `RoundtableBrainstormCard.tsx` | brainstorm result UI 和 save/plan 操作。 |
| `roundtableApi.ts` | 后续可从 `jarvisApi.ts` 拆出的圆桌非 SSE service。 |

拆分原则：

- 先抽纯函数，再抽展示组件，最后抽 service。
- SSE reader 可以暂时留在容器里。
- 不要把圆桌状态写回 `AgentChatPanel.tsx`。
- `JarvisHome.tsx` 只负责打开/关闭/返回私聊，不承接圆桌内部状态机。

---

## 14. 前端验收清单

开发圆桌前端时逐项检查：

- [ ] 六个场景都能进入。
- [ ] `schedule_coord` 和 `study_energy_decision` 初始为 `decision`。
- [ ] 其它四个场景初始为 `brainstorm`。
- [ ] start SSE 能展示角色发言。
- [ ] continue SSE 能追加用户 turn 和新一轮角色发言。
- [ ] `round_summary` 能展示纪要、共识、分歧、问题。
- [ ] `user_checkpoint` 后输入区可用。
- [ ] `scenario_stage` 能更新阶段。
- [ ] `scenario_state.next_routes` 点击只填输入框。
- [ ] `role_completed.action_results` 只统计 `pending_confirmation === true`。
- [ ] `agent_degraded` 不导致白屏。
- [ ] decision result 卡能展示推荐、选项、取舍、动作。
- [ ] accept 后显示 pending action，不显示已改日程。
- [ ] brainstorm result 卡能展示主题、想法、张力、追问。
- [ ] save 后显示已保存灵感。
- [ ] plan 后显示 Maxwell pending action，不显示已创建计划。
- [ ] local_lifestyle 展示活动排序、评分或候选事实。
- [ ] work_brainstorm 展示风险和最小验证步骤。
- [ ] emotional_care 不提供高压任务化文案。
- [ ] weekend_recharge 明确展示恢复留白。
- [ ] 历史恢复不会重新 start。
- [ ] 可从有来源私聊的圆桌返回私聊。
- [ ] 无来源私聊时 return 错误被清楚展示。

---

## 15. 与接口契约的关系

本文回答“前端应该为哪些后端功能设计什么界面和交互”。接口字段、请求模型、SSE payload 的精确定义以 `roundtable-api-contract.md` 为准。

更新规则：

1. 后端新增圆桌场景、SSE 事件或 result 字段时，先更新接口契约。
2. 再更新本文对应的前端设计要求。
3. 最后更新 `RoundtableStage.tsx` 或拆分后的组件。
