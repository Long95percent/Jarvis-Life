# 前端解耦规划与接口边界说明

**目标：** 在不打乱 demo 和现有功能的前提下，把前端从“组件直接知道接口和业务细节”整理成“页面/组件 → store/hook → service → 后端接口”的稳定结构。

**当前阶段：** 这是规划文档，先定边界和顺序，不直接改业务代码。

**核心原则：** 圆桌入口/跳转由你维护；圆桌业务开发人员只管圆桌内部业务逻辑。其它模块按前后端接口契约解耦。

---

## 1. 为什么下一步先做前端解耦

后端现在还有不少接口集中在 `jarvis_router.py`，但如果前端仍然到处直接 `fetch`、直接拼 URL、直接组 payload，那么后端一拆 router，前端会全局跟着炸。

所以正确顺序是：

1. 先固定前端 service 边界。
2. 再让页面逐步改为只调用 service/store。
3. 最后再拆后端 router/service。

这一步不是为了“代码好看”，而是为了后面多人协作时：

- 后端改接口时，前端主要改 service/type，不到处改 UI。
- 前端改 UI 时，不需要理解后端 router 细节。
- 每个模块能分配给不同人，不互相踩文件。

---

## 2. 当前前端耦合现状

### 2.1 已有基础

已有这些 service 文件：

- `shadowlink-web/src/services/api.ts`
- `shadowlink-web/src/services/jarvisApi.ts`
- `shadowlink-web/src/services/sse.ts`
- `shadowlink-web/src/services/websocket.ts`

其中 `jarvisApi.ts` 已经承担了大量 Jarvis API 门面职责，但文件已经很大，当前约 1400 行。

### 2.2 仍直接 fetch 的关键位置

当前仍有组件/页面直接 `fetch`：

| 文件 | 直连内容 | 优先级 | 处理方式 |
| --- | --- | --- | --- |
| `shadowlink-web/src/pages/KnowledgePage.tsx` | `/rag/indices`、`/file/upload-and-ingest` | 高 | 抽 `ragApi.ts` |
| `shadowlink-web/src/components/settings/SettingsProfile.tsx` | `/profile`、time/location | 中 | 抽 `jarvisSettingsApi.ts` |
| `shadowlink-web/src/components/settings/SettingsAgents.tsx` | `/agent-config`、`/shadow/profile` | 中 | 抽 `jarvisSettingsApi.ts` |
| `shadowlink-web/src/components/jarvis/DashboardCards.tsx` | `/local-life`、`/profile` | 中 | 抽 dashboard/context service 或复用 settings/context service |
| `shadowlink-web/src/components/jarvis/ScenarioGrid.tsx` | `/scenarios` | 低/圆桌入口 | 入口由你维护，暂不交给圆桌业务人员 |
| `shadowlink-web/src/components/jarvis/RoundtableStage.tsx` | start/continue SSE | 圆桌边界 | 圆桌内部展示可改，入口收口由你决定 |
| `shadowlink-web/src/stores/settings-store.ts` | settings API wrapper | 低 | 已经是 store 层 wrapper，不急着动 |
| `shadowlink-web/src/components/ambient/ModeSwitcher.tsx` | `/api/ai/system/open` | 低 | 非 Jarvis 主线，暂缓 |

### 2.3 高风险大文件

这些文件不要多人同时乱改：

| 文件 | 当前风险 | 规则 |
| --- | --- | --- |
| `shadowlink-web/src/services/jarvisApi.ts` | 类型和 API 方法太多，模块混在一起 | 只能一个人主导拆分，其他人不要同时改 |
| `shadowlink-web/src/components/jarvis/AgentChatPanel.tsx` | 私聊、日程、圆桌升级、pending action 都混在一起 | 最后拆，不要第一步就大改 |
| `shadowlink-web/src/pages/KnowledgePage.tsx` | RAG 直连 fetch，但相对独立 | 适合第一批改 |
| `shadowlink-web/src/components/settings/SettingsProfile.tsx` | 设置/时间/定位直连 fetch | 第二批改 |
| `shadowlink-web/src/components/settings/SettingsAgents.tsx` | agent config 直连 fetch | 第二批改 |

