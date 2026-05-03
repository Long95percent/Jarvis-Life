# 2026-05-04 私聊 LLM 策略路由器 worklog

## 背景

私聊智能体原来主要依赖规则判断意图。规则路由比较稳定，但对复杂任务不够灵活，尤其是复杂日程、长期计划、批量修改、延期重排等任务，容易只走单步回复或普通工具调用，不能稳定进入 ReAct / Plan-Execute 思路。

用户希望：

- 私聊智能体拥有更强的引擎能力。
- 各角色分工和工具权限仍然保持解耦。
- 日程意图至少走 ReAct，复杂日程走 Plan-Execute。
- 策略判断尽量交给 LLM，但后端必须保留安全兜底。

## 本次完成范围

### 1. 新增私聊策略路由函数

修改文件：

- `shadowlink-ai/app/api/v1/jarvis_router.py`

新增函数：

- `_build_private_chat_strategy_prompt`
- `_parse_private_chat_strategy_router`
- `_select_private_chat_strategy`
- `_normalize_private_chat_intent_text`
- `_is_schedule_intent`
- `_force_complex_schedule_strategy`

策略路由输出：

```json
{
  "domain": "schedule",
  "strategy": "plan_execute",
  "confidence": 0.93,
  "needs_tool": true,
  "reason": "用户要求复杂长期日程安排"
}
```

### 2. 接入私聊主链路

位置：

- `shadowlink-ai/app/api/v1/jarvis_router.py`
- `chat_with_agent`

处理方式：

1. 保留原来的 `plan_agent_intent` 规则工具预处理。
2. 工具预处理完成后，调用 LLM 策略路由。
3. 把 `## 私聊执行策略` 注入最终智能体 prompt。
4. 在最终响应中返回 `metadata.llm_strategy`。

这样不会破坏现有工具白名单，也不会让前端直接参与工具执行。

### 3. 后端兜底规则

LLM 策略不是唯一依据，后端增加了安全兜底：

- 如果 LLM 输出非法 JSON，回退到 `react`。
- 如果日程意图被选成 `direct`，后端提升为 `react`。
- 如果 Maxwell 处理复杂日程，例如一个月安排、长期计划、批量修改、批量删除、延期重排，后端强制提升为 `plan_execute`。

## 接口影响

请求体不变。

私聊响应新增可选字段：

```json
{
  "metadata": {
    "llm_strategy": {
      "domain": "schedule",
      "strategy": "plan_execute",
      "confidence": 0.93,
      "needs_tool": true,
      "reason": "用户要求复杂长期日程安排"
    }
  }
}
```

前端兼容要求：

- `metadata` 是可选字段。
- `metadata.llm_strategy` 是可选字段。
- 普通聊天展示仍然以 `content` 为主。
- 前端不要根据该字段直接操作数据库或工具。

接口说明已同步更新：

- `docs/解耦接口说明/private-chat-real-steps-interface.md`

## 测试记录

新增/使用测试：

- `shadowlink-ai/tests/unit/jarvis/test_agent_intent_pipeline.py`
- `test_private_chat_uses_llm_strategy_router_for_complex_schedule`

测试结果：

- `test_private_chat_uses_llm_strategy_router_for_complex_schedule` 已通过。
- 一起运行旧的 `pytest.mark.asyncio` 用例时，本机缺少 `pytest-asyncio`，导致异步测试无法由 pytest 原生执行。
- 后端文件已通过语法检查：`python -m py_compile shadowlink-ai/app/api/v1/jarvis_router.py`。

## 当前状态

本次实现的是“轻量混合路由”：

- LLM 负责判断该用哪种执行思路。
- 原规则层继续负责已知工具预处理。
- 工具运行时继续负责真实读写和安全校验。
- 前端继续只读私聊接口响应，不直接调用工具。

后续如果要进一步增强，可以把 `plan_execute` 策略真正接到统一 `AgentEngine` 的 Plan-and-Execute executor，但那会是更大范围改造，需要单独规划。

