# 4-28 修 bug 工作日志

## 2026-04-28T09:21:06.3462476+08:00
- 开始排查：用户反馈智能体对话返回 Internal server error。
- 已追踪链路：前端 Jarvis chat -> Java JarvisProxyController -> Python FastAPI /api/v1/jarvis/chat -> LLM provider。
- 初步根因：Java 网关未处理 Python AI 服务连接/转发异常，会被全局异常处理器包装成统一 Internal server error；同时 Python 配置仅按进程当前目录加载 .env，从仓库根目录/IDE 启动时会回退到默认 OpenAI 空 key，导致 LLM 连接失败。


## 修复记录
- 根因 1：Python `app.config` 的 `env_file=".env"` 依赖进程当前目录；从仓库根目录、IDE、Java/脚本不同 cwd 启动时，LLM 配置会回退到默认 `https://api.openai.com/v1`、`gpt-4o-mini`、空 API key，引发 `/api/v1/jarvis/chat` 的 `run_agent_turn` 连接失败。
- 根因 2：前端经 Vite 代理访问 Java Gateway；`JarvisProxyController.proxyRest` 只捕获 `WebClientResponseException`，当 Python AI 未启动/连接失败/网关请求异常时会抛到 `GlobalExceptionHandler`，被统一包装为 `Internal server error`，丢失真实原因。
- 修复 1：`shadowlink-ai/app/config.py` 增加项目绝对 `.env` 路径，并让所有 Settings 同时读取当前目录 `.env` 与 `shadowlink-ai/.env`，保证从任意 cwd 启动都能拿到真实 LLM 配置。
- 修复 2：`JarvisProxyController` 捕获 `WebClientRequestException`，返回 HTTP 503 JSON，明确 `Python AI service is unavailable`、异常类型和启动/地址检查建议，不再被全局异常吞成 5001。
- 修复 3：`shadowlink-web/src/services/jarvisApi.ts` 解析 Java 网关 `data.suggestion` 与 `data.error`，对话面板能展示可操作原因，而不是只显示顶层 message。

## 验证
- 从仓库根目录导入 `app.config`：确认 LLM base_url/model/api_key_present 来自 `shadowlink-ai/.env`，不再回退默认 OpenAI 空 key。
- `mvnw.cmd -pl shadowlink-gateway -am -DskipTests compile`：通过。
- 使用 mock LLM 调用 FastAPI `/api/v1/jarvis/chat`：返回 200，说明聊天主链路在不依赖外部网络时正常。
- 备注：直接跑 `python -m pytest tests\integration\test_jarvis_api.py::test_chat_with_agent -q` 失败，原因是当前全局 Python 环境缺少 `pytest-asyncio` 插件，不是本次修复代码失败。

## LLM API 管理轻量化方案补充
- 用户提出：完整 LLM API 配置中心是否耗时过长，当前是否有更轻量但能保证稳定性的方案。
- 判断：完整配置中心包含密钥持久化、多租户、多 provider fallback、成本统计等能力，当前阶段偏重，不适合作为修 bug 的立即目标。
- 方案：采用“薄封装 + 本地配置校验 + 状态接口 + provider 错误映射”的轻量方案，保留现有 `Settings + LLMClient + Provider` 结构，不新增数据库、不做设置页动态保存 key。
- 已写入计划：`docs/lsq-worklog/4-28-worklog/4-28plan.md`。
- 推荐优先级：P1 先做 `runtime_config.py`、`LLMClient.initialize()` 校验、`llm-status` 结构化错误、OpenAI-compatible provider 错误映射与少量测试；P2 再做 probe、部署文档和 request_id；P3 再做完整配置中心。

## 前端瞬时 Internal server error 复查
- 用户反馈：消息刚发出的一瞬间仍显示 `Internal server error`。
- 重新按真实链路复现：`3000 -> 8080 -> 8000` 都能瞬时复现；进一步直连 Python `/api/v1/jarvis/chat` 拿到真实响应体。
- 真实根因：Python 在 `prepare_context` 阶段查询 Jarvis 记忆表时报 `sqlite3.OperationalError: no such column: memory_tier`，不是 LLM API 调用失败。
- 深层原因：`jarvis_memories` 是旧 SQLite schema；代码里虽然有补列迁移，但 `SCHEMA` 先创建了依赖 `memory_tier/visibility` 的索引，旧库在执行 `con.executescript(SCHEMA)` 时就失败，后续 `ALTER TABLE` 迁移逻辑根本执行不到。
- 修复 1：移除 `SCHEMA` 中提前创建的 `idx_jarvis_memories_lifecycle`，保留在补齐列之后再创建索引。
- 修复 2：把 `settings.data_dir` 和文件上传目录从相对路径规范化为 `shadowlink-ai` 项目绝对路径，避免从不同 cwd 启动时产生 `data/jarvis.db` 和 `shadowlink-ai/data/jarvis.db` 两套库。
- 验证：手动触发新迁移后，`shadowlink-ai/data/jarvis.db` 已补齐 `memory_tier/visibility` 等 23 列；mock LLM 调用 `/api/v1/jarvis/chat` 返回 200。
- 验证：再次走 live 服务时，不再瞬时返回 `Internal server error`；后续请求进入 LLM 等待阶段，说明这次瞬时 500 已消除。