---

## 3. 目标前端结构

建议逐步形成这些 service 文件：

| 文件 | 负责模块 | 是否第一批创建 |
| --- | --- | --- |
| `shadowlink-web/src/services/jarvisChatApi.ts` | 私聊、流式、history、conversation open | 暂缓，等 AgentChatPanel 拆分前创建 |
| `shadowlink-web/src/services/jarvisScheduleApi.ts` | calendar、plans、plan-days、planner、background tasks、pending actions | 第一批创建外壳，第二批接 UI |
| `shadowlink-web/src/services/jarvisCareApi.ts` | care settings、tracking、trends、day detail、feedback、behavior events | 第一批创建外壳，第二批接 UI |
| `shadowlink-web/src/services/jarvisSettingsApi.ts` | profile、time context、browser/city location、agent-config、shadow profile | 第一批创建并接 settings 页面 |
| `shadowlink-web/src/services/jarvisMemoryApi.ts` | memories、conversation-history、sessions/turns | 暂缓 |
| `shadowlink-web/src/services/ragApi.ts` | RAG indices、upload-and-ingest、delete index、query/debug | 第一批创建并接 KnowledgePage |
| `shadowlink-web/src/services/jarvisRoundtableApi.ts` | 圆桌 accept/save/plan/return；start/continue SSE 后续看是否迁 | 由你决定，不交给圆桌业务人员擅自做 |

短期可以保留 `jarvisApi.ts` 作为兼容门面：

```text
UI 旧调用 → jarvisApi.xxx → 新模块 service
UI 新调用 → 直接调用新模块 service
```

这样可以避免一次性全项目大改。

---

## 4. 分阶段实施计划

### 阶段 A：只建 service 边界，不大改 UI

目标：先让模块边界出现，降低后面拆分风险。

要做：

1. 新建 `ragApi.ts`，迁移 RAG/知识库类型和接口。
2. 新建 `jarvisSettingsApi.ts`，迁移 profile、time/location、agent-config 相关接口。
3. 新建 `jarvisScheduleApi.ts`，先迁移类型和方法外壳，不急着改 `AgentChatPanel.tsx`。
4. 新建 `jarvisCareApi.ts`，先迁移 care 类型和方法外壳。
5. `jarvisApi.ts` 暂时保留旧导出，必要时从新 service re-export，避免旧 UI 全炸。

不做：

- 不拆 `AgentChatPanel.tsx`。
- 不拆后端 router。
- 不改圆桌入口/跳转逻辑。
- 不改页面布局和视觉样式。

验收：

- 新 service 文件存在。
- TypeScript 能找到原有类型。
- 旧 UI 行为不变。
- `jarvisApi.ts` 行数开始下降或至少出现清晰分区。

### 阶段 B：先接独立页面

目标：优先处理风险低、独立性高的页面。

顺序：

1. `KnowledgePage.tsx` 接入 `ragApi.ts`。
2. `SettingsProfile.tsx` 接入 `jarvisSettingsApi.ts`。
3. `SettingsAgents.tsx` 接入 `jarvisSettingsApi.ts`。
4. `DashboardCards.tsx` 的 `/local-life`、`/profile` 直连 fetch 收口。
5. `ScenarioGrid.tsx` 的 `/scenarios` 是否收口，由你决定，因为它属于圆桌入口维护范围。

不做：

- 不碰 `AgentChatPanel.tsx` 大拆。
- 不改圆桌业务逻辑。
- 不改后端路径。

验收：

- 上述页面不再直接出现业务 `fetch`。
- URL 只出现在 `services/*.ts`。
- 页面错误态保持原样或更清楚。

### 阶段 C：再拆 AgentChatPanel

目标：把 `AgentChatPanel.tsx` 从“巨型业务面板”降耦成私聊面板。

顺序：

1. 抽日程/计划相关 handler 到 hook 或 helper。
2. 抽 pending action 展示和确认逻辑。
3. 抽圆桌升级入口调用，但入口策略仍由你维护。
4. 私聊发送主流程最后动，只保留 `sendMessage`、history、loading、error。

