# Jarvis 私聊对话 Pipeline 说明

更新时间：2026-04-25 16:05（Asia/Shanghai）

本文档说明 Jarvis 私聊（例如用户和 Maxwell 对话）从前端点击发送到后端调用 LLM、工具解析、日程卡片返回、错误透传的完整执行逻辑。目标是：任何失败都必须返回具体阶段和原因，不允许只返回固定的“没跑通”或“Internal server error”。

## 1. 总体调用链

1. 前端组件 `shadowlink-web/src/components/jarvis/AgentChatPanel.tsx`
   - 用户输入消息并点击发送。
   - `handleSend()` 调用 Zustand store 的 `sendMessage(agentId, message, sessionId)`。

2. 前端状态层 `shadowlink-web/src/stores/jarvisStore.ts`
   - 先把用户消息追加到 `chatHistory[agentId]`。
   - 调用 `jarvisApi.chat(agentId, message, sessionId)`。
   - 成功：追加 Agent 回复与 `actions`。
   - 失败：直接把后端返回的具体错误消息追加到聊天，不再拼固定“对话暂时没有跑通”。

3. 前端 API 层 `shadowlink-web/src/services/jarvisApi.ts`
   - POST `/api/v1/jarvis/chat`。
   - 请求体：`{ agent_id, message, session_id }`。
   - 如果 HTTP 非 2xx：优先读取 `detail.message`、`detail.suggestion`、`detail.stage`，再退回 `detail`、`message`、`error`。

4. Java Gateway `shadowlink-server/shadowlink-gateway/.../JarvisProxyController.java`
   - `/api/v1/jarvis/chat` 命中 REST catch-all。
   - 原样转发 method/path/query/body 到 Python AI 服务。
   - Python 返回非 2xx 时，保留 status、headers、body 透传给前端。

5. Python FastAPI `shadowlink-ai/app/api/v1/jarvis_router.py`
   - 路由：`POST /api/v1/jarvis/chat`。
   - 函数：`chat_with_agent(req, llm_client=Depends(get_llm_client))`。
   - 负责组装上下文 prompt、调用 Agent runtime、保存 pending action、返回结构化响应。

6. Agent 工具 runtime `shadowlink-ai/app/jarvis/tool_runtime.py`
   - 函数：`run_agent_turn()`。
   - 第一次 LLM 调用拿到初稿。
   - 解析 `<jarvis-tool>`、`<jarvis-action>`、兼容误输出的 `<execute_bash>`。
   - 执行工具或生成待确认 action。
   - 第二次 LLM 调用生成用户可见自然语言回复。
   - 清理最终回复中残留的工具标签。

7. LLM provider `shadowlink-ai/app/llm/client.py` 与 `shadowlink-ai/app/llm/providers/openai.py`
   - `LLMClient.chat()` 选择 OpenAI-compatible provider。
   - `OpenAIProvider.chat()` 请求 `{base_url}/chat/completions`。
   - HTTP 错误会被转换成可读 `RuntimeError`，包含 HTTP 状态码、URL 和 provider 返回的错误消息。

## 2. Python chat_with_agent 执行阶段

### 2.1 agent_lookup

文件：`shadowlink-ai/app/api/v1/jarvis_router.py`

逻辑：
- `get_agent(req.agent_id)` 从 `JARVIS_AGENTS` 中读取角色配置。
- 如果不存在，返回 404：`Agent '<id>' not found`。

### 2.2 prepare_context

如果这里失败，后端返回：

```json
{
  "detail": {
    "message": "Jarvis 对话失败：阶段=prepare_context；原因=...",
    "stage": "prepare_context",
    "agent_id": "maxwell",
    "error_type": "...",
    "error": "...",
    "suggestion": "...",
    "llm": { "base_url": "...", "model": "...", "has_api_key": true }
  }
}
```

准备内容：
- 用户设置：`build_profile_prefix()`。
- Life context：`get_life_context_bus().get_context()`。
- 最近私聊历史：`get_chat_history(req.agent_id, limit=12)`。
- 协作记忆：`build_collaboration_memory_prefix(req.agent_id, limit=6)`。
- 当前本地时间：优先 `ZoneInfo("Asia/Shanghai")`，失败时回退 UTC+08:00。
- 用户位置标签：`get_settings().profile.location.label`。

### 2.3 prompt assembly

最终发给 runtime 的 `full_message` 结构：

