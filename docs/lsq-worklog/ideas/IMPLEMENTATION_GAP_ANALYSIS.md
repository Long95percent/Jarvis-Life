# ShadowLink V3.0 — 规划 vs 实现 差距分析报告

> **生成日期**: 2026-04-16  
> **基准文档**: `docs/ARCHITECTURE_PLAN.md` (V3.0-DRAFT)  
> **分析范围**: 全部代码仓库当前状态 (master 分支)

---

## 总览

| 模块 | 规划完整度 | 实际落地率 | 评级 |
|------|-----------|-----------|------|
| **Python AI 服务 (shadowlink-ai)** | 100% | ~70% | ⚠️ 核心完成，高级特性缺失 |
| **Java 后端 (shadowlink-server)** | 100% | ~55% | ⚠️ 骨架+部分模块，多处 Phase 0 stub |
| **前端 (shadowlink-web)** | 100% | ~90% | ✅ 基本完整 |
| **Electron 桌面 (shadowlink-electron)** | 100% | ~75% | ⚠️ 主流程完成，子模块内联 |
| **Proto 定义 (proto/)** | 100% | ~95% | ✅ 完整 |
| **部署配置 (deploy/)** | 100% | ~90% | ✅ 基本完整 |
| **CI/CD (.github/workflows/)** | 100% | 0% | ❌ 完全缺失 |
| **文档 (docs/)** | 100% | ~15% | ❌ 仅有架构规划，缺其他文档 |
| **Makefile** | 100% | ~95% | ✅ 完整 |

---

## 一、Python AI 服务 (shadowlink-ai)

### 1.1 Agent 引擎 (app/agent/)

| 规划模块 | 对应文件 | 状态 | 说明 |
|---------|---------|------|------|
| AgentEngine + TaskComplexityRouter | `engine.py` | ✅ 完整 | 四级策略路由、模式感知、记忆集成、流式/非流式 |
| AgentState / PlanExecuteState / SupervisorState | `state.py` | ✅ 完整 | 所有状态 schema 已定义 |
| ReAct 循环 + Reflexion | `react/graph.py`, `react/executor.py`, `react/nodes.py` | ✅ 完整 | LangGraph 图、反思节点、流式事件转换 |
| Plan-and-Execute + 动态重规划 | `plan_execute/planner.py`, `executor.py`, `graph.py`, `replan.py` | ✅ 完整 | 含 PlanCache (TTLCache) |
| Supervisor MultiAgent | `multi_agent/supervisor.py` | ⚠️ 部分 | 图+路由完成，**专家节点为 placeholder** |
| Swarm 协作模式 | `multi_agent/swarm.py` | ✅ 完整 | 提案→评估→共识→合成 |
| **Hierarchical 层级编排** | `multi_agent/hierarchical.py` | ❌ 未实现 | 文件不存在 |
| **Hermes Agent 协议** | `multi_agent/hermes.py` | ❌ 未实现 | 文件不存在 |
| **Agent-as-Judge / Debate 辩论** | `multi_agent/debate.py` | ❌ 未实现 | 规划 §7.5 中详述，未创建 |
| **Hermes 技能学习** | `agent/skill_learning/hermes.py` | ❌ 未实现 | 规划 §7.6 中详述，目录和文件均不存在 |
| **Speculative Parallel Execution** | `agent/optimization/speculative.py` | ❌ 未实现 | 规划 §7.8 中详述，目录和文件均不存在 |
| **Agent 可观测性 (StepCollector / Analytics)** | `agent/observability/` | ❌ 未实现 | 规划 §7.10 中详述，目录不存在 |
| **SystemPromptBuilder** | `agent/prompt_builder.py` | ❌ 未实现 | 规划 §2.3 中的三模式提示词构建器 |
| **ResourceLauncher** | 无 | ❌ 未实现 | 规划 §2.5 中的资源启动器 |

### 1.2 Agent 记忆系统 (app/agent/memory/)

| 规划模块 | 对应文件 | 状态 | 说明 |
|---------|---------|------|------|
| ShortTermMemory | `short_term.py` | ✅ 完整 | 滑动窗口 deque，session 级 |
| LongTermMemory | `long_term.py` | ✅ 完整 | 文件 JSON 存储，关键词搜索，Agent 可自编辑 |
| EpisodicMemory | `episodic.py` | ✅ 完整 | 执行轨迹记录，策略统计 |
| **SemanticMemory (知识图谱)** | `semantic.py` | ❌ 骨架 | 仅定义接口，无实现 |
| **Letta (MemGPT) 三层记忆管理器** | `memory/letta_memory.py` | ❌ 未实现 | 规划 §7.7 核心创新点，含 Core/Recall/Archival 三层 + Agent Tool 接口 |
| **Sleep-Time Compute** | 无 | ❌ 未实现 | 规划 §7.7 空闲时异步整理记忆 |

