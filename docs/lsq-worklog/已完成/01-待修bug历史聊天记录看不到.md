1.历史聊天记录看不到
问题描述：我在任意打开一个跟智能体的私聊后，再点击返回，并没有看到历史记录里存在一条新的记录
我的要求：只要用户点开一个聊天窗口，一旦发送文字，不必等待智能体回复，就写入历史记录，并且可以通过点击那条历史记录进入那个会话
目前链路以及问题所在：

问题拆分：
1. “历史聊天记录”指左侧/弹窗里的会话历史列表，不是单个 agent 的消息气泡历史。
2. 需求要求的触发时机是“用户发送文字后立刻入库”，不能等智能体回复成功。
3. 历史记录点击后要能恢复到同一个 agent、同一个 session，并拉取该 agent 的聊天内容。

当前链路：
1. 前端从 `shadowlink-web/src/components/jarvis/JarvisHome.tsx` 点击 agent 后调用 `useJarvisStore.openPrivateChat(agent.id)`，进入私聊页面。
2. `shadowlink-web/src/stores/jarvisStore.ts` 的 `openPrivateChat` 目前只写 `localStorage` 和 Zustand 状态：`activeAgentId / interactionMode / sessionId`，不会调用后端 `saveConversationHistory`。
3. 用户在 `shadowlink-web/src/components/jarvis/AgentChatPanel.tsx` 发送消息时，面板层会尝试调用 `jarvisApi.saveConversationHistory(...)`，但这段逻辑处在前端发送流程里，和真实后端聊天入库链路不是一个原子业务动作；如果前端提前返回、异常、路由到 Maxwell、或后端对话失败，历史列表可能没有稳定生成。
4. 后端 `shadowlink-ai/app/api/v1/jarvis_router.py` 的 `/chat` 会在进入 LLM 前调用 `save_conversation(...)`，但当前保存时机跟聊天接口绑定，前端历史列表刷新依赖 `window.dispatchEvent("jarvis:conversation-history-changed")`，而该事件现在是在完整 `jarvisApi.chat(...)` 返回后才触发。
5. 单条消息历史保存在 `shadowlink-ai/app/jarvis/persistence.py` 的 `agent_chat_turns` 表里，但该表没有 `session_id` 字段，`get_chat_history(agent_id)` 只能按 agent 拉最近消息，无法精确恢复“那条历史记录对应的那一次会话”。
6. 会话历史保存在 `conversation_history` 表里，字段包含 `session_id / agent_id / route_payload`，点击历史时 `openConversation` 会切回 `private_chat` 并调用 `loadChatHistory(conversation.agent_id)`，因此 UI 能跳回 agent，但消息列表仍是按 agent 混合加载，不是按 session 加载。

根因：
1. 会话历史的创建不是“用户发送消息”这条业务链路的第一步，而是散落在前端面板和后端聊天接口里；前端刷新事件又等后端回复后才发出，导致用户返回时看不到即时历史。
2. 聊天消息持久化缺少 `session_id`，使“历史记录 -> 对应会话消息”没有闭环，只能按 agent 粗粒度展示。
3. `openPrivateChat` 复用全局 `sessionId`，多个 agent 私聊可能共用同一 session，历史记录的边界不清晰。

解决方案（不允许只写兜底代码，必须修改实际业务链路，让它能真实运行）：

实施计划：
1. 先把“发送用户消息”拆成明确的后端业务步骤：创建/更新会话历史 -> 保存用户消息 -> 再启动 LLM 回复。
2. 改造聊天消息表和接口，让消息按 `session_id + agent_id` 存取。
3. 改造前端 store，让发送消息时先等待“用户消息已落盘”的响应并立刻刷新历史列表，再异步等待 agent 回复。
4. 改造历史点击恢复逻辑，按历史项里的 `session_id` 拉取对应消息。

具体改造：
1. 后端 `shadowlink-ai/app/jarvis/persistence.py`：
   - 给 `agent_chat_turns` 增加 `session_id TEXT` 字段，并增加索引 `idx_chat_session_agent(session_id, agent_id, timestamp)`。
   - 修改 `save_chat_turn(...)` 入参，必须支持 `session_id`；历史数据迁移时允许旧数据 `session_id` 为空。
   - 修改 `get_chat_history(...)` 支持可选 `session_id`，如果传入 session 就按 `session_id + agent_id` 查询，否则保留兼容的 agent 查询。
2. 后端 `shadowlink-ai/app/api/v1/jarvis_router.py`：
   - 在 `/chat` 开始处，确定最终 `routed_agent_id` 后，立即执行 `save_conversation(...)`，然后立即执行 `save_chat_turn(session_id=req.session_id, agent_id=routed_agent_id, role="user", content=req.message)`。
   - LLM 完成后只保存 agent 回复：`save_chat_turn(... role="agent", content=clean_reply, actions=action_results)`，不要再重复保存 user turn。
   - `/chat/{agent_id}/history` 增加 query 参数 `session_id`，传给 `get_chat_history(agent_id, session_id=session_id, limit=...)`。
   - 返回体可增加 `conversation` 或 `conversation_id`，让前端知道本轮消息已经落到哪条历史记录。
3. 前端 `shadowlink-web/src/services/jarvisApi.ts`：
   - `getChatHistory(agentId, limit, sessionId?)` 拼接 `session_id`。
   - `chat(...)` 保留原接口，但类型上接收后端返回的 `conversation_id`，便于刷新历史。
4. 前端 `shadowlink-web/src/stores/jarvisStore.ts`：
   - `openPrivateChat(agentId)` 如果是从主页新开私聊，应生成新的 `sessionId = private-${agentId}-${Date.now()}`；如果是历史记录打开，则使用历史项里的 sessionId。
   - `sendMessage(agentId, message, sessionId)` 前端可以继续先乐观追加用户气泡，但必须在调用 `/chat` 后端接口时由后端先落库用户消息；接口成功建立会话后立即 `window.dispatchEvent(new Event("jarvis:conversation-history-changed"))`，不要等 agent 回复渲染完成才刷新。
   - `loadChatHistory(agentId)` 改成 `loadChatHistory(agentId, sessionId)`，从当前 `state.sessionId` 或历史项传入 sessionId。
   - `openConversation(conversation)` 点击历史项时设置 `sessionId=conversation.session_id`，再调用 `loadChatHistory(conversation.agent_id, conversation.session_id)`。
5. 前端 `shadowlink-web/src/components/jarvis/AgentChatPanel.tsx`：
   - 移除或弱化面板层自行 `saveConversationHistory(...)` 的职责，避免前端和后端重复创建历史；历史创建统一由 `/chat` 业务接口负责。
   - 发送按钮点击后，即使 agent 回复还在等待，返回历史列表也能看到刚创建/更新的会话。
6. 验证：
   - 打开任意 agent 私聊 -> 发送“你好” -> 立刻返回 -> 历史列表出现该 agent 私聊。
   - 点击该历史项 -> 恢复到相同 agent、相同 session，并只看到这次 session 内的消息。
   - 模拟 LLM 失败 -> 历史记录和用户消息仍存在，agent 错误消息作为后续 turn 保存或前端展示。

