# ShadowLink Agent Architecture

> **Version**: 1.0  
> **Date**: 2026-04-16  
> **Status**: Active  
> **Scope**: 只定义 Agent 模块自身的核心设计、代码边界和首版落地范围

---

## 一、文档目标

这份文档只回答一个问题：

> ShadowLink 的 Agent 模块到底负责什么，内部怎么分层，首版到底实现到哪里。

它不再重复整份系统总架构，也不讨论桌面端、插件市场、企业治理这类外围能力。

---

## 二、Agent 模块定位

Agent 模块是 ShadowLink AI 服务里的“任务执行核心”。

它的职责不是保存业务数据，也不是直接承载前端状态，而是：

- 接收一次用户任务请求
- 根据任务复杂度选择执行策略
- 组装模式上下文、记忆、工具、RAG 检索结果
- 驱动具体执行流程
- 以普通响应或流式事件的形式返回结果

一句话概括：

> Agent = ShadowLink 中负责“理解任务并选择合适执行方式”的运行时引擎。

---

## 三、职责边界

### 3.1 Agent 负责什么

- 自动路由 `direct / react / plan_execute`
- 执行策略图或执行器
- 注入模式上下文
- 注入短期/长期/情节记忆
- 按需调用工具
- 按需调用 RAG
- 输出步骤、token、状态、最终答案

### 3.2 Agent 不负责什么

- 用户鉴权
- 会话持久化落库
- WorkMode 的 CRUD 管理
- 文件上传本身
- 向量索引生命周期管理
- 前端展示逻辑

这些应分别归属于 Java 网关、业务模块、RAG 模块和前端。

---

## 四、模块总览

当前 Agent 代码主要位于：

- `shadowlink-ai/app/agent/engine.py`
- `shadowlink-ai/app/agent/state.py`
- `shadowlink-ai/app/agent/react/`
- `shadowlink-ai/app/agent/plan_execute/`
- `shadowlink-ai/app/agent/multi_agent/`
- `shadowlink-ai/app/agent/memory/`

推荐从下面的角度理解：

```text
Agent API Request
    ->
AgentEngine
    ->
TaskComplexityRouter
    ->
Strategy Executor
    |- DirectExecutor
    |- ReAct Executor / Graph
    |- PlanExecute Executor / Graph
    |- Supervisor Executor (存在但不作为首版主链路)
    ->
Tools / RAG / Memory
    ->
AgentResponse or StreamEvent
```

---

## 五、核心设计原则

### 5.1 自动优先，手动可覆盖

用户默认不需要理解 Agent 策略。

系统根据任务内容自动选择执行方式；如果用户或上层调用方显式指定 `strategy`，则直接尊重。

### 5.2 模式隔离优先

Agent 不是一个全局统一人格，而是随 `mode_id` 改变行为边界。

模式至少影响：

- system prompt
- 策略偏好
- 可用工具
- 知识作用域
- 记忆上下文

### 5.3 首版先做三层闭环

首版只围绕三种执行形态建立稳定闭环：

- `direct`
- `react`
- `plan_execute`

虽然代码中已有 `supervisor / swarm / hierarchical / hermes` 等入口，但这些都不应进入当前主交付路径。

### 5.4 流式事件是首版标准输出

对前端和 Java 网关来说，Agent 的标准输出不只是最终答案，还包括中间事件。

这使前端可以展示：

- 正在思考
- 正在调用工具
- 正在执行计划步骤
- 输出 token
- 结束状态

---

## 六、请求与响应模型

核心模型定义在：

- `shadowlink-ai/app/models/agent.py`

### 6.1 AgentRequest

建议把 `AgentRequest` 视为 Agent 的统一运行指令，关键字段包括：

- `session_id`: 会话标识
- `mode_id`: 当前工作模式
- `message`: 用户输入
- `strategy`: 显式指定策略，可为空
- `stream`: 是否流式返回
- `max_iterations`: 最大循环步数
- `tools`: 指定工具覆盖
- `context`: 上层附加上下文

这意味着 Agent 层不需要知道完整业务实体，只要拿到一份足够执行的运行指令即可。

### 6.2 AgentResponse

非流式结果统一返回：

- `answer`
- `strategy`
- `steps`
- `total_tokens`
- `total_latency_ms`

### 6.3 StreamEvent

流式输出通过 SSE 返回事件流，常见事件包括：

- `thought`
- `action`
- `observation`
- `tool_call`
- `tool_result`
- `token`
- `done`
- `error`

这决定了 Agent 模块不仅是“回答生成器”，也是“执行过程事件源”。

---

## 七、AgentEngine 作为总入口

总入口位于：

- `shadowlink-ai/app/agent/engine.py`

`AgentEngine` 的职责是统一调度，而不是自己完成所有执行细节。

核心职责如下：

1. 根据请求选择策略
2. 获取记忆上下文
3. 记录用户消息到短期记忆
4. 调用对应策略执行器
5. 记录回答与 episode
6. 输出统一响应或流式事件

建议把它理解成一个 orchestrator，而不是具体策略实现本身。

### 7.1 register_strategy 机制

