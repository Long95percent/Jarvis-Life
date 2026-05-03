# MCP 外接工具闭环实施计划

> 原来的“只接 MCP / 只列工具 / 只调用 API”方案弃用。新方案以闭环为核心：MCP 只负责提供外部能力，Jarvis 负责把结果转成业务动作，最终必须进入现有业务模块落库、投影刷新和主动消息。

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用最小工作量让外接 MCP 工具真正接入 Jarvis-Life 的生活安排闭环。

**Architecture:** 外部 MCP tool 不直接写核心业务状态，只返回外部信息或外部动作结果。后端新增一个轻量闭环层，把 `MCP Tool Result` 归一化成 `ActionProposal`，再由内部业务 executor 调用日程、主动消息、记忆等现有模块完成落库和通知。

**Tech Stack:** Python FastAPI、现有 `app/mcp`、现有 `ToolRegistry`、SQLite persistence、Jarvis agent/tool runtime、现有 calendar/proactive message API。

---

## 1. 为什么原计划不够闭环

原计划重点是：
- 配置 MCP server。
- discover tools。
- 注册到 ToolRegistry。
- agent 能调用。

这些只能证明“外部工具能调用”，但不能证明它能帮 Jarvis 安排生活。真正闭环应该包含：

```text
用户目标
  -> 智能体判断需要外部工具
  -> MCP 工具获取外部信息
  -> 结果归一化
  -> 生成 ActionProposal
  -> 内部业务模块执行写入
  -> 数据库和投影更新
  -> 主动消息告诉用户
  -> 用户可继续确认/修改
```

因此第一版不要追求接很多 MCP，而是先做一个能跑通的样例闭环。

---

## 2. 最小闭环范围

第一版只做“外部信息辅助日常安排”。

推荐样例：
- 用户：`帮我安排今晚放松一下，不要太远。`
- Agent：Alfred 或 Maxwell。
- MCP/API tool：地点搜索 / 网页搜索 / 路线估算，三选一即可。
- 业务落库：创建一条 calendar event。
- 通知：创建一条 proactive message。

第一版不做：
- 完整 MCP 管理后台。
- OAuth 接入。
- 插件市场。
- 大量第三方平台适配。
- 复杂多轮 UI。

---

## 3. 核心设计

### 3.1 MCP 只作为外部能力层

MCP tool 允许做：
- 查询地点。
- 查询路线。
- 搜索网页。
- 查询飞书/高德/其它 API。
- 发送外部消息，前提是权限允许并记录日志。

MCP tool 不允许直接做：
- 直接写 Jarvis calendar DB。
- 直接写 plan_day。
- 直接写 memory。
- 直接替用户做不可追踪的外部动作。

### 3.2 新增内部闭环对象：ActionProposal

`ActionProposal` 是 MCP 结果进入 Jarvis 业务模块前的中间形态。

建议结构：

```json
{
  "id": "proposal_xxx",
  "source": "mcp_tool",
  "source_tool": "amap.search_place",
  "source_agent": "maxwell",
  "proposal_type": "calendar_event.create",
  "title": "今晚去附近公园散步",
  "reason": "距离近、低压力、适合放松",
  "confidence": 0.82,
  "requires_confirmation": true,
  "payload": {
    "title": "公园散步",
    "start": "2026-05-04T19:30:00+08:00",
    "end": "2026-05-04T20:30:00+08:00",
    "location": "附近公园",
    "notes": "由外部地点/路线工具推荐"
  },
  "tool_trace_ids": ["toolcall_xxx"]
}
```

### 3.3 新增内部执行器：ActionProposalExecutor

Executor 只负责把 proposal 交给现有业务模块：
- `calendar_event.create` -> 走日程创建接口/服务。
- `calendar_event.update` -> 走日程更新接口/服务。
- `proactive_message.create` -> 走主动消息 persistence/API。
- `memory.write` -> 走记忆模块。

Executor 不应该直接拼 SQL 写业务表，避免绕过模块边界。

### 3.4 Tool 调用日志是闭环证据

每次 MCP 调用都记录：
- `id`
- `tool_name`
- `agent_id`
- `session_id`
- `arguments_json`
- `result_json`
- `success`
- `error`
- `latency_ms`
- `created_at`

每个 ActionProposal 记录它来自哪些 tool call。

---

## 4. 文件结构建议

### 新增文件
- `shadowlink-ai/app/jarvis/external_tool_results.py`
  - 负责 MCP/tool 返回结果归一化。
- `shadowlink-ai/app/jarvis/action_proposals.py`
  - 定义 `ActionProposal`、创建 proposal、执行 proposal。
- `shadowlink-ai/tests/unit/jarvis/test_mcp_life_loop.py`
  - 覆盖 MCP 结果 -> proposal -> 日程落库 -> 主动消息 的闭环。

### 修改文件
- `shadowlink-ai/app/api/v1/mcp_router.py`
  - 调用工具时写 tool call log。
  - 可选：支持传 `agent_id`、`session_id`。
- `shadowlink-ai/app/mcp/registry.py`
  - 给工具信息附加 `permission_level`、`allowed_agents`，或用轻量 sidecar policy 实现。