### 1.3 RAG 引擎 (app/rag/)

| 规划模块 | 对应文件 | 状态 | 说明 |
|---------|---------|------|------|
| RAG Engine (9 步管线) | `engine.py` | ✅ 完整 | 查询分类→HyDE→检索→重排→CRAG 质量门→生成 |
| 递归分块 | `chunking/recursive.py` | ✅ 完整 | LangChain RecursiveCharacterTextSplitter |
| 语义分块 | `chunking/semantic.py` | ⚠️ 部分 | Phase 0 段落级 fallback，**Embedding 断点检测未实现** |
| **Agentic 智能分块** | `chunking/agentic.py` | ❌ 未实现 | 规划 §8.4 按文档大小自适应分块策略 |
| 本地 Embedding | `embedding/local.py` | ✅ 完整 | SentenceTransformers，惰性加载 |
| API Embedding | `embedding/api.py` | ✅ 完整 | OpenAI 兼容接口 |
| **向量检索** | `retrieval/vector.py` | ❌ 骨架 | 接口定义，实际委托给 FAISS index |
| **BM25 关键词检索** | `retrieval/bm25.py` | ❌ 骨架 | 接口定义，无分词和索引实现 |
| 混合检索 + RRF | `retrieval/hybrid.py` | ✅ 完整 | RRF 融合公式、去重 |
| 多查询扩展 | `retrieval/multi_query.py` | ✅ 完整 | LLM 生成 3 个变体 |
| **Self-RAG 自反思检索** | `retrieval/self_rag.py` | ❌ 未实现 | 规划中提及，文件不存在 |
| **CRAG 纠错检索** | `retrieval/crag.py` | ❌ 未实现 | 规划 §8.2 详述，单独模块不存在（engine.py 中有简化版质量门） |
| Cross-Encoder 重排 | `reranking/cross_encoder.py` | ✅ 完整 | BGE-Reranker |
| LLM 重排 | `reranking/llm_rerank.py` | ✅ 完整 | 0-10 评分归一化 |
| FAISS 索引 | `index/faiss_index.py` | ✅ 完整 | 持久化、模式分区 |
| 索引管理器 | `index/manager.py` | ✅ 完整 | 模式级索引生命周期 |
| **Milvus Lite 索引** | `index/milvus_index.py` | ❌ 未实现 | 规划的可扩展分布式选项 |
| **RAG 全链路日志 (RAGTrace / RAGTracer)** | `rag/observability/` | ❌ 未实现 | 规划 §8.7 全链路追踪 |
| **RAG 质量指标 (RAGMetrics)** | `rag/observability/` | ❌ 未实现 | 规划 §8.8 召回率/精准率/相关性监控 |
| **Query 改写器 (独立模块)** | `rag/retrieval/query_rewriter.py` | ❌ 未实现 | 规划 §8.6（engine.py 中内联了简化版 HyDE） |
| **多路召回器 (MultiPathRetriever)** | `rag/retrieval/multi_path.py` | ❌ 未实现 | 规划 §8.6 三路并行 + Metadata 过滤 |
| **文档预处理管线 (DocumentPreprocessor)** | `rag/preprocessing/` | ❌ 未实现 | 规划 §8.5 清洗（去页眉/水印/乱码）+ 结构化 |

### 1.4 MCP 协议 (app/mcp/)

| 规划模块 | 对应文件 | 状态 | 说明 |
|---------|---------|------|------|
| MCP Server | `server.py` | ✅ 完整 | 工具注册、list/call |
| MCP Client | `client.py` | ✅ 完整 | stdio + HTTP 传输 |
| Tool Registry | `registry.py` | ✅ 完整 | 统一注册中心，模式限制 |
| **LangChain 适配器** | `adapters/langchain_adapter.py` | ❌ 未实现 | LangChain Tool → MCP 转换 |
| **OpenAI 适配器** | `adapters/openai_adapter.py` | ❌ 未实现 | OpenAI Function → MCP 转换 |

### 1.5 LLM 客户端 (app/llm/)

