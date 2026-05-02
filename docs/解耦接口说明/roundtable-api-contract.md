# 圆桌模块接口契约

**模块定位：** 圆桌是独立全栈包，由同一个开发者同时维护前端 `RoundtableStage.tsx` 和后端 `app/api/v1/jarvis/roundtable/`。主 Jarvis 私聊只依赖“进入圆桌”和“圆桌返回私聊”两个边界。

**后端入口：** `shadowlink-ai/app/api/v1/jarvis/roundtable/router.py`

**请求模型：** `shadowlink-ai/app/api/v1/jarvis/roundtable/schemas.py`

**前端调用：** `shadowlink-web/src/services/jarvisApi.ts` 中 roundtable 相关方法，后续可迁移为圆桌包内部 service。

**路径前缀：** 当前 FastAPI 注册后实际路径为 `/api/v1/jarvis/...`。

---

## 1. 边界规则

- 圆桌内部可以同时改前端和后端，但不要把圆桌状态机散到 `AgentChatPanel.tsx`。
- 主聊天只负责传入 `source_session_id`、`source_agent_id`、`scenario_id`、`user_input`，并接收 return 结果。
- 圆桌接口路径保持稳定，内部拆文件不要求前端改 URL。
- 圆桌产生的日程/计划/记忆写入必须通过 pending action 或明确用户点击，不直接悄悄改其它模块数据。

---

## 2. 接口清单

| 功能 | 方法 | 路径 | 前端方法 | 请求模型 | 说明 |
| --- | --- | --- | --- | --- | --- |
| 启动圆桌 | POST | `/api/v1/jarvis/roundtable/start` | `startRoundtable` | `RoundtableStartRequest` | SSE，创建圆桌会话并让多智能体发言 |
| 继续圆桌 | POST | `/api/v1/jarvis/roundtable/continue` | `continueRoundtable` | `RoundtableContinueRequest` | SSE，在已有圆桌会话中追加用户输入 |
| 获取决策结果 | GET | `/api/v1/jarvis/roundtable/{session_id}/decision-result` | `getRoundtableDecisionResult` | 无 | 获取 decision 模式最新结果 |
| 接受决策 | POST | `/api/v1/jarvis/roundtable/{session_id}/accept` | `acceptRoundtableDecision` | `RoundtableAcceptRequest` | 生成 pending action，不直接改日历 |
| 获取脑暴结果 | GET | `/api/v1/jarvis/roundtable/{session_id}/brainstorm-result` | `getRoundtableBrainstormResult` | 无 | 获取 brainstorm 模式最新结果 |
| 保存脑暴记忆 | POST | `/api/v1/jarvis/roundtable/{session_id}/save` | `saveRoundtableBrainstorm` | `RoundtableSaveRequest` | 用户点击后写入灵感记忆 |
| 脑暴转计划 | POST | `/api/v1/jarvis/roundtable/{session_id}/plan` | `convertRoundtableBrainstormToPlan` | `RoundtablePlanRequest` | 生成 Maxwell 待确认计划 |
| 返回私聊 | POST | `/api/v1/jarvis/roundtable/{session_id}/return` | `returnRoundtableToPrivateChat` | `RoundtableReturnRequest` | 把圆桌总结写回来源私聊 session |

---

## 3. 请求模型

### `RoundtableStartRequest`

```json
{
  "scenario_id": "study_energy_decision",
  "user_input": "我今天很累但还想学习",
  "session_id": "rt_xxx",
  "mode_id": "general",
  "source_session_id": "private_session_xxx",
  "source_agent_id": "mira"
}
```

字段说明：

- `scenario_id`：圆桌场景 ID。
- `user_input`：用户带入圆桌的原始诉求。
- `session_id`：前端生成或传入的圆桌 session ID。
- `mode_id`：知识库/模式 ID，默认 `general`。
- `source_session_id`：来源私聊 session，用于圆桌结束后返回。
- `source_agent_id`：来源私聊 agent，用于返回私聊时写入对应角色。

### `RoundtableContinueRequest`

```json
{
  "session_id": "rt_xxx",
  "user_message": "请直接收敛成一个建议"
}
```

### `RoundtableAcceptRequest`

```json
{
  "result_id": "rt_result_xxx",
  "note": "我选择轻量学习方案"
}
```

### `RoundtableSaveRequest`

```json
{
  "result_id": "bs_result_xxx",
  "note": "这个想法后面可以继续展开"
}
```

### `RoundtablePlanRequest`

```json
{
  "result_id": "bs_result_xxx",
  "note": "帮我转成 Maxwell 计划"
}
```

### `RoundtableReturnRequest`

```json
{
  "result_id": "rt_result_xxx",
  "user_choice": "return_to_private_chat",
  "note": "回到原私聊继续"
}
```

---

