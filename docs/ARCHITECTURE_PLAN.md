# ShadowLink V3.0 - Core Architecture Plan

> **Version**: 3.0-core  
> **Date**: 2026-04-16  
> **Status**: Active Planning  
> **Goal**: 只保留首版必须实现的核心闭环，删除或后置所有展示型、研究型、企业增强型内容

---

## 一、这份文档的定位

这不是完整的理想态蓝图，而是 **ShadowLink 首版可落地架构**。

目标只有一个：

> 让用户可以基于工作模式，在 Web UI 中完成一次完整的 AI 工作流：
> **选择模式 -> 发起对话 -> 自动选择 Agent 策略 -> 按需调用工具 / 检索知识库 -> 流式返回结果 -> 保存会话**

凡是不能直接服务这条主链路的能力，全部降级为后置项。

---

## 二、首版必须实现的核心价值

### 2.1 产品一句话

**ShadowLink = 面向具体工作场景的 AI 工作台。**

和普通聊天助手的区别，不是功能堆叠，而是把以下几个要素绑定成一个工作模式：

- 模式上下文
- 对话策略
- 可用工具
- 知识来源
- 资源入口
- 会话记忆

### 2.2 首版只验证三件事

1. **模式化工作是否成立**
   用户切换不同模式后，系统行为、知识范围、工具集随之变化。
2. **Agent 自动适配是否实用**
   用户不需要理解 ReAct、Plan-and-Execute，也能得到合理执行策略。
3. **本地知识库是否真正提升回答质量**
   系统能 ingest 文档、建立索引、在问答时按模式检索并引用。

---

## 三、架构收敛原则

### 3.1 只做端到端闭环，不做概念预埋

优先打通：

- 前端交互
- Java 网关
- Python AI 服务
- LLM 调用
- RAG 检索
- 会话存储

不为未来能力预先引入复杂层。

### 3.2 能少一层就少一层

首版保留 Java + Python 双服务，但进一步收敛：

- Java 负责业务接口、会话、模式、鉴权、统一入口
- Python 负责 Agent、RAG、Tool 调用
- 前端只连 Java，不直连 Python

### 3.3 通信先简单，再优化

**首版只保留 HTTP REST + SSE。**

原因：

- 仓库里 REST / SSE 已具备较多基础
- gRPC 当前不是首版闭环必要条件
- WebSocket / STOMP 也不是必须，有 SSE 足够支撑流式输出

结论：

- Java -> Python：HTTP 调用为主
- Java -> 前端：REST + SSE
- gRPC、双通道、复杂流控全部后置

### 3.4 Agent 先够用，不追求炫技

首版只保留三种执行形态：

- `chat`：直接回答
- `react`：边想边调工具
- `plan_execute`：先规划再执行

不进入首版的能力：

- MultiAgent
- Debate / Judge
- Hermes 技能学习
- Speculative Parallel Execution
- Letta 三层记忆
- Sleep-Time Compute

### 3.5 RAG 先做稳定可用，不做研究型增强

首版 RAG 目标：

- 文档可摄入
- 索引可按模式隔离
- 查询时可召回相关片段
- 回答中可引用来源

不追求首版上线的能力：

- CRAG
- Self-RAG
- Agentic Chunking
- 多阶段质量评估
- 全链路指标平台
- Milvus Lite 扩展

### 3.6 CPU 可用是约束，GPU 加速不是前提

首版必须满足：

- 无 GPU 可运行
- GPU 不是安装前提
- 模型与检索方案默认按 CPU 可接受体验设计

但不单独建设复杂硬件自适应平台。

---

## 四、首版系统边界

### 4.1 必须包含

- 工作模式管理
- 会话与消息管理
- Agent 自动路由
- 基础工具调用
- 基础 RAG 摄入与检索
- 流式回答
- 前端工作台
- 基础鉴权

### 4.2 明确不进首版

- Electron 桌面壳
- 全局快捷键 / 托盘 / 悬浮窗
- 插件市场
- 多租户
- 复杂 RBAC
- 审计中心
- 全链路可观测平台
- Prometheus / Grafana 完整监控体系
- 分布式向量数据库
- 企业级工作流编排

---

## 五、核心架构总览

```text
[React Web]
    |
    | REST / SSE
    v
[Spring Boot]
    |- Auth
    |- WorkMode
    |- Session / Message
    |- AI Bridge
    |
    | HTTP
    v
[FastAPI]
    |- Agent Engine
    |- Router(chat/react/plan_execute)
    |- Tool Registry
    |- RAG Engine
    |- File Ingestion
    |
    +--> [LLM Provider]
    +--> [FAISS Index]
    +--> [Local File Storage]
    +--> [Embedding / Reranker]

[MySQL]
    |- users
    |- work_modes
    |- sessions
    |- messages
    |- knowledge_sources
```

### 5.1 服务职责划分

#### 前端

负责：

- 模式切换
- 对话输入与流式展示
- 会话列表
- 知识库管理入口
- 模式配置界面