## 等待后 Internal server error 复查
- 用户反馈：现在不是瞬时失败，而是等待一会儿后显示 `Internal server error`。
- 重新压测真实链路：`alfred/mira/maxwell/shadow` 经 `3000 -> 8080 -> 8000` 可返回 200；`notion/socrates` 稳定触发 Java 网关泛化 500。
- 真实根因 1：浏览器旧持久化状态或历史会话可能保存了后端不支持的 agent_id：`notion`、`socrates`；新进程 ASGI 验证 Python 对未知 agent 已返回结构化 404。
- 真实根因 2：Java Gateway 透传上游 4xx/5xx 时原样复制上游响应头，可能把不适合 Servlet 写回的 header 一起带回，导致响应写出阶段再次异常，被 `GlobalExceptionHandler` 包成 5001 `Internal server error`。
- 修复 1：Python `/jarvis/chat` 对未知 agent 返回结构化 404，包含 `stage=route_agent`、`AgentNotFound` 和刷新/清理 localStorage 建议。
- 修复 2：Java Gateway 透传上游 4xx/5xx 时只保留安全 `content-type` 和 `X-Request-ID`，不再原样复制所有上游 header，避免 404 被二次异常吞成 500。
- 修复 3：前端 `loadAgents()` 会校验 persisted `activeAgentId` 是否存在于后端 agent 列表；不存在时自动重置到第一个有效 agent，避免旧 localStorage 继续发 `notion/socrates`。
- 验证：`mvnw.cmd -pl shadowlink-gateway -am -DskipTests compile` 通过；新进程 ASGI 调用未知 agent 返回结构化 404。
- 注意：Java Gateway 和 Python FastAPI 的运行中旧进程需要重启后才会加载这些修复；前端需要刷新页面或等待 Vite 热更新。

## 历史对话链路打通
- 用户反馈：私聊某个智能体后点击返回，没有出现在前端“历史对话”框里；需要支持选择历史继续聊、删除历史记录、系统自动过期清理。
- 完整链路检查：Python 已有 `conversation_history` 表与 `/api/v1/jarvis/conversation-history` 增删查/open 接口；私聊 `/chat` 也会自动 `save_conversation`；前端已有 `ConversationHistoryPanel`、`openConversation()` 和删除按钮。
- 真实未打通点：Vite 前端请求走 Java Gateway，而 `JarvisProxyController` 的 REST 转发表没有包含 `/conversation-history`、`/conversation-history/{id}`、`/conversation-history/{id}/open`，导致前端拿到 Java 404 `Resource not found`，历史框无法加载。
- 修复 1：Java Gateway 增加 conversation-history 三个 REST path，允许 GET/POST/DELETE 正常转发到 Python。
- 修复 2：删除 conversation-history 时，如果是 `private_chat`，同步删除对应 `agent_chat_turns` 中同 agent/session 的聊天 turns，避免列表删除了但聊天内容还残留。
- 修复 3：过期自动清理从“仅清理从未打开且创建超过 7 天”改为按 `COALESCE(last_opened_at, updated_at, created_at)` 清理，打开或最近更新过的会话会续期，更符合“过时清理”。
- 验证：新进程 ASGI 完整验证私聊创建历史、列表可见、open 后加载 2 条 turns、delete 后 turns 清零。
- 验证：`mvnw.cmd -pl shadowlink-gateway -am -DskipTests compile` 通过。
- 注意：Java Gateway 需要重启后，前端 `/api/v1/jarvis/conversation-history` 才会从 404 变成正常列表。

