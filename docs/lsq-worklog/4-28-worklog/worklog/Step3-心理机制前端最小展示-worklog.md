# Step 3 工作留痕：心理机制前端最小展示

日期：2026-04-28  
对应计划：`docs/lsq-worklog/4-28-worklog/4-28plan.md` 中 `Step 3：心理机制前端最小展示`  
验证文档：`docs/lsq-worklog/4-28-worklog/test/Step3-心理机制前端最小展示验证方法.md`

## 一、本 Step 目标

把 Step2 后端返回的心理关怀 actions 做成前端可见、可演示、可操作的最小卡片。

目标不是完整心理中心，而是在 Mira 私聊里形成最小体验：

```text
Mira 回复文本 + 状态记录卡 + 关怀建议卡 + 后续回访卡 + 操作按钮
```

## 二、完成内容

### 1. ChatResponse 类型补充 timing

文件：`shadowlink-web/src/services/jarvisApi.ts`

补充：

- `timing?: Record<string, unknown> | null`

原因：Step1 后端已返回 timing，前端类型需要兼容。

### 2. AgentChatPanel 增加关怀卡片状态

文件：`shadowlink-web/src/components/jarvis/AgentChatPanel.tsx`

新增：

- `CareActionState`
- `careActionStates`
- `asStringList()`
- `updateCareAction()`

### 3. 支持渲染三类心理 action

文件：`shadowlink-web/src/components/jarvis/AgentChatPanel.tsx`

新增卡片分支：

- `mood.snapshot`
- `care.intervention`
- `care.followup`

展示内容：

- 状态标题
- 风险标签：轻量记录 / 需要关怀 / 高风险
- `description`
- `mood_label`
- `support_need`
- `stress_level`
- `energy_level`
- `signals`
- `next_checkin_at`
- `proactive_message_id`

### 4. 支持用户操作按钮

按钮：

- `稍后提醒`
- `我已处理`
- `不用了`

行为：

- `稍后提醒`：当前做本地状态反馈，显示 `会稍后提醒`。
- `我已处理`：如果存在 `proactive_message_id`，调用 `jarvisApi.markProactiveMessageRead()`。
- `不用了`：如果存在 `proactive_message_id`，调用 `jarvisApi.dismissProactiveMessage()`。
- 操作后刷新 proactive messages。

### 5. 调整 actions 容器布局

文件：`shadowlink-web/src/components/jarvis/AgentChatPanel.tsx`

将 actions 容器从横向 wrap 改为纵向卡片列表：

```text
flex flex-col gap-1.5
```

原因：心理关怀是信息卡，不适合被压成小标签。

## 三、已执行验证

### 1. 静态检查

已检查：

- 新增类型不影响原 `ActionResult`。
- 关怀卡片只匹配 `mood.snapshot` / `care.intervention` / `care.followup`。
- 其他 action 仍走原渲染逻辑。

### 2. 行为检查

预期：

- Step2 返回的 actions 可以在 Mira 私聊下直接渲染。
- read/dismiss 使用现有 `jarvisApi` 方法，不新增接口。

完整前端 Demo 流程见验证文档。

## 四、影响范围

代码文件：

```text
shadowlink-web/src/services/jarvisApi.ts
shadowlink-web/src/components/jarvis/AgentChatPanel.tsx
```

文档文件：

```text
docs/lsq-worklog/4-28-worklog/test/Step3-心理机制前端最小展示验证方法.md
docs/lsq-worklog/4-28-worklog/Step3-心理机制前端最小展示-worklog.md
```

## 五、后续建议

后续可以优化：

1. 把 `signals` 映射成中文标签。
2. `稍后提醒` 接真正的 snooze/update 接口。
3. 在 proactive feed 中对 `mood_care_followup` 使用专属样式。
4. 把关怀卡片抽成独立组件，避免 AgentChatPanel 继续变大。
5. 与 Step4 圆桌 decision 联动：当用户状态中风险时，推荐是否进入圆桌协商。