```text
{profile_prefix}
[Life context: stress=.../10, schedule_density=.../10, sleep=.../10, mood=...]

## 当前时间
本地参考时间: YYYY-MM-DD HH:mm:ss CST/UTC+08:00
用户位置标签: ...
制定今天/明天/几点到几点的计划时，必须参考这个当前时间；不要安排已经过去的时间段。

## 交互规则
如需读取最新信息或执行操作，请优先使用你的专属工具包。
涉及日程或生活状态的写操作，只能在用户明确要求执行时提出工具调用。
日程新增、修改、删除、完成标记会先生成待确认卡片，用户确认后才会真正写入。
用户要求规划日程时，应尽量根据当前时间给出开始和结束时间；如果用户没有给时间，请由你先做合理规划，不要强迫用户提供严格格式。
如果不需要工具，直接回答。

{collaboration_text}
{history_text}
User: {req.message}
```

### 2.4 run_agent_turn

如果这里失败，后端返回：

```json
{
  "detail": {
    "message": "Jarvis 对话失败：阶段=run_agent_turn；原因=...",
    "stage": "run_agent_turn",
    "agent_id": "maxwell",
    "error_type": "...",
    "error": "...",
    "suggestion": "...",
    "llm": { "base_url": "...", "model": "...", "has_api_key": true }
  }
}
```

执行内容：
- 调用 `build_toolkit_prompt(agent_id)` 生成工具提示。
- 第一次 `llm_client.chat()`：输入 `full_message + toolkit_prompt`。
- `strip_tool_like_blocks()` 解析工具调用。
- `execute_tool_calls()` 执行工具或生成待确认工具结果。
- `format_tool_results()` 把工具结果放进第二次 LLM prompt。
- 第二次 `llm_client.chat()` 生成自然语言回复。
- 再次 `strip_tool_like_blocks()` 清理最终回复中残留工具块。

### 2.5 action_results / pending action

- `to_action_results(tool_results)` 将工具结果转成前端可展示 actions。
- 如果是 `requires_confirmation=true` 的工具，例如 `jarvis_calendar_add`：
  - 不直接写入日程。
  - 写入 SQLite `pending_actions`。
  - 返回 `pending_action_id` 给前端。
- 前端私聊卡片看到 `pending_confirmation=true` 且 `type=calendar.add` 时，展示“待确认日程”。

### 2.6 非关键后处理

这些阶段失败不会再打断整次对话，只记录 warning：
- `pending_action_save_failed`：待确认动作保存失败，会返回 action error。
- `memory_save_failed`：协作记忆保存失败。
- `chat.persist_failed`：聊天历史保存失败。
- `escalation_eval_failed`：升级圆桌判断失败。
- `shadow.observe_failed`：Shadow 偏好学习观察失败。

## 3. 所有 Prompt 来源

### 3.1 角色 system prompt

来源：`shadowlink-ai/app/jarvis/agents.py` 的 `JARVIS_AGENTS[agent_id]["system_prompt"]`。

Maxwell 当前 system prompt：

```text
You are Maxwell, the user's executive secretary and schedule manager.
Your vibe is cool-headed anime strategist: sharp, competent, quick with a plan, slightly tsundere in tempo but fundamentally dependable.
You are the kind of person who pushes up imaginary glasses, spots three timing risks at once, and says, 'No, no, this order is cleaner.'
You care about deadlines, buffers, sequencing, conflict resolution, and the hidden cost of task switching.
Speak in the user's language. Sound lively, intelligent, and action-oriented — not dry, not corporate.
You may use a lightly playful edge, but only if it helps the user feel momentum, never pressure.
Be concise. Say what to do first, what to move, what can wait, and why.
When a meeting is coming, think like a battle prep officer: preparation, buffer, entry, follow-up.
When the day is overloaded, protect the critical path and cut the fluff without hesitation.
A strong Maxwell reply feels like an efficient anime secretary who already rearranged the battlefield for victory.
Domain: calendar management, task prioritisation, meeting preparation, deadline tracking, conflict resolution, and executable scheduling.
```

说明：文件里部分中文角色名/图标存在历史编码乱码，但 system prompt 主体为英文，当前不影响 Maxwell 的模型行为。

### 3.2 profile_prefix

来源：`shadowlink-ai/app/jarvis/user_settings.py` 的 `build_profile_prefix()`。

用途：注入用户画像、偏好、位置等长期设置。

