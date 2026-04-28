# Step 1 工作留痕：智能体回复速度基线与测试方案

日期：2026-04-28  
对应计划：`docs/lsq-worklog/4-28-worklog/4-28plan.md` 中 `Step 1：速度调优基线与测试方案`  
验证文档：`docs/lsq-worklog/4-28-worklog/test/Step1-智能体回复速度基线验证方法.md`

## 一、本 Step 目标

本 Step 目标是建立可复测的 Jarvis 回复速度基线，而不是立刻大规模优化。

核心要求：

1. 固定 20 条测试 prompt。
2. 覆盖普通私聊、跨 Agent 路由、长期记忆、心理关怀、圆桌入口。
3. 后端主链路输出 timing span。
4. 提供一键跑基线脚本。
5. 输出 JSON/CSV，方便后续 Step2/Step4 前后对比。

## 二、完成内容

### 1. 固定 20 条基线 prompt

文件：`shadowlink-ai/scripts/jarvis_perf/baseline_prompts.json`

分类：

- `normal_chat`：5 条普通陪伴/分析/建议。
- `schedule_route`：5 条日程/计划路由到 Maxwell。
- `memory_recall`：4 条需要长期记忆或偏好画像召回。
- `mood_care`：3 条心理关怀相关 prompt。
- `roundtable`：3 条圆桌启动或圆桌推荐入口 prompt。

每条记录包含：

- `id`
- `category`
- `agent_id`
- `message`
- `new_session`
- `expected`

### 2. 新增基线运行脚本

文件：`shadowlink-ai/scripts/jarvis_perf/run_baseline.py`

能力：

- 顺序执行固定 prompt。
- 支持直连 Python AI：`http://localhost:8000/v1`。
- 支持通过 Java Gateway：`http://localhost:8080/api/v1`。
- 支持 `--limit` 做冒烟测试。
- 记录客户端总耗时、首字节耗时、HTTP 状态、错误码。
- 自动提取后端 `timing.spans` 中的关键耗时。
- 输出 JSON 和 CSV。

输出位置：

```text
shadowlink-ai/data/perf_baselines/jarvis_baseline_<run_id>.json
shadowlink-ai/data/perf_baselines/jarvis_baseline_<run_id>.csv
```

### 3. Jarvis 私聊接口增加 timing

文件：`shadowlink-ai/app/api/v1/jarvis_router.py`

响应模型 `AgentChatResponse` 新增：

```text
timing: dict | None
```

成功响应会返回：

- `timing.total_ms`
- `timing.spans`

当前 span：

- `route_decided`
- `activity_marked`
- `conversation_persisted`
- `base_context`
- `memory_context`
- `consult`
- `llm_turn`
- `actions_built`
- `memory_save`
- `persist_final_turns`
- `escalation_eval`
- `shadow_observe`，仅在 Shadow learner 启用时出现。

失败响应：

- 如果 `run_agent_turn` 失败，错误 detail 中也会附带已完成的 `timing`。
- 这样 Step0 的 `error_code/suggestion` 和 Step1 的 timing 可以同时用于定位问题。

### 4. 增加后端 timing 日志

文件：`shadowlink-ai/app/api/v1/jarvis_router.py`

新增日志事件：

```text
jarvis.chat.timing
```

包含：

- `agent_id`
- `routed_agent_id`
- `session_id`
- `total_ms`
- `spans`

用途：

- 即使前端没保存 response，也可以从 AI 服务日志回查耗时。

### 5. 新增前端/命令行验证说明

文件：`docs/lsq-worklog/4-28-worklog/test/Step1-智能体回复速度基线验证方法.md`

内容包括：

- 怎么跑基线脚本。
- 怎么从前端 Network 看 timing。
- 输出 CSV/JSON 含义。
- 首轮基线记录模板。
- Step1 通过标准。

## 三、已执行验证

### 1. JSON 用例文件检查

验证：

- `baseline_prompts.json` 是合法 JSON。
- 顶层是数组。
- 数量为 20。

结果：通过。

### 2. Python 编译检查

验证文件：

```text
shadowlink-ai/scripts/jarvis_perf/run_baseline.py
shadowlink-ai/app/api/v1/jarvis_router.py
```

结果：通过。

### 3. 基线脚本静态检查

验证：

- 支持 `--base-url`。
- 支持 `--limit`。
- 输出 JSON/CSV。
- 能提取 response 中的 `timing`。

结果：通过。

说明：本轮没有强制跑完整 20 条真实 LLM 请求，因为这会消耗 Provider 调用额度和时间。真实跑法已写入验证文档。

## 四、如何跑首轮基线

直连 Python AI：

```powershell
cd D:\github_desktop\Jarvis-Life\shadowlink-ai
python scripts\jarvis_perf\run_baseline.py --base-url http://localhost:8000/v1
```

通过 Java Gateway：

```powershell
cd D:\github_desktop\Jarvis-Life\shadowlink-ai
python scripts\jarvis_perf\run_baseline.py --base-url http://localhost:8080/api/v1
```

冒烟测试：

```powershell
cd D:\github_desktop\Jarvis-Life\shadowlink-ai
python scripts\jarvis_perf\run_baseline.py --base-url http://localhost:8000/v1 --limit 3
```

## 五、影响范围

代码文件：

```text
shadowlink-ai/app/api/v1/jarvis_router.py
shadowlink-ai/scripts/jarvis_perf/baseline_prompts.json
shadowlink-ai/scripts/jarvis_perf/run_baseline.py
```

文档文件：

```text
docs/lsq-worklog/4-28-worklog/test/Step1-智能体回复速度基线验证方法.md
docs/lsq-worklog/4-28-worklog/Step1-智能体回复速度基线-worklog.md
```

## 六、后续建议

下一步进入 Step2 之前，建议先至少跑一次：

```text
--limit 3
```

如果服务和 LLM 都稳定，再跑完整 20 条，并把 CSV 中最慢 3 条记录到本文件或单独的首轮结果文件。

后续优化优先看：

1. `llm_turn` 是否占绝大多数。
2. `memory_context` 是否超过 300ms。
3. `consult` 是否在普通聊天中被误触发。
4. `persist_final_turns` 是否异常慢。
5. 前端 Network 总耗时是否明显大于 `timing.total_ms`。
