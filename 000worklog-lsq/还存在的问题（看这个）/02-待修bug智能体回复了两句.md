2.智能体回复了两句。
问题描述：我跟智能体说“你好”,它回复了两条，但是我只需要一条回复，不然很乱
我的要求：每一轮对话智能体仅一条回复
目前链路以及问题所在：

问题拆分：
1. “两句”可能来自两种来源：后端一次 `/chat` 返回了两个 agent turn；或前端除后端回复外又额外生成了一条确认/提示气泡。
2. 需求要求的是“一轮用户输入只产生一条 agent 消息气泡”，工具执行结果、待确认卡片、日程卡片都应挂在这一条 agent 消息的 `actions` 上展示，而不是追加第二条 agent 文本。

当前链路：
1. 前端发送消息走 `AgentChatPanel.handleSend -> useJarvisStore.sendMessage -> jarvisApi.chat`。
2. `jarvisStore.sendMessage` 会先乐观追加一条 `{role:"user"}`，后端返回后追加一条 `{role:"agent", content: response.content, actions: response.actions}`。
3. 后端 `shadowlink-ai/app/api/v1/jarvis_router.py` 的 `/chat` 调用 `run_agent_turn(...)`，`run_agent_turn` 在 `shadowlink-ai/app/jarvis/tool_runtime.py` 中执行“两段式 LLM”：第一次让模型决定是否输出工具块；如果有工具块，执行工具后第二次调用 LLM 生成最终自然语言回复。
4. `run_agent_turn(...)` 正常只返回 `clean_final` 一段文本和 `tool_results`，后端 `/chat` 也只返回一个 `content` 字段；从后端结构看，理论上一轮只有一条 agent content。
5. 当前容易出现“双回复”的业务点有两个：
   - `AgentChatPanel.tsx` 针对 `calendar.add` / `task.plan` 等 pending action 会展示额外的确认状态文本，例如“已保存到后台任务清单，可在日历 → 查看所有任务里看到”；如果这类提示被作为单独消息渲染，用户会感知为 agent 回复两条。
   - `jarvisStore.sendMessage` 在发生路由时会同时往原 agent 和 `routedAgentId` 的 `chatHistory` 写入同一个 `agentTurn`；如果当前页面 agentId 与 routedAgentId 切换/重渲染时没有去重，可能出现同一回复被渲染两次。
6. 另外，后端 `/chat` 当前在保存历史时会保存 user 和 agent 两边；如果前端之后再 `loadChatHistory`，乐观消息和后端消息没有 turn id 去重，也可能造成刷新瞬间重复显示。

根因：
1. 系统没有“一轮对话 turn id”的概念，前端只能按数组 append，无法判断某条 agent 回复是否已经属于当前用户消息。
2. 工具确认卡片/状态提示和 agent 自然语言回复没有统一为“同一条 agent 消息的结构化附件”，UI 层容易把它们渲染成两条回复。
3. 跨 agent 路由时，同时向两个 agent 的本地历史数组写入同一 turn，缺少 active session 下的唯一消息键。

解决方案（不允许只写兜底代码，必须修改实际业务链路，让它能真实运行）：

实施计划：
1. 为每次用户发送建立唯一 `turn_id`，贯穿前端、后端、消息表和 UI 渲染。
2. 后端保证一个 `turn_id` 最多保存一条 agent 消息。
3. 前端保证一个 `turn_id` 最多渲染一条 agent 气泡，工具卡片作为该气泡的一部分。
4. 路由到其他 agent 时移动会话归属，不在两个 agent 面板同时追加同一回复。

具体改造：
1. 后端 `persistence.py`：
   - 给 `agent_chat_turns` 增加 `turn_id TEXT`、`message_id TEXT` 或至少 `client_message_id TEXT`，并增加唯一约束或业务去重索引：`UNIQUE(session_id, agent_id, turn_id, role)`。
   - `save_chat_turn(...)` 保存前按 `session_id + agent_id + turn_id + role` upsert，避免同一轮 agent 回复重复入库。
2. 后端 `jarvis_router.py`：
   - `AgentChatRequest` 增加 `turn_id`，如果前端没传就后端生成。
   - `/chat` 保存 user turn 使用这个 `turn_id`；保存 agent turn 也使用同一个 `turn_id`。
   - `run_agent_turn(...)` 的两段式 LLM仍保留，但只允许第二段 `clean_final` 作为 `content` 返回；第一段 `draft_text` 只能作为内部上下文，不能入库、不能返回给前端。
   - 对 `action_results` 保持结构化返回，不再额外生成第二条自然语言“操作成功”消息；确认/取消后的结果只更新 pending action 或 calendar/task 状态。
3. 前端 `jarvisApi.chat(...)`：
   - 发送时携带 `turn_id`。
4. 前端 `jarvisStore.sendMessage(...)`：
   - 本地消息结构增加 `turnId` 和 `messageId`。
   - 先追加 user 消息；收到后端响应时，用 `turnId` 查找当前轮是否已有 agent 消息：有则 update，没有才 append。
   - 如果 `routedAgentId !== agentId`，不要在两个历史数组里都追加完整 agent 消息；应切换 activeAgent 到 `routedAgentId` 后，只在最终归属 agent/session 下保存和展示。
5. 前端 `AgentChatPanel.tsx`：
   - pending action、日程确认、后台任务确认卡片都从 `message.actions` 渲染在同一个 agent 气泡下。
   - `confirmPending(...)`、`cancelPending(...)` 不再向 `chatHistory` 追加新的 agent 文本，只更新卡片状态和刷新日历/任务列表。
   - 如果确实需要提示“已保存”，显示为卡片内状态文案，不作为新消息。
6. 验证：
   - 输入“你好”只出现一条 agent 气泡。
   - 输入“帮我安排今晚 8 点学习”只出现一条 Maxwell 回复，下面挂待确认日程卡；确认后卡片状态变化，不新增第二条 agent 回复。
   - 跨 agent 路由时，原 agent 面板不重复显示 Maxwell 的同一条回复。