| 规划模块 | 对应文件 | 状态 | 说明 |
|---------|---------|------|------|
| 统一 LLM Client | `client.py` | ✅ 完整 | Provider 路由，LangChain 集成 |
| OpenAI Provider | `providers/openai.py` | ✅ 完整 | 兼容接口 |
| Anthropic Provider | `providers/anthropic.py` | ⚠️ 部分 | 非流式完成，**流式回退到非流式** |
| DeepSeek Provider | `providers/deepseek.py` | ❓ 未审查 | |
| Ollama Provider | `providers/ollama.py` | ❓ 未审查 | |
| **Token 计数中间件** | `middleware/token_counter.py` | ❌ 骨架 | |
| **限流中间件** | `middleware/rate_limiter.py` | ❌ 骨架 | |
| **语义缓存中间件** | `middleware/cache.py` | ❌ 骨架 | |

### 1.6 工具集 (app/tools/)

| 规划模块 | 对应文件 | 状态 | 说明 |
|---------|---------|------|------|
| Tool 基类 | `base.py` | ✅ 完整 | 超时、分类、安全执行 |
| 代码执行器 | `code_executor.py` | ✅ 完整 | 沙盒子进程，模块黑名单 |
| 网络搜索 | `web_search.py` | ✅ 完整 | DuckDuckGo HTML |
| 文件操作 | `file_ops.py` | ❓ 未审查 | |
| 知识库搜索 | `knowledge_search.py` | ❓ 未审查 | |
| 系统工具 | `system_tools.py` | ❓ 未审查 | |

### 1.7 文件处理 (app/file_processing/)

| 规划模块 | 对应文件 | 状态 | 说明 |
|---------|---------|------|------|
| 处理管线 | `pipeline.py` | ✅ 完整 | 格式分发、错误处理 |
| PDF 解析 | `parsers/pdf_parser.py` | ✅ 完整 | PyMuPDF 页面提取 |
| **DOCX 解析** | `parsers/docx_parser.py` | ❓ 未审查 | 可能为骨架 |
| **XLSX 解析** | `parsers/xlsx_parser.py` | ❓ 未审查 | 可能为骨架 |
| **PPTX 解析** | `parsers/pptx_parser.py` | ❓ 未审查 | 可能为骨架 |
| **Markdown 解析** | `parsers/markdown_parser.py` | ❓ 未审查 | 可能为骨架 |
| **代码解析 (Tree-sitter AST)** | `parsers/code_parser.py` | ❓ 未审查 | 可能为骨架 |
| **图片 OCR (PaddleOCR / Tesseract)** | `parsers/image_parser.py` | ❓ 未审查 | 可能为骨架 |
| **表格提取器** | `extractors/table_extractor.py` | ❓ 未审查 | 可能为骨架 |
| **公式提取器** | `extractors/formula_extractor.py` | ❓ 未审查 | 可能为骨架 |
| **元数据提取器** | `extractors/metadata_extractor.py` | ❓ 未审查 | 可能为骨架 |

### 1.8 硬件自适应层 (app/core/)

| 规划模块 | 对应文件 | 状态 | 说明 |
|---------|---------|------|------|
| **HardwareProbe 硬件探测器** | `core/hardware.py` | ❓ 未审查 | 规划 §3.5.2 — CPU/GPU/RAM 自动检测 |
| **MemoryBudget 内存预算管理** | `core/hardware.py` | ❓ 未审查 | 规划 §3.5.5 — 8/16/16+ 三档 |
| **ONNXEmbedder** | 无 | ❌ 未实现 | 规划 §3.5.4 — ONNX Runtime CPU 加速 |
| **TieredEmbeddingCache** | 无 | ❌ 未实现 | 规划 §3.5.4 — LRU + SQLite 双层缓存 |
| **LazyModelLoader** | 无 | ❌ 未实现 | 规划 §3.5.4 — 惰性加载（embedding/local.py 中有简版） |
| **BatchProcessor** | 无 | ❌ 未实现 | 规划 §3.5.4 — 100ms 批次合并 |
| **AgentPlanCache** | 无 | ❌ 未实现 | 规划 §3.5.4 — 独立模块（planner.py 中有简版 TTLCache） |

### 1.9 API 层 (app/api/)