## 4. SSE 事件

`start` 和 `continue` 返回 SSE。

常见事件：

- `phase`：阶段变化，比如 session 初始化、准备上下文。
- `agent_start`：某个智能体开始发言。
- `token`：某个智能体产出完整片段或内容。
- `agent_degraded`：某个智能体失败后的降级输出。
- `decision_result`：decision 模式收敛结果。
- `brainstorm_result`：brainstorm 模式收敛结果。
- `roundtable_timing`：耗时统计。
- `done`：本轮圆桌结束。

前端要求：

- 不要假设每次都有 `decision_result` 或 `brainstorm_result`，要按场景模式判断。
- 遇到 `agent_degraded` 不要白屏，继续展示 fallback 内容。
- `done` 只代表本轮结束，不代表用户已经接受/保存/返回。

---

## 5. 响应形状摘要

### Decision result

```json
{
  "id": "rt_result_xxx",
  "session_id": "rt_xxx",
  "mode": "decision",
  "status": "draft",
  "summary": "建议先恢复精力，再做最小学习块",
  "options": [],
  "recommended_option": "轻量学习 + 恢复窗口",
  "tradeoffs": [],
  "actions": [],
  "handoff_target": "maxwell",
  "context": {}
}
```

### Brainstorm result

```json
{
  "id": "rt_result_xxx",
  "session_id": "rt_xxx",
  "mode": "brainstorm",
  "status": "draft",
  "summary": "本轮沉淀出若干方向",
  "themes": [],
  "ideas": [],
  "tensions": [],
  "followup_questions": [],
  "save_as_memory": false,
  "handoff_target": "maxwell",
  "context": {}
}
```

### Return response

```json
{
  "source_session_id": "private_session_xxx",
  "source_agent_id": "mira",
  "return_turn_id": "turn_xxx",
  "summary": "圆桌讨论总结...",
  "result": {}
}
```

---

## 6. 变更规范

- 新增字段优先做可选字段。
- 不要随意改 URL；如果必须改，先在本文档记录旧路径、新路径、兼容期。
- `start` / `continue` 的 SSE event 名称属于高风险契约，改动前必须通知前端。
- `return` 影响私聊主链路，改动前必须确认 `source_session_id` 和 `source_agent_id` 的兼容逻辑。
- 圆桌内部可以整体重构，但对外接口要稳定。

---

## 7. 圆桌业务开发人员可动文件清单

这一节用于给圆桌业务开发人员划边界：**他基本只改圆桌内部业务逻辑**。从哪里进入圆桌、圆桌结束后回到哪里、主界面如何切换，这些入口/跳转接口由你维护，不交给圆桌业务开发人员处理。

### 7.1 圆桌业务开发人员主要修改

这些文件属于圆桌内部业务逻辑，圆桌业务开发人员可以作为主要 owner：

| 文件 | 类型 | 可改内容 |
| --- | --- | --- |
| `shadowlink-ai/app/api/v1/jarvis/roundtable/schemas.py` | 后端圆桌请求模型 | 仅限圆桌内部需要的请求字段；改字段前必须同步你 |
| `shadowlink-ai/app/jarvis/roundtable_sessions.py` | 后端圆桌会话 | 圆桌 session、turn、rehydrate 相关逻辑 |
| `shadowlink-ai/app/jarvis/roundtable_graph.py` | 后端圆桌图编排 | schedule/local/emotional/weekend/work brainstorm 等图执行状态和事件 |
| `shadowlink-ai/app/jarvis/scenarios.py` | 圆桌场景配置 | 场景 ID、参与 agent、场景文案；新增/删除场景前必须同步你，因为入口会受影响 |
| `shadowlink-ai/app/jarvis/shadow_roundtable.py` | Shadow 圆桌能力 | proactive/shadow 触发的圆桌能力，不要和主 UI 入口混淆 |
| `shadowlink-ai/app/api/v1/jarvis/roundtable/service.py` | 后端圆桌业务服务 | 后续迁移圆桌业务实现的目标文件；如果不存在，由圆桌业务开发人员创建 |
| `docs/解耦接口说明/roundtable-api-contract.md` | 接口契约 | 只更新圆桌内部请求/响应/SSE 事件，不改入口归属规则 |

### 7.2 圆桌业务开发人员只能在你确认后修改

这些文件属于“圆桌和主系统的连接处”。它们不是圆桌业务开发人员的自由修改范围，必须先和你确认：

