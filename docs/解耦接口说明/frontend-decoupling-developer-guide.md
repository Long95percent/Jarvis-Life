# 前端解耦接口说明与可改文件清单

本文只给前端开发人员看，目的有两个：

1. 知道前端应该通过哪些 service 调后端接口。
2. 知道自己可以改哪些文件，哪些文件改之前必须先确认。

---

## 1. 总规则

### 1.1 前端组件不要直接写接口

普通页面和组件里不要新增：

```ts
fetch('/api/...')
```

应该先使用或新增 `shadowlink-web/src/services/*.ts` 里的 service。

正确结构：

```text
组件 / 页面 → service → 后端接口
```

不要写成：

```text
组件 / 页面 → fetch('/api/...')
```

### 1.2 改接口时怎么做

如果后端接口路径、请求字段、返回字段变了：

1. 先改对应的 `shadowlink-web/src/services/*.ts`。
2. 再改使用它的组件。
3. 最后更新本文档对应接口说明。
4. 跑类型检查：

```powershell
Push-Location shadowlink-web
npm.cmd run type-check
Pop-Location
```

### 1.3 前后端同步开发期间的接口变更要求

现在前端正在并行开发，所以原则是：**能不改接口就不改接口，能新增字段就不要破坏旧字段，能新增接口就不要随意改旧接口语义。**

如果新功能确实需要改接口，必须同时在本文档写清楚：

1. **改了哪个接口**：写明后端路径，例如 `GET /api/v1/jarvis/care/trends`。
2. **前端从哪里调用**：写明 service 文件和方法，例如 `shadowlink-web/src/services/jarvisCareApi.ts` 的 `getCareTrends()`。
3. **请求字段变化**：新增、删除、改名的字段都要列出来。
4. **返回字段变化**：新增、删除、改名的字段都要列出来。
5. **兼容性说明**：旧前端还能不能用；如果不能，要说明前端必须改哪里。
6. **新功能怎么用**：给前端开发人员一个最小调用示例。
7. **相关组件**：写明哪些组件会用到这个接口。

推荐写法：

```text
接口：GET /api/v1/jarvis/xxx
前端 service：shadowlink-web/src/services/xxxApi.ts -> xxxApi.methodName()
是否破坏旧接口：否 / 是
新增字段：xxx, yyy
前端使用方式：组件只调用 service，不直接 fetch 后端路径
影响组件：xxx.tsx, yyy.tsx
```

特别注意：心理关怀、日程、RAG、圆桌这些模块如果新增接口，都要先放进对应的 `services/*Api.ts`，再让组件使用。不要在组件里临时写 `fetch('/api/...')`。

---

## 2. 当前前端 service 接口说明

### 2.1 RAG / 知识库

文件：`shadowlink-web/src/services/ragApi.ts`

使用者：`shadowlink-web/src/pages/KnowledgePage.tsx`

```ts
ragApi.listIndices(): Promise<RagIndexInfo[]>
ragApi.listSupportedFormats(): Promise<string[]>
ragApi.uploadAndIngest(file: File, modeId: string): Promise<RagIngestResult>
ragApi.deleteIndex(modeId: string): Promise<void>
```

前端开发注意：

- 知识库页面不要直接写 RAG 后端路径。
- 上传、删除、索引列表都通过 `ragApi`。

---

### 2.2 Settings / Profile / Time / Agent 配置

文件：`shadowlink-web/src/services/jarvisSettingsApi.ts`

使用者：

- `shadowlink-web/src/components/settings/SettingsProfile.tsx`
- `shadowlink-web/src/components/settings/SettingsAgents.tsx`
- `shadowlink-web/src/components/jarvis/DashboardCards.tsx`