| 规划模块 | 对应文件 | 状态 | 说明 |
|---------|---------|------|------|
| Agent REST API | `v1/agent_router.py` | ✅ 完整 | /chat, /stream, /cancel |
| RAG REST API | `v1/rag_router.py` | ✅ 完整 | /query, /ingest, /indices |
| File REST API | `v1/file_router.py` | ❓ 未审查 | |
| MCP REST API | `v1/mcp_router.py` | ❓ 未审查 | |
| Settings REST API | `v1/settings_router.py` | ❓ 未审查 | |
| Health REST API | `v1/health_router.py` | ❓ 未审查 | |
| **gRPC Agent Servicer** | `grpc/agent_servicer.py` | ❓ 未审查 | |
| **gRPC RAG Servicer** | `grpc/rag_servicer.py` | ❓ 未审查 | |
| **gRPC MCP Servicer** | `grpc/mcp_servicer.py` | ❓ 未审查 | |

### 1.10 Pydantic 数据模型 (app/models/)

| 规划模块 | 对应文件 | 状态 | 说明 |
|---------|---------|------|------|
| Agent 模型 | `models/agent.py` | ❓ 未审查 | |
| RAG 模型 | `models/rag.py` | ❓ 未审查 | |
| MCP 模型 | `models/mcp.py` | ❓ 未审查 | |
| Common 模型 | `models/common.py` | ❓ 未审查 | |

---

## 二、Java 后端 (shadowlink-server)

### 2.1 模块级对照

| 规划模块 | 存在 | 状态 | 说明 |
|---------|------|------|------|
| shadowlink-common | ✅ | ✅ 完整 (13 类) | 异常处理、统一响应、CORS、日志切面、分页 |
| shadowlink-auth | ✅ | ⚠️ Phase 0 (11 类) | JWT 生成/验证完整，**用户为内存硬编码 demo** |
| shadowlink-session | ✅ | ✅ 完整 (11 类) | 会话+消息 CRUD，级联删除 |
| shadowlink-business | ✅ | ⚠️ 部分 (9 类) | WorkMode 完整，**知识库目录为空骨架** |
| shadowlink-websocket | ✅ | ❌ Phase 0 stub (3 类) | STOMP 配置完成，**消息处理为 echo 占位** |
| shadowlink-ai-bridge | ✅ | ⚠️ REST 完成 (9 类) | REST Client 完整，**gRPC Client 未实现** |
| shadowlink-gateway | ✅ | ⚠️ Phase 0 (4 类) | SSE 代理完成，**限流为内存版，熔断未启用** |
| shadowlink-starter | ✅ | ✅ 完整 (1 类) | 可执行 JAR 入口 |

### 2.2 详细未落地清单

#### shadowlink-auth

| 功能 | 状态 | 说明 |
|------|------|------|
| JWT Token (Access + Refresh) | ✅ 完整 | HMAC-SHA 签名，可配置过期时间 |
| JwtAuthFilter | ✅ 完整 | Bearer Token 提取、验证、设置 SecurityContext |
| Spring Security 6 配置 | ✅ 完整 | 白名单路径、无状态会话 |
| Login / Refresh 端点 | ✅ 完整 | |
| **User 数据库实体** | ❌ 未实现 | 当前 admin/shadowlink 硬编码在 DemoUserConfig |
| **用户注册端点** | ❌ 未实现 | |
| **Token 黑名单 (Redis)** | ❌ 未实现 | logout 端点存在但不实际失效 Token |
| **RBAC 权限校验** | ❌ 未实现 | 无 @PreAuthorize 使用示例 |
| **BCrypt 密码存储** | ❌ 未实现 | demo 用户使用 NoOpPasswordEncoder |

#### shadowlink-session

| 功能 | 状态 | 说明 |
|------|------|------|
| 会话 CRUD | ✅ 完整 | 创建/列表/详情/删除/重命名 |
| 消息管理 | ✅ 完整 | 按会话查消息 |
| **Redis 会话缓存** | ❌ 未实现 | 当前纯 DB，无缓存层 |
| **会话状态机 (Active→Idle→Archive)** | ❌ 未实现 | |

#### shadowlink-business

| 功能 | 状态 | 说明 |
|------|------|------|
| WorkMode 模式管理 | ✅ 完整 | CRUD + 内置保护 + 4 种预置模式 |
| **知识库管理** | ❌ 空骨架 | 目录存在，无任何文件 |
| **插件管理** | ❌ 未实现 | 规划提及，目录不存在 |
| **Agent 记忆管理** | ❌ 未实现 | 规划提及，目录不存在 |

#### shadowlink-websocket