不负责：

- 直接调用 LLM
- 直接访问 Python AI 服务
- 复杂业务编排

#### Java 服务

负责：

- 用户鉴权
- WorkMode CRUD
- Session / Message CRUD
- 统一 API 入口
- AI 请求代理与转发
- SSE 流式输出给前端

不负责：

- Agent 推理逻辑
- RAG 检索细节
- 工具执行细节

#### Python 服务

负责：

- LLM 适配
- Agent 执行
- 工具调用
- RAG 摄入与检索
- 模式上下文拼装

不负责：

- 用户体系
- 长事务业务状态
- 前端会话编排

---

## 六、首版核心数据模型

### 6.1 WorkMode

`WorkMode` 是首版最关键的领域对象。

建议保留最小字段：

```yaml
WorkMode:
  id: string
  name: string
  description: string
  system_prompt: string
  strategy: auto | chat | react | plan_execute
  enabled_tools: string[]
  knowledge_scope:
    - source_id
  resources:
    - type: folder | file | url | app
      value: string
      label: string
```

说明：

- 不做过度自动推断
- 不做复杂主题引擎建模
- 不做模式模板体系设计扩张
- 先让模式真正影响 Agent、RAG、工具即可

### 6.2 Session / Message

```yaml
Session:
  id: string
  user_id: string
  mode_id: string
  title: string
  created_at: datetime
  updated_at: datetime

Message:
  id: string
  session_id: string
  role: user | assistant | system | tool
  content: text
  metadata: json
  created_at: datetime
```

说明：

- 会话必须绑定模式
- 消息持久化优先于复杂记忆系统
- 首版记忆 = 当前上下文 + 历史消息摘要，不引入 Letta

### 6.3 KnowledgeSource

```yaml
KnowledgeSource:
  id: string
  user_id: string
  mode_id: string
  name: string
  type: local_file | local_folder
  path: string
  status: pending | indexing | ready | failed
  last_indexed_at: datetime
```

说明：

- 首版先支持本地文件 / 本地目录
- URL 抓取、网页同步、增量监听后置

---

## 七、首版核心执行流

### 7.1 模式切换流

```text
用户切换模式
  -> 前端记录当前 mode_id
  -> 后端读取 WorkMode 配置
  -> 后续对话请求携带 mode_id
  -> Python 按 mode_id 装载 system_prompt / tools / knowledge scope
```

核心要求：

- 模式切换必须真正改变后续回答行为
- 不要求切换时同步做复杂 UI 动画和预热逻辑

### 7.2 对话执行流

```text
前端发送消息
  -> Java 校验用户、会话、mode_id
  -> Java 转发到 Python /agent/stream
  -> Python 读取模式配置
  -> Router 判断使用 chat / react / plan_execute
  -> 按需调用工具或 RAG
  -> 结果流式返回 Java
  -> Java 透传 SSE 给前端
  -> Java 落库消息
```

这是首版最重要的主链路。

### 7.3 知识库摄入流

```text
用户上传文件或登记目录
  -> Java 保存知识源记录
  -> Java 调 Python /rag/ingest
  -> Python 解析文档
  -> Chunk
  -> Embedding
  -> 写入 FAISS 索引
  -> 更新 knowledge source 状态
```

核心要求：

- 至少能看见 ingest 状态
- 至少能按模式命中对应索引
- 至少能返回引用来源

---

## 八、Agent 核心设计

### 8.1 首版策略范围

#### `chat`

用于：

- 普通问答
- 润色
- 翻译
- 不需要工具的轻任务

#### `react`

用于：

- 需要搜索知识库
- 需要调用工具
- 中等复杂度任务

#### `plan_execute`

用于：

- 明显多步骤任务
- 需要先拆解再完成的任务

### 8.2 自动路由原则

首版采用 **规则优先**，不要引入重型分类器。

示例规则：

- 明确问答类 -> `chat`
- 包含查找 / 搜索 / 打开 / 根据文档 -> `react`
- 包含规划 / 分步骤 / 方案 / 对比后给建议 -> `plan_execute`

要求：

- 用户可手动覆盖
- 路由可解释
- 默认回退到 `react`

### 8.3 首版记忆边界

只保留：

- 当前对话窗口
- 历史消息持久化
- 可选摘要压缩

不保留：

- 自主记忆管理
- 长短期多层记忆编排
- 自动技能沉淀

---

## 九、RAG 核心设计

### 9.1 首版 RAG 最小闭环

```text
文档解析 -> 文本分块 -> Embedding -> FAISS 检索 -> 可选重排 -> 拼装上下文 -> 回答
```

### 9.2 首版建议保留的能力

- 本地文件摄入
- 基础文档清洗
- 递归分块
- 向量检索
- 简单混合检索（如果当前实现已稳定）
- 引用来源回传

### 9.3 首版建议后置的能力

- Agentic Chunking
- 多路 query 改写框架化
- CRAG / Self-RAG
- 大量质量指标
- 复杂观测面板

