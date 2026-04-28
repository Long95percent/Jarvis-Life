# Step 1 智能体回复速度基线验证方法

日期：2026-04-28  
验证对象：Jarvis 私聊主链路、固定 20 条 prompt、后端 timing span、前端 Network 端到端耗时。

## 一、验证目标

Step 1 不以大优化为目标，而是建立可复测基线：

1. 固定 20 条 prompt，覆盖普通私聊、跨 Agent 路由、长期记忆、心理关怀、圆桌入口。
2. 每次优化前后可重复执行同一批 prompt。
3. 后端返回 `timing.total_ms` 和关键 `timing.spans`。
4. 前端可通过 DevTools Network 查看接口总耗时和 response timing。
5. 命令行脚本可输出 JSON/CSV，方便横向对比。

## 二、基线用例位置

固定用例文件：

```text
shadowlink-ai/scripts/jarvis_perf/baseline_prompts.json
```

分类数量：

- `normal_chat`：5 条
- `schedule_route`：5 条
- `memory_recall`：4 条
- `mood_care`：3 条
- `roundtable`：3 条

## 三、后端 timing 字段

调用：

```text
POST /api/v1/jarvis/chat
```

或直连 Python：

```text
POST /v1/jarvis/chat
```

成功响应中会新增：

```json
{
  "timing": {
    "total_ms": 1234.5,
    "spans": [
      {"name": "route_decided", "duration_ms": 0.2},
      {"name": "activity_marked", "duration_ms": 1.1},
      {"name": "conversation_persisted", "duration_ms": 5.3},
      {"name": "base_context", "duration_ms": 12.4, "history_turns": 6},
      {"name": "memory_context", "duration_ms": 42.8},
      {"name": "consult", "duration_ms": 0.6},
      {"name": "llm_turn", "duration_ms": 1800.0},
      {"name": "actions_built", "duration_ms": 4.0},
      {"name": "memory_save", "duration_ms": 30.0},
      {"name": "persist_final_turns", "duration_ms": 8.0},
      {"name": "escalation_eval", "duration_ms": 0.4}
    ]
  }
}
```

重点看：

- `total_ms`：后端处理总耗时。
- `llm_turn`：主 LLM 调用耗时。
- `memory_context`：长期记忆、偏好画像、协作记忆拼装耗时。
- `consult`：私下 Agent consult 耗时。
- `persist_final_turns`：最终聊天记录写库耗时。

## 四、命令行跑基线

### 1. 直连 Python AI

```powershell
cd D:\github_desktop\Jarvis-Life\shadowlink-ai
python scripts\jarvis_perf\run_baseline.py --base-url http://localhost:8000/v1
```

### 2. 通过 Java Gateway 跑

```powershell
cd D:\github_desktop\Jarvis-Life\shadowlink-ai
python scripts\jarvis_perf\run_baseline.py --base-url http://localhost:8080/api/v1
```

### 3. 只跑前 3 条冒烟

```powershell
cd D:\github_desktop\Jarvis-Life\shadowlink-ai
python scripts\jarvis_perf\run_baseline.py --base-url http://localhost:8000/v1 --limit 3
```

## 五、输出位置

脚本会输出：

```text
shadowlink-ai/data/perf_baselines/jarvis_baseline_<run_id>.json
shadowlink-ai/data/perf_baselines/jarvis_baseline_<run_id>.csv
```

CSV 关键列：

- `case_id`
- `category`
- `agent_id`
- `routed_agent_id`
- `status_code`
- `ok`
- `first_byte_ms`
- `total_ms`
- `server_total_ms`
- `llm_ms`
- `memory_ms`
- `consult_ms`
- `persist_ms`
- `actions_count`
- `content_len`
- `error_code`

## 六、从前端手动验证

1. 打开前端：

```text
http://localhost:5173
```

2. 进入 Jarvis 私聊，任选 3 条基线 prompt 手动发送。

推荐：

```text
我今天有点累，想随便聊两句。
明天下午 3 点提醒我复习英语听力 1 小时。
结合我之前的状态，你觉得我最近最需要注意什么？
```

3. 打开浏览器 DevTools：

```text
Network -> /api/v1/jarvis/chat
```

4. 检查：

- Request 耗时是否和 response 里的 `timing.total_ms` 接近。
- Response 是否包含 `timing.spans`。
- `llm_turn` 是否是最大耗时来源。
- 路由类 prompt 的 `agent_id` 是否变成 `maxwell`。
- 如果失败，是否包含 Step0 的 `error_code` 和 `suggestion`。

## 七、首轮基线记录模板

```text
验证时间：
验证人：
运行入口：Python AI / Java Gateway / 前端手动
base_url：
数据规模：小 / 中 / 大 / 未确认
LLM Provider：
模型：

总用例数：
成功数：
失败数：

normal_chat 平均耗时：
schedule_route 平均耗时：
memory_recall 平均耗时：
mood_care 平均耗时：
roundtable 平均耗时：

最慢 3 条：
1.
2.
3.

初步慢点判断：路由 / 记忆召回 / consult / LLM / 写库 / 前端渲染
备注：
```

## 八、通过标准

Step 1 当前阶段通过标准：

- 20 条固定 prompt 已落盘。
- 私聊接口返回后端 timing。
- 命令行脚本能生成 JSON/CSV 结果。
- 前端 Network 能看到 `timing.total_ms` 和 `timing.spans`。
- 能基于首轮结果判断最慢 3 个环节。