## 历史对话模块完整链路梳理（复查版）
- 用户反馈：即使修复过网关路径后，前端右侧“历史对话”模块依旧没有显示历史记录。
- 预期链路：用户在 `AgentChatPanel` 私聊发送消息 -> 前端 `jarvisStore.sendMessage()` 调 `/api/v1/jarvis/chat` -> Python `chat_with_agent()` 调 `save_conversation()` 写 `conversation_history`，并调 `save_chat_turn()` 写 `agent_chat_turns` -> 前端派发 `jarvis:conversation-history-changed` -> `ConversationHistoryPanel` 监听事件后调用 `jarvisApi.listConversationHistory()` -> 浏览器经 Vite `/api` 代理到 Java Gateway -> Java `JarvisProxyController` 转发 `/api/v1/jarvis/conversation-history` 到 Python -> Python `list_conversation_history()` 返回 `{ conversations: [...] }` -> 前端 `setItems()` 渲染列表。
- 续聊链路：用户点击历史项 -> `ConversationHistoryPanel.handleOpen()` -> store `openConversation()` -> POST `/conversation-history/{id}/open` 更新 `last_opened_at` -> 切换到 `private_chat`，设置 `activeAgentId/sessionId` -> GET `/chat/{agentId}/history?session_id=...` 加载 turns -> `AgentChatPanel` 按 session 继续展示和发送。
- 删除链路：用户点删除 -> DELETE `/conversation-history/{id}` -> Python soft delete `conversation_history.status='deleted'`，私聊同步删除同 agent/session 的 `agent_chat_turns` -> 前端从 items 移除。
- 自动清理链路：Python `list_conversations()` 调 `_cleanup_expired_conversations_sync(days=7)`，按 `COALESCE(last_opened_at, updated_at, created_at)` 软删除超过 7 天未打开/未更新会话。
- 当前需要继续排查的可能问题：1) Java 运行进程未重启，仍然 404；2) Java 网关路径模式不匹配带冒号的 conversation id；3) 前端 `listConversationHistory()` 返回解析失败或被 `load()` catch 后只显示错误但用户未注意；4) `ConversationHistoryPanel` flex 布局高度为 0 或被压缩不可见；5) `loadAgents/loadContext` 初始化失败影响 `JarvisHome` 渲染；6) 浏览器仍在旧 bundle/HMR 状态；7) 前端历史模块使用的 BASE 仍走 8080 而不是 Python，且网关未重启。

## 历史对话模块彻底 Debug 记录
- 复查用户仍看不到“历史对话”后，按浏览器真实路径重新验证：`http://localhost:3000/api/v1/jarvis/conversation-history` 返回 404，`http://localhost:8080/api/v1/jarvis/conversation-history` 返回 Java 404，`http://localhost:8000/api/v1/jarvis/conversation-history` 返回 200 且包含多条历史记录。
- 结论：Python 后端、SQLite 数据、前端组件逻辑都有数据；当前前端不显示的直接原因仍是开发链路代理/网关未把 history route 送到 Python。
- 为什么上次修了还不显示：运行中的 Java Gateway 仍未重启，仍使用旧路由；且 Java 网关采用显式 path allow-list，后续新增 Jarvis API 很容易再次漏配。
- 根治修复 1：`JarvisProxyController` 的 REST catch-all 从显式 path 列表改成 `value = "/**"`，让 `/api/v1/jarvis/*` 下所有非 SSE REST 路由都透明转发到 Python，避免 conversation-history 或未来新增接口再漏网关。
- 根治修复 2：`shadowlink-web/vite.config.ts` 增加 `/api/v1/jarvis -> http://localhost:8000` 的开发代理，并放在泛型 `/api` 之前；本地开发时 Jarvis 前端直接打 Python，不再依赖 Java Gateway 是否重启/allow-list 是否完整。
- 验证：Python 8000 历史接口返回 200 且有记录；Java gateway 新代码编译通过；Vite 代理顺序已改为 Jarvis 专用规则优先。
- 注意：Vite 的 `vite.config.ts` 代理变更必须重启 `shadowlink-web` dev server 才生效；Java 通配网关也必须重启 `shadowlink-server` 才生效。
- 验证补充：`npm.cmd run type-check` 通过，说明前端 Vite 配置与 TS 代码无类型问题。
- 当前运行态验证结论：未重启前，`3000/8080` 仍会返回旧 Java 404；重启 `shadowlink-web` 后 Vite 会优先把 `/api/v1/jarvis` 代理到 Python，历史模块应立即显示 Python 8000 已返回的记录；重启 `shadowlink-server` 后 Java 通配代理也会生效。

