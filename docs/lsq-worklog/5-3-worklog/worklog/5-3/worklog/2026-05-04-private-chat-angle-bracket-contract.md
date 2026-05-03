# 2026-05-04 私聊尖括号协议标签不可见契约 worklog

## 背景

用户继续测试后发现：除了 JSON / function_call 外，智能体还可能把 `<invoke>`、`<parameter>` 等带尖括号的工具协议标签直接返回到聊天框。

用户希望通过 prompt 让智能体明确记住：带 `<>` 的协议格式不是发给用户的内容。

## 本次完成范围

### 1. 增强用户可见回复契约

修改文件：

- `shadowlink-ai/app/api/v1/jarvis_router.py`

增强内容：

- 明确所有带尖括号的协议标签都不是用户可见回复。
- 举例包括 `<invoke>`、`<parameter>`、`<tool_call>`、`<tool_calls>`、`<jarvis-tool>`、`<jarvis-action>`、`<execute_bash>`。
- 用户再次提醒这类问题时，自动沉淀为主人长期行为约束。

### 2. 增强工具 runtime 提示

修改文件：

- `shadowlink-ai/app/jarvis/tool_runtime.py`

增强内容：

- 工具包提示中说明尖括号协议标签不是最终用户回复。
- 工具执行后的 follow-up prompt 中再次禁止输出 `<invoke>`、`<parameter>`、`<tool_call>`、`<tool_calls>` 等标签。
- 二次重试时也禁止输出任何带尖括号的协议标签。

### 3. 测试覆盖

修改文件：

- `shadowlink-ai/tests/unit/jarvis/test_agent_intent_pipeline.py`

新增断言：

- 私聊最终 prompt 必须包含“所有带尖括号的协议标签都不是用户可见回复”。

### 4. 接口说明同步

修改文件：

- `docs/解耦接口说明/private-chat-real-steps-interface.md`

说明：

- 这些协议标签属于后端 runtime 内部协议。
- 前端不应该把它们当作普通聊天文本处理，也不应该自己执行它们。

## 接口影响

请求体不变。

响应字段不变。

前端不需要新增接口。

这次仍然是后端 prompt / runtime 约束，不是前端过滤逻辑。

## 测试命令

```powershell
python -m py_compile shadowlink-ai/app/api/v1/jarvis_router.py shadowlink-ai/app/jarvis/tool_runtime.py
python -m pytest shadowlink-ai/tests/unit/jarvis/test_agent_intent_pipeline.py -k llm_strategy -q
```