```ts
jarvisSettingsApi.getProfile(): Promise<UserProfile>
jarvisSettingsApi.updateProfile(profile: UserProfile): Promise<UserProfile>
jarvisSettingsApi.getTimeContext(browserTimezone?: string): Promise<JarvisTimeContext>
jarvisSettingsApi.resolveBrowserLocation(payload: BrowserLocationPayload): Promise<LocationSuggestion>
jarvisSettingsApi.resolveCityLocation(payload: CityLocationPayload): Promise<LocationSuggestion>
jarvisSettingsApi.getAgentConfig(): Promise<AgentConfigResponse>
jarvisSettingsApi.updateAgentConfig(agentId: string, patch: Partial<AgentCfg>): Promise<void>
jarvisSettingsApi.getShadowProfile(): Promise<ShadowProfile | null>
jarvisSettingsApi.toggleShadowLearner(enabled: boolean): Promise<AgentConfigResponse>
```

前端开发注意：

- Profile、定位、时间、Agent 开关都走 `jarvisSettingsApi`。
- 页面里不要直接请求 `/profile`、`/time/*`、`/agent-config/*`。

---

### 2.3 Schedule / 日程 / Planner

文件：`shadowlink-web/src/services/jarvisScheduleApi.ts`

使用者：

- `shadowlink-web/src/components/jarvis/CalendarPanel.tsx`
- `shadowlink-web/src/components/jarvis/DashboardCards.tsx`
- `shadowlink-web/src/components/jarvis/AgentChatPanel.tsx`
- `shadowlink-web/src/stores/jarvisStore.ts`

常用接口：

```ts
jarvisScheduleApi.getLocalLife(force?: boolean): Promise<any>
jarvisScheduleApi.listCalendarEvents(hoursAhead?: number, range?: { start: string; end: string }): Promise<CalendarEvent[]>
jarvisScheduleApi.addCalendarEvent(payload: CalendarEventPayload)
jarvisScheduleApi.deleteCalendarEvent(eventId: string): Promise<void>
jarvisScheduleApi.updateCalendarEvent(eventId: string, patch: CalendarEventPatch)

jarvisScheduleApi.getPlannerCalendar(range: { start: string; end: string })
jarvisScheduleApi.listPlannerTasks(params?)
jarvisScheduleApi.listPlans(status?)
jarvisScheduleApi.createPlan(payload)
jarvisScheduleApi.updatePlan(planId, payload)
jarvisScheduleApi.cancelPlan(planId)
jarvisScheduleApi.deletePlan(planId)
jarvisScheduleApi.listPlanDays(params?)
jarvisScheduleApi.updatePlanDay(dayId, payload)
jarvisScheduleApi.movePlanDay(dayId, payload)
jarvisScheduleApi.bulkUpdatePlanDays(payload)
jarvisScheduleApi.listBackgroundTasks(status?)
jarvisScheduleApi.listBackgroundTaskDays(params?)
jarvisScheduleApi.listMaxwellWorkbenchItems(params?)
jarvisScheduleApi.pushDailyTasksToMaxwellWorkbench(planDate?)
```

前端开发注意：

- 日程、计划、后台任务、Maxwell 工作台都走 `jarvisScheduleApi`。
- `CalendarPanel.tsx` 可以改 UI，但不要把 API 路径写回组件里。
- `CalendarPanel.tsx` 只做日程投影和用户显式编辑入口，不再展示“冲突处理 / Free window”区域；冲突判断和重排决策交给 Maxwell 后端工具链处理。
- `getPlannerCalendar()` 后端仍可能返回 `conflicts` / `free_windows`，这是给后端/智能体/兼容接口保留的数据，普通前端不要自行展示或处理冲突。

#### Maxwell 秘书日程编辑 skill（2026-05-03）

用途：让 Maxwell/Alfred 在聊天中接管日程查询、修改、删除，支持大范围甚至全量查询后再按 `event_id` 精确执行。

后端工具：`jarvis_schedule_editor`

所在文件：

- `shadowlink-ai/app/tools/jarvis_tools.py`
- `shadowlink-ai/app/core/lifespan.py`
- `shadowlink-ai/app/jarvis/agents.py`

前端是否新增接口：否。

前端接入方式：