### 9.4 文件格式范围

首版建议只承诺以下格式：

- PDF
- Markdown
- TXT
- 常规代码文本
- DOCX（仅在现有解析已稳定时保留）

图片 OCR、表格提取、公式提取不作为首版目标。

---

## 十、工具系统核心设计

### 10.1 首版工具范围

只保留真正提升主链路的工具：

- 知识库检索
- 文件读取
- Web 搜索
- 基础代码执行或命令执行（仅在安全边界明确时）

### 10.2 工具接入原则

- 工具必须可控
- 工具必须可超时
- 工具结果必须能回显到对话流
- 工具权限先按模式白名单控制

### 10.3 MCP 的首版定位

MCP 可以保留，但只作为 **统一工具接入协议**，不做插件生态扩张。

首版不做：

- 插件市场
- 社区发现系统
- 第三方生态运营能力

---

## 十一、前端核心设计

### 11.1 首版页面只保留四类

- 登录页
- 主工作台
- 模式管理页
- 知识库管理页

### 11.2 主工作台必须具备

- 模式切换器
- 会话列表
- 消息输入区
- 流式消息展示区
- 引用来源展示
- 简单工具 / 状态提示

### 11.3 前端不要进入首版的内容

- 插件市场页面
- 复杂主题动画引擎
- 桌面控制中心
- 过度细分的 Agent 可视化面板

可以保留基础美观，但不要让 UI 复杂度压过功能闭环。

---

## 十二、存储设计

### 12.1 首版必须存什么

MySQL：

- 用户
- 工作模式
- 会话
- 消息
- 知识源记录

本地文件系统：

- 原始上传文件
- 解析中间结果（可选）
- FAISS 索引文件

### 12.2 首版可以不强依赖什么

- Redis
- MinIO
- PostgreSQL 双选型
- 分布式对象存储

如果当前代码已经接入 Redis，可以保留为增强项，但不要让它成为启动前提。

---

## 十三、安全与稳定性收敛

### 13.1 首版安全目标

只做基础必需项：

- JWT 登录鉴权
- 接口权限校验
- 文件路径合法性校验
- 工具执行超时
- 基础输入校验

### 13.2 明确后置项

- 多租户
- 细粒度 RBAC
- 审计中心
- Prompt 注入治理体系
- 企业级限流与熔断平台

### 13.3 首版可观测性目标

只保留：

- 结构化日志
- 请求级错误日志
- ingest 状态日志
- Agent 执行关键事件日志

不做独立指标平台和复杂可视化分析系统。

---

## 十四、推荐实施顺序

### Phase 1：打通最小对话闭环

- 前端 -> Java -> Python -> LLM 流式返回
- Session / Message 落库
- 基础登录
- 单模式对话可用

### Phase 2：引入 WorkMode

- WorkMode CRUD
- 对话绑定 mode_id
- system_prompt / tools / knowledge_scope 随模式变化
- 前端模式切换完成

### Phase 3：引入基础 RAG

- 文件摄入
- 文档索引
- 按模式检索
- 回答附引用来源

### Phase 4：完善 Agent 自动适配

- chat / react / plan_execute 路由
- 用户手动覆盖策略
- 常用工具接入

### Phase 5：做必要打磨

- 错误处理
- ingest 状态展示
- 简单日志
- 基础性能优化

---

## 十五、完成标准

满足以下条件，即视为核心架构落地完成：

1. 用户可以登录并进入工作台。
2. 用户可以创建和切换工作模式。
3. 用户可以在模式下发起对话，并收到流式结果。
4. 系统能根据任务自动选择 `chat / react / plan_execute`。
5. 用户可以给模式绑定知识源，并成功完成索引。
6. 问答时系统可以命中模式对应知识库并返回引用。
7. 会话和消息可以持久化保存。

如果以上 7 条没有全部完成，不要继续扩展高级能力。

---

## 十六、明确删除或后置的内容

以下内容从核心架构文档中移除，不作为当前实现目标：

- gRPC 主通道
- WebSocket / STOMP 实时体系
- MultiAgent 全家桶
- Hermes 技能学习
- Letta 三层记忆
- Speculative Execution
- CRAG / Self-RAG / Agentic Chunking
- 插件市场
- Electron 桌面集成
- 全局快捷键 / 托盘 / QuickBar
- 多租户 / 审计 / 企业级治理
- 完整监控平台
- 分布式向量数据库扩展
- 大而全的目录树和技术选型附录

这些能力不是不能做，而是 **在核心闭环完成前都属于冗余**。

---

## 十七、最终结论

ShadowLink 首版不应该做成功能百科全书，而应该做成一个 **真正能用的模式化 AI 工作台**。

真正的核心只有四个：

- `WorkMode`
- `Chat / Agent`
- `RAG`
- `Session Persistence`

围绕这四个核心完成闭环，产品就成立；脱离这四个核心继续扩写，就是架构噪音。