| 文件 | 为什么敏感 | 规则 |
| --- | --- | --- |
| `shadowlink-ai/app/api/v1/jarvis/roundtable/router.py` | 暴露 `/roundtable/*` HTTP 接口 | 路径、方法、SSE event 不能擅自改；业务实现可以转调 service |
| `shadowlink-ai/app/api/v1/jarvis_router.py` | 仍承接部分旧圆桌实现和其它模块大逻辑 | 只能迁出圆桌实现，不许顺手改私聊、日程、关怀、RAG |
| `shadowlink-ai/app/main.py` | 注册 router | 一般不需要圆桌业务开发人员改 |
| `shadowlink-ai/app/jarvis/persistence.py` | 跨模块数据持久化 | 改 roundtable result/session 字段前必须同步你，并兼容旧数据 |
| `shadowlink-ai/app/core/lifespan.py` | 启动恢复逻辑 | 只在 rehydrate 失效时改，且先同步你 |
| `shadowlink-web/src/components/jarvis/RoundtableStage.tsx` | 圆桌前端主界面 | 只改圆桌内部展示/交互；不要改进入来源和返回私聊策略 |
| `shadowlink-web/src/services/jarvisApi.ts` | 当前圆桌 API 方法仍在这里 | 不要顺手拆总 service；圆桌 API 迁移方案由你定 |

### 7.3 入口/跳转接口由你维护

下面这些文件控制“从哪里进入圆桌”和“圆桌回到哪里”，由你维护。圆桌业务开发人员不要主动改：

| 文件 | 你维护的内容 |
| --- | --- |
| `shadowlink-web/src/stores/jarvisStore.ts` | `startRoundtable`、`closeRoundtable`、`openPrivateChat`、`openExistingPrivateChat`、interaction mode 状态 |
| `shadowlink-web/src/components/jarvis/JarvisHome.tsx` | scenario/private_chat/roundtable 三种界面切换，RoundtableStage props，返回私聊回调 |
| `shadowlink-web/src/components/jarvis/ScenarioGrid.tsx` | 圆桌入口展示、用户从场景卡片进入圆桌 |
| `shadowlink-web/src/components/jarvis/AgentChatPanel.tsx` | 私聊中升级到圆桌的入口、escalation hint 展示 |
| `shadowlink-web/src/components/jarvis/CareTrendsPanel.tsx` | 从关怀模块进入 Mira 私聊，不归圆桌业务开发人员处理 |
| `shadowlink-web/src/components/jarvis/ConversationHistoryPanel.tsx` | 从历史会话回到私聊，不归圆桌业务开发人员处理 |

### 7.4 圆桌业务开发人员不要修改

这些模块不属于圆桌业务逻辑，除非你明确安排，否则不要在圆桌任务里改：

- `shadowlink-web/src/components/jarvis/CalendarPanel.tsx`
- `shadowlink-web/src/components/jarvis/CareCard.tsx`
- `shadowlink-web/src/components/jarvis/CareTrendsPanel.tsx`
- `shadowlink-web/src/pages/KnowledgePage.tsx`
- `shadowlink-ai/app/api/v1/rag_router.py`
- 日程/计划相关 persistence 和 planner 逻辑
- 设置页、provider、LLM 配置相关文件
- 私聊发送主流程、私聊历史、私聊 agent 路由逻辑

### 7.5 圆桌业务开发人员本轮建议交付

1. 只保证圆桌内部业务逻辑正确：多 agent 发言、收敛、decision/brainstorm result、accept/save/plan/return 的业务含义。
2. 不负责“从哪里进入圆桌”和“圆桌返回哪个私聊入口”，这些由你维护。
3. 保证 `/api/v1/jarvis/roundtable/*` 8 个接口路径不变。
4. 可以继续把 `jarvis_router.py` 中圆桌实现函数迁到 `shadowlink-ai/app/api/v1/jarvis/roundtable/service.py`，但每次只迁一组函数。
5. 迁移后跑圆桌测试：`test_roundtable_decision.py`、`test_roundtable_brainstorm.py`。
6. 每次改 SSE event 名称、请求体字段、返回字段，都先同步你并更新本文档。

---

## 8. 当前私聊入口与模块解耦现状

### 8.1 现在确实存在多个“进入私聊”的入口

目前私聊不是只有一个入口，主要有这些：