- 用户仍然通过 `AgentChatPanel.tsx` 的聊天接口和 Maxwell/Alfred 对话。
- 前端不要直接调用 `jarvis_schedule_editor`，也不要直接写新的日程数据库接口。
- 这个 skill 是后端 Tool Runtime 给智能体用的外部工具 API，前端只展示聊天回复和 `actions` 结果。

工具能力：

```json
{
  "operation": "query | update | delete",
  "scope": "upcoming | range | all",
  "hours_ahead": 720,
  "start": "2026-05-01T00:00:00+08:00",
  "end": "2026-06-01T00:00:00+08:00",
  "keyword": "阅读",
  "status": "confirmed",
  "limit": 200,
  "event_ids": ["event_id_1"],
  "patches": [
    {
      "event_id": "event_id_1",
      "title": "新的标题",
      "start": "2026-05-18T10:00:00+08:00",
      "end": "2026-05-18T11:00:00+08:00",
      "location": "图书馆",
      "notes": "由 Maxwell 批量调整",
      "status": "confirmed",
      "stress_weight": 1.0,
      "route_required": false
    }
  ]
}
```

返回结果：

- `query` 返回 `matched_count`、`returned_count`、压缩后的 `events`。
- `update` 返回 `updated_count`、`updated_events`、`skipped`、`new_schedule_density`。
- `delete` 返回 `deleted_count`、`deleted_event_ids`、`skipped`、`new_schedule_density`。

解耦边界：

- 前端组件不能直连这个 skill，也不能绕过 `jarvisScheduleApi` 改普通日程接口。
- Maxwell 修改/删除日程必须经 Tool Runtime 调 `jarvis_schedule_editor` 或现有 `jarvis_calendar_*` 工具。
- 用户聊天里明确要求执行时，后端 skill 可以直接修改，不再走前端确认弹窗。
- 如果后续要把这个能力做成按钮或面板，必须先在 `jarvisScheduleApi.ts` 增加 service 方法，再由组件调用 service。

#### Maxwell 工作台新增返回字段（2026-05-03）

接口：`GET /api/v1/jarvis/maxwell/workbench-items`

前端 service：`shadowlink-web/src/services/jarvisScheduleApi.ts` -> `jarvisScheduleApi.listMaxwellWorkbenchItems()`

是否破坏旧接口：否。只是给每个 `MaxwellWorkbenchItem` 新增可选字段，旧前端不使用这些字段也能继续运行。

新增字段：

```ts
work_logs?: Array<{
  at: string
  actor: string
  event: string
  detail?: string | null
  category?: 'daily_push' | 'auto_maintenance' | 'user_reschedule' | 'secretary_reschedule' | 'manual_edit' | string
  source?: 'routine' | 'planner_daily_maintenance' | 'user_action' | 'maxwell_skill' | 'schedule_api' | string
}>

live_state?: {
  source_status?: string | null
  source_title?: string | null
  workbench_status?: string | null
  is_completed: boolean
  is_cancelled: boolean
  is_overdue: boolean
  minutes_until_due?: number | null
  basis: 'jarvis_plan_days' | 'background_task_days' | 'workbench_only' | string
  checked_at: string
}
```

字段含义：

- `work_logs`：后端真实记录的 Maxwell 工作过程，例如“接收今日执行项”“完成延期重排”“逾期后自动重排”“移动到新时间”。前端只负责展示，不要自己编造日志。
- `work_logs.category`：可选分类，方便区分 `daily_push`（今日推送）、`auto_maintenance`（固定维护自动整理）、`user_reschedule`（用户点击延后）、`secretary_reschedule`（秘书 skill 重排）、`manual_edit`（日程接口手动编辑）。旧前端不使用也不影响。
- `work_logs.source`：可选来源，说明日志由 `routine`、`planner_daily_maintenance`、`user_action`、`maxwell_skill`、`schedule_api` 等哪条链路写入。
- `live_state`：后端实时查询关联任务得到的状态。前端展示“仍未完成 / 已超时 / 已完成”等文案时，必须依据这个字段，不要只靠前端时间判断。
- `live_state.basis`：说明实时状态来自哪里，可能是 `jarvis_plan_days`、`background_task_days` 或仅工作台自身记录。