## Maxwell 私聊 prepare_context / plan_day_id 问题定位（仅定位未修复）
- 用户反馈：打开秘书 Maxwell 私聊并发送一句话后，前端显示 `Jarvis 对话失败：阶段=prepare_context；原因=no such column: plan_day_id`。
- 复现：直连 Python `POST /api/v1/jarvis/chat`，payload `{agent_id: "maxwell", message: "你好", session_id: "debug-plan-day-id"}`，稳定返回 500，stage=`prepare_context`，error=`no such column: plan_day_id`。
- 当前数据库状态：`shadowlink-ai/data/jarvis.db` 的 `maxwell_workbench_items` 表只有 `id/task_day_id/agent_id/title/description/due_at/status/pushed_at/created_at/updated_at`，缺少代码新版本期望的 `plan_day_id` 列。
- 代码期望状态：`shadowlink-ai/app/jarvis/persistence.py` 的 `SCHEMA` 里 `maxwell_workbench_items` 已定义 `plan_day_id TEXT`，并且 `_ensure_initialized()` 后半段也写了旧表补列逻辑：如果 `plan_day_id` 不存在就 `ALTER TABLE maxwell_workbench_items ADD COLUMN plan_day_id TEXT`。
- 真正失败点：`_ensure_initialized()` 一开始先执行 `con.executescript(SCHEMA)`；但 `SCHEMA` 里已经包含 `CREATE UNIQUE INDEX IF NOT EXISTS idx_maxwell_workbench_plan_day ON maxwell_workbench_items(plan_day_id) WHERE plan_day_id IS NOT NULL`。对于旧表，`CREATE TABLE IF NOT EXISTS maxwell_workbench_items` 不会改表结构，随后立刻创建依赖 `plan_day_id` 的索引，于是 SQLite 在执行 SCHEMA 阶段直接报 `no such column: plan_day_id`，导致后面的 `ALTER TABLE` 补列逻辑根本执行不到。
- 触发链路：`chat_with_agent()` 的 `prepare_context` 阶段会调用多种上下文函数；任何第一次进入 `_conn()`/`_ensure_initialized()` 的持久化读取都可能触发这个 migration failure。拆步骤验证时，`get_chat_history()` 和 `build_collaboration_memory_prefix()` 内部吞掉了该异常并返回空，但 `build_bounded_memory_recall_prefix()` -> `list_jarvis_memories()` 没吞异常，因此最终在 `prepare_context` 外层被包装成 500。
- 相关业务来源：`plan_day_id` 属于 Maxwell 计划系统/工作台新字段，用于把统一计划表 `jarvis_plan_days` 的日计划项关联到 `maxwell_workbench_items`；相关查询在 `list_maxwell_workbench_items()` 中会 LEFT JOIN `jarvis_plan_days pd ON pd.id = w.plan_day_id`。
- 问题性质：这是 SQLite 旧库 schema migration 顺序 bug，不是 LLM API、不是前端、也不是 Maxwell prompt 本身。和之前 `memory_tier` 缺列属于同类问题：SCHEMA 中提前创建依赖新列的索引，阻断了后续补列迁移。
- 暂未修复：按用户要求，本轮只定位问题，没有修改代码。

## 2026-04-29 Maxwell plan_day_id 修复
- 重新分析原因：当前代码仍在 `SCHEMA` 中提前执行 `CREATE UNIQUE INDEX IF NOT EXISTS idx_maxwell_workbench_plan_day ON maxwell_workbench_items(plan_day_id)`，而旧库 `shadowlink-ai/data/jarvis.db` 的 `maxwell_workbench_items` 缺少 `plan_day_id` 列，导致 `_ensure_initialized()` 在 `con.executescript(SCHEMA)` 阶段失败，后续 `ALTER TABLE ... ADD COLUMN plan_day_id` 迁移执行不到。
- 修复：从 `SCHEMA` 中移除提前创建 `idx_maxwell_workbench_plan_day` 的语句，保留 `_ensure_initialized()` 中“先检测/补列，再创建索引”的顺序。
- 迁移验证：手动触发 `persistence._ensure_initialized()` 后，`shadowlink-ai/data/jarvis.db.maxwell_workbench_items` 已补齐 `plan_day_id` 列，`idx_maxwell_workbench_plan_day` 也已创建。
- 额外发现并修复：用户刚改的 `jarvis_router.py` 中 `full_message` 被缩进到 `if schedule_intent` 内，普通 Maxwell 私聊会在 `run_agent_turn` 阶段报 `UnboundLocalError`；已将 `full_message` 构造移回普通路径，确保无 schedule intent 时也有完整 prompt。
- 验证：使用 mock LLM 通过 ASGI 调 `POST /api/v1/jarvis/chat`，`agent_id=maxwell` 返回 200，timing 显示 `prepare_context`、`memory_context`、`llm_turn`、`persist_final_turns` 全部完成。
- 静态验证：`python -m py_compile app\jarvis\persistence.py app\api\v1\jarvis_router.py` 通过。
- 验证修正：上一条 py_compile 首次在仓库根目录用错相对路径，随后已在 `shadowlink-ai` 工作目录重新执行 `python -m py_compile app\jarvis\persistence.py app\api\v1\jarvis_router.py`，结果通过。