| 功能 | 状态 | 说明 |
|------|------|------|
| STOMP + SockJS 配置 | ✅ 完整 | /ws/chat 端点，消息前缀 |
| **调用 AIBridgeService 流式推送** | ❌ echo 占位 | 当前返回 `[echo] {content}` |
| **Agent 事件类型推送** | ❌ 未实现 | token/tool_call/thought/plan/status 等 |

#### shadowlink-ai-bridge

| 功能 | 状态 | 说明 |
|------|------|------|
| REST Client (Agent) | ✅ 完整 | 流式 + 非流式 |
| REST Client (RAG) | ✅ 完整 | query + ingest |
| Health Check | ✅ 完整 | |
| **gRPC Client** | ❌ 未实现 | preferGrpc 配置存在但未使用 |
| **gRPC/REST 自动切换** | ❌ 未实现 | fallback 逻辑未写 |
| **Proto 代码生成 (Java)** | ❌ 未实现 | pom.xml 中无 protobuf-maven-plugin |

#### shadowlink-gateway

| 功能 | 状态 | 说明 |
|------|------|------|
| SSE 代理到 Python | ✅ 完整 | /api/ai/agent/stream |
| 内存限流 (60 req/min) | ✅ Phase 0 | 单实例可用 |
| **Resilience4j @RateLimiter** | ❌ 未启用 | 依赖已添加，注解未使用 |
| **Resilience4j @CircuitBreaker** | ❌ 未启用 | application.yml 中有配置但未注解 |
| **Resilience4j @Bulkhead** | ❌ 未启用 | |
| **Redis 分布式限流** | ❌ 未实现 | |

#### 其他规划但未实现的 Java 模块

| 功能 | 状态 | 说明 |
|------|------|------|
| **多租户隔离 (shadowlink-tenant)** | ❌ 未实现 | 规划 §15 目录树中提及 |
| **配置中心 (shadowlink-config)** | ❌ 未实现 | 规划 §15 目录树中提及 |
| **审计日志** | ❌ 未实现 | 规划 §14 安全体系提及 |
| **Prompt 注入检测** | ❌ 未实现 | 规划 §14 安全体系提及 |
| **Test 覆盖** | ❌ 0 测试类 | 所有模块均无测试 |

---

## 三、前端 (shadowlink-web)

### 3.1 总体评价

前端是落地最完整的模块，核心功能均已实现。

### 3.2 已完成

| 功能 | 说明 |
|------|------|
| React 18 + TypeScript + Vite | 框架搭建完整 |
| 4 个 Zustand Store (chat/agent/ambient/settings) | 全部功能完整，含 Immer + localStorage 持久化 |
| Theme Engine + 6 套氛围主题 | CSS Variable 驱动，HSL 色盘生成，渐变过渡 |
| ChatPanel + MessageBubble + InputArea | 流式渲染、Markdown + KaTeX、自动滚动 |
| AgentPanel + ThoughtProcess + ToolCallCard + PlanProgress | 实时步骤追踪、可展开详情 |
| AmbientProvider + ModeSwitcher + AmbientBackground | Canvas 粒子/矩阵雨/极光/萤火虫动画 |
| KnowledgePage | 文件上传、拖放、索引管理、模式分区 |
| SettingsPage | LLM Provider CRUD、测试连接、预设快添 |
| useAgent (SSE)、useWebSocket、useAmbient | Hook 全部完整 |
| api.ts / sse.ts / websocket.ts | 服务层全部完整 |
| 完整 TypeScript 类型系统 | chat/agent/ambient/api 全覆盖 |
| Vite proxy 配置 | Java + Python 双后端代理 |
| AppLayout + Sidebar + TopBar + StatusBar | 整体布局完成 |

### 3.3 未落地 / 差异