`AgentEngine` 通过 `register_strategy()` 注册具体策略执行器。

这使它具备两个好处：

- 策略和入口解耦
- 生命周期初始化时可以按配置启用或替换执行器

### 7.2 Memory Integration

当前引擎会从以下记忆源拉取上下文：

- `short_term_memory`
- `long_term_memory`
- `episodic_memory`

然后把这些内容注入到 `request.context["memory"]` 中，交给具体策略使用。

这说明记忆不是某个策略私有能力，而是 Agent 的通用输入层。

---

## 八、任务路由设计

任务路由器位于：

- `shadowlink-ai/app/agent/engine.py`

类名：

- `TaskComplexityRouter`

### 8.1 路由目标

它要解决的问题不是“判断语义类别”，而是：

> 这条请求最适合用哪种执行开销来完成。

也就是说，路由本质上是执行策略选择，而不是传统意图识别。

### 8.2 当前复杂度分层

当前代码中的复杂度层级是：

- `simple`
- `moderate`
- `complex`
- `multi_domain`

默认映射关系为：

- `simple` -> `direct`
- `moderate` -> `react`
- `complex` -> `plan_execute`
- `multi_domain` -> `supervisor`

### 8.3 当前路由依据

目前主要基于轻量启发式判断：

- 文本长度
- 计划型关键词
- 多领域关键词
- 工具相关关键词
- 模式偏好覆盖

这是首版合理选择，因为它：

- 成本低
- 可解释
- 容易调参
- 不依赖额外模型

### 8.4 首版路由建议

虽然代码支持 `supervisor`，但首版建议收敛成：

- `simple` -> `direct`
- `moderate` -> `react`
- `complex` -> `plan_execute`

`multi_domain -> supervisor` 可以保留代码入口，但不作为默认主链路。

原因很简单：

- MultiAgent 的收益不稳定
- 测试成本高
- 前端交互复杂度高
- 会掩盖首版真正需要验证的单 Agent 主链路

---

## 九、三种核心执行策略

## 9.1 Direct

Direct 是最轻量策略，对应：

- 单次 LLM 调用
- 不进入 Agent 循环
- 不调用规划器
- 默认不依赖工具

适合：

- 简单问答
- 翻译
- 改写
- 轻量解释

当前实现中，`DirectExecutor` 会：

- 基于 `mode_id` 选择系统提示词
- 将 memory context 拼接进 prompt
- 流式返回 token
- 返回最终 `done` 事件

因此 Direct 不是“降级兜底”，而是一个正式的低成本执行路径。

## 9.2 ReAct

ReAct 的核心思想是：

> 先推理，再决定要不要调用工具，再根据观察结果继续推理。

相关代码位于：

- `shadowlink-ai/app/agent/react/graph.py`
- `shadowlink-ai/app/agent/react/executor.py`
- `shadowlink-ai/app/agent/react/nodes.py`

当前图结构可以概括为：

```text
START
  -> reason
  -> act (如果产生 tool call)
  -> reflect (按条件触发)
  -> reason
  -> END
```

它适合：

- 需要查资料
- 需要知识检索
- 需要少量工具调用
- 需要边执行边调整的问题

ReAct 是首版最重要的主力策略。

## 9.3 Plan-and-Execute

Plan-and-Execute 的核心思想是：

> 对复杂任务先拆计划，再按步骤执行，失败时允许重规划。

相关代码位于：

- `shadowlink-ai/app/agent/plan_execute/graph.py`
- `shadowlink-ai/app/agent/plan_execute/planner.py`
- `shadowlink-ai/app/agent/plan_execute/executor.py`
- `shadowlink-ai/app/agent/plan_execute/replan.py`

当前流程是：

```text
planner
  -> executor(loop)
  -> replanner(必要时)
  -> reporter
```

适合：

- 分阶段分析
- 报告生成
- 对比研究
- 项目规划

它的价值不在于“更高级”，而在于能显式控制复杂任务的过程。

---

## 十、状态模型设计

状态定义位于：

- `shadowlink-ai/app/agent/state.py`

这是整个 Agent 模块非常关键的一层，因为 LangGraph 的节点流转都依赖状态结构。

### 10.1 AgentState

用于 ReAct 流程，核心字段包括：

- `messages`
- `mode_id`
- `tools_available`
- `memory_context`
- `rag_context`
- `iteration_count`
- `max_iterations`
- `reflection_notes`

这个状态说明 ReAct 的核心关切是：

- 对话上下文
- 工具可用性
- 记忆注入
- RAG 注入
- 安全循环限制

### 10.2 PlanExecuteState

用于计划执行流程，核心字段包括：

- `input`
- `plan`
- `step_index`
- `step_results`
- `completed_steps`
- `current_issue`
- `final_answer`

这个状态说明 Plan-and-Execute 的核心关切是：

- 是否有结构化计划
- 执行到哪一步
- 每一步结果是什么
- 是否因为异常需要重规划

### 10.3 SupervisorState

用于多 Agent 协调，字段包括：

- `task`
- `current_agent`
- `agent_results`
- `delegation_history`
- `next_action`
- `iteration_count`

这套状态在代码上已经存在，但不建议让它进入首版主链路。