前端使用方式：

```ts
const items = await jarvisScheduleApi.listMaxwellWorkbenchItems({ limit: 200 })
for (const item of items) {
  if (item.live_state?.is_overdue && !item.live_state.is_completed) {
    // 可以展示“已超时仍未完成”
  }
  // item.work_logs 可以渲染为 Maxwell 工作记录时间线
}
```

影响组件：

- `shadowlink-web/src/components/jarvis/CalendarPanel.tsx`：Maxwell 工作台卡片会展示实时状态和工作记录。

注意：如果后续还要新增“更新工作台状态”“追加工作台日志”等写接口，必须继续写在 `jarvisScheduleApi`，不要让组件直接 `fetch('/api/v1/jarvis/maxwell/...')`。

#### Maxwell 单任务重排接口（2026-05-03）

接口：`POST /api/v1/jarvis/maxwell/reschedule-task`

前端 service：`shadowlink-web/src/services/jarvisApi.ts` -> `jarvisScheduleApi.requestMaxwellReschedule()`

用途：用户在日/周/月视图点开某个任务后，点击“延后一天”时使用。前端只表达“把这个条目交给 Maxwell 重排”，不自己计算新日期。

请求体：

```ts
{
  item_type: 'plan_day' | 'background_task_day' | string
  item_id: string
  action?: 'postpone_one_day' | string
  reason?: string | null
  today?: string | null
}
```

响应体：

```ts
{
  item_type: string
  action: string
  changed: unknown
  message: string
  work_logs?: Array<{
    at: string
    actor: string
    event: string
    detail?: string | null
  }>
  pressure_review?: {
    reviewed_by?: string
    consulted_roles?: string[]
    level?: string
    summary?: string
  }
  warnings?: string[]
}
```

前端使用规则：

- `CalendarPanel.tsx` 里只能调用 `jarvisScheduleApi.requestMaxwellReschedule()`，不能直接写 `fetch('/api/v1/jarvis/maxwell/reschedule-task')`。
- 这类重排只用于 `plan_day` 和 `background_task_day`，不处理外部 `calendar_event`。
- `message` 用于提示结果；`work_logs` 用于显示 Maxwell 的真实操作记录；`pressure_review` 用于展示 Maxell 对压力/负载的简要判断。
- 如果后续要扩展“改成具体某天某时”或“重排整组长期任务”，仍然沿用这个接口，后端通过 `action` 扩展，不要再单独在组件里拼 URL。

---

### 2.4 Care / 心理关怀

文件：`shadowlink-web/src/services/jarvisCareApi.ts`

使用者：

- `shadowlink-web/src/components/jarvis/CareCard.tsx`
- `shadowlink-web/src/components/jarvis/CareTrendsPanel.tsx`
- `shadowlink-web/src/components/jarvis/AgentChatPanel.tsx`

```ts
jarvisCareApi.getCareSettings(): Promise<{ psychological_tracking_enabled: boolean }>
jarvisCareApi.setPsychologicalTracking(enabled: boolean): Promise<{ psychological_tracking_enabled: boolean }>
jarvisCareApi.clearCareData(): Promise<{ deleted: Record<string, number> }>
jarvisCareApi.getCareTrends(params?: { range?: 'week' | 'month' | 'year'; end?: string }): Promise<CareTrendsResponse>
jarvisCareApi.getCareDayDetail(day: string): Promise<CareTrendDetail>
jarvisCareApi.sendCareFeedback(id: string, payload: CareFeedbackPayload)
```

前端开发注意：

- 关怀趋势、关怀设置、关怀反馈都走 `jarvisCareApi`。
- 不要在关怀组件里直接写 `/care/*` 路径。

---

### 2.5 Scenario / 场景入口

文件：`shadowlink-web/src/services/jarvisScenarioApi.ts`

使用者：`shadowlink-web/src/components/jarvis/ScenarioGrid.tsx`

```ts
jarvisScenarioApi.listScenarios(): Promise<Scenario[]>
```

前端开发注意：