| 规划功能 | 状态 | 说明 |
|---------|------|------|
| **Shadcn/UI + Radix 组件库** | ❌ 未集成 | 规划选型，实际使用自定义 Tailwind 组件 |
| **React Query (TanStack)** | ⚠️ 依赖已装 | package.json 中存在，实际使用程度不确定 |
| **Shiki 代码高亮** | ❌ 未集成 | 规划选型，可能使用其他方案 |
| **Recharts 数据可视化** | ❌ 未使用 | 规划中的 Agent 统计仪表盘/RAG 质量图表未实现 |
| **PluginMarket 插件市场** | ❌ 未实现 | 规划 §6.4 中的 plugins/ 组件 |
| **PluginCard / PluginSettings** | ❌ 未实现 | |
| **ModeEditor 模式编辑器** | ❌ 未实现 | 规划 §2.2 中的可视化模式编辑器 |
| **MultiAgentFlow 多 Agent 流程图** | ❌ 未实现 | 规划 §6.4 中的 agent/ 组件 |
| **FileDropZone 拖放组件** | ❌ 单独组件未找到 | 可能内联在 KnowledgePage |
| **StreamingDisplay 流式显示** | ❌ 单独组件未找到 | 可能内联在 ChatPanel |
| **grpc-web.ts** | ❌ 未实现 | 规划的可选 gRPC-Web 客户端 |
| **Agent 统计仪表盘** | ❌ 未实现 | 规划 §7.10.2 的前端部分 |
| **RAG 质量监控仪表盘** | ❌ 未实现 | 规划 §8.8 的前端部分 |
| **useRAG Hook** | ❌ 未实现 | 规划提及但未找到 |

---

## 四、Electron 桌面壳 (shadowlink-electron)

### 4.1 已完成

| 功能 | 说明 |
|------|------|
| 主窗口 + 加载 React Web UI | dev/prod 模式切换 |
| 全局热键 (Alt+Space, Ctrl+Shift+S) | 唤起 Quick Assist / 截屏 |
| 系统托盘 + 上下文菜单 | 最小化到托盘 |
| Quick Assist 悬浮窗 | 无边框、置顶 |
| IPC 通信 (剪贴板/截屏/系统信息/窗口控制) | preload 暴露完整 API |
| 单实例锁 | 防止重复启动 |
| electron-builder 构建配置 | Win/Mac/Linux 全平台 |

### 4.2 未落地 / 差异

| 规划功能 | 状态 | 说明 |
|---------|------|------|
| **hotkey.ts 独立模块** | ❌ 内联 | 规划 §15 独立文件，实际内联在 main/index.ts |
| **tray.ts 独立模块** | ❌ 内联 | 同上 |
| **quickbar.ts 独立模块** | ❌ 内联 | 同上 |
| **clipboard.ts 剪贴板监控模块** | ❌ 内联 | 同上 |
| **截屏 → OCR → AI 分析** | ⚠️ 部分 | 截屏 IPC 存在，**OCR 处理管线未集成** |
| **选中文本 → AI 问答流程** | ⚠️ 部分 | 剪贴板读取 IPC 存在，**完整流程未串联** |
| **模式快速切换 (托盘菜单)** | ⚠️ 部分 | 托盘存在，**动态模式列表未实现** |

---

## 五、Proto 定义 (proto/)

### ✅ 已完成

5 个 proto 文件全部定义完整:
- `common.proto` — 枚举、通用消息
- `agent_service.proto` — Agent 服务 (StreamChat/Chat/Cancel/Status/Classify)
- `rag_service.proto` — RAG 服务 (Query/Retrieve/Ingest/BatchIngest/Index/Doc)
- `mcp_service.proto` — MCP 桥接 (ListTools/CallTool/ManageServer/ManagePlugin)
- `memory_service.proto` — 记忆服务 (ShortTerm/LongTerm/Episodic/Context)
- `buf.yaml` + `buf.gen.yaml` + `generate.sh` — 代码生成配置

### ⚠️ 未落地

| 问题 | 说明 |
|------|------|
| **Python gRPC 代码生成** | proto 已定义，但 Python 侧 generated stubs 是否最新未确认 |
| **Java gRPC 代码生成** | pom.xml 中无 protobuf-maven-plugin，Java 侧无 stubs |
| **gRPC 端到端通信** | proto 是文档级完整，但双端 stub 生成+服务实现未串通 |

---

## 六、部署配置 (deploy/)

### ✅ 已完成

- `docker-compose.yml` — 生产环境全栈 (MySQL/Redis/Java/Python/Web/Nginx/Prometheus/Grafana)
- `docker-compose.dev.yml` — 开发环境 (H2/热重载/调试端口)
- `nginx/nginx.conf` — 反向代理、限流区域、gzip、安全头
- `scripts/init-db.sql` — 初始 Schema
- `.env.example` — 环境变量文档
- `mysql/my.cnf`, `redis/redis.conf`, `prometheus/prometheus.yml` — 基础设施配置

### ⚠️ 未落地

| 问题 | 说明 |
|------|------|
| **Grafana Dashboard 预配置** | prometheus.yml 存在，但无 Grafana dashboard JSON |
| **SSL/TLS 证书配置** | nginx.conf 中无 HTTPS server 块 |
| **生产环境 docker-compose.prod.yml** | 未区分 prod 和通用配置 |