---

## 十一、记忆如何接入 Agent

记忆模块位于：

- `shadowlink-ai/app/agent/memory/short_term.py`
- `shadowlink-ai/app/agent/memory/long_term.py`
- `shadowlink-ai/app/agent/memory/episodic.py`
- `shadowlink-ai/app/agent/memory/semantic.py`

### 11.1 当前接入方式

当前设计不是让每个策略单独管理记忆，而是：

- 先由 `AgentEngine` 汇总 memory context
- 再把记忆内容注入到请求上下文
- 由具体执行器决定如何使用

### 11.2 首版建议

首版只把以下能力视为稳定目标：

- 短期记忆
- 历史消息注入
- episode 记录

以下能力建议降级处理或暂不纳入主路径：

- semantic memory
- 自主记忆写回
- 复杂长期记忆检索策略

原因：

- 记忆系统太容易把简单问题做复杂
- 首版核心目标是让策略切换和执行质量成立
- 复杂记忆应晚于会话持久化和 RAG 稳定化

---

## 十二、工具与 RAG 的接入方式

### 12.1 工具不是 Agent 的附属品

Agent 负责决定“何时调用工具”，但工具本身属于独立模块。

也就是说：

- Agent 负责 orchestration
- Tools 负责 capability

### 12.2 RAG 不是单独策略，而是上下文增强层

RAG 不应该被理解为第四种 Agent 策略。

更合理的定位是：

- Direct 可以不用 RAG
- ReAct 经常会用 RAG
- Plan-and-Execute 的某些步骤可以用 RAG

因此 RAG 应该作为 Agent 的增强输入层，而不是平级策略。

### 12.3 模式对工具和 RAG 的影响

`mode_id` 至少应影响：

- 默认 system prompt
- 策略倾向
- 工具白名单
- 检索索引作用域

这一点在 `engine.py` 的 mode prompt、mode strategy override、preferred tools 中已经有雏形。

---

## 十三、流式事件模型

Agent 对前端最重要的价值之一，是能暴露执行过程。

首版建议统一事件语义：

- `thought`: 当前正在做什么
- `action`: 决定执行哪个动作
- `tool_call`: 发起工具调用
- `tool_result`: 工具结果返回
- `observation`: 对工具或检索结果的解释
- `token`: 正文 token 流
- `done`: 任务完成
- `error`: 执行失败

好处是：

- Java 网关只需透传
- 前端可按事件类型渲染
- 不同策略可以共享统一展示协议

---

## 十四、当前代码结构与推荐认知方式

### 14.1 核心入口层

- `app/agent/engine.py`
- `app/models/agent.py`
- `app/api/v1/agent_router.py`

### 14.2 策略层

- `app/agent/react/`
- `app/agent/plan_execute/`
- `app/agent/multi_agent/`

### 14.3 状态层

- `app/agent/state.py`

### 14.4 记忆层

- `app/agent/memory/`

建议以后始终按这四层来维护，不要把 prompt、路由、graph、memory、tool glue 混在一个文件里。

---

## 十五、首版落地范围

### 15.1 必须完成

- `AgentEngine` 作为统一入口稳定可用
- `TaskComplexityRouter` 稳定输出 `direct / react / plan_execute`
- ReAct 流程稳定执行工具调用
- Plan-and-Execute 能完成规划、逐步执行、失败重规划
- memory context 能稳定注入
- 流式事件协议稳定

### 15.2 可以保留但不作为核心承诺

- `supervisor`
- `swarm`
- mode-specific override
- plan cache
- reflection

### 15.3 明确不作为当前实现重点

- hierarchical orchestration
- hermes protocol
- skill learning
- debate / judge
- speculative execution
- 完整 Agent observability 平台

---

## 十六、推荐实施顺序

### Phase A：统一入口稳定

- 固化 `AgentRequest / AgentResponse / StreamEvent`
- 打通注册式策略执行器
- 确保 Direct/ReAct/PlanExecute 都能被统一调度

### Phase B：ReAct 成为主力路径

- 规范工具调用事件
- 打通 RAG 检索事件
- 控制循环上限与错误回退

### Phase C：Plan-and-Execute 稳定

- 提高 planner 输出的结构化稳定性
- 明确 step tool 参数生成逻辑
- 完善 replan 触发条件

### Phase D：模式与记忆融合

- 把 `mode_id` 真正映射到 prompt / tools / knowledge scope
- 统一 memory context 注入格式

### Phase E：最后再考虑多 Agent

只有单 Agent 主链路稳定后，再决定是否让 `supervisor / swarm` 成为对外能力。

---

## 十七、最终结论

ShadowLink 的 Agent 模块不应该被设计成“所有前沿 Agent 名词的收集器”，而应该是一个稳定的任务执行内核。

首版真正需要成立的只有三件事：

1. 自动把任务路由到合适策略  
2. 让 ReAct 和 Plan-and-Execute 真正可用  
3. 让模式、记忆、工具、RAG 能被统一注入执行过程

只要这三件事成立，Agent 模块就已经具备产品价值；反之，再多 MultiAgent 名词也只是噪音。