- `shadowlink-ai/app/jarvis/persistence.py`
  - 新增 tool call log 表和 action proposal 表的轻量存储函数。
- `shadowlink-ai/app/tools/jarvis_tools.py`
  - 新增一个 Jarvis 内部工具，例如 `jarvis_external_life_arrange`，负责触发外部工具并生成 proposal。
- `shadowlink-ai/app/jarvis/agents.py`
  - 给 Alfred/Maxwell 增加该内部工具白名单。

### 暂不修改
- 前端正式管理后台先不做。
- 圆桌接口文档不动。
- 日程接口不新增 URL，优先复用现有写入路径。

---

## 5. 实施任务

### Task 1: Tool 调用日志

**Files:**
- Modify: `shadowlink-ai/app/jarvis/persistence.py`
- Modify: `shadowlink-ai/app/api/v1/mcp_router.py`
- Test: `shadowlink-ai/tests/unit/jarvis/test_mcp_life_loop.py`

- [ ] **Step 1: 写失败测试**

新增测试：调用一个假 tool 后，能查到 tool call log。

测试意图：证明 MCP/API 调用不是黑盒，后续 proposal 能追踪来源。

- [ ] **Step 2: 新增 persistence 表**

增加 `jarvis_tool_call_logs`：

```sql
CREATE TABLE IF NOT EXISTS jarvis_tool_call_logs (
  id TEXT PRIMARY KEY,
  tool_name TEXT NOT NULL,
  agent_id TEXT,
  session_id TEXT,
  arguments_json TEXT NOT NULL,
  result_json TEXT,
  success INTEGER NOT NULL DEFAULT 0,
  error TEXT,
  latency_ms REAL,
  created_at REAL NOT NULL
)
```

- [ ] **Step 3: 新增保存/查询函数**

建议函数：
- `save_tool_call_log(...) -> dict`
- `list_tool_call_logs(limit=100) -> list[dict]`

- [ ] **Step 4: 接入 `/v1/mcp/tools/call`**

`mcp_router.call_tool` 执行成功/失败都写 log。

- [ ] **Step 5: 跑测试**

```bash
pytest shadowlink-ai/tests/unit/jarvis/test_mcp_life_loop.py::test_tool_call_is_logged -q
```

---

### Task 2: 定义 ActionProposal

**Files:**
- Create: `shadowlink-ai/app/jarvis/action_proposals.py`
- Modify: `shadowlink-ai/app/jarvis/persistence.py`
- Test: `shadowlink-ai/tests/unit/jarvis/test_mcp_life_loop.py`

- [ ] **Step 1: 写失败测试**

测试：创建一个 `calendar_event.create` proposal 后，能保存并读取。

- [ ] **Step 2: 定义 proposal 类型**

第一版只支持：
- `calendar_event.create`
- `calendar_event.update`
- `proactive_message.create`

- [ ] **Step 3: 新增 proposal 表**

```sql
CREATE TABLE IF NOT EXISTS jarvis_action_proposals (
  id TEXT PRIMARY KEY,
  proposal_type TEXT NOT NULL,
  title TEXT NOT NULL,
  reason TEXT,
  source TEXT NOT NULL,
  source_tool TEXT,
  source_agent TEXT,
  requires_confirmation INTEGER NOT NULL DEFAULT 1,
  status TEXT NOT NULL DEFAULT 'pending',
  payload_json TEXT NOT NULL,
  tool_trace_ids_json TEXT NOT NULL DEFAULT '[]',
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
)
```

- [ ] **Step 4: 新增保存/读取函数**

建议函数：
- `save_action_proposal(proposal: dict) -> dict`
- `get_action_proposal(proposal_id: str) -> dict | None`
- `list_action_proposals(status: str | None = None) -> list[dict]`

- [ ] **Step 5: 跑测试**

```bash
pytest shadowlink-ai/tests/unit/jarvis/test_mcp_life_loop.py::test_action_proposal_can_be_saved_and_loaded -q
```

---

### Task 3: MCP 结果归一化

**Files:**
- Create: `shadowlink-ai/app/jarvis/external_tool_results.py`
- Test: `shadowlink-ai/tests/unit/jarvis/test_mcp_life_loop.py`

- [ ] **Step 1: 写失败测试**

输入一个地点搜索结果，输出一个统一候选项列表。

示例输入：

```python
raw = {
    "places": [
        {"name": "滨江公园", "address": "江边路", "distance_minutes": 18}
    ]
}
```

期望输出：

```python
[
    {
        "kind": "place",
        "title": "滨江公园",
        "location": "江边路",
        "estimated_minutes": 18,
        "source_tool": "amap.search_place"
    }
]
```

- [ ] **Step 2: 实现轻量 normalizer**

第一版只做三种 shape：
- `places`
- `items`
- `results`

字段尽量容错：`name/title`、`address/location`、`distance_minutes/duration_minutes`。

- [ ] **Step 3: 跑测试**

```bash
pytest shadowlink-ai/tests/unit/jarvis/test_mcp_life_loop.py::test_normalize_place_search_result -q
```

---

### Task 4: Proposal Executor 走现有业务模块