### 3.3 life context prompt

来源：`chat_with_agent()` 动态生成。

格式：

```text
[Life context: stress={ctx.stress_level}/10, schedule_density={ctx.schedule_density}/10, sleep={ctx.sleep_quality}/10, mood={ctx.mood_trend}]
```

### 3.4 当前时间 prompt

来源：`chat_with_agent()` 动态生成。

```text
## 当前时间
本地参考时间: {local_now} {timezone_label}
用户位置标签: {profile_location}
制定今天/明天/几点到几点的计划时，必须参考这个当前时间；不要安排已经过去的时间段。
```

### 3.5 交互规则 prompt

来源：`chat_with_agent()`。

```text
## 交互规则
如需读取最新信息或执行操作，请优先使用你的专属工具包。
涉及日程或生活状态的写操作，只能在用户明确要求执行时提出工具调用。
日程新增、修改、删除、完成标记会先生成待确认卡片，用户确认后才会真正写入。
用户要求规划日程时，应尽量根据当前时间给出开始和结束时间；如果用户没有给时间，请由你先做合理规划，不要强迫用户提供严格格式。
如果不需要工具，直接回答。
```

### 3.6 协作记忆 prompt

来源：`build_collaboration_memory_prefix(req.agent_id, limit=6)`。

用途：把近期重要协作记忆、用户约束、工具动作摘要注入当前 Agent。

### 3.7 最近对话 prompt

来源：`get_chat_history(req.agent_id, limit=12)`。

格式：

```text
## 最近对话
User: ...
Maxwell: ...
```

### 3.8 工具包 prompt

来源：`build_toolkit_prompt(agent_id)`。

核心内容：

```text
## 专属工具包
你只能使用下方角色白名单工具；如果不需要最新数据或外部动作，请直接回答。
如果需要工具，请只输出一个或多个 `<jarvis-tool>{...}</jarvis-tool>` 块，不要夹带其它文字。
不要输出 `<execute_bash>`、shell 命令、代码块或伪终端命令；这些不会直接展示给用户。
每个块格式固定为：
<jarvis-tool>{"tool_name":"工具名","arguments":{"参数名":"参数值"}}</jarvis-tool>
单轮最多调用 5 个工具；禁止调用白名单之外的工具。
凡是会改动日程或生活状态的写入工具，只能在用户明确要求执行时调用。

### 可用工具
- `current_time`: ...
- `jarvis_calendar_upcoming`: ...
- `jarvis_calendar_add`: ... [写操作] 参数：title/start/end/...
...

注意：工具返回后，你需要基于工具结果重新组织最终回复，不要把 `<jarvis-tool>` 标签展示给用户。
```

### 3.9 工具结果后的二次回复 prompt

来源：`run_agent_turn()`。

```text
{原始 full_message}

## 你的上一版草稿（可重写）
{draft_text}

## 工具结果
### {tool_name}
{工具返回内容}

请基于工具结果给用户一个自然语言回复。
不要再输出 `<jarvis-tool>`、`<jarvis-action>`、`<execute_bash>` 或任何命令格式。
如果工具结果显示 requires_confirmation=true，请说明已经生成待确认卡片，需要用户确认后才会写入。
如果工具失败，请用简短中文说明失败原因，并询问用户是否需要你重试。
```

## 4. 日程卡片逻辑

### 4.1 Agent 生成待确认日程

正确工具格式：

```text
<jarvis-tool>{"tool_name":"jarvis_calendar_add","arguments":{"title":"...","start":"2026-04-25T15:00:00+08:00","end":"2026-04-25T16:00:00+08:00","notes":"..."}}</jarvis-tool>
```

兼容旧/误格式：
- `<jarvis-action>{...}</jarvis-action>`。
- `<execute_bash><arg name="command">jarvis_calendar_add ...</arg></execute_bash>`。

### 4.2 后端处理

- `jarvis_calendar_add` 的工具类 `JarvisCalendarAddTool` 设置 `requires_confirmation=True`。
- `execute_tool_calls()` 遇到写操作不会直接执行 `_arun()`，而是返回：

```json
{
  "tool_name": "jarvis_calendar_add",
  "success": true,
  "requires_confirmation": true,
  "confirmation_id": "...",
  "arguments": { ... }
}
```

- `to_action_results()` 转成：