| 入口 | 位置 | 说明 | 当前状态 |
| --- | --- | --- | --- |
| 点击 agent 卡片进入私聊 | `JarvisHome.tsx` 调 `openPrivateChat(agent.id)` | 用户从左侧/首页 agent 卡片进入某个 agent 私聊 | 已通过 store 收口，但仍和 JarvisHome 强绑定 |
| 从历史会话打开私聊 | `JarvisHome.tsx` 调 `openExistingPrivateChat(agentId, sessionId)` | 从 conversation history 回到旧私聊 | 已通过 store 收口 |
| 关怀趋势打开 Mira | `CareTrendsPanel` 通过 `onOpenMira={() => openPrivateChat("mira")}` | 心机关怀模块跳转到 Mira 私聊 | 入口清楚，但关怀和私聊仍在主界面层耦合 |
| 圆桌返回私聊 | `RoundtableStage.tsx` 调 `returnRoundtableToPrivateChat` 后触发 `openExistingPrivateChat(...)` | 圆桌结束后回到来源私聊 | 已有接口和回跳，但属于圆桌/私聊边界，需保持稳定 |
| 私聊中升级到圆桌 | `AgentChatPanel.tsx` 调 `startRoundtable(scenarioId, message, { sessionId, agentId })` | 私聊识别到需要多 agent 讨论时进入圆桌 | 入口清楚，但仍在 AgentChatPanel 内部 |
| store 内部路由私聊 | `jarvisStore.ts` 的 `sendMessage` 根据后端 routed agent 改 `activeAgentId` | 后端可能把用户消息路由给其它 agent | 逻辑集中在 store，但与聊天 response 强耦合 |

结论：**私聊入口已经大多收口到 `jarvisStore.ts`，但还没有完全“入口解耦”。** 后续最好新增一个明确的 `chatNavigation` 或 `chatSession` helper/store，把“打开新私聊、打开旧私聊、从圆桌返回私聊、从关怀跳 Mira”统一成同一套入口函数。

### 8.2 各模块解耦状态判断

| 模块 | 前端解耦状态 | 后端解耦状态 | 是否已经完成 | 下一步 |
| --- | --- | --- | --- | --- |
| 圆桌 | 部分完成：主界面入口清楚，但 `RoundtableStage.tsx` 仍直接 `fetch` start/continue SSE | 部分完成：HTTP router/schema 已独立，业务实现仍在 `jarvis_router.py` | 未完全完成，但圆桌业务逻辑可由圆桌业务开发人员并行推进；入口/跳转由你维护 | 业务实现迁到 `roundtable/service.py`；start/continue 的入口收口由你决定 |
| 私聊 | 部分完成：发送走 `jarvisStore.sendMessage` + `jarvisApi.chatStream`，但入口多个且 `AgentChatPanel.tsx` 很重 | 未完成：`/chat`、`/chat/stream`、history 仍在 `jarvis_router.py` | 未完成 | 建 `chatApi/chatStore` 边界，后端拆 `chat_router.py`/`chat_pipeline.py` |
| 日程安排 | 未完成：大量逻辑仍在 `AgentChatPanel.tsx` 和 `jarvisApi.ts` 同一个大对象中 | 未完成：calendar/plans/planner/background tasks 仍在 `jarvis_router.py` | 未完成 | 先抽 `jarvisScheduleApi.ts`，再拆 `schedule_router.py` |
| 心机关怀 | 前端较好：`CareCard`、`CareTrendsPanel` 基本通过 `jarvisApi` 调用 | 未完成：`/care/*` 仍在 `jarvis_router.py` | 部分完成 | 抽 `jarvisCareApi.ts`，后端拆 `care_router.py` |
| RAG/知识库 | 未完成：`KnowledgePage.tsx` 仍直接 `fetch` `/rag/*`、`/file/upload-and-ingest` | 较好：已有 `rag_router.py`、`app/rag/*` | 后端基本解耦，前端未完成 | 新建 `ragApi.ts`，让 KnowledgePage 只调 service |
| 设置/Profile/Agent 配置 | 未完成：`SettingsProfile.tsx`、`SettingsAgents.tsx` 仍直接 `fetch` | 部分完成：settings/provider 有独立 router，但 Jarvis profile/time/agent-config 仍在 `jarvis_router.py` | 未完成 | 抽 `settingsApi.ts` 或补进现有 settings store |
| 记忆/历史 | 部分完成：多数通过 `jarvisApi` | 未完成：memories/conversation-history/sessions 仍在 `jarvis_router.py` | 未完成 | 抽 `memoryApi.ts`，后端拆 memory/history router |

### 8.3 回答“每一部分的解耦都做了吗”

没有。现在的真实状态是：

- **圆桌：接口层已初步解耦，圆桌内部业务逻辑可以并行交给圆桌业务开发人员，但入口/跳转仍由你维护，业务实现还没完全迁出。**
- **RAG：后端本来就比较独立，但前端还没解耦。**
- **关怀：前端调用相对规整，但还没从 `jarvisApi.ts` 拆文件，后端也没拆。**
- **日程：还没完成，是下一批重点。**
- **私聊：发送 API 有 service/store，但入口和 `AgentChatPanel.tsx` 仍偏重，也还没完成。**
- **设置/记忆/历史：还没完成。**

所以目前只能说：**已经具备并行开发的边界雏形，但不是每个模块都完成了解耦。** 最安全的并行方式仍然是：圆桌业务开发人员只推进圆桌内部业务逻辑；你维护入口/跳转和前端 service 解耦；后端其它 router 拆分等前端边界稳定后再推进。