- `ScenarioGrid.tsx` 只负责展示场景和触发进入。
- 不要擅自改启动圆桌的参数和入口逻辑。

---

### 2.6 Memory / 长期记忆

文件：`shadowlink-web/src/services/jarvisMemoryApi.ts`

使用者：`shadowlink-web/src/components/jarvis/MemoryPanel.tsx`

```ts
jarvisMemoryApi.listMemories(params?: { memoryKind?: string; limit?: number }): Promise<JarvisMemory[]>
jarvisMemoryApi.deleteMemory(memoryId: number): Promise<void>
```

前端开发注意：

- 记忆列表和删除都走 `jarvisMemoryApi`。

---

### 2.7 Conversation History / 历史对话

文件：`shadowlink-web/src/services/jarvisConversationApi.ts`

使用者：

- `shadowlink-web/src/components/jarvis/ConversationHistoryPanel.tsx`
- `shadowlink-web/src/components/jarvis/AgentChatPanel.tsx`
- `shadowlink-web/src/stores/jarvisStore.ts`

```ts
jarvisConversationApi.listConversationHistory(limit?: number): Promise<ConversationHistoryItem[]>
jarvisConversationApi.deleteConversationHistory(conversationId: string): Promise<void>
jarvisConversationApi.saveConversationHistory(payload): Promise<ConversationHistoryItem>
jarvisConversationApi.openConversationHistory(conversationId: string): Promise<ConversationHistoryItem>
```

前端开发注意：

- 历史对话列表、删除、保存、打开都走 `jarvisConversationApi`。
- 打开历史对话后的具体跳转仍由 `jarvisStore.ts` 管。

---

### 2.8 Pending Action / 待确认动作

文件：`shadowlink-web/src/services/jarvisPendingActionApi.ts`

使用者：`shadowlink-web/src/components/jarvis/AgentChatPanel.tsx`

```ts
jarvisPendingActionApi.listPendingActions(status?: string): Promise<PendingAction[]>
jarvisPendingActionApi.updatePendingAction(pendingId: string, payload: PendingActionPatch): Promise<PendingAction>
jarvisPendingActionApi.confirmPendingAction(pendingId: string, payload?: PendingActionPatch): Promise<ConfirmPendingActionResult>
jarvisPendingActionApi.cancelPendingAction(pendingId: string): Promise<PendingAction>
```

前端开发注意：

- 私聊里的确认日程、确认后台任务、取消动作都走 `jarvisPendingActionApi`。

---

### 2.9 Roundtable / 圆桌 SSE

文件：

- `shadowlink-web/src/components/jarvis/RoundtableStage.tsx`
- `shadowlink-web/src/components/jarvis/roundtableStageLogic.ts`
- `shadowlink-web/src/services/jarvisApi.ts`

前端开发注意：

- 圆桌 start / continue 目前仍在 `RoundtableStage.tsx` 内直接消费 SSE；这是圆桌模块边界内的例外，不要扩散到普通组件。
- 圆桌前端界面和功能逻辑的完整设计要求见 `docs/解耦接口说明/roundtable-frontend-design-guide.md`；这里不重复维护场景级 UI 细节。
- 场景模式必须和后端一致：`schedule_coord`、`study_energy_decision` 是 decision，其余预设圆桌是 brainstorm。
- `role_completed.action_results` 不是纯待确认数组；只有 `pending_confirmation === true` 的 action 才能显示为待确认数量。
- `scenario_state.next_routes` 是后端给出的下一轮建议路线，前端可以渲染为按钮；点击按钮只把 `prompt` 填进输入框，由用户再发送 continue。
- 圆桌相关纯展示/解析逻辑优先放到 `roundtableStageLogic.ts`，避免把 `RoundtableStage.tsx` 继续堆大。

---

## 3. 前端开发人员可以改什么

### 3.1 可以直接改的 UI 文件

这些文件主要是 UI 展示或已经完成 service 解耦，前端开发人员可以改：