---

## 七、CI/CD (.github/workflows/)

### ❌ 完全缺失

规划 §13.3 定义了:
- `ci.yml` — Java build + Python test + Web build + Integration test
- `cd.yml` — 持续部署
- `quality.yml` — 代码质量检查

**实际状态**: `.github/workflows/` 目录不存在，无任何 CI/CD 配置。

---

## 八、文档 (docs/)

| 规划文档 | 状态 | 说明 |
|---------|------|------|
| `ARCHITECTURE_PLAN.md` | ✅ 存在 | 3800+ 行完整架构规划 |
| **`API.md`** | ❌ 不存在 | API 接口文档 |
| **`DEVELOPMENT.md`** | ❌ 不存在 | 开发指南 |
| **`DEPLOYMENT.md`** | ❌ 不存在 | 部署指南 |
| **`README.md` (根目录)** | ❓ 未确认 | |

---

## 九、工具脚本 (scripts/)

| 规划脚本 | 状态 | 说明 |
|---------|------|------|
| `bootstrap_resources.py` | ❌ 不存在 | 资源引导脚本 |
| `gen_proto.sh` | ✅ 存在 | proto/generate.sh |
| `dev_setup.sh` | ❌ 不存在 | 开发环境搭建 |

---

## 十、数据库设计 vs 实际 Schema

### 规划表 (§12.1) vs 实际存在

| 规划表名 | Java 实体 | init-db.sql | 状态 |
|---------|-----------|-------------|------|
| `users` | ❌ 无 User 实体 | ❓ | ❌ 未实现（demo 硬编码） |
| `sessions` | ✅ ChatSession | ✅ | ✅ 完成（字段略简于规划） |
| `messages` | ✅ ChatMessage | ✅ | ✅ 完成（字段略简于规划） |
| `ambient_modes` | ✅ WorkMode | ✅ | ✅ 完成（命名为 work_mode） |
| `knowledge_bases` | ❌ | ❌ | ❌ 未实现 |
| `documents` | ❌ | ❌ | ❌ 未实现 |
| `rag_trace_logs` | ❌ | ❌ | ❌ 未实现 |
| `agent_execution_logs` | ❌ | ❌ | ❌ 未实现 |
| `agent_memories` | ❌ | ❌ | ❌ 未实现 |

### Redis 数据结构 (§12.2)

| 规划 Key 模式 | 状态 | 说明 |
|--------------|------|------|
| `session:{id}` 缓存 | ❌ 未实现 | Redis 依赖已添加，未使用 |
| `user:{id}:online` | ❌ 未实现 | |
| `agent:task:{id}` 状态 | ❌ 未实现 | |
| `rate_limit:{user}:{endpoint}` | ❌ 未实现 | 当前用内存限流 |
| `token:blacklist:{jti}` | ❌ 未实现 | logout 不实际失效 |

---

## 十一、按路线图 Phase 对照

### Phase 0: 基础设施搭建 — ✅ 已完成

```
[x] 创建 Monorepo 结构
[x] 搭建 Java SpringBoot 骨架项目 (Maven Multi-Module)
[x] 搭建 Python FastAPI 骨架项目
[x] 搭建 React + Vite + TypeScript 前端骨架
[x] 配置 Docker Compose 开发环境
[x] 定义 gRPC Proto 文件
[ ] 配置 CI Pipeline                    ← 未完成
```

### Phase 1: 核心通信链路 — ⚠️ 部分完成

```
[ ] Java <-> Python gRPC 通信打通        ← 未完成 (REST 已通，gRPC 未通)
[ ] Java <-> 前端 WebSocket 打通         ← 未完成 (配置完成，handler 为 echo)
[x] 前端 <-> Java REST API 打通          ← 已完成
[~] 端到端消息流通                       ← 部分 (前端→Java→Python SSE 已通，WebSocket 链路未通)
[x] 迁移现有 LLM Client 到 Python 服务
[x] 迁移现有 RAG Engine 到 Python 服务
```

### Phase 2: Agent 引擎升级 — ⚠️ 核心完成，高级特性缺失