不做：

- 不在同一步里改 schedule/care/rag/settings 多个模块。
- 不改后端返回结构。
- 不把圆桌业务状态机塞回 AgentChatPanel。

验收：

- `AgentChatPanel.tsx` 行数下降。
- 日程 payload 构造不再散落在聊天 UI 里。
- 私聊发送主链路保持可用。

### 阶段 D：前端稳定后再拆后端

前端 service 边界稳定后，再拆后端：

1. `chat_router.py` / `chat_pipeline.py`
2. `schedule_router.py`
3. `care_router.py`
4. `memory_router.py`
5. RAG 内部 query/ingest/indices 子路由

原则：后端拆文件不改 URL。

---

## 5. 文件所有权建议

### 5.1 你负责

你负责入口、跳转、前端解耦主线：

- `shadowlink-web/src/stores/jarvisStore.ts`
- `shadowlink-web/src/components/jarvis/JarvisHome.tsx`
- `shadowlink-web/src/components/jarvis/AgentChatPanel.tsx`
- `shadowlink-web/src/services/jarvisApi.ts`
- `shadowlink-web/src/services/ragApi.ts`
- `shadowlink-web/src/services/jarvisSettingsApi.ts`
- `shadowlink-web/src/services/jarvisScheduleApi.ts`
- `shadowlink-web/src/services/jarvisCareApi.ts`

### 5.2 圆桌业务开发人员负责

圆桌业务开发人员只负责圆桌内部业务逻辑，详见：

- `docs/解耦接口说明/roundtable-api-contract.md`

他不负责从哪里进入圆桌，也不负责圆桌返回哪个私聊入口。

### 5.3 暂时不要多人同时改

这些文件容易冲突：

- `shadowlink-web/src/services/jarvisApi.ts`
- `shadowlink-web/src/components/jarvis/AgentChatPanel.tsx`
- `shadowlink-web/src/stores/jarvisStore.ts`
- `shadowlink-ai/app/api/v1/jarvis_router.py`

如果必须多人改，先约定谁改哪一段，并且当天尽快合并。

---

## 6. 接口变更规则

前端解耦期间，接口可以改，但不能偷偷改。

每次改接口必须写清楚：

```text
模块：
接口：
改动原因：
改前：
改后：
是否破坏旧前端：是/否
兼容方案：
需要谁适配：
验证方式：
```

优先级规则：

- 新增可选字段：可以做，但要更新 type。
- 新增接口：可以做，但要写 service 方法。
- 字段改名：尽量不要；必须改时后端先同时返回新旧字段一段时间。
- 删除字段/改 URL/SSE event 改名：高风险，必须先同步。

---

## 7. 初步检测标准

前端解耦做得好不好，可以用这几个标准初筛：

1. `rg "fetch\(" shadowlink-web/src` 后，业务页面里的 fetch 数量明显减少。
2. `/calendar`、`/care`、`/rag`、`/profile`、`/agent-config` 这些路径主要出现在 `services/*.ts`。
3. `KnowledgePage.tsx` 不直接知道 `/rag/indices` 和 `/file/upload-and-ingest`。
4. `SettingsProfile.tsx` 不直接知道 `/profile`、`/time/browser-location`。
5. `AgentChatPanel.tsx` 不继续新增日程/关怀/RAG 逻辑。
6. 改一个接口字段时，主要改 service/type，不需要全局改 UI。

---

## 8. 下一步建议

建议下一步只做阶段 A + 阶段 B 的前半段：

1. 新建 `ragApi.ts`。
2. 让 `KnowledgePage.tsx` 改用 `ragApi.ts`。
3. 新建 `jarvisSettingsApi.ts`。
4. 让 `SettingsProfile.tsx` 和 `SettingsAgents.tsx` 改用 `jarvisSettingsApi.ts`。
5. 暂时不碰 `AgentChatPanel.tsx` 大拆。

这样风险最低，而且能很快看到“前端直连 fetch 变少”的效果。