| 模块 | 文件 |
| --- | --- |
| Agent 卡片 | `shadowlink-web/src/components/jarvis/AgentCard.tsx` |
| 顶部栏 | `shadowlink-web/src/components/jarvis/JarvisTopBar.tsx` |
| Dashboard 卡片 | `shadowlink-web/src/components/jarvis/DashboardCards.tsx` |
| 场景入口 | `shadowlink-web/src/components/jarvis/ScenarioGrid.tsx` |
| 长期记忆面板 | `shadowlink-web/src/components/jarvis/MemoryPanel.tsx` |
| 历史对话面板 | `shadowlink-web/src/components/jarvis/ConversationHistoryPanel.tsx` |
| 关怀卡片 | `shadowlink-web/src/components/jarvis/CareCard.tsx` |
| 关怀趋势 | `shadowlink-web/src/components/jarvis/CareTrendsPanel.tsx` |
| 主动消息列表 | `shadowlink-web/src/components/jarvis/ProactiveMessageFeed.tsx` |
| 设置 Profile | `shadowlink-web/src/components/settings/SettingsProfile.tsx` |
| 设置 Agents | `shadowlink-web/src/components/settings/SettingsAgents.tsx` |
| RAG 页面 | `shadowlink-web/src/pages/KnowledgePage.tsx` |

可以做：

- 改布局。
- 改样式。
- 改文案。
- 改空状态展示。
- 改卡片排列。
- 改按钮视觉。

不应该做：

- 新增直接 `fetch('/api/...')`。
- 擅自改后端接口字段。
- 改入口跳转逻辑。

---

### 3.2 可以改，但需要小心的文件

这些文件可以改 UI，但改之前最好说清楚改动范围：

| 文件 | 为什么要小心 |
| --- | --- |
| `shadowlink-web/src/components/jarvis/JarvisHome.tsx` | 控制私聊、圆桌、日历等入口切换 |
| `shadowlink-web/src/components/jarvis/AgentChatPanel.tsx` | 私聊主链路，里面还有发送流、行为埋点、局部状态 |
| `shadowlink-web/src/components/jarvis/CalendarPanel.tsx` | 日程大面板，状态和交互很多 |
| `shadowlink-web/src/components/jarvis/RoundtableStage.tsx` | 圆桌内部业务，和 SSE 流式事件有关 |
| `shadowlink-web/src/components/jarvis/roundtableStageLogic.ts` | 圆桌前端纯逻辑 helper，影响场景模式、pending 计数、next_routes 展示 |

可以做：

- 改 className。
- 改布局结构。
- 改视觉层级。
- 改局部展示文案。

不要做：

- 改 `startRoundtable`、`closeRoundtable`、`openConversation` 这类入口逻辑。
- 改聊天发送流程。
- 改 pending action 确认逻辑。
- 改圆桌 SSE 事件解析。
- 改日程保存逻辑。

---

### 3.3 不建议普通前端开发人员直接改的文件

这些文件属于全局状态、接口边界或基础设施，改之前必须确认：

| 文件 | 原因 |
| --- | --- |
| `shadowlink-web/src/stores/jarvisStore.ts` | 全局状态、私聊/圆桌/历史对话入口都在这里 |
| `shadowlink-web/src/services/jarvisApi.ts` | 旧兼容大门面，影响范围大 |
| `shadowlink-web/src/services/api.ts` | 通用 API 基础设施 |
| `shadowlink-web/src/services/sse.ts` | SSE 流式通信基础设施 |
| `shadowlink-web/src/services/websocket.ts` | WebSocket 基础设施 |
| 后端 Python 文件 | 纯前端任务一般不应该动后端 |

---

## 4. 前端重新排版怎么做

### 4.1 如果只是重新排版

通常只需要改这些：

```text
shadowlink-web/src/components/**/*.tsx
shadowlink-web/src/pages/**/*.tsx
```

重点文件：

```text
JarvisHome.tsx
JarvisTopBar.tsx
DashboardCards.tsx
AgentCard.tsx
AgentChatPanel.tsx
CalendarPanel.tsx
MemoryPanel.tsx
ConversationHistoryPanel.tsx
CareCard.tsx
CareTrendsPanel.tsx
ScenarioGrid.tsx
SettingsProfile.tsx
SettingsAgents.tsx
KnowledgePage.tsx
```

