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
```

可以改：

- 圆桌内部 UI。
- 圆桌内部阶段展示。
- 圆桌内部业务交互。

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