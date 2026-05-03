# 私聊真实执行步骤与策略路由接口说明

更新时间：2026-05-04

## 1. 目标

私聊智能体不再只做“单步口头回复”。后端会先判断本轮对话适合哪种执行策略，再把策略、工具结果和真实执行要求一起交给智能体生成最终回复。

前端只负责展示聊天内容、执行步骤和结构化结果，不直接调用工具、不直接读写数据库。

## 2. 核心原则

- 角色边界不变：Maxwell、Nora、Mira、Leo、Athena 仍然各自负责自己的业务。
- 工具权限不变：每个角色仍然只能使用自己的 `tool_whitelist`。
- 前后端解耦不变：前端只调用私聊接口和模块 service，不绕过接口访问后端工具。
- 策略路由增强：后端会用 LLM 判断本轮应走 `direct`、`react` 还是 `plan_execute`。
- 安全兜底不变：LLM 策略只决定“怎么想”，不能绕过工具白名单、参数校验和后端安全规则。

## 3. 私聊接口

请求接口仍然是原私聊接口：

```http
POST /api/v1/jarvis/agents/chat
```

请求体不变：

```json
{
  "agent_id": "maxwell",
  "session_id": "session-001",
  "message": "帮我安排接下来一个月每天学习，并避开已有日程",
  "browser_timezone": "Asia/Shanghai"
}
```

## 4. 新增响应字段

响应新增 `metadata.llm_strategy`，用于告诉前端本轮后端选择了什么执行策略。

```json
{
  "agent_id": "maxwell",
  "agent_name": "Maxwell",
  "content": "我会先查看已有日程，再分阶段安排学习计划……",
  "actions": [],
  "routing": null,
  "timing": {},
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

字段说明：

- `domain`：本轮领域，例如 `schedule`、`care`、`study`、`chat`、`other`。
- `strategy`：执行策略，只会是 `direct`、`react`、`plan_execute` 之一。
- `confidence`：策略判断置信度，范围 `0` 到 `1`。
- `needs_tool`：后端判断本轮是否需要工具参与。
- `reason`：后端选择该策略的原因，供调试和开发人员查看。

前端兼容要求：

- `metadata` 可能为空，前端必须允许不存在。
- `metadata.llm_strategy` 可能为空，前端必须允许不存在。
- 普通聊天气泡不需要展示该字段。
- 如果有“执行过程/调试详情/智能体工作台”，可以展示该字段。

## 5. 三种策略含义

### direct

适合普通聊天、解释、轻量建议。

前端表现：直接展示 `content`。

### react

适合需要查询、验证、调用一个或少量工具的任务。

后端会提示智能体：先观察上下文，必要时调用工具，最后基于真实工具结果回复。

前端表现：

- 展示 `content`。
- 如果接口返回 `actions` 或实时步骤事件，可以展示执行过程。

### plan_execute

适合复杂日程、长期计划、批量修改/删除、延期重排、多轮校验任务。

后端会提示智能体：先制定简短计划，再分步查询、修改、校验，最后汇总真实结果。

前端表现：

- 展示 `content`。
- 如果有步骤流，建议展示“正在规划 / 查询日程 / 执行修改 / 校验结果”等真实阶段。
- 不要在前端自己模拟数据库操作结果。

## 6. 日程领域特别规则

日程类意图不能只靠口头承诺完成。

后端策略规则：

- 普通日程查询、单次修改、单次删除：优先 `react`。
- 长期计划、一个月安排、批量修改、批量删除、延期重排：优先 `plan_execute`。
- 如果 LLM 错选 `direct`，后端会把日程意图兜底提升到 `react`。
- Maxwell 的复杂日程意图会被后端兜底提升到 `plan_execute`。

这不改变前端接口调用方式。前端仍然只调用私聊接口，日程数据展示仍然走日程模块 service。

## 7. 工具结果相关字段

私聊中如果智能体调用了日程工具，`actions` 或工具结果里可能出现以下字段：

- `auto_resolved`：后端自动补齐了唯一匹配的日程 ID。
- `auto_resolved_event_id`：自动补齐的日程 ID。
- `repair_strategy`：补参策略，例如 `REACT`。
- `retry_count`：工具重试次数。
- `bulk`：是否批量执行。
- `updated_count`：更新数量。
- `deleted_count`：删除数量。
- `needs_disambiguation`：需要用户澄清多个候选项。
- `candidates`：候选日程列表。

前端不要自己根据关键词循环删除或修改日程。所有写操作必须由后端工具完成。

## 8. 前端开发人员能做什么

可以改：

- 聊天气泡样式。
- Markdown 渲染样式。
- 执行步骤展示组件。
- `metadata.llm_strategy` 的可选调试展示。
- `actions` 的展示方式。

不可以改：

- 不可以让前端直接调用后端工具函数。
- 不可以让前端直接读写数据库。
- 不可以在前端伪造“已删除 / 已更新 / 已写入”。
- 不可以绕过 service 层直接拼接后端内部路径。

## 9. 用户可见回复契约

2026-05-04 新增后端提示词约束，不改前端接口。

目标：减少智能体把内部工具 JSON、`function_call`、`tool_name`、`arguments`、`<tool_call>`、`<jarvis-tool>` 原样发到聊天框的问题。

后端行为：

- 私聊最终 prompt 会注入“用户可见回复契约”。
- 智能体如果需要操作，必须通过后端可解析的工具协议执行。
- 最终给用户看的回复只能是自然语言总结。
- 如果工具没有真实执行成功，不能说“已完成”。
- 如果用户再次提醒“不要把 JSON / function_call 返回给我”，后端会把这条作为主人长期行为约束写入协作记忆。
- 所有带尖括号的协议标签都不是用户可见回复，例如 `<invoke>`、`<parameter>`、`<tool_call>`、`<tool_calls>`、`<jarvis-tool>`、`<jarvis-action>`、`<execute_bash>`。

接口影响：

- 请求体不变。
- 响应字段不变。
- 前端不需要新增接口。
- 前端不要自己清洗或执行 JSON 工具指令；这仍然属于后端工具 runtime 的职责。

### 9.1 兼容的工具协议格式

后端当前兼容多种工具块格式，前端都不应直接展示这些格式作为最终聊天内容：

- `<jarvis-tool>{...}</jarvis-tool>`
- `<tool_calls>...<tool_call name="...">{...}</tool_call>...</tool_calls>`
- `<invoke name="..."> <parameter name="...">...</parameter> ... </invoke>`

这些都是给后端 runtime 解析并执行的内部协议，不是给用户看的回复内容。
如果模型把这些标签输出出来，后端应优先解析执行或二次要求自然语言总结，而不是让前端把它当普通聊天文本处理。

## 10. 验收标准

- 复杂日程请求会在 `metadata.llm_strategy.strategy` 中显示 `plan_execute`。
- 日程类请求不会只走口头 `direct` 承诺。
- 前端在缺少 `metadata` 时不报错。
- 前端展示内容仍以 `content` 为主。
- 所有实际日程增删改查仍由后端日程接口和工具完成。
- 智能体最终给用户的聊天内容不应暴露内部工具 JSON / function_call / tool_name / arguments。