一般不需要改：

```text
shadowlink-web/src/services/*.ts
shadowlink-web/src/stores/jarvisStore.ts
后端 Python 文件
```

### 4.2 推荐排版顺序

1. 先改 `JarvisHome.tsx`，确定整体布局。
2. 再改 `JarvisTopBar.tsx`、`DashboardCards.tsx`、`AgentCard.tsx`。
3. 再改 `MemoryPanel.tsx`、`ConversationHistoryPanel.tsx`、`CareCard.tsx`、`CareTrendsPanel.tsx`。
4. 最后改 `AgentChatPanel.tsx` 和 `CalendarPanel.tsx`。
5. 圆桌 `RoundtableStage.tsx` 单独一轮改，不要和主界面混在一起。

### 4.3 排版时不要做的事

- 不要新增直接 `fetch`。
- 不要改 service 接口。
- 不要改 store 状态流。
- 不要改后端字段。
- 不要把 UI 排版和业务逻辑重构放在同一次改动里。

---

## 5. 圆桌模块边界

圆桌比较特殊。

### 5.1 圆桌开发人员可以改

```text
shadowlink-web/src/components/jarvis/RoundtableStage.tsx
shadowlink-web/src/components/jarvis/roundtableStageLogic.ts
```

可以改：

- 圆桌内部 UI。
- 圆桌内部阶段展示。
- 圆桌内部业务交互。
- 圆桌 SSE payload 的纯解析和展示 helper。

### 5.2 圆桌开发人员不要改

```text
shadowlink-web/src/components/jarvis/JarvisHome.tsx
shadowlink-web/src/stores/jarvisStore.ts
shadowlink-web/src/components/jarvis/AgentChatPanel.tsx
```

不要改：

- 从私聊怎么进入圆桌。
- 圆桌怎么返回私聊。
- 历史对话怎么打开圆桌。
- 主界面怎么切换圆桌/私聊。

圆桌现在的后端行为边界是：

- `start` / `continue` 会先复用共享意图识别，再把只读工具结果或缺槽信息注入圆桌上下文。
- 六个预设圆桌场景的角色回合都经过共享 agent-turn 入口；Jarvis 角色可按自己的工具白名单动态判断是否用工具。
- 六个预设圆桌场景会读取后端内部 `ScenarioProtocol`，因此每个场景现在有自己的阶段顺序和结果契约；这不要求前端新增请求字段。
- `work_brainstorm` 和 `local_lifestyle` 现在会额外发 `scenario_stage` / `scenario_state`，前端可以在结果卡和完整记录里展示它们的专属中间产物。
- `scenario_state.next_routes` 可以展示为下一轮路线按钮；按钮只能把后端 prompt 填进输入框，不能替用户直接执行。
- 当前 `RoundtableStage.tsx` 已支持这些增强字段：进行中展示当前阶段和阶段轨迹；结果卡展示协议阶段；本地生活展示 `ranked_activities`；工作脑暴展示 `risks` / `minimum_validation_steps`；完整记录里展示每个角色的工具数量和 pending confirmation 数量。
- `crossfire` 当前是轻量交叉质询阶段，表现为角色 prompt 约束和 final result 上下文追踪，不是新的必处理 SSE event。
- 写操作仍只生成待确认动作，不直接改日历、计划或关怀数据；`jarvis_task_plan_decompose` 在圆桌中也按待确认动作处理，不能直接生成计划或日历投射。
- 前端如果以后接圆桌的增强事件，也要按这个确认链路理解，不要把圆桌当成直接执行层。

圆桌接口单独看：

```text
docs/解耦接口说明/roundtable-api-contract.md
```

---

## 6. 每次改完怎么验收

### 6.1 必跑

```powershell
Push-Location shadowlink-web
npm.cmd run type-check
Pop-Location
```

### 6.2 如果改了接口或 service，再跑

