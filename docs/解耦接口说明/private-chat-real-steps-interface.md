# 私聊真实执行步骤接口说明

更新时间：2026-05-02

## 1. 当前目标

私聊发送消息时，不再用前端固定文案假装进度，而是展示后端真实完成的执行步骤和真实耗时。

本次只改私聊 `/chat/stream`，不改圆桌流程。

## 2. 前端可以改什么

前端开发人员可以改这些展示文件：

- `shadowlink-web/src/components/jarvis/AgentChatPanel.tsx`

如果只是调整步骤列表样式、颜色、排版，只改这个文件即可。

## 3. 前端接口边界

前端页面不能直接 `fetch` 私聊接口。

页面只通过：

```ts
useJarvisStore((s) => s.sendMessage)
```

store 再调用：

```ts
jarvisApi.chatStream(agentId, message, sessionId, browserTimezone, {
  onStep(step) {}
})
```

接口解析位置：`shadowlink-web/src/services/jarvisApi.ts`

页面展示位置：`shadowlink-web/src/components/jarvis/AgentChatPanel.tsx`

## 4. SSE 事件

后端接口：

```http
POST /api/v1/jarvis/chat/stream
Accept: text/event-stream
```

事件顺序：

```text
chat_status
chat_step
chat_step
...
chat_result
chat_done
```

## 5. chat_step 数据结构

```ts
interface ChatExecutionStep {
  id: string
  label: string
  status: 'running' | 'done' | 'error' | string
  duration_ms?: number | null
  detail?: string | null
  metadata?: Record<string, unknown>
}
```

当前版本每个阶段会尽量发送两次：

- `status: 'running'`：这个阶段刚开始。
- `status: 'done'`：这个阶段已完成，并带上真实 `duration_ms`。

前端应按 `id` 原地合并更新同一个步骤，不要把 `running` 和 `done` 当成两条不同步骤展示。

## 6. 当前步骤来源

步骤来自后端真实 timing span：

- `route_decided`：确认负责的智能体
- `activity_marked`：记录本次用户活动
- `conversation_persisted`：保存会话入口
- `base_context`：读取基础上下文和历史对话
- `memory_context`：检索长期记忆、偏好和协作记忆
- `consult`：判断是否需要其他智能体协助
- `local_life_context`：读取本地生活上下文
- `local_intent`：判断是否需要调用工具
- `llm_turn`：生成智能体回复并执行工具
- `actions_built`：整理工具执行结果
- `background_scheduled`：安排旁路记忆和偏好学习
- `persist_final_turns`：保存最终对话记录
- `escalation_eval`：评估是否需要进入圆桌

后端实现位置：`shadowlink-ai/app/api/v1/jarvis_router.py`

## 7. 协作注意点

- 前端只展示 `label`、`duration_ms`、`detail`，不要依赖后端内部函数名做业务判断。
- 如果要新增步骤，优先后端新增 span 或扩展 `chat_step`，前端无需改接口路径。
- 如果要改文案，优先改后端 `label`，这样所有前端都一致。
- 如果要做更细的工具调用过程，可以继续按同样协议新增更细的 `id`。

## 8. 验收方法

```powershell
Push-Location shadowlink-web
npm.cmd run type-check
Pop-Location
rg "CHAT_PROGRESS_STEPS|setInterval\(" shadowlink-web/src/components/jarvis/AgentChatPanel.tsx
rg "fetch\(" shadowlink-web/src/components/jarvis/AgentChatPanel.tsx
```

预期：

- type-check 通过。
- `AgentChatPanel.tsx` 没有 `CHAT_PROGRESS_STEPS`。
- `AgentChatPanel.tsx` 没有直接 `fetch(`。
