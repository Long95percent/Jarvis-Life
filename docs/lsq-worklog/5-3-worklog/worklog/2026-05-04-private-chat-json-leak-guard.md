# 2026-05-04 私聊工具 JSON 泄漏提示词约束 worklog

## 背景

用户测试私聊智能体时发现：智能体偶尔会把 `function_call`、`tool_name`、`arguments` 或 JSON 工具调用内容直接返回到聊天框，导致工具没有实际执行，用户还需要手动提醒“不要把 function_call 的 JSON 格式指令返回给我”。

用户要求：

- 不希望只靠前端强制过滤。
- 优先通过 prompt 调整解决。
- 可以让 Agent 记住主人经常提醒的注意点。
- 不破坏前后端解耦，不让前端直接执行工具。

## 本次完成范围

### 1. 新增用户可见回复契约

修改文件：

- `shadowlink-ai/app/api/v1/jarvis_router.py`

新增函数：

- `_build_user_visible_reply_contract`

私聊最终 prompt 中新增 `## 用户可见回复契约`，明确要求：

- 不要把 `function_call`、`tool_name`、`arguments`、JSON 指令、`<tool_call>`、`<jarvis-tool>` 等内部工具调用内容直接发到聊天框。
- 需要操作时必须通过后端工具协议执行。
- 最终用户回复只能是自然语言总结。
- 如果工具没有真实执行成功，不能说已经完成。
- 回复前自检是否暴露了内部工具参数或把 JSON 当成最终回复。

### 2. 加强工具 runtime 提示

修改文件：

- `shadowlink-ai/app/jarvis/tool_runtime.py`

调整点：

- 在 `build_toolkit_prompt` 中强调：工具参数 JSON 只允许放在 `<jarvis-tool>` 块中交给后端执行。
- 工具执行后的最终回复提示中强调：不要把工具标签、`function_call`、`tool_name`、`arguments` 或 JSON 指令展示给用户。

### 3. 用户提醒自动沉淀为行为记忆

修改文件：

- `shadowlink-ai/app/api/v1/jarvis_router.py`

新增函数：

- `_mentions_tool_json_leakage`

行为：

- 当用户消息中同时出现 JSON / function_call / tool_name / arguments / 工具调用等关键词，以及“不要 / 错误 / 返回给我 / 根本没有实际执行”等抱怨语气时，后端会自动写入一条主人长期行为约束。
- 后续私聊会通过协作记忆前缀把该约束注入给相关 Agent。

## 接口影响

请求体不变。

响应字段不变。

前端不需要新增接口，也不需要自己清洗 JSON。

这次修改仍然遵守前后端解耦：

- 前端只展示 `content`、`actions`、`metadata` 等接口返回。
- 工具调用仍然只由后端 `tool_runtime` 解析和执行。
- 前端不能把聊天框里的 JSON 当成工具调用去执行。

接口说明已同步：

- `docs/解耦接口说明/private-chat-real-steps-interface.md`

## 测试记录

更新测试：

- `shadowlink-ai/tests/unit/jarvis/test_agent_intent_pipeline.py`

新增断言：

- 私聊最终 prompt 必须包含 `## 用户可见回复契约`。
- 私聊最终 prompt 必须包含“不要把 function_call、tool_name、arguments、JSON 指令”约束。

待验证命令：

```powershell
python -m py_compile shadowlink-ai/app/api/v1/jarvis_router.py shadowlink-ai/app/jarvis/tool_runtime.py
python -m pytest shadowlink-ai/tests/unit/jarvis/test_agent_intent_pipeline.py -k llm_strategy -q
```