```
[x] 实现 ReAct 循环 (LangGraph)
[x] 实现 Plan-and-Execute (LangGraph)
[x] 实现 Agent 策略切换 (TaskComplexityRouter)
[~] 实现 Supervisor MultiAgent            ← 图完成，专家节点为 placeholder
[ ] 实现 Hermes Agent 协议基础            ← 未开始
[x] 实现 Agent 记忆系统 (短期 + 长期 + 情景)
[x] MCP 协议集成
[x] 内置工具迁移 + 扩展
```

**Phase 2 缺失的高级特性:**
- Hierarchical MultiAgent
- Agent-as-Judge / Debate
- Hermes 技能学习
- Speculative Parallel Execution
- Letta 三层记忆 (MemGPT)
- Sleep-Time Compute
- Agent 可观测性

### Phase 3: RAG 高级引擎 — ⚠️ 基础完成，高级缺失

```
[~] 混合检索 (Vector + BM25 + RRF)       ← RRF 完成，BM25 为骨架
[x] 查询扩展 (HyDE, Multi-Query)
[x] Reranker 集成 (Cross-Encoder + LLM)
[ ] Self-RAG 实现                        ← 未开始
[ ] Agentic Chunking                     ← 未开始
[~] 多格式文件解析管线                     ← PDF 完成，其他格式待确认
```

**Phase 3 缺失的高级特性:**
- 独立 CRAG 纠错模块
- Query 改写器独立模块
- MultiPath 三路并行检索
- 文档预处理管线 (去页眉/水印/乱码)
- Milvus Lite 索引
- RAG 全链路日志
- RAG 质量指标监控

### Phase 4: 氛围感 UI — ✅ 基本完成

```
[x] 主界面布局实现
[x] 氛围 Theme Engine
[x] 6 套预设氛围主题
[x] 模式切换动画
[x] 对话面板 (流式 Markdown 渲染)
[x] Agent 面板 (思考过程、工具调用、计划进度)
[x] 知识库管理界面
[ ] 插件市场界面                          ← 未开始
[x] 设置面板
```

### Phase 5: 桌面集成 — ⚠️ 基础完成

```
[x] Electron 壳搭建
[x] 全局热键注册
[x] QuickBar 悬浮窗
[x] 系统托盘
[ ] 截屏 OCR 集成                        ← IPC 存在，OCR 管线未集成
[ ] 剪贴板监控                           ← IPC 存在，完整流程未串联
```

### Phase 6: 企业级加固 — ❌ 大部分未开始

```
[~] JWT 认证 + RBAC 权限                  ← JWT 完成，RBAC 未落地
[ ] 多租户隔离                            ← 未开始
[ ] 限流 & 熔断                          ← Phase 0 内存版，Resilience4j 未启用
[ ] 审计日志                             ← 未开始
[ ] 可观测性 (Metrics + Logging + Tracing) ← Prometheus 配置存在，应用埋点未做
[ ] 安全加固 (XSS/CSRF/注入防护)          ← 未开始
[ ] 性能优化 & 压力测试                    ← 未开始
[ ] 文档完善                             ← 仅有架构规划
```

---

## 十二、优先级建议

### P0 — 阻塞核心流程

1. **WebSocket 消息处理实现** — 替换 echo stub，调用 AIBridgeService，打通实时推送
2. **BM25 检索实现** — 混合检索的关键一路，当前为空骨架
3. **Supervisor 专家节点实现** — placeholder 导致 MultiAgent 不可用

### P1 — 完善核心体验

4. User 数据库实体 + 注册端点（替代 demo 硬编码）
5. 知识库 Java 模块实现（entity/mapper/service/controller）
6. gRPC 端到端打通（Proto stub 生成 + Servicer 实现 + Java Client）
7. Letta 三层记忆（规划核心创新点）
8. 语义分块 Phase 1+（Embedding 断点检测）
9. 插件市场前端 + 后端

### P2 — 高级特性

10. CRAG 独立纠错模块
11. Self-RAG
12. Agentic Chunking
13. Hermes 技能学习
14. Agent-as-Judge / Debate
15. Speculative Execution
16. Sleep-Time Compute
17. Agent 可观测性 (StepCollector + Analytics + Dashboard)
18. RAG 全链路日志 + 质量监控

### P3 — 企业级加固

19. Resilience4j 熔断/限流注解
20. Redis 集成（会话缓存 + Token 黑名单 + 分布式限流）
21. RBAC 权限校验
22. 多租户隔离
23. 审计日志
24. CI/CD Pipeline
25. 文档补全 (API.md / DEVELOPMENT.md / DEPLOYMENT.md)
26. 测试覆盖（Java 0 测试类）
