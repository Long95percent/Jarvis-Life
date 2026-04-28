# ShadowLink V3.0 — Enterprise Architecture Master Plan

> **Version**: 3.0-DRAFT  
> **Date**: 2026-04-16  
> **Status**: Planning  
> **Author**: Architecture Team  

---

## 目录

- [一、Executive Summary](#一executive-summary)
- [一点五、技术亮点总览](#一点五技术亮点总览--问题驱动的深度场景化方案)
- [二、核心设计哲学：氛围感工作（Ambient Work）](#二核心设计哲学氛围感工作ambient-work)
- [三、系统全局架构](#三系统全局架构)
- [三点五、硬件自适应层 — CPU-First 架构](#三点五硬件自适应层--cpu-first-架构)
- [四、Java 后端（SpringBoot Gateway）](#四java-后端springboot-gateway)
- [五、Python AI 服务层](#五python-ai-服务层)
- [六、前端架构（Web UI）](#六前端架构web-ui)
- [七、Agent 系统深度设计](#七agent-系统深度设计)
- [八、RAG 高级引擎](#八rag-高级引擎)
- [九、MCP 协议与插件生态](#九mcp-协议与插件生态)
- [十、全局快捷键 & 桌面集成](#十全局快捷键--桌面集成)
- [十一、多文件格式处理管线](#十一多文件格式处理管线)
- [十二、数据库设计](#十二数据库设计)
- [十三、DevOps & 工程化](#十三devops--工程化)
- [十四、安全体系](#十四安全体系)
- [十五、目录结构规划](#十五目录结构规划)
- [十六、实施路线图](#十六实施路线图)
- [附录A：技术选型对照表](#附录a技术选型对照表)
- [附录B：核心创新点清单](#附录b核心创新点清单)

---

## 一、Executive Summary

ShadowLink V3.0 是一次从桌面应用到**企业级本地 Web 平台**的全面架构升级。核心理念是**「氛围感工作」(Ambient Work)**——通过工作模式隔离，让 AI 在不同专业场景下提供高度贴合的智能辅助。

### 架构核心决策

| 维度 | 决策 | 理由 |
|------|------|------|
| **后端入口** | Java SpringBoot | 企业级权限/租户/流量管控，生态成熟 |
| **AI 服务** | Python FastAPI + LangGraph | Agent 编排/RAG/ToolCall 生态最强 |
| **跨语言通信** | gRPC + HTTP REST 双通道 | gRPC 高性能编排，REST 兼容调试 |
| **前端** | React 18 + TypeScript + Vite | 现代 SPA，组件化，氛围感 UI |
| **Agent 框架** | LangGraph（双模式） | ReAct + Plan-and-Execute 统一图引擎 |
| **向量数据库** | FAISS + Milvus Lite | 本地高性能，可选分布式扩展 |
| **协议标准** | MCP (Model Context Protocol) | 开放工具生态，兼容社区插件 |

### 系统一句话定位

> **ShadowLink = 氛围感 AI 工作站 + 企业级 Agent 编排平台 + 本地知识引擎**

---

## 一点五、技术亮点总览 — 问题驱动的深度场景化方案

> **核心思想：深度场景化（Deep Scenario-Oriented）。**
> 不是"通用 AI 助手加个皮肤"，而是让每个工作场景从 Agent 策略、知识检索、工具集、记忆空间到 UI 氛围做到端到端适配。

### 亮点 1：氛围感工作模式 — 解决「AI 助手千人一面」

| | |
|---|---|
| **要解决的问题** | 现有 AI 助手（ChatGPT、Copilot 等）在所有场景下行为一致。写论文时给你代码建议，写代码时给你散文口吻。用户需要反复在提示词里描述上下文，切换工具，手动管理不同任务的知识库。 |
| **常规方案的不足** | 大多数产品的「自定义」仅限于切换 System Prompt 或换个主题色，Agent 策略、工具集、知识域、记忆空间仍然全局共享，无法做到场景级隔离。 |
| **ShadowLink 的方案** | **全栈上下文切换**：一个"氛围模式"绑定了 UI 主题 + Agent 策略 + RAG 索引 + 工具集 + 记忆 namespace + 资源快捷入口。切换模式 = 切换整个工作环境。用户零门槛配置：只需拖入文件夹/链接/软件，系统自动推断其余配置。 |

### 亮点 2：Agent 策略自动适配 — 解决「用户需要懂 AI 才能用好 AI」

| | |
|---|---|
| **要解决的问题** | 不同复杂度的任务适合不同的 Agent 策略（简单问答用 Chat，工具任务用 ReAct，复杂规划用 Plan-and-Execute，多角色用 MultiAgent）。但普通用户不知道什么是 ReAct，更不知道何时该选哪种。 |
| **常规方案的不足** | 大多数系统要么只提供一种策略（ReAct），要么让用户手动选——等于要求用户具备 Agent 架构知识。 |
| **ShadowLink 的方案** | **TaskComplexityRouter**：轻量规则引擎（< 5ms，纯 CPU）根据用户输入自动路由到最优策略。用户不选就自动适配，用户选了就尊重用户。Reflexion 在失败时自动反思重试，Hermes 技能学习让重复任务越来越快。用户只感知到"它越来越懂我"。 |

### 亮点 3：生产级 RAG 管线 — 解决「检索了但答非所问」

| | |
|---|---|
| **要解决的问题** | 基础 RAG（embed → top-K → 拼接）召回率低、噪音多、答案不可靠。尤其是中文文档、混合格式（PDF 表格+图片+公式）场景，单一向量检索效果骤降。 |
| **常规方案的不足** | 只做向量召回 + 固定窗口分块，没有 query 改写、没有关键词补充、没有重排序、没有结果质量评估。文档预处理粗糙，表格和公式丢失。 |
| **ShadowLink 的方案** | **六层 RAG 管线**：① 文档清洗+结构化解析（表格/公式/元数据提取）→ ② 智能分块（按文档大小自适应）→ ③ Query 改写（HyDE + 同义扩展）→ ④ 多路召回（向量 + BM25 + metadata 过滤）→ ⑤ RRF 融合 + Cross-Encoder 重排 → ⑥ CRAG 质量自检（不合格则纠正重检索或回退网络搜索）。全链路日志 `query→chunk→prompt→answer` 可追溯。召回率/精准率/答案相关性指标实时监控。 |

### 亮点 4：CPU-First 硬件自适应 — 解决「AI 应用吃 GPU 才能跑」

| | |
|---|---|
| **要解决的问题** | 大多数 AI 应用默认依赖 GPU，在纯 CPU 笔记本上要么无法运行，要么卡顿到不可用。比赛/企业场景中，部署机器不一定有 GPU。 |
| **常规方案的不足** | 要么硬性要求 GPU（排除大量用户），要么简单地提供 CPU fallback 但不做任何优化（体验极差）。 |
| **ShadowLink 的方案** | **HardwareProbe 启动自检**：自动检测 CPU/RAM/GPU，按三档内存预算（8GB/16GB/16GB+）调整模型大小、批次、缓存策略。Embedding 模型转 ONNX（CPU 提速 3x），双层缓存避免重复计算，惰性加载按需占内存。有 GPU 自动加速，无 GPU 流畅运行。 |

### 亮点 5：全链路可观测 — 解决「AI 是黑盒，出了问题无法定位」

| | |
|---|---|
| **要解决的问题** | AI 应用最大的运维痛点：不知道为什么回答不好。是检索没召回？是 chunk 不相关？是 prompt 太长截断了？是 token 超限？ |
| **常规方案的不足** | 大多数 AI 应用只记录最终输入输出，中间的检索→拼接→生成过程是黑盒。 |
| **ShadowLink 的方案** | **RAG 全链路日志**：每次请求记录 `query → 改写后 query → 召回 chunks (含 score) → 拼装的 prompt → LLM 原始回答 → 后处理结果`，全部可在管理后台查看。**Agent 侧统计**：每步 token 用量、耗时、工具调用次数，按时间段可视化。**RAG 质量指标**：召回率、精准率、答案相关性评分，持续监控 RAG 效果退化。 |

### 亮点 6：Java + Python 双语言解耦 — 解决「AI 服务和业务治理耦合」

| | |
|---|---|
| **要解决的问题** | AI 编排（Agent/RAG/ToolCall）和业务治理（权限/会话/CRUD/限流）放在同一个服务中，一个 Python OOM 导致整个系统不可用，而且 Python 不擅长高并发网关。 |
| **常规方案的不足** | 纯 Python 栈（FastAPI 全包）虽然开发快，但缺乏 Spring 生态的企业级治理能力（成熟的 RBAC、限流、熔断）。纯 Java 栈则 AI 生态不如 Python。 |
| **ShadowLink 的方案** | **Java 做业务网关**（权限、会话、CRUD、限流熔断），**Python 专注 AI 能力**（Agent、RAG、MCP）。gRPC 高性能通信，互不影响。Java 侧故障不影响 AI 推理，Python OOM 不影响用户登录和数据。各自用最擅长的语言做最擅长的事。 |

---

## 二、核心设计哲学：氛围感工作（Ambient Work）

### 2.1 什么是氛围感工作

氛围感工作是 ShadowLink 的灵魂。它不是简单的「切换主题」，而是一种**全栈上下文切换**：

```
氛围感 = UI 氛围 + Agent 行为 + 知识域 + 工具集 + 提示策略 + 记忆空间
```

当用户进入某个工作模式时，整个系统从视觉到智能都为这个场景做了专属适配。

### 2.2 用户自定义模式 — 零门槛配置接口

**核心原则：用户不需要懂 Agent，只需要描述「我要做什么」。**

系统提供可视化模式编辑器，用户可以像配置桌面一样配置自己的工作模式：

```
┌─────────────────────────────────────────────────────────────┐
│  ✏️ 编辑模式：我的论文工作台                                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  模式名称：[ 我的论文工作台           ]                       │
│  模式描述：[ 阅读和写作学术论文时使用   ]  ← 自然语言即可      │
│  图标：    [📚] 选择                                         │
│                                                             │
│  ── 工作资源（拖入或点击添加）──────────────────────────────  │
│  📁 D:\Papers\2026                        [本地文件夹]       │
│  📁 D:\MyThesis\draft.docx                [本地文件]         │
│  🔗 https://scholar.google.com            [网页链接]         │
│  🔗 https://arxiv.org/list/cs.AI/recent   [网页链接]         │
│  💻 Zotero                                [本地软件]         │
│  💻 TeXstudio                             [本地软件]         │
│  [+ 添加资源]                                                │
│                                                             │
│  ── Agent 策略 ─────────────────────────────────────────────  │
│  ◉ 自动适配（推荐：系统根据任务自动选择最优策略）              │
│  ○ 手动选择：[ ReAct ▼ ]                                     │
│                                                             │
│  ── 系统提示词（可选）──────────────────────────────────────  │
│  ◉ 使用系统默认（根据模式自动生成）                           │
│  ○ 自定义提示词：                                            │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 你是一位学术研究助手，擅长论文分析和文献综述。           │  │
│  │ 回答时请：                                             │  │
│  │ 1. 优先引用用户知识库中的文献                           │  │
│  │ 2. 使用学术化的语言风格                                │  │
│  │ 3. 对观点给出来源标注                                  │  │
│  └───────────────────────────────────────────────────────┘  │
│  字数：86/2000          [插入变量 ▼]  [恢复默认]             │
│                                                             │
│  ── 高级设置（可选，折叠）──────────────────────────────────  │
│  主题色：[#4FC3F7]  字体：[默认 ▼]  氛围动画：[自动 ▼]       │
│  额外工具：☐ 代码执行  ☑ PDF解析  ☑ 网络搜索  ☐ 数据分析     │
│                                                             │
│  [保存]  [预览效果]  [从模板创建]                             │
└─────────────────────────────────────────────────────────────┘
```

#### 模式配置数据模型

```yaml
AmbientMode:
  # ===== 用户填写（简单直觉）=====
  id: "user_paper_desk"                    # 自动生成
  name: "我的论文工作台"                     # 用户起名
  description: "阅读和写作学术论文时使用"    # 自然语言描述，用于 Agent 理解场景
  icon: "book-open"                         # 用户选择
  
  resources:                                # 用户拖入的工作资源
    - type: "folder"
      path: "D:\\Papers\\2026"
      label: "论文库"
    - type: "file"
      path: "D:\\MyThesis\\draft.docx"
      label: "毕业论文草稿"
    - type: "url"
      url: "https://scholar.google.com"
      label: "Google Scholar"
    - type: "url"
      url: "https://arxiv.org/list/cs.AI/recent"
      label: "arXiv AI"
    - type: "application"
      executable: "C:\\Program Files\\Zotero\\zotero.exe"
      label: "Zotero"
    - type: "application"
      executable: "C:\\Program Files\\TeXstudio\\texstudio.exe"
      label: "TeXstudio"

  # ===== Agent 策略：自动 or 手动 =====
  agent:
    strategy: "auto"                        # "auto" | "react" | "plan_and_execute"
    # strategy = "auto" 时，由 TaskComplexityRouter 实时判断：
    #   简单问答 → 直接 LLM (零开销)
    #   中等任务 → ReAct 循环
    #   复杂任务 → Plan-and-Execute
    #   多角色任务 → Supervisor MultiAgent
    system_prompt:
      mode: "auto"                          # "auto" | "custom" | "append"
      # auto   → 系统根据模式名称+描述+资源自动生成提示词
      # custom → 完全使用用户自定义提示词
      # append → 系统提示词 + 用户追加内容（两者拼接）
      content: ""                           # 用户自定义内容（mode=custom/append 时生效）
    extra_tools: []                          # 用户额外启用的工具

  # ===== 以下由系统根据 description + resources 自动推断 =====
  _inferred:                                 # 前缀 _ 表示系统自动生成
    theme:
      primary_color: "#5B8DEF"               # 根据 description 语义自动选色
      bg_gradient: "linear-gradient(135deg, #0f1923, #1a2332)"
      ambient_animation: "auto"              # 系统根据场景选择
    rag:
      index_sources: ["D:\\Papers\\2026", "D:\\MyThesis\\draft.docx"]
      retrieval_strategy: "adaptive"         # 默认自适应
    memory:
      namespace: "user_paper_desk"           # 自动按 mode id 隔离
    inferred_tools: ["pdf_parser", "web_search", "citation_analysis"]
```

### 2.3 系统提示词自定义

用户可以根据自己的需求场景添加、修改系统提示词，三种模式覆盖所有使用习惯：

```
┌────────────────────────────────────────────────────────────┐
│  系统提示词设置                                              │
│                                                            │
│  ◉ 自动生成（推荐）                                         │
│    系统根据模式名称、描述、资源自动生成最合适的提示词。        │
│    当前自动生成结果：                                        │
│    ┌──────────────────────────────────────────────────┐    │
│    │ 你是 ShadowLink AI 助手，当前处于「我的论文工作台」│    │
│    │ 模式。用户正在进行学术论文研读与写作。你的知识库中  │    │
│    │ 包含 D:\Papers\2026 下的论文和毕业论文草稿。       │    │
│    │ 请优先基于知识库内容回答，引用时标注来源。          │    │
│    └──────────────────────────────────────────────────┘    │
│    [只读预览]                                               │
│                                                            │
│  ○ 追加模式                                                 │
│    在自动生成的提示词后面追加你的自定义内容。                  │
│    ┌──────────────────────────────────────────────────┐    │
│    │ 额外要求：                                       │    │
│    │ 1. 回答使用中英双语术语                           │    │
│    │ 2. 每段结论附带置信度评估                          │    │
│    └──────────────────────────────────────────────────┘    │
│                                                            │
│  ○ 完全自定义                                               │
│    完全替换系统提示词，适合高级用户。                         │
│    ┌──────────────────────────────────────────────────┐    │
│    │ （自由编辑区）                                    │    │
│    └──────────────────────────────────────────────────┘    │
│                                                            │
│  可用变量（点击插入）：                                      │
│  {{mode_name}}    — 当前模式名称                             │
│  {{mode_desc}}    — 当前模式描述                             │
│  {{resources}}    — 资源列表摘要                             │
│  {{current_date}} — 当前日期                                │
│  {{user_name}}    — 用户名称                                │
│                                                            │
│  字数：86/2000                    [恢复默认]  [保存]         │
└────────────────────────────────────────────────────────────┘
```

#### 提示词构建逻辑

```python
# agent/prompt_builder.py
class SystemPromptBuilder:
    """
    根据用户配置构建最终系统提示词。
    三种模式：auto / append / custom。
    """
    
    def build(self, mode: AmbientMode, user: User) -> str:
        prompt_config = mode.agent.system_prompt
        
        match prompt_config.mode:
            case "auto":
                # 自动生成：基于模式元信息拼装
                return self._auto_generate(mode, user)
            
            case "append":
                # 追加模式：自动生成 + 用户追加
                base = self._auto_generate(mode, user)
                custom = self._render_variables(prompt_config.content, mode, user)
                return f"{base}\n\n{custom}"
            
            case "custom":
                # 完全自定义：只用用户内容
                return self._render_variables(prompt_config.content, mode, user)
    
    def _auto_generate(self, mode: AmbientMode, user: User) -> str:
        """根据模式名称、描述、资源自动生成提示词"""
        resources_summary = self._summarize_resources(mode.resources)
        
        return f"""你是 ShadowLink AI 助手，当前处于「{mode.name}」模式。
{mode.description}

可用资源：
{resources_summary}

请基于用户的知识库和上下文信息回答问题。如果引用了知识库内容，请标注来源。"""
    
    def _render_variables(self, template: str, mode: AmbientMode, user: User) -> str:
        """替换模板变量"""
        return template.replace(
            "{{mode_name}}", mode.name
        ).replace(
            "{{mode_desc}}", mode.description
        ).replace(
            "{{resources}}", self._summarize_resources(mode.resources)
        ).replace(
            "{{current_date}}", datetime.now().strftime("%Y-%m-%d")
        ).replace(
            "{{user_name}}", user.username
        )
```

### 2.4 Agent 策略自动适配（TaskComplexityRouter）

**用户不选 = 系统自动选。用户选了 = 尊重用户。**

```
用户输入
    │
    ▼
┌──────────────────────────────┐
│   TaskComplexityRouter       │  ← 轻量分类器，CPU 友好 (< 5ms)
│                              │
│   输入：用户消息 + 模式上下文 │
│   输出：策略 + 置信度         │
│                              │
│   判断维度：                  │
│   · 是否需要工具？(关键词+意图)│
│   · 步骤数预估 (1步 vs 多步)  │
│   · 是否需要多角色协作？      │
│   · 历史相似任务的策略记录     │
└──────────────┬───────────────┘
               │
    ┌──────────┼──────────┬──────────────┐
    ▼          ▼          ▼              ▼
  直接回答   ReAct      Plan &        Supervisor
  (chat)     循环       Execute       MultiAgent
             
  "翻译这    "帮我搜    "写一篇关于    "审查代码
   句话"      下XX的     XX的文献       并写测试
              最新论文"  综述"          并部署"

  开销最低    中等开销   较高开销       最高开销
  0 工具调用  1-5轮      5-20步        多Agent协作
```

```python
# agent/router.py — 任务复杂度路由器
class TaskComplexityRouter:
    """
    零配置策略选择：用户不需要知道什么是 ReAct。
    
    实现：规则引擎 + 轻量 LLM 分类（可选），CPU 开销极低。
    用户手动选择时直接跳过此路由。
    """
    
    # 规则引擎 (无 LLM 调用，纯 CPU，< 5ms)
    SIMPLE_PATTERNS = [
        r"翻译|解释|什么意思|帮我改|润色",           # 直接回答
    ]
    REACT_PATTERNS = [
        r"搜索|查找|帮我看下|打开|最新",             # 需要工具
    ]
    PLAN_PATTERNS = [
        r"写一篇|分析.*并.*总结|对比.*然后|步骤",     # 多步骤
    ]
    MULTI_AGENT_PATTERNS = [
        r"审查.*并.*修改|分别.*然后.*汇总",           # 多角色
    ]
    
    def route(self, query: str, mode: AmbientMode, user_override: str | None) -> str:
        # 用户手动选择 → 直接用
        if user_override and user_override != "auto":
            return user_override
        
        # 规则快速匹配
        if self.match_patterns(query, self.SIMPLE_PATTERNS):
            return "chat"
        if self.match_patterns(query, self.MULTI_AGENT_PATTERNS):
            return "supervisor"
        if self.match_patterns(query, self.PLAN_PATTERNS):
            return "plan_and_execute"
        if self.match_patterns(query, self.REACT_PATTERNS):
            return "react"
        
        # 兜底：中等复杂度默认 ReAct（最通用）
        return "react"
```

### 2.5 资源启动器 — 一键打开工作环境

用户配置的链接/路径/软件不只是静态展示，还支持一键打开：

```
┌── 我的论文工作台 ──────────────────────────────┐
│                                                │
│  📂 论文库 (D:\Papers\2026)          [打开]    │
│  📄 毕业论文草稿                      [打开]    │
│  🌐 Google Scholar                   [打开]    │
│  🌐 arXiv AI                         [打开]    │
│  🔧 Zotero                           [启动]    │
│  🔧 TeXstudio                        [启动]    │
│                                                │
│  [▶ 一键启动全部]  ← 打开所有链接+启动所有软件   │
│                                                │
│  知识库状态：已索引 342 篇文档 | 上次更新 2h前   │
│  [重新索引]                                     │
└────────────────────────────────────────────────┘
```

```python
# 资源启动器
class ResourceLauncher:
    """根据资源类型选择打开方式"""
    
    async def launch(self, resource: ModeResource):
        match resource.type:
            case "folder":
                subprocess.Popen(f'explorer "{resource.path}"')    # 打开文件夹
            case "file":
                os.startfile(resource.path)                        # 用默认程序打开
            case "url":
                webbrowser.open(resource.url)                      # 打开浏览器
            case "application":
                subprocess.Popen(resource.executable)              # 启动软件
    
    async def launch_all(self, mode: AmbientMode):
        """一键启动模式下所有资源"""
        for r in mode.resources:
            await self.launch(r)
```

### 2.6 预设模式模板（用户可一键克隆后自定义）

| 模板 | 默认 Agent 策略 | 预置资源类型 | 预置工具 |
|------|----------------|-------------|---------|
| **论文研读** | auto (倾向 Plan) | 论文文件夹、学术网站 | PDF解析、引用分析 |
| **代码开发** | auto (倾向 ReAct) | 项目目录、GitHub、IDE | 代码执行、Git、Lint |
| **写作创作** | auto (倾向 Plan) | 素材文件夹、参考网站 | 大纲生成、润色 |
| **项目管理** | auto (倾向 Multi) | 项目文档、任务平台 | 进度追踪、汇报 |
| **数据分析** | auto (倾向 ReAct) | 数据目录、数据库连接 | Python沙盒、可视化 |
| **日常助手** | auto (倾向 Chat) | 个人文档、常用网站 | 搜索、翻译、日程 |

> 用户可从模板创建，也可完全从零自建。所有高级选项折叠隐藏，普通用户只需要填名字+拖入资源即可使用。

### 2.7 模式切换流程

```
用户切换模式
    ├─> [前端] Theme Engine: 渐变切换 UI 主题 + 氛围动画
    ├─> [Java]  Session Context: 更新当前会话的 mode_id
    ├─> [Python] Agent Reconfigure:
    │       ├─> TaskComplexityRouter 重置（准备根据新模式推断策略）
    │       ├─> 重新加载 Tool Registry（模式工具 + 用户额外工具）
    │       ├─> 加载模式 system_prompt（自动生成 or 用户自定义）
    │       └─> 切换 Memory Namespace
    ├─> [Python] RAG Reconfigure:
    │       ├─> 切换到模式关联的 FAISS Index（从 resources 自动构建）
    │       ├─> 自适应检索策略
    │       └─> 按需加载 Reranker
    ├─> [前端] Resource Panel: 展示模式资源列表 + 一键启动
    └─> [前端] Layout Adapt: 调整面板布局
```

---

## 三、系统全局架构

### 3.1 架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                         用户层 (User Layer)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │  Web UI      │  │  全局热键     │  │  System Tray 托盘      │ │
│  │  React SPA   │  │  Electron    │  │  Quick Panel           │ │
│  └──────┬───────┘  └──────┬───────┘  └────────────┬───────────┘ │
└─────────┼──────────────────┼──────────────────────┼─────────────┘
          │ HTTP/WS          │ IPC                   │ IPC
┌─────────┼──────────────────┼──────────────────────┼─────────────┐
│         ▼                  ▼                       ▼             │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Java SpringBoot Gateway                     │    │
│  │  ┌─────────┐ ┌─────────┐ ┌──────────┐ ┌─────────────┐  │    │
│  │  │ Auth &  │ │ Session │ │ Rate     │ │ API Router  │  │    │
│  │  │ Tenant  │ │ Manager │ │ Limiter  │ │ & Gateway   │  │    │
│  │  └─────────┘ └─────────┘ └──────────┘ └──────┬──────┘  │    │
│  │  ┌─────────┐ ┌─────────┐ ┌──────────┐        │         │    │
│  │  │ CRUD    │ │ Config  │ │ WebSocket│        │         │    │
│  │  │ Service │ │ Center  │ │ Hub      │        │         │    │
│  │  └─────────┘ └─────────┘ └──────────┘        │         │    │
│  └──────────────────────────────────────────────┼──────────┘    │
│              Java 层 (Business & Governance)      │              │
└──────────────────────────────────────────────────┼──────────────┘
                    gRPC / HTTP                     │
┌──────────────────────────────────────────────────┼──────────────┐
│              Python AI 服务层                      ▼              │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    FastAPI Server                           │ │
│  │  ┌──────────────┐  ┌───────────────┐  ┌────────────────┐  │ │
│  │  │ Agent Engine │  │ RAG Engine    │  │ MCP Gateway    │  │ │
│  │  │ (LangGraph)  │  │ (FAISS+)     │  │ (Protocol Hub) │  │ │
│  │  └──────┬───────┘  └───────┬───────┘  └───────┬────────┘  │ │
│  │         │                  │                   │           │ │
│  │  ┌──────┴───────┐  ┌──────┴───────┐  ┌───────┴────────┐  │ │
│  │  │ MultiAgent   │  │ Embedding &  │  │ Plugin         │  │ │
│  │  │ Orchestrator │  │ Reranking    │  │ Registry       │  │ │
│  │  └──────────────┘  └──────────────┘  └────────────────┘  │ │
│  │  ┌──────────────┐  ┌───────────────┐  ┌────────────────┐  │ │
│  │  │ Memory       │  │ Tool         │  │ File           │  │ │
│  │  │ Manager      │  │ Executor     │  │ Processor      │  │ │
│  │  └──────────────┘  └───────────────┘  └────────────────┘  │ │
│  └────────────────────────────────────────────────────────────┘ │
│              Python 层 (AI & Intelligence)                       │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────┼───────────────────────────────────┐
│              数据层 (Data Layer)                                  │
│  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ MySQL/   │  │ Redis     │  │ FAISS    │  │ MinIO/Local   │  │
│  │ PostgreSQL│  │ Cache &   │  │ Vector   │  │ File Storage  │  │
│  │ (CRUD)   │  │ Session   │  │ Index    │  │ (Documents)   │  │
│  └──────────┘  └───────────┘  └──────────┘  └───────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 核心通信流

```
[浏览器] ──HTTP/WS──> [Nginx] ──> [SpringBoot :8080]
                                       │
                                       ├─ 业务 CRUD ──> [MySQL]
                                       ├─ 缓存/会话 ──> [Redis]
                                       │
                                       ├─ gRPC(:50051) ──> [Python FastAPI :8000]
                                       │                       ├─ Agent 编排
                                       │                       ├─ RAG 检索
                                       │                       ├─ MCP 调用
                                       │                       └─> [FAISS / LLM API]
                                       │
                                       └─ WebSocket ──> [前端实时推送]
```

### 3.3 跨语言通信设计

#### gRPC 通道（高性能、强类型）

用于：Agent 编排请求、RAG 检索、流式 Token 传输

```protobuf
// proto/agent_service.proto
syntax = "proto3";
package shadowlink.agent;

service AgentService {
  // 单次 Agent 调用
  rpc Execute (AgentRequest) returns (AgentResponse);
  // 流式 Agent 交互（Token by Token）
  rpc StreamExecute (AgentRequest) returns (stream AgentChunk);
  // Agent 状态查询
  rpc GetStatus (StatusRequest) returns (AgentStatus);
  // 取消执行
  rpc Cancel (CancelRequest) returns (CancelResponse);
}

service RAGService {
  rpc Retrieve (RetrieveRequest) returns (RetrieveResponse);
  rpc Ingest (IngestRequest) returns (IngestResponse);
  rpc BuildIndex (BuildIndexRequest) returns (stream BuildProgress);
}

service MCPService {
  rpc ListTools (ListToolsRequest) returns (ToolList);
  rpc CallTool (ToolCallRequest) returns (ToolCallResponse);
  rpc StreamCallTool (ToolCallRequest) returns (stream ToolCallChunk);
}

message AgentRequest {
  string session_id = 1;
  string mode_id = 2;
  string strategy = 3;        // "react" | "plan_and_execute"
  repeated Message messages = 4;
  AgentConfig config = 5;
  map<string, string> context = 6;
}

message AgentChunk {
  string type = 1;             // "token" | "tool_call" | "tool_result" | "thought" | "plan" | "status"
  string content = 2;
  ToolCallInfo tool_call = 3;
  PlanStep plan_step = 4;
}
```

#### HTTP REST 通道（兼容、调试友好）

用于：配置管理、文件上传、健康检查、外部集成

```
POST   /api/v1/ai/agent/execute          # Agent 执行
GET    /api/v1/ai/agent/{task_id}/status  # 状态查询
DELETE /api/v1/ai/agent/{task_id}         # 取消任务
POST   /api/v1/ai/rag/retrieve           # RAG 检索
POST   /api/v1/ai/rag/ingest             # 文档摄入
GET    /api/v1/ai/mcp/tools              # 工具列表
POST   /api/v1/ai/mcp/call               # 工具调用
GET    /api/v1/ai/health                  # 健康检查
```

---

## 三点五、硬件自适应层 — CPU-First 架构

### 3.5.1 设计原则

```
核心约束：整个系统必须在纯 CPU 机器上流畅运行。
GPU 是加速器，不是必需品。
```

**三条铁律：**
1. **CPU 是底线** — 所有功能在 CPU 上必须可用，无 GPU 时不降级功能，只降级速度
2. **GPU 是加速** — 检测到 GPU 时自动利用，无需用户配置
3. **智能调度** — 系统自己判断什么时候值得用 GPU，什么时候 CPU 就够了

### 3.5.2 硬件探测器 (HardwareProbe)

```python
# core/hardware.py — 启动时自动执行，全局单例
class HardwareProbe:
    """
    系统启动时自动探测硬件能力，结果缓存全局使用。
    不依赖任何 GPU 库——检测失败 = 纯 CPU 模式，不会报错。
    """
    
    @cached_property
    def profile(self) -> HardwareProfile:
        return HardwareProfile(
            cpu_cores=os.cpu_count(),
            ram_gb=psutil.virtual_memory().total / (1024**3),
            gpu=self._detect_gpu(),           # 可能为 None
            disk_type=self._detect_disk(),    # ssd / hdd
        )
    
    def _detect_gpu(self) -> GPUInfo | None:
        """安全检测 GPU，任何异常直接返回 None"""
        # 1. 尝试 CUDA (NVIDIA)
        try:
            import torch
            if torch.cuda.is_available():
                return GPUInfo(
                    type="cuda",
                    name=torch.cuda.get_device_name(0),
                    vram_gb=torch.cuda.get_device_properties(0).total_mem / (1024**3),
                )
        except ImportError:
            pass
        
        # 2. 尝试 DirectML (Windows 通用 GPU，AMD/Intel/NVIDIA 都支持)
        try:
            import torch_directml
            return GPUInfo(type="directml", name="DirectML Device", vram_gb=0)
        except ImportError:
            pass
        
        # 3. 无 GPU
        return None

    def recommend(self, task: str) -> ComputeDevice:
        """根据任务类型 + 硬件能力推荐计算设备"""
        gpu = self.profile.gpu
        
        match task:
            case "embedding":
                # 嵌入模型：小模型 CPU 够快，大模型才需要 GPU
                if gpu and gpu.vram_gb >= 2:
                    return "gpu"
                return "cpu"
            
            case "reranking":
                # Cross-Encoder 重排：计算密集，有 GPU 就用
                if gpu and gpu.vram_gb >= 2:
                    return "gpu"
                return "cpu"
            
            case "ocr":
                # OCR：PaddleOCR GPU 加速明显，但 CPU 也能跑
                if gpu and gpu.vram_gb >= 2:
                    return "gpu"
                return "cpu"
            
            case "llm_local":
                # 本地 LLM：强依赖 GPU，无 GPU 则建议用 API
                if gpu and gpu.vram_gb >= 4:
                    return "gpu"
                return "cpu_with_warning"  # 提示用户可能较慢
            
            case _:
                return "cpu"  # 默认 CPU
```

### 3.5.3 各模块 CPU 优化策略

```
┌──────────────┬──────────────────────────────┬──────────────────────────┐
│   模块        │   CPU 模式 (默认)             │   GPU 加速 (自动启用)     │
├──────────────┼──────────────────────────────┼──────────────────────────┤
│ Embedding    │ ONNX Runtime (CPU 优化)       │ CUDA / DirectML          │
│              │ 模型: multilingual-e5-small   │ 同模型，GPU 推理          │
│              │ 批量: 8 条/批                  │ 批量: 64 条/批            │
├──────────────┼──────────────────────────────┼──────────────────────────┤
│ Reranker     │ ONNX Runtime (CPU)            │ CUDA / DirectML          │
│              │ 模型: bge-reranker-v2-m3-mini │ 模型: bge-reranker-v2-m3 │
│              │ Top-K 预筛后再重排(减少计算量) │ 全量重排                  │
├──────────────┼──────────────────────────────┼──────────────────────────┤
│ FAISS 索引   │ faiss-cpu (自带 SIMD 优化)    │ faiss-gpu                │
│              │ 索引类型: Flat / IVF          │ 索引类型: IVF / HNSW     │
├──────────────┼──────────────────────────────┼──────────────────────────┤
│ OCR          │ PaddleOCR (CPU, mkldnn加速)   │ PaddleOCR (CUDA)         │
│              │ 或 Tesseract (纯CPU)          │                          │
├──────────────┼──────────────────────────────┼──────────────────────────┤
│ LLM 推理     │ API 调用 (推荐，零本地开销)    │ Ollama + GPU             │
│ (本地可选)   │ Ollama CPU (量化模型)          │ llama.cpp + CUDA         │
├──────────────┼──────────────────────────────┼──────────────────────────┤
│ Agent 编排   │ 纯逻辑，无计算开销             │ 不需要 GPU               │
│ Tool 调用    │ 纯 I/O，无计算开销             │ 不需要 GPU               │
│ gRPC 通信    │ 纯网络，无计算开销             │ 不需要 GPU               │
└──────────────┴──────────────────────────────┴──────────────────────────┘
```

### 3.5.4 CPU 性能优化技巧（全局贯穿）

```python
# 1. ONNX Runtime — 将 PyTorch 模型转为 ONNX，CPU 推理提速 2-5x
class ONNXEmbedder:
    """CPU 友好的嵌入推理，比原生 PyTorch 快 3 倍"""
    def __init__(self, model_path):
        import onnxruntime as ort
        providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
        # ONNX 自动选择可用的 Provider，CUDA 没装就自动回退 CPU
        self.session = ort.InferenceSession(model_path, providers=providers)

# 2. Embedding Cache — 相同文本不重复计算
# 已有 SQLite 缓存，升级为 LRU 内存缓存 + SQLite 持久化双层
class TieredEmbeddingCache:
    def __init__(self, memory_size=10000):
        self.l1 = LRUCache(memory_size)      # 内存，纳秒级
        self.l2 = SQLiteCache("embeddings")  # 磁盘，毫秒级

# 3. 惰性加载 — 模型按需加载，不用不占内存
class LazyModelLoader:
    """首次调用时才加载模型，节省启动时间和内存"""
    def __init__(self, model_factory):
        self._factory = model_factory
        self._model = None
    
    @property
    def model(self):
        if self._model is None:
            self._model = self._factory()
        return self._model

# 4. 异步非阻塞 — 等待 LLM API 响应时不阻塞 CPU
# FastAPI 天然 async，所有 I/O 操作使用 await

# 5. 批量处理 — 合并小请求为大批次，减少模型加载开销
class BatchProcessor:
    """收集 100ms 内的请求，合并为一个批次处理"""
    async def process(self, items, batch_size=8):
        for batch in chunked(items, batch_size):
            yield await self.model.encode_batch(batch)

# 6. 计划缓存 — 相似任务复用历史执行计划，跳过重复规划
class AgentPlanCache:
    """缓存 Agent 执行计划模板，相似任务直接复用，减少 LLM 调用"""
    async def get_or_plan(self, task, planner):
        similar = await self.find_similar(task, threshold=0.85)
        if similar:
            return self.adapt_plan(similar, task)  # 微调复用
        plan = await planner.plan(task)
        await self.save(task, plan)
        return plan
```

### 3.5.5 内存预算管理

```python
# 根据系统 RAM 自动调整各组件内存预算
class MemoryBudget:
    def __init__(self, total_ram_gb: float):
        if total_ram_gb <= 8:           # 8GB 及以下：极省模式
            self.embedding_model = "small"        # ~100MB
            self.faiss_max_vectors = 50_000
            self.embedding_cache_size = 5_000
            self.reranker = None                  # 不加载 Reranker
            self.batch_size = 4
        elif total_ram_gb <= 16:        # 16GB：标准模式
            self.embedding_model = "small"        # ~100MB
            self.faiss_max_vectors = 200_000
            self.embedding_cache_size = 20_000
            self.reranker = "mini"                # 小型 Reranker
            self.batch_size = 8
        else:                           # 16GB+：充裕模式
            self.embedding_model = "base"         # ~400MB
            self.faiss_max_vectors = 1_000_000
            self.embedding_cache_size = 100_000
            self.reranker = "full"                # 完整 Reranker
            self.batch_size = 16
```

### 3.5.6 用户无感知 — 系统启动日志示例

```
[ShadowLink] Hardware Detection:
  CPU: Intel i7-12700H (14 cores) ✓
  RAM: 16 GB ✓
  GPU: NVIDIA RTX 3060 Laptop (6GB VRAM) ✓
  Disk: NVMe SSD ✓

[ShadowLink] Compute Strategy:
  Embedding:  GPU (CUDA) — RTX 3060, batch_size=64
  Reranker:   GPU (CUDA) — bge-reranker-v2-m3
  FAISS:      CPU (AVX2 SIMD) — faiss-cpu, max 200K vectors
  OCR:        GPU (CUDA) — PaddleOCR
  LLM:        API (DeepSeek) — no local inference
  Memory:     Standard mode (16GB), cache=20K embeddings

[ShadowLink] All systems ready. CPU-first with GPU acceleration. ✓
```

```
[ShadowLink] Hardware Detection:
  CPU: Intel i5-1135G7 (4 cores) ✓
  RAM: 8 GB ⚠ (limited)
  GPU: None detected
  Disk: SSD ✓

[ShadowLink] Compute Strategy:
  Embedding:  CPU (ONNX Runtime) — multilingual-e5-small, batch_size=4
  Reranker:   DISABLED (RAM < 16GB) — using vector-only retrieval
  FAISS:      CPU — faiss-cpu, max 50K vectors
  OCR:        CPU — Tesseract (lighter than PaddleOCR)
  LLM:        API (DeepSeek) — recommended for CPU-only
  Memory:     Economy mode (8GB), cache=5K embeddings

[ShadowLink] All systems ready. Pure CPU mode. ✓
```

---

## 四、Java 后端（SpringBoot Gateway）

### 4.1 模块划分

```
shadowlink-server/
├── shadowlink-gateway/          # API 网关 & 路由 & 限流熔断
├── shadowlink-auth/             # 认证 & 授权 (Spring Security + JWT + RBAC)
├── shadowlink-session/          # 会话管理 (Redis-backed)
├── shadowlink-business/         # 业务 CRUD (模式、知识库、插件、用户配置)
├── shadowlink-websocket/        # WebSocket 实时推送 (Agent 流式输出)
├── shadowlink-ai-bridge/       # Python AI 服务桥接层 (gRPC Client)
├── shadowlink-common/           # 公共组件 (统一响应体、异常处理、工具类)
└── shadowlink-starter/          # 自动配置 & 启动器
```

### 4.2 核心能力详述

#### 4.2.1 认证与权限 (shadowlink-auth)

```java
// 基于 Spring Security 6 + JWT + RBAC
@Configuration
@EnableMethodSecurity
public class SecurityConfig {

    // JWT Token 体系
    // - Access Token (30min, 无状态)
    // - Refresh Token (7d, Redis 存储, 支持撤销)
    
    // RBAC 权限模型
    // User -> Role -> Permission
    // 支持数据权限 (行级隔离)
    // 支持 API 权限 (接口级控制)
}

// 权限注解
@PreAuthorize("@perm.check('agent:execute')")
@PreAuthorize("@perm.check('rag:admin')")
@PreAuthorize("@perm.check('mode:switch')")
```

#### 4.2.2 会话管理 (shadowlink-session)

```java
// Redis-backed 分布式会话
// 支持：多设备同步、会话恢复、上下文窗口管理

@Service
public class SessionService {
    // 会话生命周期
    // Create -> Active -> Idle -> Archive -> Delete
    
    // 会话元数据
    // - mode_id (当前氛围模式)
    // - agent_state (Agent 状态快照)
    // - rag_context (RAG 上下文缓存)
    // - message_window (滑动窗口消息)
}
```

#### 4.2.4 流量治理 (shadowlink-gateway)

```java
// 基于 Resilience4j 的流量治理
@RateLimiter(name = "agentExecute", fallbackMethod = "rateLimitFallback")
@CircuitBreaker(name = "pythonAI", fallbackMethod = "circuitBreakerFallback")
@Bulkhead(name = "agentPool", type = Bulkhead.Type.THREADPOOL)
@Retry(name = "agentRetry")
public AgentResponse executeAgent(AgentRequest request) {
    // 限流：令牌桶算法，每用户 10 req/min
    // 熔断：Python 服务不可用时快速失败
    // 隔舱：Agent 执行线程池隔离
    // 重试：网络抖动自动重试（非幂等操作除外）
}
```

#### 4.2.5 WebSocket Hub (shadowlink-websocket)

```java
// 全双工实时通信
@ServerEndpoint("/ws/chat/{sessionId}")
public class ChatWebSocket {
    // 消息类型：
    // - agent.token       : Agent 流式输出
    // - agent.tool_call   : 工具调用事件
    // - agent.tool_result : 工具执行结果
    // - agent.thought     : Agent 思考过程
    // - agent.plan        : Plan 步骤更新
    // - agent.status      : 状态变更
    // - rag.progress      : 索引构建进度
    // - mode.switch       : 模式切换通知
    // - system.heartbeat  : 心跳保活
}
```

#### 4.2.6 AI Bridge — Java 调用 Python 的桥接层

```java
@Service
public class AIBridgeService {

    @GrpcClient("python-ai-service")
    private AgentServiceGrpc.AgentServiceStub agentStub;

    /**
     * 流式 Agent 调用
     * Java 接收 gRPC stream -> 转换为 WebSocket 推送
     */
    public Flux<AgentChunk> streamExecute(AgentRequest request) {
        return Flux.create(sink -> {
            agentStub.streamExecute(request, new StreamObserver<AgentChunk>() {
                @Override
                public void onNext(AgentChunk chunk) {
                    sink.next(chunk);
                    // 同时通过 WebSocket 推送给前端
                    webSocketHub.send(request.getSessionId(), chunk);
                }
                @Override
                public void onCompleted() { sink.complete(); }
                @Override
                public void onError(Throwable t) { sink.error(t); }
            });
        });
    }
}
```

### 4.3 Spring Boot 技术栈

| 组件 | 技术选型 | 版本 |
|------|---------|------|
| 框架 | Spring Boot | 3.2+ |
| 安全 | Spring Security 6 + JWT | 6.2+ |
| ORM | MyBatis-Plus | 3.5+ |
| 缓存 | Redis (Lettuce) | 7.0+ |
| 数据库 | MySQL 8 / PostgreSQL 16 | - |
| gRPC | grpc-spring-boot-starter | 3.0+ |
| 限流 | Resilience4j | 2.2+ |
| 文档 | SpringDoc OpenAPI (Swagger) | 2.3+ |
| 监控 | Micrometer + Prometheus | - |
| 日志 | SLF4J + Logback + ELK-ready | - |
| 消息 | Spring WebSocket + STOMP | - |

---

## 五、Python AI 服务层

### 5.1 模块架构

```
shadowlink-ai/
├── app/
│   ├── main.py                      # FastAPI 入口
│   ├── config.py                    # 配置加载 (Pydantic Settings)
│   │
│   ├── api/                         # API 层
│   │   ├── v1/
│   │   │   ├── agent_router.py      # Agent 相关接口
│   │   │   ├── rag_router.py        # RAG 相关接口
│   │   │   ├── mcp_router.py        # MCP 工具接口
│   │   │   └── file_router.py       # 文件处理接口
│   │   └── grpc/
│   │       ├── agent_servicer.py    # gRPC Agent 服务实现
│   │       ├── rag_servicer.py      # gRPC RAG 服务实现
│   │       └── mcp_servicer.py      # gRPC MCP 服务实现
│   │
│   ├── agent/                       # Agent 核心引擎
│   │   ├── engine.py                # Agent 统一入口
│   │   ├── react/                   # ReAct 循环实现
│   │   │   ├── graph.py             # LangGraph ReAct 图定义
│   │   │   └── nodes.py             # 节点实现
│   │   ├── plan_execute/            # Plan-and-Execute 实现
│   │   │   ├── planner.py           # 计划生成器
│   │   │   ├── executor.py          # 步骤执行器
│   │   │   ├── replan.py            # 动态重规划
│   │   │   └── graph.py             # LangGraph Plan 图定义
│   │   ├── multi_agent/             # MultiAgent 编排
│   │   │   ├── supervisor.py        # Supervisor 模式
│   │   │   ├── hierarchical.py      # 层级式编排
│   │   │   ├── swarm.py             # Swarm 协作模式
│   │   │   └── hermes.py            # Hermes Agent 协议实现
│   │   ├── memory/                  # Agent 记忆系统
│   │   │   ├── short_term.py        # 短期记忆 (会话内)
│   │   │   ├── long_term.py         # 长期记忆 (跨会话)
│   │   │   ├── episodic.py          # 情景记忆 (事件序列)
│   │   │   └── semantic.py          # 语义记忆 (知识图谱)
│   │   └── state.py                 # Agent 状态定义
│   │
│   ├── rag/                         # RAG 高级引擎
│   │   ├── engine.py                # RAG 统一入口
│   │   ├── chunking/                # 分块策略
│   │   │   ├── semantic.py          # 语义分块
│   │   │   ├── recursive.py         # 递归分块
│   │   │   └── agentic.py           # Agent 驱动的智能分块
│   │   ├── embedding/               # 嵌入引擎
│   │   │   ├── local.py             # 本地模型 (E5, BGE)
│   │   │   └── api.py               # API 嵌入 (OpenAI, etc.)
│   │   ├── retrieval/               # 检索策略
│   │   │   ├── vector.py            # 向量检索
│   │   │   ├── bm25.py              # BM25 关键词检索
│   │   │   ├── hybrid.py            # 混合检索 (RRF 融合)
│   │   │   ├── multi_query.py       # 多查询扩展
│   │   │   └── self_rag.py          # Self-RAG 自反思检索
│   │   ├── reranking/               # 重排序
│   │   │   ├── cross_encoder.py     # 交叉编码器重排
│   │   │   └── llm_rerank.py        # LLM 重排
│   │   └── index/                   # 索引管理
│   │       ├── faiss_index.py       # FAISS 索引
│   │       ├── milvus_index.py      # Milvus Lite 索引
│   │       └── manager.py           # 索引生命周期管理
│   │
│   ├── mcp/                         # MCP 协议层
│   │   ├── server.py                # MCP Server 实现
│   │   ├── client.py                # MCP Client (调用外部工具)
│   │   ├── registry.py              # 工具注册中心
│   │   └── adapters/                # 协议适配器
│   │       ├── langchain_adapter.py # LangChain Tool -> MCP
│   │       └── openai_adapter.py    # OpenAI Function -> MCP
│   │
│   ├── tools/                       # 内置工具集
│   │   ├── base.py                  # 工具基类
│   │   ├── web_search.py            # 网络搜索
│   │   ├── code_executor.py         # 代码执行沙盒
│   │   ├── file_ops.py              # 文件操作
│   │   ├── knowledge_search.py      # 知识库搜索
│   │   └── system_tools.py          # 系统工具
│   │
│   ├── plugins/                     # 插件系统
│   │   ├── loader.py                # 插件加载器
│   │   ├── interface.py             # 插件接口定义
│   │   └── builtin/                 # 内置插件
│   │       ├── pdf_plugin.py
│   │       ├── docx_plugin.py
│   │       ├── excel_plugin.py
│   │       └── image_plugin.py
│   │
│   ├── file_processing/             # 文件处理管线
│   │   ├── pipeline.py              # 处理管线编排
│   │   ├── parsers/                 # 格式解析器
│   │   │   ├── pdf_parser.py        # PDF (PyMuPDF + Marker)
│   │   │   ├── docx_parser.py       # Word
│   │   │   ├── xlsx_parser.py       # Excel
│   │   │   ├── pptx_parser.py       # PowerPoint
│   │   │   ├── markdown_parser.py   # Markdown
│   │   │   ├── code_parser.py       # 源代码 (Tree-sitter AST)
│   │   │   └── image_parser.py      # 图片 OCR (Tesseract/PaddleOCR)
│   │   └── extractors/             # 结构提取器
│   │       ├── table_extractor.py   # 表格提取
│   │       ├── formula_extractor.py # 公式提取 (LaTeX)
│   │       └── metadata_extractor.py# 元数据提取
│   │
│   ├── llm/                         # LLM 客户端
│   │   ├── client.py                # 统一 LLM 客户端
│   │   ├── providers/               # 提供商适配
│   │   │   ├── openai.py
│   │   │   ├── deepseek.py
│   │   │   ├── ollama.py
│   │   │   └── anthropic.py
│   │   └── middleware/              # 中间件
│   │       ├── token_counter.py     # Token 计数
│   │       ├── rate_limiter.py      # 限流
│   │       └── cache.py             # 语义缓存
│   │
│   └── models/                      # 数据模型 (Pydantic)
│       ├── agent.py
│       ├── rag.py
│       ├── mcp.py
│       └── common.py
│
├── proto/                           # gRPC Proto 定义
│   ├── agent_service.proto
│   ├── rag_service.proto
│   └── mcp_service.proto
│
├── tests/                           # 测试
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── pyproject.toml                   # 项目配置
└── Dockerfile                       # 容器化
```

### 5.2 Agent 引擎核心设计

#### 5.2.1 ReAct 循环 (Reasoning + Acting)

```python
# agent/react/graph.py
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

class ReactGraph:
    """
    ReAct 循环：Thought -> Action -> Observation -> Repeat
    
    适用场景：
    - 简单问答 + 工具调用
    - 实时交互式任务
    - 信息检索与聚合
    """
    
    def build(self, tools, llm, config):
        graph = StateGraph(AgentState)
        
        graph.add_node("reason", self.reason_node)       # LLM 推理
        graph.add_node("act", ToolNode(tools))            # 工具执行
        graph.add_node("reflect", self.reflect_node)      # 反思节点 (可选)
        
        graph.add_edge(START, "reason")
        graph.add_conditional_edges("reason", self.should_act, {
            "act": "act",
            "reflect": "reflect",
            "end": END,
        })
        graph.add_edge("act", "reason")
        graph.add_edge("reflect", "reason")
        
        return graph.compile(checkpointer=MemorySaver())
```

#### 5.2.2 Plan-and-Execute

```python
# agent/plan_execute/graph.py
class PlanExecuteGraph:
    """
    Plan-and-Execute：先规划，再逐步执行，可动态重规划
    
    适用场景：
    - 复杂多步骤任务
    - 论文研读 & 报告生成
    - 项目管理 & 任务分解
    """
    
    def build(self, tools, llm, config):
        graph = StateGraph(PlanExecuteState)
        
        graph.add_node("planner", self.plan_node)          # 生成计划
        graph.add_node("executor", self.execute_step_node)  # 执行单步
        graph.add_node("replanner", self.replan_node)       # 动态重规划
        graph.add_node("reporter", self.report_node)        # 结果汇报
        
        graph.add_edge(START, "planner")
        graph.add_edge("planner", "executor")
        graph.add_conditional_edges("executor", self.check_progress, {
            "continue": "executor",      # 继续执行下一步
            "replan": "replanner",       # 需要重规划
            "report": "reporter",        # 所有步骤完成
        })
        graph.add_edge("replanner", "executor")
        graph.add_edge("reporter", END)
        
        return graph.compile(checkpointer=MemorySaver())
    
    def plan_node(self, state):
        """生成结构化执行计划"""
        plan = self.planner_llm.invoke([
            SystemMessage(content=PLANNER_PROMPT),
            HumanMessage(content=state["input"]),
        ])
        return {"plan": parse_plan(plan), "step_index": 0}
    
    def replan_node(self, state):
        """根据执行结果动态调整计划"""
        new_plan = self.planner_llm.invoke([
            SystemMessage(content=REPLANNER_PROMPT),
            HumanMessage(content=f"""
                原始计划: {state['plan']}
                已完成步骤: {state['completed_steps']}
                当前问题: {state['current_issue']}
                请重新规划剩余步骤。
            """),
        ])
        return {"plan": parse_plan(new_plan)}
```

#### 5.2.3 MultiAgent 编排

```python
# agent/multi_agent/supervisor.py
class SupervisorMultiAgent:
    """
    Supervisor 模式：一个主管 Agent 协调多个专家 Agent
    
    拓扑：
    ┌──────────┐
    │Supervisor│──────┬──────┬──────┬──────┐
    └──────────┘      │      │      │      │
               ┌──────┴┐ ┌──┴───┐ ┌┴────┐ ┌┴──────┐
               │Coder  │ │Writer│ │RAG  │ │Review │
               │Agent  │ │Agent │ │Agent│ │Agent  │
               └───────┘ └──────┘ └─────┘ └───────┘
    """
    
    def build(self):
        # 定义专家 Agent
        coder = create_react_agent(tools=code_tools, llm=code_llm)
        writer = create_react_agent(tools=write_tools, llm=write_llm)
        rag_expert = create_react_agent(tools=rag_tools, llm=rag_llm)
        reviewer = create_react_agent(tools=review_tools, llm=review_llm)
        
        # Supervisor 决策
        graph = StateGraph(SupervisorState)
        graph.add_node("supervisor", self.supervisor_node)
        graph.add_node("coder", coder)
        graph.add_node("writer", writer)
        graph.add_node("rag_expert", rag_expert)
        graph.add_node("reviewer", reviewer)
        
        # Supervisor 根据任务类型路由到专家
        graph.add_conditional_edges("supervisor", self.route, {
            "coder": "coder",
            "writer": "writer",
            "rag_expert": "rag_expert",
            "reviewer": "reviewer",
            "FINISH": END,
        })
        
        # 专家完成后回到 Supervisor
        for agent in ["coder", "writer", "rag_expert", "reviewer"]:
            graph.add_edge(agent, "supervisor")
        
        return graph.compile()


# agent/multi_agent/hermes.py
class HermesAgent:
    """
    Hermes Agent 协议实现
    
    特点：
    - 自描述能力：每个 Agent 声明自己的能力边界
    - 动态发现：Agent 运行时注册和发现
    - 异步消息传递：Agent 间通过消息队列通信
    - 协商协议：多 Agent 通过协商达成一致
    """
    
    def __init__(self, name, capabilities, tools):
        self.name = name
        self.capabilities = capabilities  # 能力声明
        self.tools = tools
        self.inbox = asyncio.Queue()      # 消息收件箱
        self.registry = AgentRegistry()   # 全局注册中心
    
    async def register(self):
        """向注册中心注册自身能力"""
        await self.registry.register(AgentDescriptor(
            name=self.name,
            capabilities=self.capabilities,
            endpoint=self.endpoint,
        ))
    
    async def delegate(self, task, required_capability):
        """根据能力需求委派任务给合适的 Agent"""
        candidates = await self.registry.find_by_capability(required_capability)
        best = self.select_best(candidates, task)
        response = await best.handle(task)
        return response
    
    async def negotiate(self, agents, task):
        """多 Agent 协商机制"""
        proposals = await asyncio.gather(*[
            agent.propose(task) for agent in agents
        ])
        consensus = self.evaluate_proposals(proposals)
        return consensus
```

#### 5.2.4 Agent 状态与 Graph 流转

```python
# agent/state.py
from typing import TypedDict, Annotated, Sequence
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    """ReAct Agent 状态"""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    mode_id: str                          # 当前氛围模式
    tools_available: list[str]            # 可用工具列表
    memory_context: dict                  # 记忆上下文
    rag_context: str                      # RAG 检索结果
    iteration_count: int                  # 迭代计数 (防无限循环)
    max_iterations: int                   # 最大迭代次数

class PlanExecuteState(TypedDict):
    """Plan-and-Execute Agent 状态"""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    input: str                            # 原始输入
    plan: list[PlanStep]                  # 执行计划
    step_index: int                       # 当前步骤
    step_results: list[StepResult]        # 步骤结果
    completed_steps: list[str]            # 已完成步骤描述
    current_issue: str | None             # 当前问题 (触发重规划)
    final_answer: str | None              # 最终答案

class SupervisorState(TypedDict):
    """Supervisor MultiAgent 状态"""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    task: str
    current_agent: str | None
    agent_results: dict[str, str]         # 各 Agent 返回结果
    delegation_history: list[Delegation]  # 委派历史
    next_action: str                      # supervisor 决策
```

### 5.3 Python 技术栈

| 组件 | 技术选型 | 说明 |
|------|---------|------|
| Web 框架 | FastAPI 0.110+ | 异步、自动文档、Pydantic 集成 |
| gRPC | grpcio + grpcio-tools | Java 高性能通信 |
| Agent | LangGraph 0.2+ | 状态图引擎 |
| LLM | LangChain 0.3+ | LLM 抽象层 |
| 向量搜索 | FAISS + Milvus Lite | 本地 + 可扩展 |
| 嵌入 | SentenceTransformers | 本地嵌入模型 |
| 重排 | FlagEmbedding (BGE) | Cross-Encoder 重排 |
| 文件解析 | PyMuPDF, python-docx, openpyxl | 多格式支持 |
| OCR | PaddleOCR / Tesseract | 图片文字识别 |
| 代码沙盒 | RestrictedPython / Docker | 安全代码执行 |
| 异步 | asyncio + uvloop | 高性能事件循环 |
| 验证 | Pydantic V2 | 数据模型 & 配置 |
| 测试 | pytest + pytest-asyncio | 测试框架 |
| 日志 | structlog | 结构化日志 |

---

## 六、前端架构（Web UI）

### 6.1 技术栈

| 组件 | 技术选型 | 说明 |
|------|---------|------|
| 框架 | React 18 + TypeScript | 组件化 + 类型安全 |
| 构建 | Vite 5 | 极速 HMR |
| 状态管理 | Zustand + React Query | 轻量 + 服务端状态 |
| UI 组件 | Shadcn/UI + Radix | 可定制、无样式锁定 |
| 样式 | Tailwind CSS 3 + CSS Variables | 原子化 + 动态主题 |
| 路由 | React Router 6 | SPA 路由 |
| WebSocket | Socket.IO Client | 实时通信 |
| 图表 | Recharts | 数据可视化 |
| Markdown | react-markdown + KaTeX | 渲染 + 公式 |
| 代码高亮 | Shiki | 语法高亮 |
| 动画 | Framer Motion | 氛围切换动画 |
| 桌面集成 | Electron (可选) | 全局热键、托盘 |

### 6.2 页面结构

```
┌──────────────────────────────────────────────────────────┐
│  ┌─────┐  ShadowLink                    [模式切换] [设置] │  <- TopBar
│  │ Logo│  ────────────────────────────                    │
├──┼─────┼──────────────────────────────────────────────────┤
│  │     │                                                  │
│  │ 导  │  ┌──────────────────────────────────────────┐   │
│  │ 航  │  │                                          │   │
│  │ 栏  │  │           主内容区                        │   │
│  │     │  │     (根据氛围模式动态变化)                  │   │
│  │ ·会 │  │                                          │   │
│  │  话 │  │  ┌────────────┐ ┌─────────────────────┐  │   │
│  │ ·知 │  │  │ Agent 面板  │ │ 对话 / 工作面板      │  │   │
│  │  识 │  │  │ 思考过程    │ │ 流式输出             │  │   │
│  │  库 │  │  │ 工具调用    │ │ 富文本渲染           │  │   │
│  │ ·工 │  │  │ 计划进度    │ │ 代码块 + 预览        │  │   │
│  │  具 │  │  └────────────┘ └─────────────────────┘  │   │
│  │ ·插 │  │                                          │   │
│  │  件 │  │  ┌──────────────────────────────────────┐│   │
│  │     │  │  │ 输入区：消息 + 文件拖放 + 语音       ││   │
│  │     │  │  └──────────────────────────────────────┘│   │
│  │     │  └──────────────────────────────────────────┘   │
├──┴─────┴──────────────────────────────────────────────────┤
│  [氛围状态指示器]  Agent: ReAct | 模式: 论文研读 | RAG: 3 │  <- StatusBar
└──────────────────────────────────────────────────────────┘
```

### 6.3 氛围感 Theme Engine

```typescript
// theme/ambient-engine.ts
interface AmbientTheme {
  id: string;
  name: string;
  colors: {
    primary: string;
    background: string;
    surface: string;
    text: string;
    accent: string;
    gradient: string;
  };
  typography: {
    fontFamily: string;
    codeFont: string;
  };
  ambient: {
    animation: 'none' | 'particles' | 'matrix_rain' | 'aurora' | 'fireflies';
    backgroundEffect: 'static' | 'gradient_shift' | 'mesh_gradient';
    transitionDuration: number;  // ms
  };
  layout: {
    sidebarWidth: number;
    panelRatio: [number, number];  // [agent面板, 对话面板]
  };
}

// 模式切换时的渐变动画
const switchAmbientMode = async (newTheme: AmbientTheme) => {
  // 1. CSS Variable 渐变过渡
  document.documentElement.style.setProperty('--transition-duration', `${newTheme.ambient.transitionDuration}ms`);
  
  // 2. 更新所有 CSS Variables
  Object.entries(newTheme.colors).forEach(([key, value]) => {
    document.documentElement.style.setProperty(`--color-${key}`, value);
  });
  
  // 3. 切换氛围动画
  await ambientRenderer.transition(newTheme.ambient.animation);
  
  // 4. 调整布局
  layoutStore.setPanelRatio(newTheme.layout.panelRatio);
};
```

### 6.4 核心组件

```
src/
├── components/
│   ├── chat/
│   │   ├── ChatPanel.tsx            # 对话面板
│   │   ├── MessageBubble.tsx        # 消息气泡 (支持 Markdown/代码/图片)
│   │   ├── StreamingDisplay.tsx     # 流式输出显示
│   │   ├── InputArea.tsx            # 输入区 (文本+文件+语音)
│   │   └── FileDropZone.tsx         # 文件拖放区
│   │
│   ├── agent/
│   │   ├── AgentPanel.tsx           # Agent 面板
│   │   ├── ThoughtProcess.tsx       # 思考过程可视化
│   │   ├── ToolCallCard.tsx         # 工具调用卡片
│   │   ├── PlanProgress.tsx         # Plan 步骤进度
│   │   └── MultiAgentFlow.tsx       # MultiAgent 流程图
│   │
│   ├── ambient/
│   │   ├── AmbientProvider.tsx      # 氛围上下文提供者
│   │   ├── ModeSwitcher.tsx         # 模式切换器
│   │   ├── AmbientBackground.tsx    # 氛围背景动画
│   │   └── StatusBar.tsx            # 状态栏
│   │
│   ├── knowledge/
│   │   ├── KnowledgeBase.tsx        # 知识库管理
│   │   ├── DocumentList.tsx         # 文档列表
│   │   ├── IndexProgress.tsx        # 索引进度
│   │   └── RetrievalResults.tsx     # 检索结果展示
│   │
│   ├── plugins/
│   │   ├── PluginMarket.tsx         # 插件市场
│   │   ├── PluginCard.tsx           # 插件卡片
│   │   └── PluginSettings.tsx       # 插件配置
│   │
│   └── settings/
│       ├── LLMConfig.tsx            # LLM 配置
│       ├── ModeEditor.tsx           # 模式编辑器
│       └── SystemSettings.tsx       # 系统设置
│
├── hooks/
│   ├── useWebSocket.ts              # WebSocket Hook
│   ├── useAgent.ts                  # Agent 交互 Hook
│   ├── useAmbient.ts                # 氛围模式 Hook
│   └── useRAG.ts                    # RAG 操作 Hook
│
├── stores/
│   ├── chatStore.ts                 # 对话状态
│   ├── agentStore.ts                # Agent 状态
│   ├── ambientStore.ts              # 氛围模式状态
│   └── settingsStore.ts             # 设置状态
│
├── theme/
│   ├── ambient-engine.ts            # 氛围引擎
│   ├── themes/                      # 预设主题
│   │   ├── paper-reading.ts
│   │   ├── code-dev.ts
│   │   ├── creative-writing.ts
│   │   ├── project-management.ts
│   │   ├── data-analysis.ts
│   │   └── daily-assistant.ts
│   └── animations/                  # 氛围动画
│       ├── particles.ts
│       ├── matrix-rain.ts
│       ├── aurora.ts
│       └── fireflies.ts
│
└── services/
    ├── api.ts                       # REST API Client
    ├── websocket.ts                 # WebSocket Manager
    └── grpc-web.ts                  # gRPC-Web Client (可选)
```

---

## 七、Agent 系统深度设计

### 7.1 Agent 能力全景

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ShadowLink Agent 能力谱                           │
│                                                                     │
│  ┌─ 执行策略层 ──────────────────────────────────────────────────┐  │
│  │  Direct Chat ◄──► ReAct ◄──► Plan-and-Execute ◄──► MultiAgent│  │
│  │       ▲                                                ▲      │  │
│  │       └──── TaskComplexityRouter 自动选择 ──────────────┘      │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌─ 推理增强层 ──────────────────────────────────────────────────┐  │
│  │  Reflexion (自我反思)  │  Agent-as-Judge (质量评审)            │  │
│  │  Plan Cache (计划复用) │  Speculative Exec (推测并行)          │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌─ 记忆层 ──────────────────────────────────────────────────────┐  │
│  │  Letta 三层记忆: Core ↔ Recall ↔ Archival                    │  │
│  │  Sleep-Time Compute: 空闲时异步整理记忆                        │  │
│  │  Mode-Scoped Namespace: 每个氛围模式独立记忆                   │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌─ 技能学习层 ──────────────────────────────────────────────────┐  │
│  │  Hermes Skill Learning: 复杂任务自动沉淀为可复用技能           │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 7.2 统一引擎 + 自动路由

```python
# agent/engine.py
class AgentEngine:
    """
    Agent 统一入口。
    用户说 "auto" → TaskComplexityRouter 自动判断策略。
    用户指定策略 → 直接用。
    """
    
    STRATEGY_MAP = {
        "chat": DirectChatHandler,             # 直接对话，0 开销
        "react": ReactGraph,                   # ReAct 循环
        "plan_and_execute": PlanExecuteGraph,   # Plan-and-Execute
        "supervisor": SupervisorMultiAgent,     # Supervisor MultiAgent
    }
    
    async def execute(
        self,
        session_id: str,
        mode_id: str,
        messages: list[Message],
        strategy: str = "auto",               # 默认自动
        config: AgentConfig | None = None,
    ) -> AsyncIterator[AgentChunk]:
        
        # 1. 加载氛围模式
        mode = self.mode_registry.get(mode_id)
        
        # 2. 路由策略：用户选了就用用户的，否则自动
        resolved_strategy = self.router.route(
            query=messages[-1].content,
            mode=mode,
            user_override=strategy if strategy != "auto" else None,
        )
        
        # 3. 构建工具集（模式内置 + 用户额外 + 插件）
        tools = self.build_tools(mode)
        
        # 4. 加载记忆 (Letta 三层)
        memory = await self.memory_manager.load(
            session_id, mode.memory_namespace
        )
        
        # 5. RAG 预检索 (Adaptive RAG，按需检索)
        rag_context = await self.rag_engine.adaptive_retrieve(
            query=messages[-1].content,
            mode_config=mode.rag,
        )
        
        # 6. 构建并执行
        handler = self.STRATEGY_MAP[resolved_strategy]
        graph = handler().build(tools, self.llm, config)
        
        initial_state = AgentState(
            messages=messages,
            mode_id=mode_id,
            tools_available=[t.name for t in tools],
            memory_context=memory,
            rag_context=rag_context,
        )
        
        async for event in graph.astream_events(initial_state, version="v2"):
            chunk = self.transform_event(event)
            yield chunk
        
        # 7. 后处理：保存记忆 + Reflexion + 技能沉淀
        await self._post_execute(session_id, mode, state, resolved_strategy)
    
    async def _post_execute(self, session_id, mode, state, strategy):
        """执行后处理（异步，不阻塞用户）"""
        # 保存短期记忆
        await self.memory_manager.save(session_id, mode.memory_namespace, state)
        
        # Hermes 技能沉淀：复杂任务自动提取为可复用技能
        if strategy in ("plan_and_execute", "supervisor"):
            await self.skill_learner.maybe_extract(state)
```

### 7.3 ReAct + Reflexion（自我反思增强）

```python
# agent/react/graph.py
class ReactGraph:
    """
    ReAct + Reflexion：基础 ReAct 循环，失败时自动反思并重试。
    
    流程：
    Thought → Action → Observation → [成功 → 回答]
                                     [失败 → Reflect → Retry]
    
    CPU 开销：低。Reflexion 只在失败时触发，不增加正常路径开销。
    """
    
    def build(self, tools, llm, config):
        graph = StateGraph(AgentState)
        
        graph.add_node("reason", self.reason_node)
        graph.add_node("act", ToolNode(tools))
        graph.add_node("reflect", self.reflect_node)  # Reflexion 节点
        
        graph.add_edge(START, "reason")
        graph.add_conditional_edges("reason", self.should_act, {
            "act": "act",
            "end": END,
        })
        graph.add_conditional_edges("act", self.check_result, {
            "success": "reason",          # 正常继续
            "failure": "reflect",         # 失败 → 反思
        })
        graph.add_edge("reflect", "reason")  # 反思后带着经验重试
        
        return graph.compile(checkpointer=MemorySaver())
    
    async def reflect_node(self, state):
        """
        Reflexion：分析失败原因，生成 verbal feedback 注入下次推理。
        不增加工具调用，只是一次额外 LLM 调用。
        """
        last_error = state["messages"][-1]  # 工具报错信息
        
        reflection = await self.llm.ainvoke([
            SystemMessage(content="分析上一步失败的原因，给出改进建议。简洁扼要，3 句以内。"),
            HumanMessage(content=f"失败信息：{last_error.content}"),
        ])
        
        # 将反思结果注入 Agent 的工作记忆
        return {
            "messages": [SystemMessage(content=f"[自我反思] {reflection.content}")],
            "reflection_count": state.get("reflection_count", 0) + 1,
        }
    
    def check_result(self, state):
        """失败检测 + 反思次数限制（防止无限循环）"""
        last_msg = state["messages"][-1]
        is_error = hasattr(last_msg, "status") and last_msg.status == "error"
        
        if is_error and state.get("reflection_count", 0) < 2:
            return "failure"   # 最多反思 2 次
        return "success"
```

### 7.4 Plan-and-Execute + 动态重规划

```python
# agent/plan_execute/graph.py
class PlanExecuteGraph:
    """
    Plan → Execute → Observe → [Replan if needed] → Continue
    
    特点：
    - Plan Cache: 相似任务复用历史计划（减少 LLM 调用，CPU 友好）
    - 动态 Replan: 执行中发现问题自动调整
    - 并行执行: 无依赖的步骤并发运行
    """
    
    def build(self, tools, llm, config):
        graph = StateGraph(PlanExecuteState)
        
        graph.add_node("planner", self.plan_node)
        graph.add_node("executor", self.execute_step_node)
        graph.add_node("replanner", self.replan_node)
        graph.add_node("reporter", self.report_node)
        
        graph.add_edge(START, "planner")
        graph.add_edge("planner", "executor")
        graph.add_conditional_edges("executor", self.check_progress, {
            "continue": "executor",
            "replan": "replanner",
            "report": "reporter",
        })
        graph.add_edge("replanner", "executor")
        graph.add_edge("reporter", END)
        
        return graph.compile(checkpointer=MemorySaver())
    
    async def plan_node(self, state):
        """
        生成计划。优先从 PlanCache 中查找相似任务的历史计划。
        命中缓存时 0 LLM 调用，极省资源。
        """
        # 尝试复用历史计划
        cached = await self.plan_cache.get_or_plan(
            task=state["input"],
            planner=self._generate_plan,
        )
        return {"plan": cached, "step_index": 0}
    
    async def execute_step_node(self, state):
        """执行计划中的单个步骤，用 ReAct 子循环完成"""
        step = state["plan"][state["step_index"]]
        
        # 每个步骤用一个轻量 ReAct Agent 执行
        step_result = await self.step_agent.execute(
            task=step.description,
            tools=state["tools"],
            context=state["step_results"],  # 前序步骤结果作为上下文
        )
        
        return {
            "step_results": state["step_results"] + [step_result],
            "step_index": state["step_index"] + 1,
        }
```

### 7.5 MultiAgent 编排

```
┌──────────────────────────────────────────────────────┐
│               MultiAgent 拓扑（按需自动选择）          │
├────────────────┬─────────────────┬───────────────────┤
│   Supervisor   │   Debate/Judge  │   Swarm           │
│   (主管式)     │   (辩论+评审)    │   (群体协作)      │
│                │                 │                   │
│  ┌───┐         │  ┌─┐   ┌─┐     │  ┌─┐ ┌─┐ ┌─┐    │
│  │ S │         │  │A│◄─►│B│     │  │A├─┤B├─┤C│    │
│  └┬┬┬┘         │  └┬┘   └┬┘     │  └┬┘ └┬┘ └┬┘    │
│   │││          │   └──┬──┘      │   └───┼───┘     │
│  ┌┘│└┐         │   ┌──┴──┐      │       │          │
│  A B C         │   │Judge│      │  自组织协作       │
│                │   └─────┘      │                   │
│  适用：         │  适用：         │  适用：           │
│  明确分工       │  需要高质量输出  │  探索性任务        │
│  任务型工作     │  代码审查        │  头脑风暴          │
│                │  方案评估        │  创意协作          │
└────────────────┴─────────────────┴───────────────────┘
```

```python
# agent/multi_agent/debate.py
class AgentDebateProtocol:
    """
    Agent-as-Judge + 多 Agent 辩论
    
    前沿方法 (ICLR 2025 CourtEval):
    多个 Agent 各自生成方案 → 结构化辩论(2-3 轮) → Judge Agent 裁决
    
    比单 Agent 输出质量高 15-30%（论文数据），
    但 LLM 调用量 x3-5，仅用于高价值任务。
    CPU 开销：高（多次 LLM 调用），但都是 API 调用，不消耗本地 CPU。
    """
    
    async def debate_and_judge(self, task, agents, judge, rounds=2):
        # 1. 各 Agent 独立提案
        proposals = await asyncio.gather(*[
            agent.propose(task) for agent in agents
        ])
        
        # 2. 结构化辩论（每个 Agent 可以质疑和回应）
        for round_num in range(rounds):
            critiques = await asyncio.gather(*[
                agent.critique(proposals, exclude_self=True)
                for agent in agents
            ])
            proposals = await asyncio.gather(*[
                agent.revise(proposals[i], critiques[i])
                for i, agent in enumerate(agents)
            ])
        
        # 3. Judge 裁决
        verdict = await judge.evaluate(proposals, criteria=task.quality_criteria)
        return verdict.best_proposal


# agent/multi_agent/supervisor.py
class SupervisorMultiAgent:
    """
    Supervisor 模式：一个主管 Agent 协调多个专家 Agent。
    LangGraph 原生支持。
    """
    
    def build(self):
        graph = StateGraph(SupervisorState)
        
        # 注册专家
        experts = {
            "researcher": create_react_agent(tools=search_tools),
            "writer": create_react_agent(tools=write_tools),
            "coder": create_react_agent(tools=code_tools),
            "analyst": create_react_agent(tools=data_tools),
        }
        
        graph.add_node("supervisor", self.supervisor_node)
        for name, agent in experts.items():
            graph.add_node(name, agent)
        
        # Supervisor 路由 + 专家回报
        graph.add_conditional_edges("supervisor", self.route,
            {name: name for name in experts} | {"FINISH": END})
        for name in experts:
            graph.add_edge(name, "supervisor")
        
        return graph.compile()
```

### 7.6 Hermes 技能学习 — Agent 越用越聪明

```python
# agent/skill_learning/hermes.py
class HermesSkillLearner:
    """
    Hermes Agent 核心创新：闭环技能学习。
    
    当 Agent 完成一个复杂任务（≥5 步工具调用）后，
    自动将执行轨迹提炼为「可复用技能」。
    
    下次遇到相似任务时，直接调用技能，跳过重复推理。
    Agent 越用越快、越用越准。
    
    CPU 开销：技能提取异步执行，不阻塞用户；技能调用几乎零开销。
    """
    
    async def maybe_extract(self, execution_state: AgentState):
        """判断是否值得提取技能"""
        trajectory = execution_state["messages"]
        tool_calls = [m for m in trajectory if m.type == "tool"]
        
        # 只有复杂任务才值得沉淀
        if len(tool_calls) < 5:
            return
        
        # 异步提取，不阻塞
        asyncio.create_task(self._extract_skill(trajectory))
    
    async def _extract_skill(self, trajectory):
        """从执行轨迹提炼技能"""
        skill = await self.llm.ainvoke([
            SystemMessage(content=SKILL_EXTRACTION_PROMPT),
            HumanMessage(content=f"""
                执行轨迹：{self.summarize(trajectory)}
                请提炼为一个可复用的技能文档，包含：
                1. 技能名称和描述
                2. 适用场景（什么任务应该触发此技能）
                3. 步骤模板（参数化的执行步骤）
                4. 注意事项（从执行中学到的经验）
            """),
        ])
        
        parsed = SkillDocument.parse(skill.content)
        await self.skill_store.save(parsed)
    
    async def find_applicable_skill(self, task: str) -> SkillDocument | None:
        """查找可复用技能（向量相似度匹配）"""
        return await self.skill_store.search(task, threshold=0.8)
    
    # 技能随时间自我改进
    async def improve_skill(self, skill_id, new_trajectory):
        """技能执行后，根据新轨迹更新技能文档"""
        existing = await self.skill_store.get(skill_id)
        improved = await self.llm.ainvoke([
            SystemMessage(content="比较旧技能文档和新执行轨迹，生成改进版。"),
            HumanMessage(content=f"旧版：{existing}\n新执行：{self.summarize(new_trajectory)}"),
        ])
        await self.skill_store.update(skill_id, improved)
```

### 7.7 Letta 三层记忆 (MemGPT 架构)

```
┌─────────────────────────────────────────────────────┐
│              Letta (MemGPT) 三层记忆架构              │
│                                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │  Core Memory (核心记忆)                      │    │
│  │  · 始终在 LLM 上下文窗口中                    │    │
│  │  · Agent 可自行编辑 (tool: core_memory_edit)  │    │
│  │  · 存储：用户画像、当前任务要点、模式规则      │    │
│  │  · 大小限制：~2000 tokens                     │    │
│  └──────────────────┬──────────────────────────┘    │
│                     │ Agent 主动读写                  │
│  ┌──────────────────┴──────────────────────────┐    │
│  │  Recall Memory (回忆记忆)                    │    │
│  │  · 对话历史的向量化存储                       │    │
│  │  · Agent 按需检索 (tool: recall_search)       │    │
│  │  · "上次我们讨论过 XX 吗？" → 自动搜索        │    │
│  │  · 存储：SQLite + FAISS 双索引               │    │
│  └──────────────────┬──────────────────────────┘    │
│                     │ Agent 按需检索                  │
│  ┌──────────────────┴──────────────────────────┐    │
│  │  Archival Memory (归档记忆)                   │    │
│  │  · 无限容量外部存储                           │    │
│  │  · Agent 按需读写 (tool: archival_insert/search)│   │
│  │  · 存储：长期知识、学习到的技能、重要结论      │    │
│  │  · 实现：FAISS 向量索引                       │    │
│  └─────────────────────────────────────────────┘    │
│                                                     │
│  ── Sleep-Time Compute (空闲时异步整理) ──           │
│  · 用户不活跃时，Agent 后台整理记忆                   │
│  · 合并重复信息、提炼关键知识、清理过时内容           │
│  · 不消耗用户等待时间，纯后台 CPU 任务               │
└─────────────────────────────────────────────────────┘
```

```python
# agent/memory/letta_memory.py
class LettaMemoryManager:
    """
    Letta (MemGPT) 风格的三层记忆。
    Agent 通过 Tool 自主管理记忆，而非被动存储。
    """
    
    def get_memory_tools(self) -> list[BaseTool]:
        """将记忆操作暴露为 Agent 可调用的 Tool"""
        return [
            Tool(name="core_memory_read", func=self.read_core,
                 description="读取核心记忆（用户画像、当前任务要点）"),
            Tool(name="core_memory_edit", func=self.edit_core,
                 description="编辑核心记忆（更新用户偏好、任务要点）"),
            Tool(name="recall_search", func=self.search_recall,
                 description="搜索历史对话记忆"),
            Tool(name="archival_insert", func=self.insert_archival,
                 description="将重要信息存入长期记忆"),
            Tool(name="archival_search", func=self.search_archival,
                 description="搜索长期知识库"),
        ]
    
    async def sleep_time_consolidate(self, namespace: str):
        """
        Sleep-Time Compute：空闲时自动整理记忆。
        - 合并重复记忆
        - 从近期对话中提炼关键知识 → Archival
        - 更新用户画像 → Core
        - 删除过时或低价值记忆
        """
        recent = await self.recall.get_recent(namespace, hours=24)
        
        summary = await self.llm.ainvoke([
            SystemMessage(content="从以下对话记录中提炼关键知识和用户偏好变化。"),
            HumanMessage(content=str(recent)),
        ])
        
        # 关键知识 → Archival
        await self.archival.insert(namespace, summary.knowledge_points)
        # 用户画像更新 → Core
        await self.core.merge_update(namespace, summary.user_profile_delta)
```

### 7.8 Speculative Parallel Execution（推测并行）

```python
# agent/optimization/speculative.py
class SpeculativeExecutor:
    """
    推测并行执行：当 Agent 需要多个工具结果时，
    不等一个完成再开始下一个，而是并行启动所有可能需要的工具调用。
    
    类比 CPU 的分支预测——投机执行，命中则加速，不命中则丢弃。
    
    CPU 开销：几乎为零（并行的是 I/O，不是计算）。
    效果：多工具场景延迟降低 40-60%。
    """
    
    async def execute_with_speculation(self, state, tools, llm):
        # LLM 返回 "可能需要的工具调用" 列表
        predicted_calls = await llm.predict_tool_calls(state)
        
        # 并行启动所有预测的工具调用
        tasks = {
            call.tool_name: asyncio.create_task(
                self.execute_tool(call, tools)
            )
            for call in predicted_calls
        }
        
        # LLM 决定实际需要哪些结果
        actual_needed = await llm.decide_needed(state, predicted_calls)
        
        # 取用需要的结果，取消不需要的
        results = {}
        for name, task in tasks.items():
            if name in actual_needed:
                results[name] = await task
            else:
                task.cancel()  # 不需要的直接丢弃
        
        return results
```

### 7.9 Agent 技术选型决策总结

| 技术 | 用途 | 何时触发 | CPU 开销 | 实现方式 |
|------|------|---------|----------|---------|
| **TaskComplexityRouter** | 策略自动选择 | 每次用户输入 | 极低 (规则引擎) | 自研 |
| **ReAct** | 基础工具调用循环 | 中等复杂度任务 | 低 | LangGraph |
| **Reflexion** | 失败自动反思重试 | ReAct 工具调用失败时 | 低 (仅失败时) | LangGraph 自定义节点 |
| **Plan-and-Execute** | 多步骤复杂任务 | 高复杂度任务 | 中 | LangGraph |
| **Plan Cache** | 复用历史执行计划 | Plan 策略触发时优先查缓存 | 极低 (向量匹配) | 自研 |
| **Supervisor MultiAgent** | 多角色协作 | 需要多专家的任务 | 高 (多 Agent) | LangGraph |
| **Agent-as-Judge/Debate** | 高质量输出评审 | 高价值输出场景 | 高 (多轮辩论) | 自研 |
| **Hermes Skill Learning** | 技能自动沉淀复用 | 复杂任务完成后(异步) | 极低 (后台) | 自研 |
| **Letta 三层记忆** | Agent 自主记忆管理 | 始终运行 | 低 | Letta/自研 |
| **Sleep-Time Compute** | 空闲时整理记忆 | 用户空闲时(后台) | 极低 (后台) | 自研 |
| **Speculative Execution** | 工具调用并行加速 | 多工具场景 | 零 (并行 I/O) | 自研 |

> **设计哲学：在正常路径上保持极低开销，高级能力只在需要时触发，后处理异步执行不阻塞用户。**

### 7.10 Agent 全链路可观测 — Token 统计 / 耗时分解 / 细分可视化

#### 7.10.1 每步埋点采集

```python
# agent/observability/collector.py
class AgentStepCollector:
    """
    Agent 执行过程中逐步采集统计数据。
    嵌入 LangGraph 的回调系统，零侵入。
    """
    
    def __init__(self, session_id, message_id, strategy):
        self.log = AgentExecutionLog(
            session_id=session_id,
            message_id=message_id,
            strategy=strategy,
            steps_detail=[],
        )
        self._step_start = None
    
    def on_llm_start(self, serialized, prompts, **kwargs):
        self._step_start = time.perf_counter_ns()
    
    def on_llm_end(self, response, **kwargs):
        elapsed_ms = (time.perf_counter_ns() - self._step_start) // 1_000_000
        usage = response.llm_output.get("token_usage", {})
        
        step = {
            "step": len(self.log.steps_detail) + 1,
            "type": "llm",
            "tokens_in": usage.get("prompt_tokens", 0),
            "tokens_out": usage.get("completion_tokens", 0),
            "latency_ms": elapsed_ms,
            "model": response.llm_output.get("model_name", ""),
        }
        self.log.steps_detail.append(step)
        self.log.total_tokens_in += step["tokens_in"]
        self.log.total_tokens_out += step["tokens_out"]
    
    def on_tool_start(self, tool_name, tool_input, **kwargs):
        self._step_start = time.perf_counter_ns()
        self._current_tool = tool_name
    
    def on_tool_end(self, output, **kwargs):
        elapsed_ms = (time.perf_counter_ns() - self._step_start) // 1_000_000
        
        step = {
            "step": len(self.log.steps_detail) + 1,
            "type": "tool_call",
            "tool": self._current_tool,
            "latency_ms": elapsed_ms,
        }
        self.log.steps_detail.append(step)
        self.log.tool_calls_count += 1
    
    async def finalize(self):
        """持久化到 agent_execution_logs 表"""
        self.log.total_steps = len(self.log.steps_detail)
        self.log.total_ms = sum(s["latency_ms"] for s in self.log.steps_detail)
        await self.db.insert("agent_execution_logs", self.log.to_dict())
```

#### 7.10.2 Agent 统计仪表盘

```
┌─────────────────────────────────────────────────────────────────┐
│                    Agent 运营仪表盘                               │
│                                                                 │
│  ┌─ 总览 (今日) ───────────────────────────────────────────────┐│
│  │  总请求: 342   成功率: 96.2%   平均耗时: 3.4s              ││
│  │  总 Token: 输入 824K / 输出 156K   预估费用: ¥12.8         ││
│  │  策略分布: Chat 58% | ReAct 31% | Plan 8% | Multi 3%      ││
│  └──────────────────────────────────────────────────────────── ┘│
│                                                                 │
│  ┌─ Token 消耗趋势 (按小时) ──────────────────────────────────┐│
│  │  50K|          ╲                                           ││
│  │  40K|    ╱╲  ╱  ╲                                         ││
│  │  30K|  ╱    ╲     ╲    ╱╲                                 ││
│  │  20K|╱              ╲╱    ╲                               ││
│  │  10K|                       ╲───                          ││
│  │     └──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──                ││
│  │       8  9 10 11 12 13 14 15 16 17 18 19                 ││
│  │       ■ Input Tokens  ■ Output Tokens                     ││
│  └──────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌─ 耗时分布 (P50 / P90 / P99) ──────────────────────────────┐│
│  │                    P50     P90     P99                     ││
│  │  Chat            0.8s    1.2s    2.1s                     ││
│  │  ReAct           2.1s    4.5s    8.3s                     ││
│  │  Plan-Execute    5.2s   12.1s   25.0s                     ││
│  │  MultiAgent      8.7s   18.3s   35.0s                     ││
│  └──────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌─ 单次执行详情 (点击展开) ─────────────────────────────────┐ │
│  │  Session: abc123 | 策略: ReAct | 总耗时: 3.2s             │ │
│  │                                                           │ │
│  │  Step 1  [LLM]  reasoning   320 tok → 85 tok   420ms    │ │
│  │  Step 2  [Tool] web_search  —                   1200ms   │ │
│  │  Step 3  [LLM]  reasoning   580 tok → 120 tok  680ms    │ │
│  │  Step 4  [Tool] kb_search   —                   350ms    │ │
│  │  Step 5  [LLM]  final       720 tok → 200 tok  550ms    │ │
│  │  ─────────────────────────────────────────────────────── │ │
│  │  Total:  1620 in + 405 out = 2025 tokens  |  3200ms     │ │
│  └──────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

#### 7.10.3 时间段细分聚合 API

```python
# agent/observability/analytics.py
class AgentAnalytics:
    """Agent 统计分析服务，支持按时间段、策略、模式多维聚合"""
    
    async def aggregate(
        self,
        time_range: tuple[datetime, datetime],
        group_by: str = "hour",        # hour / day / week
        filters: dict | None = None,   # strategy, mode_id, status
    ) -> list[AggregatedMetrics]:
        """
        返回按时间段聚合的指标，用于前端图表渲染。
        
        示例: group_by="hour" →
        [
            {"time": "2026-04-16 09:00", "requests": 42, "tokens_in": 52000, ...},
            {"time": "2026-04-16 10:00", "requests": 38, "tokens_in": 48000, ...},
            ...
        ]
        """
        # SQL 按时间分桶聚合
        sql = """
            SELECT 
                DATE_FORMAT(created_at, %s) AS time_bucket,
                COUNT(*) AS requests,
                SUM(total_tokens_in) AS tokens_in,
                SUM(total_tokens_out) AS tokens_out,
                AVG(total_ms) AS avg_latency_ms,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY total_ms) AS p50_ms,
                PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY total_ms) AS p90_ms,
                SUM(tool_calls_count) AS total_tool_calls,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failures
            FROM agent_execution_logs
            WHERE created_at BETWEEN %s AND %s
            GROUP BY time_bucket
            ORDER BY time_bucket
        """
        return await self.db.query(sql, format_pattern(group_by), *time_range)
    
    async def strategy_breakdown(self, date: str) -> dict:
        """按策略分布统计"""
        return await self.db.query("""
            SELECT strategy, COUNT(*) as count,
                   AVG(total_ms) as avg_ms,
                   SUM(total_tokens_in + total_tokens_out) as total_tokens
            FROM agent_execution_logs
            WHERE DATE(created_at) = %s
            GROUP BY strategy
        """, date)
```

---

## 八、RAG 高级引擎

### 8.1 检索策略演进 — Adaptive RAG

```
V2 (当前):  Query ──────────────> Vector Search (FAISS) ──> Top-K ──> Context
                                        (一刀切)

V3 (目标):  Query ──> Adaptive Router ──┬──> 不检索 (简单问答，LLM 直答)
               ▲                        ├──> 单步检索 (Vector + BM25 + Rerank)
               │ CPU 友好               ├──> CRAG 纠错检索 (检索 → 评估 → 补救)
               │ 轻量分类器             └──> 多步推理检索 (Agentic RAG)
               │ 减少 4x 不必要检索
```

```python
# rag/engine.py
class AdaptiveRAGEngine:
    """
    Adaptive RAG：根据查询复杂度自动选择检索策略。
    简单问题不浪费检索资源，复杂问题不遗漏关键信息。
    
    参考：LangGraph Adaptive RAG Tutorial + CRAG 论文。
    CPU 开销：路由判断极低，整体比固定策略更省资源。
    """
    
    async def adaptive_retrieve(self, query: str, mode_config) -> RAGResult:
        # 1. 路由决策（规则 + 轻量分类，< 5ms）
        route = self._classify_query(query)
        
        match route:
            case "no_retrieval":
                # 简单问答/闲聊 → 不检索
                return RAGResult(chunks=[], strategy="direct")
            
            case "single_step":
                # 中等问题 → 混合检索 + Rerank
                return await self._hybrid_retrieve(query, mode_config)
            
            case "corrective":
                # 不确定检索质量 → CRAG 纠错流程
                return await self._crag_retrieve(query, mode_config)
            
            case "multi_step":
                # 复杂问题 → 多步推理检索
                return await self._agentic_retrieve(query, mode_config)
    
    def _classify_query(self, query: str) -> str:
        """规则优先，零 LLM 调用"""
        # 闲聊/打招呼 → 不检索
        if self._is_chitchat(query):
            return "no_retrieval"
        # 关键词明确 → 单步检索
        if len(query.split()) < 15:
            return "single_step"
        # 多子问题 → 多步推理
        if any(kw in query for kw in ["对比", "分别", "逐一", "综述", "所有"]):
            return "multi_step"
        # 默认 CRAG（带自检的安全路径）
        return "corrective"
```

### 8.2 CRAG — 纠错式检索增强生成

```python
# rag/retrieval/crag.py
class CorrectiveRAG:
    """
    CRAG (Corrective RAG)：检索后自动评估结果质量，
    不合格则纠正查询或回退到网络搜索。
    
    流程：检索 → 评估 → [合格→用] [不合格→纠正/补充] → 生成
    
    CPU 开销：评估用规则+阈值，不额外调用 LLM。
    """
    
    async def retrieve_with_correction(self, query, config):
        # 1. 初始检索
        chunks = await self.hybrid_retriever.search(query, top_k=10)
        
        # 2. 相关性评估（基于向量相似度阈值，无 LLM 调用）
        relevant = [c for c in chunks if c.score >= config.relevance_threshold]
        ambiguous = [c for c in chunks if config.low_threshold <= c.score < config.relevance_threshold]
        
        # 3. 纠正策略
        if len(relevant) >= 3:
            # 足够多高质量结果 → 直接用
            return RAGResult(chunks=relevant, strategy="direct")
        
        if len(relevant) + len(ambiguous) >= 3:
            # 有模糊结果 → 重写查询再检索一次
            rewritten = await self._rewrite_query(query)
            extra = await self.hybrid_retriever.search(rewritten, top_k=5)
            return RAGResult(chunks=relevant + extra, strategy="rewritten")
        
        # 几乎无结果 → 回退到网络搜索
        web_results = await self.web_searcher.search(query, top_k=3)
        return RAGResult(chunks=relevant + web_results, strategy="web_fallback")
```

### 8.3 混合检索 + RRF 融合

```python
# rag/retrieval/hybrid.py
class HybridRetriever:
    """
    Vector + BM25 双路检索，用 RRF (Reciprocal Rank Fusion) 融合排名。
    比单一策略召回率提升 15-25%。
    
    CPU 开销：BM25 纯 CPU（Whoosh/rank_bm25 库），几乎零额外开销。
    """
    
    async def search(self, query: str, top_k: int = 10):
        # 并行执行两路检索
        vector_results, bm25_results = await asyncio.gather(
            self.vector_index.search(query, top_k=top_k * 2),
            self.bm25_index.search(query, top_k=top_k * 2),
        )
        
        # RRF 融合
        fused = self._rrf_fusion(vector_results, bm25_results, k=60)
        
        # 可选 Reranker（根据硬件决定是否启用，见 3.5 节）
        if self.hardware.recommend("reranking") != "disabled":
            fused = await self.reranker.rerank(query, fused, top_k=top_k)
        
        return fused[:top_k]
    
    def _rrf_fusion(self, *result_lists, k=60):
        """Reciprocal Rank Fusion：多路结果融合排序"""
        scores = defaultdict(float)
        for results in result_lists:
            for rank, doc in enumerate(results):
                scores[doc.id] += 1.0 / (k + rank + 1)
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)
```

### 8.4 Agentic Chunking (智能分块，CPU 友好版)

```python
# rag/chunking/agentic.py
class AgenticChunker:
    """
    智能分块策略：
    - 小文档 (< 5 页): 递归字符分块（纯 CPU，零 LLM 调用）
    - 中文档 (5-50 页): 语义分块（用 Embedding 检测语义断点）
    - 大文档 (> 50 页): LLM 辅助分块（仅对章节边界调用 LLM）
    
    CPU 优先：大部分文档用纯 CPU 分块即可，LLM 只处理真正需要理解的大文档。
    """
    
    async def chunk(self, document):
        page_count = document.page_count
        
        if page_count <= 5:
            return self.recursive_chunk(document)        # 纯 CPU
        elif page_count <= 50:
            return await self.semantic_chunk(document)   # Embedding (CPU/GPU)
        else:
            return await self.llm_assisted_chunk(document) # LLM 仅处理边界
    
    def recursive_chunk(self, doc, chunk_size=800, overlap=120):
        """递归字符分块 — 零 LLM 调用，CPU 瞬间完成"""
        return RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=overlap,
            separators=["\n\n", "\n", "。", ".", " "],
        ).split_text(doc.text)
    
    async def semantic_chunk(self, doc):
        """语义分块 — 用 Embedding 余弦相似度检测断点"""
        sentences = self.split_sentences(doc.text)
        embeddings = await self.embedder.encode_batch(sentences)
        
        # 相邻句子余弦相似度低于阈值 → 语义断点
        breakpoints = []
        for i in range(1, len(embeddings)):
            sim = cosine_similarity(embeddings[i-1], embeddings[i])
            if sim < 0.5:
                breakpoints.append(i)
        
        return self.merge_at_breakpoints(sentences, breakpoints)
```

### 8.5 文档预处理管线 — 清洗 + 结构化解析

```python
# rag/preprocessing/pipeline.py
class DocumentPreprocessor:
    """
    文档摄入前的清洗和结构化解析。
    原则：垃圾进 = 垃圾出，预处理质量决定 RAG 上限。
    """
    
    async def preprocess(self, raw_doc: RawDocument) -> CleanDocument:
        # 1. 格式解析（按 MIME 类型选解析器）
        parsed = await self.parser_registry.parse(raw_doc)
        
        # 2. 文本清洗
        cleaned = self.clean(parsed)
        
        # 3. 结构化元素提取
        structures = await self.extract_structures(parsed)
        
        # 4. 元数据提取
        metadata = self.extract_metadata(raw_doc, parsed)
        
        return CleanDocument(
            text=cleaned,
            tables=structures.tables,
            formulas=structures.formulas,
            images=structures.images,
            metadata=metadata,
        )
    
    def clean(self, parsed) -> str:
        """文本清洗管线"""
        text = parsed.text
        text = self.remove_headers_footers(text)       # 去页眉页脚
        text = self.remove_watermarks(text)             # 去水印文字
        text = self.normalize_whitespace(text)          # 合并多余空白
        text = self.fix_encoding(text)                  # 修复编码乱码
        text = self.remove_control_chars(text)          # 去控制字符
        text = self.merge_hyphenated_words(text)        # 合并断字 (PDF 跨行)
        text = self.normalize_unicode(text)             # Unicode 归一化
        return text
    
    def extract_metadata(self, raw_doc, parsed) -> dict:
        """提取结构化元数据 — 用于 metadata 过滤检索"""
        return {
            "source": raw_doc.file_path,
            "filename": raw_doc.filename,
            "mime_type": raw_doc.mime_type,
            "file_size": raw_doc.file_size,
            "page_count": parsed.page_count,
            "title": parsed.title or "",
            "author": parsed.author or "",
            "created_date": parsed.created_date,
            "language": detect_language(parsed.text[:500]),
            "tags": [],                                 # 用户或 LLM 后续标注
        }
```

### 8.6 Query 改写与多路召回

```python
# rag/retrieval/query_rewriter.py
class QueryRewriter:
    """
    Query 改写策略：提升召回率的关键。
    CPU 友好：HyDE 需要 1 次 LLM 调用，同义扩展纯规则。
    """
    
    async def rewrite(self, query: str, strategy: str = "auto") -> list[str]:
        queries = [query]  # 原始 query 始终保留
        
        match strategy:
            case "synonym":
                # 同义词扩展（纯 CPU，规则引擎）
                queries.extend(self.synonym_expand(query))
            
            case "hyde":
                # HyDE: 让 LLM 先生成一个假设性回答，用回答去检索
                hypothetical = await self.llm.ainvoke(
                    f"请直接回答以下问题（不需要检索，用你的知识）：{query}"
                )
                queries.append(hypothetical.content)
            
            case "decompose":
                # 子问题分解：复杂问题拆成多个子问题
                sub_questions = await self.llm.ainvoke(
                    f"将以下问题分解为 2-3 个更具体的子问题：{query}"
                )
                queries.extend(parse_sub_questions(sub_questions.content))
            
            case "auto":
                # 自动选择：短 query 用同义扩展，长 query 用 HyDE
                if len(query) < 20:
                    queries.extend(self.synonym_expand(query))
                else:
                    hypothetical = await self.llm.ainvoke(
                        f"请直接回答以下问题：{query}"
                    )
                    queries.append(hypothetical.content)
        
        return queries


# rag/retrieval/multi_path.py
class MultiPathRetriever:
    """
    多路召回 + Metadata 过滤 + RRF 融合
    
    三路并行：
    1. 向量检索 (语义相似度)
    2. BM25 检索 (关键词匹配)
    3. Metadata 过滤检索 (结构化条件)
    """
    
    async def retrieve(self, queries: list[str], filters: MetadataFilter | None = None, top_k: int = 10):
        # 对每个改写 query 并行执行三路检索
        all_tasks = []
        for q in queries:
            all_tasks.append(self.vector_index.search(q, top_k=top_k * 2, filters=filters))
            all_tasks.append(self.bm25_index.search(q, top_k=top_k * 2))
        
        # Metadata 过滤可单独走（如 "只搜 2026 年的 PDF"）
        if filters:
            all_tasks.append(self.metadata_index.filter_search(filters, top_k=top_k))
        
        results = await asyncio.gather(*all_tasks)
        
        # RRF 融合所有结果
        fused = self.rrf_fusion(*results, k=60)
        
        return fused[:top_k]


class MetadataFilter(BaseModel):
    """用户可在检索时指定的结构化过滤条件"""
    source_type: list[str] | None = None      # ["pdf", "docx"]
    date_range: tuple[str, str] | None = None # ("2025-01-01", "2026-04-16")
    author: str | None = None
    tags: list[str] | None = None
    filename_pattern: str | None = None       # "论文*"
```

### 8.7 RAG 全链路日志 — query → chunk → prompt → answer

```python
# rag/observability/trace.py
@dataclass
class RAGTrace:
    """
    每次 RAG 请求的完整追踪记录。
    全链路可追溯：出了问题能精确定位是哪个环节。
    """
    trace_id: str                              # 唯一追踪 ID
    session_id: str
    message_id: str
    timestamp: float
    
    # ===== 链路数据 =====
    original_query: str                        # 1. 用户原始输入
    rewritten_queries: list[str]               # 2. 改写后的查询列表
    retrieved_chunks: list[ChunkWithScore]      # 3. 召回的 chunks (含 score)
    filtered_chunks: list[ChunkWithScore]       # 4. metadata 过滤后
    reranked_chunks: list[ChunkWithScore]       # 5. 重排后 (含新 score)
    assembled_prompt: str                       # 6. 最终拼装的 prompt
    llm_raw_answer: str                         # 7. LLM 原始回答
    post_processed_answer: str                  # 8. 后处理后的回答
    
    # ===== 决策记录 =====
    retrieval_strategy: str                     # 使用的策略 (adaptive 路由结果)
    rewrite_strategy: str                       # 改写策略
    chunks_retrieved: int                       # 召回数
    chunks_used: int                            # 最终使用数
    
    # ===== 耗时分解 =====
    query_rewrite_ms: int
    retrieval_ms: int
    rerank_ms: int
    prompt_assembly_ms: int
    generation_ms: int
    total_ms: int
    
    # ===== Token 统计 =====
    prompt_tokens: int
    completion_tokens: int


class RAGTracer:
    """在 RAG 管线各环节埋点，自动收集 trace"""
    
    def __init__(self):
        self.trace = RAGTrace(trace_id=uuid4().hex, ...)
        self._timers = {}
    
    @contextmanager
    def step(self, name: str):
        """计时上下文管理器"""
        start = time.perf_counter_ns()
        yield
        elapsed_ms = (time.perf_counter_ns() - start) // 1_000_000
        setattr(self.trace, f"{name}_ms", elapsed_ms)
    
    async def save(self):
        """持久化到 rag_trace_logs 表"""
        await self.db.insert("rag_trace_logs", self.trace.to_dict())


# 在 RAG 管线中使用
async def rag_pipeline(query, mode_config, tracer: RAGTracer):
    tracer.trace.original_query = query
    
    with tracer.step("query_rewrite"):
        queries = await rewriter.rewrite(query)
        tracer.trace.rewritten_queries = queries
    
    with tracer.step("retrieval"):
        chunks = await retriever.retrieve(queries, filters=mode_config.filters)
        tracer.trace.retrieved_chunks = chunks
    
    with tracer.step("rerank"):
        reranked = await reranker.rerank(query, chunks)
        tracer.trace.reranked_chunks = reranked
    
    with tracer.step("prompt_assembly"):
        prompt = assemble_prompt(query, reranked, budget=mode_config.context_budget)
        tracer.trace.assembled_prompt = prompt
    
    with tracer.step("generation"):
        answer = await llm.generate(prompt)
        tracer.trace.llm_raw_answer = answer
    
    tracer.trace.total_ms = sum_all_steps(tracer)
    await tracer.save()
    return answer
```

### 8.8 RAG 质量指标监控

```
┌─────────────────────────────────────────────────────────────┐
│                  RAG 质量监控仪表盘                           │
│                                                             │
│  ┌─ 核心指标 (实时) ──────────────────────────────────────┐ │
│  │  召回率 Recall@10    : 82.3%  (▲ 2.1% vs 上周)        │ │
│  │  精准率 Precision@5  : 74.5%  (▲ 1.8% vs 上周)        │ │
│  │  答案相关性 Relevance : 4.2/5  (LLM-as-Judge 评分)     │ │
│  │  CRAG 纠错触发率     : 12.7%  (偏高时提示优化索引)      │ │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─ 性能指标 ─────────────────────────────────────────────┐ │
│  │  平均检索耗时  : 45ms   │  平均重排耗时  : 120ms       │ │
│  │  平均生成耗时  : 1.2s   │  平均总耗时    : 1.8s        │ │
│  │  平均 Prompt Token : 2400  │  平均输出 Token : 380     │ │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─ 时间趋势图 ──────────────────────────────────────────┐ │
│  │  Recall@10 趋势 (最近 7 天)                            │ │
│  │  85%|         ╱─╲                                      │ │
│  │  80%|    ╱──╱    ╲──╱─                                │ │
│  │  75%|──╱                                               │ │
│  │     └──┬──┬──┬──┬──┬──┬──                             │ │
│  │       Mon Tue Wed Thu Fri Sat Sun                      │ │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

```python
# rag/observability/metrics.py
class RAGMetrics:
    """
    RAG 质量指标计算。
    
    评估方式：
    - Recall/Precision: 基于用户反馈 (点赞/踩) + 自动标注
    - 答案相关性: LLM-as-Judge (定期批量评估，不阻塞线上)
    """
    
    async def compute_recall_at_k(self, trace: RAGTrace, k: int = 10) -> float:
        """召回率：标注为相关的文档有多少被召回了"""
        relevant_ids = await self.get_relevant_doc_ids(trace.original_query)
        retrieved_ids = {c.doc_id for c in trace.retrieved_chunks[:k]}
        if not relevant_ids:
            return 0.0
        return len(relevant_ids & retrieved_ids) / len(relevant_ids)
    
    async def compute_precision_at_k(self, trace: RAGTrace, k: int = 5) -> float:
        """精准率：召回的文档中有多少是真正相关的"""
        top_k = trace.reranked_chunks[:k]
        relevant_count = sum(1 for c in top_k if c.score >= self.relevance_threshold)
        return relevant_count / k if k > 0 else 0.0
    
    async def compute_answer_relevance(self, query: str, answer: str) -> float:
        """答案相关性：LLM-as-Judge 评分 (1-5)"""
        score = await self.judge_llm.ainvoke(
            f"对以下回答的相关性打分 (1-5):\n问题: {query}\n回答: {answer}\n只输出数字。"
        )
        return float(score.content.strip())
    
    async def aggregate_daily(self, date: str) -> DailyMetrics:
        """按天聚合指标，用于趋势图"""
        traces = await self.db.query("rag_trace_logs", date=date)
        return DailyMetrics(
            date=date,
            avg_recall=mean([t.recall for t in traces]),
            avg_precision=mean([t.precision for t in traces]),
            avg_relevance=mean([t.relevance for t in traces]),
            avg_latency_ms=mean([t.total_ms for t in traces]),
            avg_tokens=mean([t.prompt_tokens + t.completion_tokens for t in traces]),
            total_queries=len(traces),
            crag_trigger_rate=sum(1 for t in traces if t.strategy == "corrective") / len(traces),
        )
```

### 8.9 RAG 管线完整流程图

```
用户输入 Query
    │
    ▼
┌─────────────────────┐
│ 1. Adaptive Router  │  根据 query 复杂度选策略 (< 5ms)
│    no_retrieval     │──────────────────────────────────────── 直接 LLM 回答
│    single_step      │──┐
│    corrective       │──┤
│    multi_step       │──┤
└─────────────────────┘  │
                         ▼
┌─────────────────────┐
│ 2. Query 改写       │  HyDE / 同义扩展 / 子问题分解
│    original + N 个  │
│    改写 query       │
└─────────┬───────────┘
          │
          ▼ (并行三路)
┌─────────────────────────────────────────┐
│ 3. 多路召回                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐│
│  │ 向量检索  │ │ BM25     │ │ Metadata ││
│  │ (FAISS)  │ │ 关键词   │ │ 过滤     ││
│  └────┬─────┘ └────┬─────┘ └────┬─────┘│
│       └────────────┼────────────┘      │
│                    ▼                    │
│         4. RRF 融合排序                 │
└────────────────────┬────────────────────┘
                     ▼
┌─────────────────────┐
│ 5. Cross-Encoder    │  BGE-Reranker (有 GPU 时启用完整版)
│    重排序 Top-K      │
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ 6. CRAG 质量自检    │  score < 阈值 → 改写重检索 / 回退网络搜索
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ 7. Prompt 拼装      │  context budget 控制，去重，引用标注
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ 8. LLM 生成         │  流式输出
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ 9. Trace 日志持久化  │  全链路写入 rag_trace_logs
│    + 指标计算        │
└─────────────────────┘
```

---

## 九、MCP 协议与插件生态

### 9.1 MCP 集成架构

```
┌───────────────────────────────────────────────────┐
│                  MCP Gateway                       │
│                                                   │
│  ┌─────────────┐  ┌──────────────┐               │
│  │ MCP Server  │  │ MCP Client   │               │
│  │ (暴露本地   │  │ (调用外部    │               │
│  │  工具给外部) │  │  MCP 服务)   │               │
│  └──────┬──────┘  └──────┬───────┘               │
│         │                │                        │
│  ┌──────┴────────────────┴───────┐               │
│  │        Tool Registry          │               │
│  │  ┌─────────────────────────┐  │               │
│  │  │ Built-in Tools          │  │               │
│  │  │ · web_search            │  │               │
│  │  │ · code_executor         │  │               │
│  │  │ · file_operations       │  │               │
│  │  │ · knowledge_search      │  │               │
│  │  └─────────────────────────┘  │               │
│  │  ┌─────────────────────────┐  │               │
│  │  │ MCP External Tools      │  │               │
│  │  │ · github-mcp            │  │               │
│  │  │ · slack-mcp             │  │               │
│  │  │ · notion-mcp            │  │               │
│  │  │ · browser-mcp           │  │               │
│  │  └─────────────────────────┘  │               │
│  │  ┌─────────────────────────┐  │               │
│  │  │ Plugin Tools            │  │               │
│  │  │ · user_plugin_1         │  │               │
│  │  │ · user_plugin_2         │  │               │
│  │  └─────────────────────────┘  │               │
│  └───────────────────────────────┘               │
└───────────────────────────────────────────────────┘
```

### 9.2 插件接口定义

```python
# plugins/interface.py
from abc import ABC, abstractmethod
from pydantic import BaseModel

class PluginManifest(BaseModel):
    """插件清单"""
    name: str
    version: str
    description: str
    author: str
    capabilities: list[str]          # 能力标签
    compatible_modes: list[str]      # 兼容的氛围模式
    tools: list[ToolDefinition]      # 提供的工具
    config_schema: dict | None       # 配置 Schema
    dependencies: list[str]          # 依赖的其他插件

class PluginInterface(ABC):
    """插件基类"""
    
    @abstractmethod
    def get_manifest(self) -> PluginManifest:
        """返回插件清单"""
        ...
    
    @abstractmethod
    async def initialize(self, config: dict) -> None:
        """初始化插件"""
        ...
    
    @abstractmethod
    async def get_tools(self) -> list[BaseTool]:
        """返回插件提供的工具列表"""
        ...
    
    async def on_mode_switch(self, mode_id: str) -> None:
        """模式切换时的钩子"""
        pass
    
    async def on_message(self, message: Message) -> None:
        """消息钩子（可用于拦截/增强）"""
        pass
    
    async def shutdown(self) -> None:
        """插件卸载"""
        pass
```

### 9.3 插件市场设计

```yaml
# 插件注册格式
plugins:
  - name: "pdf-reader"
    source: "builtin"
    description: "PDF 文档解析、表格提取、公式识别"
    tools:
      - parse_pdf
      - extract_tables
      - extract_formulas
    
  - name: "code-interpreter"
    source: "builtin"
    description: "Python 代码沙盒执行"
    tools:
      - execute_python
      - plot_chart
    
  - name: "github-mcp"
    source: "mcp://github.com/modelcontextprotocol/servers/github"
    description: "GitHub 仓库操作"
    tools:
      - search_repos
      - create_issue
      - read_file
    
  - name: "browser-mcp"
    source: "mcp://github.com/anthropics/mcp-servers/browser"
    description: "浏览器自动化"
    tools:
      - navigate
      - screenshot
      - click
```

---

## 十、全局快捷键 & 桌面集成

### 10.1 架构

```
┌──────────────────────────────────────────────┐
│           Electron Shell (可选)               │
│                                              │
│  ┌──────────────────────────────────────┐    │
│  │  Global Hotkey Manager               │    │
│  │  · Ctrl+Shift+Space : 唤起 QuickBar │    │
│  │  · Ctrl+Shift+C     : 截屏识别      │    │
│  │  · Ctrl+Shift+V     : 选中文本问答   │    │
│  └───────────────┬──────────────────────┘    │
│                  │                            │
│  ┌───────────────▼──────────────────────┐    │
│  │  QuickBar (悬浮面板)                  │    │
│  │  ┌────────────────────────────────┐  │    │
│  │  │ [当前模式图标] 输入问题...      │  │    │
│  │  │ ────────────────────────────── │  │    │
│  │  │ 📋 剪贴板内容预览              │  │    │
│  │  │ 🖼️ 截图 OCR 结果               │  │    │
│  │  │ ────────────────────────────── │  │    │
│  │  │ AI 回答区 (流式输出)           │  │    │
│  │  └────────────────────────────────┘  │    │
│  └──────────────────────────────────────┘    │
│                  │                            │
│  ┌───────────────▼──────────────────────┐    │
│  │  System Tray (托盘)                   │    │
│  │  · 模式快速切换                       │    │
│  │  · 最近会话                           │    │
│  │  · 打开主界面                         │    │
│  └──────────────────────────────────────┘    │
└──────────────────────────────────────────────┘
```

### 10.2 实现方案

**方案 A（推荐）：Electron 薄壳 + React 共享**

```
Electron App (thin shell)
├── 全局热键注册 (globalShortcut)
├── 系统托盘 (Tray)
├── QuickBar 窗口 (BrowserWindow, frameless)
└── 加载 React Web UI (同一份代码)
    └── http://localhost:3000 或 file://index.html
```

**方案 B：Python 后台服务 + 原生热键**

```
Python Background Service
├── pynput / keyboard 库监听全局热键
├── 截屏: mss + PaddleOCR
├── 剪贴板: pyperclip
└── 通过 HTTP 调用 AI 服务
    └── 结果通过系统通知 / 悬浮窗展示
```

### 10.3 文本选中 -> AI 问答流程

```
用户在任意应用中选中文本
    ↓
按下 Ctrl+Shift+V
    ↓
Electron 捕获热键
    ↓
读取系统剪贴板 (clipboard.readText())
    ↓
打开 QuickBar 悬浮窗
    ↓
展示剪贴板文本 + 输入框
    ↓
用户可直接提问或编辑
    ↓
发送到 AI 服务:
  {
    "clipboard_text": "选中的文本内容",
    "user_query": "用户的追加问题",
    "mode_id": "当前氛围模式",
    "context": {
      "source_app": "来源应用名",
      "memory": "相关记忆",
      "rag_results": "本地知识库匹配"
    }
  }
    ↓
流式返回 AI 回答
    ↓
用户可：复制 / 继续追问 / 打开主界面深入探讨
```

---

## 十一、多文件格式处理管线

### 11.1 支持格式

| 格式 | 解析库 | 能力 |
|------|--------|------|
| **PDF** | PyMuPDF + Marker | 文本、表格、公式、图片 |
| **Word (.docx)** | python-docx | 文本、样式、表格 |
| **Excel (.xlsx)** | openpyxl | 表格数据、图表描述 |
| **PowerPoint (.pptx)** | python-pptx | 幻灯片文本、备注 |
| **Markdown (.md)** | markdown-it-py | 结构化解析 |
| **代码文件** | Tree-sitter | AST 解析、函数/类提取 |
| **图片** | PaddleOCR / Tesseract | OCR 文字识别 |
| **HTML** | BeautifulSoup4 | 网页内容提取 |
| **CSV/JSON** | pandas | 结构化数据 |
| **纯文本** | charset-normalizer | 编码检测 + 读取 |

### 11.2 处理管线

```python
# file_processing/pipeline.py
class FileProcessingPipeline:
    """
    统一文件处理管线
    
    流程: 文件 -> 格式检测 -> 解析器 -> 结构提取 -> 分块 -> 嵌入 -> 索引
    """
    
    async def process(self, file_path: str) -> ProcessedDocument:
        # 1. 格式检测
        mime_type = self.detect_format(file_path)
        
        # 2. 选择解析器
        parser = self.parser_registry.get(mime_type)
        
        # 3. 解析
        raw_doc = await parser.parse(file_path)
        
        # 4. 结构提取 (表格、公式、元数据)
        enriched = await self.extract_structures(raw_doc)
        
        # 5. 智能分块
        chunks = await self.chunker.chunk(enriched)
        
        return ProcessedDocument(
            source=file_path,
            mime_type=mime_type,
            chunks=chunks,
            metadata=enriched.metadata,
            tables=enriched.tables,
            formulas=enriched.formulas,
        )
```

---

## 十二、数据库设计

### 12.1 MySQL/PostgreSQL (Java 管理)

```sql
-- ==================== 用户 ====================
CREATE TABLE users (
    id          BIGINT PRIMARY KEY AUTO_INCREMENT,
    username    VARCHAR(50) UNIQUE NOT NULL,
    password    VARCHAR(255) NOT NULL,                 -- BCrypt
    email       VARCHAR(100),
    role        VARCHAR(20) DEFAULT 'user',            -- admin / user
    status      TINYINT DEFAULT 1,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==================== 会话 ====================
CREATE TABLE sessions (
    id          VARCHAR(36) PRIMARY KEY,               -- UUID
    user_id     BIGINT NOT NULL REFERENCES users(id),
    mode_id     VARCHAR(64) NOT NULL,
    title       VARCHAR(200),
    status      VARCHAR(20) DEFAULT 'active',          -- active/archived/deleted
    is_pinned   BOOLEAN DEFAULT FALSE,
    is_protected BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_mode (user_id, mode_id),
    INDEX idx_updated (updated_at DESC)
);

CREATE TABLE messages (
    id          VARCHAR(36) PRIMARY KEY,
    session_id  VARCHAR(36) NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role        VARCHAR(20) NOT NULL,                  -- user/assistant/system/tool
    content     TEXT NOT NULL,
    metadata    JSON,                                  -- tool_calls, citations, etc.
    tokens_in   INT DEFAULT 0,                         -- 输入 token 数
    tokens_out  INT DEFAULT 0,                         -- 输出 token 数
    latency_ms  INT DEFAULT 0,                         -- 响应耗时
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_session_time (session_id, created_at)
);

-- ==================== 氛围模式 ====================
CREATE TABLE ambient_modes (
    id          VARCHAR(64) PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(id),
    name        VARCHAR(100) NOT NULL,
    config      JSON NOT NULL,                         -- AmbientMode 完整配置
    is_system   BOOLEAN DEFAULT FALSE,                 -- 系统预设 vs 用户自定义
    sort_order  INT DEFAULT 0,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==================== 知识库 ====================
CREATE TABLE knowledge_bases (
    id          VARCHAR(64) PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(id),
    mode_id     VARCHAR(64) REFERENCES ambient_modes(id),
    name        VARCHAR(100) NOT NULL,
    index_status VARCHAR(20) DEFAULT 'pending',        -- pending/building/ready/error
    doc_count   INT DEFAULT 0,
    chunk_count INT DEFAULT 0,
    config      JSON,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE documents (
    id          VARCHAR(64) PRIMARY KEY,
    kb_id       VARCHAR(64) NOT NULL REFERENCES knowledge_bases(id),
    filename    VARCHAR(255) NOT NULL,
    file_path   VARCHAR(1000),
    mime_type   VARCHAR(100),
    file_size   BIGINT,
    chunk_count INT DEFAULT 0,
    status      VARCHAR(20) DEFAULT 'pending',         -- pending/processing/indexed/error
    metadata    JSON,                                  -- 作者、日期、标签等结构化元数据
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==================== RAG 全链路日志 ====================
CREATE TABLE rag_trace_logs (
    id          BIGINT PRIMARY KEY AUTO_INCREMENT,
    session_id  VARCHAR(36) NOT NULL,
    message_id  VARCHAR(36) NOT NULL,
    -- 全链路追踪字段
    original_query   TEXT NOT NULL,                    -- 用户原始查询
    rewritten_query  TEXT,                             -- 改写后的查询
    retrieved_chunks JSON,                             -- 召回的 chunks [{id, text, score, source}]
    filtered_chunks  JSON,                             -- metadata 过滤后的 chunks
    reranked_chunks  JSON,                             -- 重排序后的 chunks [{id, score}]
    assembled_prompt TEXT,                             -- 最终拼装的 prompt
    llm_answer       TEXT,                             -- LLM 原始回答
    -- 质量指标
    retrieval_strategy VARCHAR(50),                    -- 使用的检索策略
    chunk_count_retrieved INT DEFAULT 0,
    chunk_count_used      INT DEFAULT 0,
    -- 耗时分解
    query_rewrite_ms     INT DEFAULT 0,
    retrieval_ms         INT DEFAULT 0,
    rerank_ms            INT DEFAULT 0,
    generation_ms        INT DEFAULT 0,
    total_ms             INT DEFAULT 0,
    -- Token 统计
    prompt_tokens        INT DEFAULT 0,
    completion_tokens    INT DEFAULT 0,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_session (session_id),
    INDEX idx_time (created_at DESC)
);

-- ==================== Agent 执行统计 ====================
CREATE TABLE agent_execution_logs (
    id          BIGINT PRIMARY KEY AUTO_INCREMENT,
    session_id  VARCHAR(36) NOT NULL,
    message_id  VARCHAR(36) NOT NULL,
    strategy    VARCHAR(30) NOT NULL,                  -- chat/react/plan_and_execute/supervisor
    mode_id     VARCHAR(64),
    -- 执行概要
    total_steps       INT DEFAULT 0,                   -- 总步骤数
    tool_calls_count  INT DEFAULT 0,                   -- 工具调用次数
    reflection_count  INT DEFAULT 0,                   -- 反思次数
    -- Token 统计
    total_tokens_in   INT DEFAULT 0,
    total_tokens_out  INT DEFAULT 0,
    -- 耗时统计
    planning_ms       INT DEFAULT 0,                   -- 规划耗时
    execution_ms      INT DEFAULT 0,                   -- 执行耗时
    total_ms          INT DEFAULT 0,
    -- 步骤明细 (JSON Array)
    steps_detail JSON,                                 -- [{step, type, tool, tokens, latency_ms}]
    status      VARCHAR(20) DEFAULT 'completed',       -- completed/failed/cancelled
    error       TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_session (session_id),
    INDEX idx_strategy (strategy),
    INDEX idx_time (created_at DESC)
);

-- ==================== Agent 记忆 ====================
CREATE TABLE agent_memories (
    id          VARCHAR(36) PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(id),
    namespace   VARCHAR(64) NOT NULL,                  -- 对应氛围模式
    memory_type VARCHAR(20) NOT NULL,                  -- core/recall/archival
    content     TEXT NOT NULL,
    importance  FLOAT DEFAULT 0.5,
    access_count INT DEFAULT 0,
    last_accessed TIMESTAMP,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_ns (user_id, namespace),
    INDEX idx_importance (importance DESC)
);
```

### 12.2 Redis 数据结构

```
# 会话缓存
session:{session_id}              -> Hash (mode_id, user_id, state)
session:{session_id}:messages     -> List (最近 N 条消息)

# 用户在线状态
user:{user_id}:online             -> String (TTL 5min)
user:{user_id}:current_mode       -> String (当前模式 ID)

# Agent 执行状态
agent:task:{task_id}              -> Hash (status, progress, result)
agent:task:{task_id}:stream       -> Stream (流式输出)

# 限流
rate_limit:{user_id}:{endpoint}   -> String (计数, TTL)

# Token 黑名单 (JWT 撤销)
token:blacklist:{jti}             -> String (TTL = token 剩余有效期)
```

---

## 十三、DevOps & 工程化

### 13.1 项目结构 (Monorepo)

```
ShadowLink/
├── shadowlink-server/               # Java SpringBoot 后端
│   ├── pom.xml                      # Maven 父 POM
│   ├── shadowlink-gateway/
│   ├── shadowlink-auth/
│   ├── shadowlink-tenant/
│   ├── shadowlink-session/
│   ├── shadowlink-business/
│   ├── shadowlink-config/
│   ├── shadowlink-websocket/
│   ├── shadowlink-ai-bridge/
│   ├── shadowlink-common/
│   └── shadowlink-starter/
│
├── shadowlink-ai/                   # Python AI 服务
│   ├── app/
│   ├── proto/
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
│
├── shadowlink-web/                  # React 前端
│   ├── src/
│   ├── public/
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
│
├── shadowlink-electron/             # Electron 桌面壳 (可选)
│   ├── src/
│   ├── package.json
│   └── electron-builder.yml
│
├── proto/                           # 共享 Proto 定义
│   ├── agent_service.proto
│   ├── rag_service.proto
│   └── mcp_service.proto
│
├── deploy/                          # 部署配置
│   ├── docker-compose.yml           # 一键启动全部服务
│   ├── docker-compose.dev.yml       # 开发环境
│   ├── nginx/
│   │   └── nginx.conf
│   └── scripts/
│       ├── start.sh
│       └── init-db.sql
│
├── docs/                            # 文档
│   ├── ARCHITECTURE_PLAN.md         # 本文档
│   ├── API.md                       # API 文档
│   ├── DEVELOPMENT.md               # 开发指南
│   └── DEPLOYMENT.md                # 部署指南
│
├── .github/                         # CI/CD
│   └── workflows/
│       ├── ci.yml                   # 持续集成
│       ├── cd.yml                   # 持续部署
│       └── quality.yml              # 代码质量检查
│
├── Makefile                         # 统一构建命令
└── README.md
```

### 13.2 Docker Compose 一键启动

```yaml
# deploy/docker-compose.yml
version: '3.8'

services:
  # ---- 基础设施 ----
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: ${DB_PASSWORD}
      MYSQL_DATABASE: shadowlink
    volumes:
      - mysql_data:/var/lib/mysql
      - ./scripts/init-db.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "3306:3306"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  # ---- 应用服务 ----
  shadowlink-server:
    build: ../shadowlink-server
    ports:
      - "8080:8080"
      - "50051:50051"     # gRPC
    depends_on:
      - mysql
      - redis
      - shadowlink-ai
    environment:
      SPRING_DATASOURCE_URL: jdbc:mysql://mysql:3306/shadowlink
      SPRING_REDIS_HOST: redis
      AI_SERVICE_HOST: shadowlink-ai
      AI_SERVICE_GRPC_PORT: 50052

  shadowlink-ai:
    build: ../shadowlink-ai
    ports:
      - "8000:8000"       # REST
      - "50052:50052"     # gRPC
    volumes:
      - models_data:/app/models
      - indexes_data:/app/rag_indexes
    environment:
      LLM_CONFIG_PATH: /app/config/llm_config.json
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]   # 可选 GPU 加速

  shadowlink-web:
    build: ../shadowlink-web
    ports:
      - "3000:80"
    depends_on:
      - shadowlink-server

  # ---- 反向代理 ----
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - shadowlink-server
      - shadowlink-web

volumes:
  mysql_data:
  models_data:
  indexes_data:
```

### 13.3 CI/CD Pipeline

```yaml
# .github/workflows/ci.yml
name: CI Pipeline

on: [push, pull_request]

jobs:
  # Java 后端
  java-build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with: { java-version: '17' }
      - run: cd shadowlink-server && mvn verify
      - run: cd shadowlink-server && mvn spotbugs:check     # 静态分析
      - run: cd shadowlink-server && mvn jacoco:report      # 覆盖率

  # Python AI 服务
  python-build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: cd shadowlink-ai && pip install -e ".[dev]"
      - run: cd shadowlink-ai && pytest --cov=app tests/
      - run: cd shadowlink-ai && ruff check app/            # Lint
      - run: cd shadowlink-ai && mypy app/                  # 类型检查

  # 前端
  web-build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: cd shadowlink-web && npm ci
      - run: cd shadowlink-web && npm run type-check         # TypeScript
      - run: cd shadowlink-web && npm run lint               # ESLint
      - run: cd shadowlink-web && npm run test               # Vitest
      - run: cd shadowlink-web && npm run build              # 构建

  # 集成测试
  integration:
    needs: [java-build, python-build, web-build]
    runs-on: ubuntu-latest
    steps:
      - run: docker compose -f deploy/docker-compose.yml up -d
      - run: sleep 30 && npm run test:e2e
```

### 13.4 可观测性

```
┌──────────────────────────────────────────┐
│           可观测性体系                     │
├──────────┬───────────┬───────────────────┤
│  Metrics │  Logging  │  Tracing          │
│  指标    │  日志     │  链路追踪          │
├──────────┼───────────┼───────────────────┤
│Prometheus│ ELK Stack │ Jaeger/Zipkin     │
│+Grafana  │ or Loki   │                   │
│          │           │                   │
│ · QPS    │ · 结构化  │ · Java->Python    │
│ · 延迟   │ · 分级    │ · Agent 执行链路  │
│ · 错误率 │ · 可检索  │ · Tool Call 追踪  │
│ · Token  │ · 告警    │ · RAG 检索追踪    │
│   消耗   │           │                   │
└──────────┴───────────┴───────────────────┘
```

---

## 十四、安全体系

### 14.1 安全要点

| 层面 | 措施 |
|------|------|
| **网络** | HTTPS/TLS 1.3、CORS 白名单、Rate Limiting (Resilience4j) |
| **认证** | JWT (Access 30min + Refresh 7d)、BCrypt 密码、Token 黑名单 (Redis) |
| **授权** | RBAC 权限模型、API 接口级权限控制 |
| **数据** | API Key AES 加密存储、参数化查询防 SQL 注入、CSP Header 防 XSS |
| **Agent** | Tool 文件访问权限控制、代码执行沙盒 (RestrictedPython)、Prompt 注入检测 |
| **审计** | 全操作审计日志、Agent 行为日志 |

---

## 十五、目录结构规划

### 完整项目目录树

```
D:\ShadowLink\ShadowLink/
│
├── shadowlink-server/                    # ===== Java SpringBoot 后端 =====
│   ├── pom.xml
│   ├── shadowlink-common/
│   │   └── src/main/java/com/shadowlink/common/
│   │       ├── exception/                # 全局异常处理
│   │       ├── response/                 # 统一响应体
│   │       ├── utils/                    # 工具类
│   │       └── constants/               # 常量
│   ├── shadowlink-auth/
│   │   └── src/main/java/com/shadowlink/auth/
│   │       ├── config/SecurityConfig.java
│   │       ├── filter/JwtAuthFilter.java
│   │       ├── service/AuthService.java
│   │       └── controller/AuthController.java
│   ├── shadowlink-tenant/
│   ├── shadowlink-session/
│   ├── shadowlink-business/
│   │   └── src/main/java/com/shadowlink/business/
│   │       ├── mode/                     # 氛围模式管理
│   │       ├── knowledge/                # 知识库管理
│   │       ├── plugin/                   # 插件管理
│   │       └── memory/                   # 记忆管理
│   ├── shadowlink-ai-bridge/
│   │   └── src/main/java/com/shadowlink/bridge/
│   │       ├── grpc/                     # gRPC Client Stubs
│   │       ├── service/AIBridgeService.java
│   │       └── converter/               # Proto <-> DTO 转换
│   ├── shadowlink-websocket/
│   ├── shadowlink-gateway/
│   └── shadowlink-starter/
│       └── src/main/java/com/shadowlink/
│           └── ShadowLinkApplication.java  # 启动类
│
├── shadowlink-ai/                        # ===== Python AI 服务 =====
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── api/
│   │   ├── agent/
│   │   │   ├── engine.py
│   │   │   ├── react/
│   │   │   ├── plan_execute/
│   │   │   ├── multi_agent/
│   │   │   ├── memory/
│   │   │   └── state.py
│   │   ├── rag/
│   │   ├── mcp/
│   │   ├── tools/
│   │   ├── plugins/
│   │   ├── file_processing/
│   │   ├── llm/
│   │   └── models/
│   ├── proto/
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
│
├── shadowlink-web/                       # ===== React 前端 =====
│   ├── src/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── stores/
│   │   ├── theme/
│   │   ├── services/
│   │   ├── pages/
│   │   ├── types/
│   │   └── App.tsx
│   ├── public/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── tailwind.config.ts
│
├── shadowlink-electron/                  # ===== Electron 桌面壳 =====
│   ├── src/
│   │   ├── main/
│   │   │   ├── index.ts                 # Electron 主进程
│   │   │   ├── hotkey.ts                # 全局热键
│   │   │   ├── tray.ts                  # 系统托盘
│   │   │   ├── quickbar.ts              # QuickBar 窗口
│   │   │   └── clipboard.ts             # 剪贴板监控
│   │   └── preload/
│   │       └── index.ts
│   ├── package.json
│   └── electron-builder.yml
│
├── proto/                                # ===== 共享 Proto =====
│   ├── agent_service.proto
│   ├── rag_service.proto
│   └── mcp_service.proto
│
├── deploy/                               # ===== 部署 =====
│   ├── docker-compose.yml
│   ├── docker-compose.dev.yml
│   ├── nginx/
│   └── scripts/
│
├── docs/                                 # ===== 文档 =====
│   ├── ARCHITECTURE_PLAN.md
│   ├── API.md
│   ├── DEVELOPMENT.md
│   └── DEPLOYMENT.md
│
├── assets/                               # ===== 静态资源 (保留) =====
│   ├── icons/
│   └── images/
│
├── scripts/                              # ===== 工具脚本 =====
│   ├── bootstrap_resources.py
│   ├── gen_proto.sh                      # Proto 代码生成
│   └── dev_setup.sh                      # 开发环境一键搭建
│
├── Makefile                              # 统一构建入口
├── .gitignore
└── README.md
```

---

## 十六、实施路线图

### Phase 0：基础设施搭建（Week 1-2）

```
[x] 创建 Monorepo 结构
[x] 搭建 Java SpringBoot 骨架项目 (Maven Multi-Module)
[x] 搭建 Python FastAPI 骨架项目
[x] 搭建 React + Vite + TypeScript 前端骨架
[x] 配置 Docker Compose 开发环境
[x] 定义 gRPC Proto 文件
[x] 配置 CI Pipeline
```

### Phase 1：核心通信链路（Week 3-4）

```
[ ] Java <-> Python gRPC 通信打通
[ ] Java <-> 前端 WebSocket 打通
[ ] 前端 <-> Java REST API 打通
[ ] 端到端消息流通：前端 -> Java -> Python -> LLM -> 流式返回
[ ] 迁移现有 LLM Client 到 Python 服务
[ ] 迁移现有 RAG Engine 到 Python 服务
```

### Phase 2：Agent 引擎升级（Week 5-7）

```
[ ] 实现 ReAct 循环 (LangGraph)
[ ] 实现 Plan-and-Execute (LangGraph)
[ ] 实现 Agent 策略切换
[ ] 实现 Supervisor MultiAgent
[ ] 实现 Hermes Agent 协议基础
[ ] 实现 Agent 记忆系统 (短期 + 长期)
[ ] MCP 协议集成
[ ] 内置工具迁移 + 扩展
```

### Phase 3：RAG 高级引擎（Week 8-9）

```
[ ] 混合检索 (Vector + BM25 + RRF)
[ ] 查询扩展 (HyDE, Multi-Query)
[ ] Reranker 集成 (BGE Reranker)
[ ] Self-RAG 实现
[ ] Agentic Chunking
[ ] 多格式文件解析管线
```

### Phase 4：氛围感 UI（Week 10-12）

```
[ ] 主界面布局实现
[ ] 氛围 Theme Engine
[ ] 6 套预设氛围主题
[ ] 模式切换动画
[ ] 对话面板 (流式 Markdown 渲染)
[ ] Agent 面板 (思考过程、工具调用、计划进度)
[ ] 知识库管理界面
[ ] 插件市场界面
[ ] 设置面板
```

### Phase 5：桌面集成（Week 13-14）

```
[ ] Electron 壳搭建
[ ] 全局热键注册
[ ] QuickBar 悬浮窗
[ ] 系统托盘
[ ] 截屏 OCR 集成
[ ] 剪贴板监控
```

### Phase 6：企业级加固（Week 15-16）

```
[ ] JWT 认证 + RBAC 权限
[ ] 多租户隔离
[ ] 限流 & 熔断
[ ] 审计日志
[ ] 可观测性 (Metrics + Logging + Tracing)
[ ] 安全加固 (XSS/CSRF/注入防护)
[ ] 性能优化 & 压力测试
[ ] 文档完善
```

---

## 附录A：技术选型对照表

| 类别 | 技术 | 版本 | 用途 |
|------|------|------|------|
| **Java** | Spring Boot | 3.2+ | 后端框架 |
| | Spring Security 6 | 6.2+ | 认证授权 |
| | MyBatis-Plus | 3.5+ | ORM |
| | Resilience4j | 2.2+ | 流量治理 |
| | grpc-spring-boot-starter | 3.0+ | gRPC 集成 |
| | SpringDoc OpenAPI | 2.3+ | API 文档 |
| | Micrometer | latest | 指标采集 |
| **Python** | FastAPI | 0.110+ | AI 服务框架 |
| | LangGraph | 0.2+ | Agent 图引擎 |
| | LangChain | 0.3+ | LLM 工具链 |
| | FAISS | latest | 向量索引 |
| | SentenceTransformers | latest | 嵌入模型 |
| | FlagEmbedding | latest | Reranker |
| | PyMuPDF | latest | PDF 解析 |
| | PaddleOCR | latest | OCR |
| | grpcio | latest | gRPC 服务 |
| | Pydantic V2 | 2.0+ | 数据验证 |
| | structlog | latest | 结构化日志 |
| **前端** | React | 18+ | UI 框架 |
| | TypeScript | 5.0+ | 类型安全 |
| | Vite | 5+ | 构建工具 |
| | Zustand | 4+ | 状态管理 |
| | React Query | 5+ | 服务端状态 |
| | Shadcn/UI | latest | 组件库 |
| | Tailwind CSS | 3+ | 样式 |
| | Framer Motion | latest | 动画 |
| | Socket.IO | 4+ | WebSocket |
| | Shiki | latest | 代码高亮 |
| **桌面** | Electron | 28+ | 桌面壳 |
| **基础设施** | MySQL | 8.0+ | 关系数据库 |
| | Redis | 7+ | 缓存/会话 |
| | Nginx | latest | 反向代理 |
| | Docker | 24+ | 容器化 |
| | Prometheus + Grafana | latest | 监控 |

---

## 附录B：核心创新点清单

### B.1 氛围感工作系统（核心差异化）
- **用户零门槛配置**：拖入链接/文件夹/软件即创建工作模式，无需理解技术概念
- **全栈上下文切换**：一键切换从 UI 到 Agent 到 RAG 到记忆的完整工作氛围
- **资源启动器**：一键打开模式下所有链接、文件夹、软件，进入工作状态
- **模式记忆隔离**：每个氛围模式拥有独立的 Letta 三层记忆空间

### B.2 智能 Agent 策略（用户无感知）
- **TaskComplexityRouter**：自动判断任务复杂度，路由到最优策略（用户不选也能用最好的）
- **用户可选覆盖**：高级用户可手动指定策略，系统尊重用户选择
- **四级策略梯度**：Direct Chat → ReAct → Plan-and-Execute → MultiAgent，按需升级

### B.3 前沿 Agent 技术
- **Reflexion 自我反思**：工具调用失败时自动反思原因并重试（ICML 2024）
- **Agent-as-Judge 辩论**：多 Agent 辩论 + 裁判评审，高价值输出质量提升 15-30%（ICLR 2025 CourtEval）
- **Hermes 技能学习**：复杂任务自动沉淀为可复用技能，Agent 越用越聪明（Nous Research 2026）
- **Letta 三层记忆**：Core/Recall/Archival，Agent 自主管理记忆（MemGPT 架构）
- **Sleep-Time Compute**：空闲时异步整理记忆和预计算，不消耗用户等待时间
- **Plan Cache**：相似任务复用历史执行计划，减少 46% LLM 调用
- **Speculative Execution**：多工具场景推测并行，延迟降低 40-60%
- **Supervisor MultiAgent**：多专家协作，任务自动分派（LangGraph 原生支持）

### B.4 生产级 RAG 管线
- **文档预处理**：清洗（去页眉页脚/水印/乱码）+ 结构化解析（表格/公式/元数据提取）
- **智能分块**：按文档大小自适应（递归/语义/LLM辅助），CPU 友好
- **Query 改写**：HyDE + 同义扩展 + 子问题分解，提升召回率
- **多路召回**：向量 + BM25 + Metadata 过滤，三路并行
- **RRF 融合 + Cross-Encoder 重排**：BGE Reranker，按硬件自动启用
- **Adaptive RAG + CRAG**：按复杂度选策略，质量不合格自动纠错
- **全链路日志**：`query → 改写 → chunks(score) → prompt → answer` 完整追踪
- **质量指标监控**：召回率、精准率、答案相关性(LLM-as-Judge)，按天趋势

### B.4.5 Agent 全链路可观测
- **逐步 Token 统计**：每步 LLM 调用的 input/output tokens + 工具调用耗时
- **耗时分解**：规划/执行/重排各环节毫秒级拆分，P50/P90/P99 分位
- **时间段细分可视化**：按小时/天/周聚合的 Token 消耗趋势、策略分布、错误率
- **单次执行详情**：可展开查看每一步的 tool/token/latency 明细

### B.5 CPU-First 硬件自适应
- **自动硬件探测**：启动时检测 CPU/RAM/GPU，自动选择最优计算方案
- **ONNX Runtime 加速**：嵌入/重排模型转 ONNX，CPU 推理提速 2-5x
- **双层 Embedding 缓存**：内存 LRU + SQLite 持久化，避免重复计算
- **内存预算管理**：8GB/16GB/16GB+ 三档自适应，低配机器也流畅
- **惰性模型加载**：按需加载，不用不占内存，启动秒级

### B.6 MCP 协议 & 开放生态
- **MCP 原生支持**：兼容社区所有 MCP Server 工具
- **插件市场**：可扩展的插件架构，支持热加载
- **双向 MCP**：既是 MCP Client（调用外部工具），也是 MCP Server（暴露能力）

### B.7 全局桌面集成
- **全局热键唤起**：任何应用中 Ctrl+Shift+Space 召唤 AI
- **选中文本问答**：选中 → 快捷键 → AI 在当前模式上下文中回答
- **截屏 OCR 理解**：截屏 → OCR → AI 分析图中内容
- **系统托盘常驻**：后台运行，随叫随到

### B.8 企业级工程
- **Java + Python 双语言架构**：业务治理与 AI 能力解耦
- **gRPC + REST 双通道**：高性能编排 + 兼容调试
- **多租户 Schema 隔离**：企业级数据隔离
- **Resilience4j 流量治理**：限流、熔断、隔舱、重试
- **全链路可观测**：Prometheus + Grafana + 结构化日志 + 链路追踪
- **Docker Compose 一键部署**：开发/生产环境一致

---

> **下一步**：请审阅本架构方案，确认后我们将按 Phase 0 开始搭建基础设施骨架。
