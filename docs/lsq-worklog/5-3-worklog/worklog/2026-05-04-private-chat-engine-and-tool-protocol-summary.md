# 2026-05-04 私聊引擎能力与工具协议稳定化工作总结

## 背景

今天主要围绕私聊智能体能力增强和工具调用稳定性处理。用户测试发现：

- 私聊智能体经常不主动进入 ReAct / Plan-Execute，多数时候像单步回复。
- 复杂日程、批量修改、批量删除、长期计划等任务需要更强执行策略。
- 智能体偶尔把 `function_call`、`tool_name`、`arguments`、JSON 指令或 `<invoke>`、`<parameter>` 等协议标签直接发到聊天框，导致工具没有真实执行。
- 用户希望优先通过 prompt、工具 runtime、长期行为记忆解决，而不是让前端强行过滤。
- 所有改动必须继续遵守前后端解耦：前端只调用接口，不直连工具或数据库。

## 今日完成内容

### 1. 私聊 LLM 策略路由

核心文件：

- `shadowlink-ai/app/api/v1/jarvis_router.py`
- `shadowlink-ai/tests/unit/jarvis/test_agent_intent_pipeline.py`

完成内容：

- 新增私聊策略路由，让 LLM 先判断本轮适合 `direct`、`react` 还是 `plan_execute`。
- 策略输出包含 `domain`、`strategy`、`confidence`、`needs_tool`、`reason`。
- 复杂日程、长期计划、批量修改/删除、延期重排优先进入 `plan_execute`。
- 普通日程工具意图至少进入 `react`，避免只口头承诺。
- 后端仍保留安全兜底：非法 JSON 回退、日程意图从 `direct` 提升到 `react`、Maxwell 复杂日程提升到 `plan_execute`。

接口影响：

- 请求体不变。
- 私聊响应新增可选字段 `metadata.llm_strategy`。
- 前端可以展示这个字段，也可以忽略；不能用它直接操作数据库。

### 2. 用户可见回复契约

核心文件：

- `shadowlink-ai/app/api/v1/jarvis_router.py`
- `shadowlink-ai/app/jarvis/tool_runtime.py`

完成内容：

- 新增 `## 用户可见回复契约`。
- 明确告诉智能体：不要把 `function_call`、`tool_name`、`arguments`、JSON 指令、`<tool_call>`、`<jarvis-tool>` 等内部工具调用内容直接发到聊天框。
- 如果需要操作，必须走后端工具协议执行。
- 最终给用户看的回复只能是自然语言总结。
- 如果工具没有真实执行成功，不能说已经完成。
- 回复前自检：是否暴露了内部工具参数、是否声称完成但没有工具结果、是否把 function_call JSON 当成最终回复。

### 3. 主人提醒自动沉淀为行为记忆

核心文件：

- `shadowlink-ai/app/api/v1/jarvis_router.py`

完成内容：

- 新增检测逻辑：当用户提醒“不要把 JSON / function_call / tool_name / arguments / 工具调用指令返回给我”等内容时，后端会把这类提醒写入协作记忆。
- 后续各私聊 Agent 会通过协作记忆读到这条主人长期行为约束。
- 这个机制用于让 Agent 自己逐渐记住用户反复强调的注意点。

### 4. `<invoke>` 工具协议兼容

核心文件：

- `shadowlink-ai/app/jarvis/tool_runtime.py`
- `shadowlink-ai/tests/unit/jarvis/test_tool_runtime.py`

完成内容：

- 后端 runtime 新增对 `<invoke name="...">...</invoke>` 的解析。
- 支持解析 `<parameter name="...">...</parameter>`。
- 可把类似下面内容转成真实工具调用：

```xml
<invoke name="jarvis_schedule_editor">
  <parameter name="operation">update</parameter>
  <parameter name="scope">all</parameter>
</invoke>
```

- 与原有 `<jarvis-tool>`、`<tool_calls>`、`<tool_call>` 协议并存。

意义：

- 如果模型输出这种格式，后端优先识别为工具协议并执行，而不是让它当作普通聊天文本泄漏给用户。

### 5. 尖括号协议标签不可见契约

核心文件：

- `shadowlink-ai/app/api/v1/jarvis_router.py`
- `shadowlink-ai/app/jarvis/tool_runtime.py`
- `shadowlink-ai/tests/unit/jarvis/test_agent_intent_pipeline.py`

完成内容：

- 明确告诉智能体：所有带尖括号的协议标签都不是用户可见回复。
- 包括但不限于：`<invoke>`、`<parameter>`、`<tool_call>`、`<tool_calls>`、`<jarvis-tool>`、`<jarvis-action>`、`<execute_bash>`。
- 工具执行后的 follow-up prompt 和二次重试 prompt 也同步加强，避免最终回复继续输出协议标签。

### 6. 接口说明文档同步

核心文件：

- `docs/解耦接口说明/private-chat-real-steps-interface.md`

同步内容：

- 私聊策略路由响应字段 `metadata.llm_strategy`。
- `direct` / `react` / `plan_execute` 的含义。
- 日程领域特别规则。
- 用户可见回复契约。
- 后端兼容的工具协议格式：`<jarvis-tool>`、`<tool_calls>` / `<tool_call>`、`<invoke>`。
- 明确前端不需要新增接口，不应该自己清洗或执行工具协议。

## 今日新增/更新的详细 worklog

今天也在旧目录下分别写了分项记录：

- `docs/lsq-worklog/5-3/worklog/2026-05-04-private-chat-llm-strategy-router.md`
- `docs/lsq-worklog/5-3/worklog/2026-05-04-private-chat-json-leak-guard.md`
- `docs/lsq-worklog/5-3/worklog/2026-05-04-private-chat-invoke-compatibility.md`
- `docs/lsq-worklog/5-3/worklog/2026-05-04-private-chat-angle-bracket-contract.md`

本文件是按用户要求补写到：

- `docs/lsq-worklog/5-3-worklog/worklog/`

## 验证记录

已运行：

```powershell
python -m py_compile shadowlink-ai/app/api/v1/jarvis_router.py shadowlink-ai/app/jarvis/tool_runtime.py
python -m pytest shadowlink-ai/tests/unit/jarvis/test_agent_intent_pipeline.py -k llm_strategy -q
python -m pytest shadowlink-ai/tests/unit/jarvis/test_tool_runtime.py -q
```

结果：

- 策略路由专项测试通过。
- 工具 runtime 测试通过。
- `test_tool_runtime.py` 结果为 `4 passed`。
- 本机仍存在 `pytest-asyncio` 缺失导致部分 `pytest.mark.asyncio` 用例不能整体直接跑的问题，这不是本次业务代码失败。

## 当前状态

当前私聊链路已经具备：

- LLM 策略选择能力。
- 后端策略兜底能力。
- 工具协议防泄漏提示。
- `<invoke>` 协议兼容解析。
- 用户反复提醒的行为约束记忆。

前端接口仍保持解耦：

- 前端仍然只调用私聊接口。
- 前端不直接调用工具。
- 前端不直接读写数据库。
- 前端不负责执行或清洗工具协议。

## 后续建议

- 继续用复杂日程修改、批量删除、延期重排等场景实测。
- 如果仍有新的工具协议格式泄漏，优先在 `tool_runtime.py` 中增加解析兼容，而不是让前端过滤。
- 后续如果要真正把 `plan_execute` 接到统一 `AgentEngine` executor，需要单独做计划，避免影响现有私聊稳定性。