**Files:**
- Modify: `shadowlink-ai/app/jarvis/action_proposals.py`
- Test: `shadowlink-ai/tests/unit/jarvis/test_mcp_life_loop.py`

- [ ] **Step 1: 写失败测试**

测试：执行 `calendar_event.create` proposal 后，真实创建 calendar event，并能在 planner calendar items 查到。

- [ ] **Step 2: 实现 executor**

`execute_action_proposal(proposal_id, confirmed_by="system")`：
- 读取 proposal。
- 如果 `requires_confirmation=True` 且没有确认参数，则不执行。
- `calendar_event.create` 调用现有 calendar adapter/API 等价服务创建事件。
- 成功后把 proposal status 改成 `executed`。

- [ ] **Step 3: 主动消息联动**

执行成功后创建一条主动消息，内容类似：

```text
我用了外部工具查到这个安排比较合适，已经帮你加入日程：今晚 19:30 滨江公园散步。
```

- [ ] **Step 4: 跑测试**

```bash
pytest shadowlink-ai/tests/unit/jarvis/test_mcp_life_loop.py::test_execute_calendar_proposal_writes_event_and_message -q
```

---

### Task 5: Agent 可调用的最小内部工具

**Files:**
- Modify: `shadowlink-ai/app/tools/jarvis_tools.py`
- Modify: `shadowlink-ai/app/jarvis/agents.py`
- Test: `shadowlink-ai/tests/unit/jarvis/test_mcp_life_loop.py`

- [ ] **Step 1: 写失败测试**

测试：调用 `jarvis_external_life_arrange`，给定 fake external result，返回 proposal。

- [ ] **Step 2: 新增工具**

工具职责：
- 接收用户目标、候选外部工具结果。
- 调用 normalizer。
- 选择第一个安全候选项。
- 生成 `calendar_event.create` proposal。

第一版可以先不让它真实调用外部 MCP，而是接受 `external_result` 参数。这样先打通闭环，后续再接真实 MCP。

- [ ] **Step 3: 加入 agent whitelist**

给 Alfred / Maxwell 增加：
- `jarvis_external_life_arrange`

- [ ] **Step 4: 跑测试**

```bash
pytest shadowlink-ai/tests/unit/jarvis/test_mcp_life_loop.py::test_external_life_arrange_tool_creates_proposal -q
```

---

### Task 6: 接一个真实 MCP 或模拟 MCP 样例

**Files:**
- Modify: `config/mcp_servers.example.json` 或 Create: `config/mcp_servers.example.json`
- Modify: `shadowlink-ai/app/mcp/client.py`
- Modify: `shadowlink-ai/app/core/lifespan.py`
- Test: `shadowlink-ai/tests/unit/jarvis/test_mcp_life_loop.py`

- [ ] **Step 1: 写配置示例**

```json
[
  {
    "name": "web-search-demo",
    "enabled": false,
    "transport": "http",
    "endpoint": "http://localhost:8765/mcp",
    "allowed_agents": ["alfred", "maxwell"],
    "permission_level": "read_only"
  }
]
```

- [ ] **Step 2: 启动时读取配置**

如果配置不存在，不报错。

- [ ] **Step 3: discover tools 后注册**

注册名使用：

```text
{server_name}.{tool_name}
```

- [ ] **Step 4: 保持第一版可降级**

没有真实 MCP server 时，系统照常启动。测试使用 fake MCP client 或 fake registry。

---

## 6. 最小验收标准

第一版完成后，必须能证明：

- `/v1/mcp/tools/call` 的调用会写日志。
- 外部工具结果能归一化。
- 外部结果能生成 `ActionProposal`。
- `ActionProposal` 能通过内部业务模块创建真实日程。
- 日程能在 planner calendar items 中出现。
- 系统能创建主动消息告诉用户安排结果。
- 没有真实 MCP server 时，系统不崩。
- 未授权 agent 不能执行受限工具。

---

## 7. 未来扩展但不在第一版做

- 完整 MCP 管理前端。
- OAuth 授权。
- 美团/飞书完整业务适配。
- 多 MCP server 健康检查 UI。
- 参数 schema 可视化编辑器。
- 大规模 tool marketplace。
- 复杂多智能体协商 UI。

---

## 8. 推荐开发顺序

1. Tool call log。
2. ActionProposal 表和模型。
3. MCP result normalizer。
4. Proposal executor 写日程和主动消息。
5. Agent 内部工具 `jarvis_external_life_arrange`。
6. MCP server 配置和 discover 注册。

这个顺序保证每一步都有业务价值。即使时间只够做到第 4 步，也已经形成了“外部结果 -> Jarvis 业务闭环”的核心能力。

---

## 9. 对项目闭环的最终定义

外接 MCP 不算完成，除非它至少完成一次：

```text
外部工具结果
  -> Jarvis action proposal
  -> 后端业务模块写入
  -> 数据库状态变化
  -> 投影/上下文刷新
  -> 用户收到主动消息或可见反馈
```

只要缺少“业务模块写入”和“用户反馈”，就只是外部工具调用，不是 Jarvis-Life 闭环。