```powershell
rg "fetch\(" shadowlink-web/src/components shadowlink-web/src/pages -n --glob "*.tsx"
```

期望：

- 普通页面/组件不要出现新的业务直连 `fetch`。
- 圆桌内部 `RoundtableStage.tsx` 例外，按圆桌边界单独处理。

---

## 7. 现在前端解耦状态

已经完成 service 解耦的模块：

- RAG / 知识库
- Settings / Profile / Time / Agent 配置
- Schedule / 日程 / Planner
- Care / 心理关怀
- Scenario / 场景入口
- Memory / 长期记忆
- Conversation History / 历史对话
- Pending Action / 待确认动作

当前可以并行开发。

建议：

- 前端排版人员主要改组件文件。
- 接口开发人员主要改 service 文件。
- 圆桌开发人员主要改 `RoundtableStage.tsx` 内部。
- 主维护者负责 `JarvisHome.tsx`、`jarvisStore.ts`、入口跳转和跨模块状态。

### 私聊真实执行步骤说明

如果你要看私聊智能体如何展示真实执行步骤、如何理解角色边界 + 引擎能力，请优先看：

```text
docs/解耦接口说明/private-chat-real-steps-interface.md
```

这个文档说明：

- 角色边界不变
- 引擎只是执行层增强
- 前端如何展示 `strategy`、`steps`、`tool_results`、`retry_count`
- 缺参写操作如何自动补参并继续执行
---

## 8. 防止中文乱码的要求

前端文件里有大量中文文案，开发时必须特别注意编码问题。之前出现过乱码，原因是用 PowerShell 管道或 `Set-Content` 写入文件时，编码处理不一致，导致 UTF-8 中文被错误保存。

### 8.1 必须使用 UTF-8

所有前端源码、文档、接口说明都统一使用 UTF-8 编码。

包括：

- `.tsx`
- `.ts`
- `.md`
- `.json`

保存文件时确认编辑器右下角显示：

```text
UTF-8
```

如果不是 UTF-8，先切换编码再保存。

### 8.2 推荐修改文件的方法

推荐用以下方式修改文件：

1. 用 VS Code / Cursor / WebStorm 直接编辑并保存。
2. 用 `apply_patch` 做小范围补丁。
3. 如果必须用脚本写文件，使用 Python，并显式指定：

```python
from pathlib import Path

path = Path('目标文件路径')
path.write_text(content, encoding='utf-8', newline='\n')
```

### 8.3 不推荐的方法

不要用这些方式批量写包含中文的文件：

```powershell
Get-Content file | Set-Content file
Add-Content file "中文内容"
"中文内容" > file
```

这些命令在不同 PowerShell 版本、终端编码、系统区域设置下，可能把中文写坏。

如果必须用 PowerShell 写文件，必须显式指定 UTF-8：

```powershell
Set-Content -Path "目标文件" -Value $content -Encoding utf8
Add-Content -Path "目标文件" -Value $content -Encoding utf8
```

但即使这样，也优先推荐用编辑器或 Python。

### 8.4 修改后如何检查是否乱码

改完包含中文的文件后，至少检查一次：

```powershell
rg "�|馃|鈥|閿|锛|涓|鏃|绋|鍦|姝|浣|缁|鐨|濞|瀹|婧|褰|銆|����" shadowlink-web/src docs -n
```

如果出现这些字符，要先确认是不是正常内容。大多数情况下，它们代表乱码。

也要跑类型检查：

```powershell
Push-Location shadowlink-web
npm.cmd run type-check
Pop-Location
```

注意：类型检查通过不代表没有乱码。乱码可能只是文案坏了，不一定导致 TypeScript 报错。

### 8.5 发现乱码后怎么处理

如果发现某个文件乱码：

1. 不要继续在乱码文件上改。
2. 先用 Git 对比正常版本：

```powershell
git diff -- 文件路径
```

3. 如果乱码来自本次改动，优先从 Git 正常版本恢复该文件，再重新用 UTF-8 方法套回必要改动。
4. 修复后重新检查乱码字符和类型检查。

---