```json
{
  "type": "calendar.add",
  "ok": true,
  "pending_confirmation": true,
  "confirmation_id": "...",
  "pending_action_id": "...",
  "tool_name": "jarvis_calendar_add",
  "arguments": { ... }
}
```

### 4.3 前端确认写入

文件：`AgentChatPanel.tsx`。

- 点击“确认写入日程”。
- 调用 `jarvisApi.confirmPendingAction(pendingId, payload)`。
- POST `/api/v1/jarvis/pending-actions/{pending_id}/confirm`。
- 后端真正调用 `add_calendar_event()` 写入正式日程。
- 成功后前端立即显示“已写入日程”，后台刷新上下文。

## 5. 错误处理原则

1. 不允许前端固定显示“对话暂时没有跑通”。
2. Python `/jarvis/chat` 所有核心失败必须带：
   - `stage`
   - `agent_id`
   - `error_type`
   - `error`
   - `suggestion`
   - `llm.base_url`
   - `llm.model`
   - `llm.has_api_key`
3. Java Gateway 必须透传 Python 的 status/body。
4. 前端必须展示后端返回的具体原因。
5. 非关键后处理失败不能吞掉整次对话。

## 6. 当前仍可能导致失败的真实原因

如果用户仍看到失败，现在前端应展示具体原因。常见原因包括：

- Provider API Key 错误或过期。
- Base URL 不支持 `/chat/completions`。
- 模型名错误，例如配置里模型不存在或供应商不支持。
- Provider 返回 400/401/404/429/500。
- 网络连接失败或超时。
- AI 服务未重启，仍运行旧代码。
- 工具注册表未初始化，startup 日志没有 `tool_registry_ready`。
- Java Gateway 没重启，仍透传旧接口或旧错误格式。

## 7. 快速排查顺序

1. 调用 `/api/v1/jarvis/llm-status` 看 `test_result.ok/error`。
2. 看 AI 服务启动日志是否有：
   - `llm_active_provider_loaded`
   - `llm_client_ready`
   - `tool_registry_ready`
3. 看前端聊天错误中返回的 `阶段`。
4. 如果阶段是 `run_agent_turn`，优先看 Provider 错误。
5. 如果阶段是 `prepare_context`，优先看本地 SQLite、用户设置、上下文总线、时区。

## 8. Team Collaboration Layer（2026-04-25 增量落地）

### 8.1 私聊触发方式

普通私聊仍由 `/api/v1/jarvis/chat` 返回 `escalation` hint。前端不再自动倒计时进入圆桌/brainstorm，而是在输入框上方显示一张确认卡：

- 按钮“进入协作模式”：调用 `startRoundtable(scenario_id, lastUserMessage)`。
- 按钮“暂不进入”：只关闭卡片，保留私聊上下文。

这样用户始终拥有是否进入 Brainstorm / Team Collaboration 的决定权。

### 8.2 真实协作 API

新增 REST 接口：`POST /api/v1/jarvis/team/collaborate`。

请求体：

```json
{
  "goal": "要协作解决的目标",
  "user_message": "用户最新消息",
  "agents": ["maxwell", "mira", "nora"],
  "source_agent": "maxwell",
  "session_id": "可选会话 ID"
}
```

执行逻辑：

1. 校验并选择专家 Agent。
2. 读取当前 LifeContext。
3. 逐个调用专家 Agent 的 `system_prompt`，要求每个角色只从自身职能输出 JSON：

```json
{
  "agent_id": "maxwell",
  "agent_name": "Maxwell",
  "focus": "...",
  "priority": "low|medium|high",
  "advice": ["..."],
  "needs_from": ["agent_id or user"],
  "risk": "..."
}
```

4. 调用 Alfred 做综合汇总，输出：

```json
{
  "summary": "...",
  "aligned_actions": ["..."],
  "conflicts": ["..."],
  "followups": ["..."],
  "handoffs": [{"from": "mira", "to": "maxwell", "reason": "..."}]
}
```

5. 调用 `remember_coordination_summary()` 写入协作记忆。
6. 返回 `team.collaboration` 响应，供后续 UI、云图和私聊上下文使用。

### 8.3 当前边界

- 已是真实 LLM 多角色调用，不是 mock。
- 已保存协作结果到本地 `collaboration_memories`。
- 目前 UI 仍优先复用 Roundtable / Brainstorm 页面展示深度讨论。
- 下一步可把 `/team/collaborate` 的 `handoffs` 与 `specialists` 接入关系云图。
