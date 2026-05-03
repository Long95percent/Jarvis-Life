# 2026-05-04 私聊 `<invoke>` 工具协议兼容 worklog

## 背景

用户测试私聊时发现：智能体有时不会输出 `<jarvis-tool>`，而是输出另一种工具格式：

```xml
<invoke name="jarvis_schedule_editor">
  <parameter name="operation">update</parameter>
</invoke>
```

这说明模型已经开始使用别的工具协议格式，但后端 runtime 还没有把这种格式当作可执行工具调用处理，导致这些内容有时会泄漏到聊天框。

## 本次完成范围

### 1. 后端工具 runtime 兼容 `<invoke>`

修改文件：

- `shadowlink-ai/app/jarvis/tool_runtime.py`

新增能力：

- 识别 `<invoke name="...">...</invoke>`。
- 识别其中的 `<parameter name="...">...</parameter>`。
- 解析成后端可执行的 `tool_name` + `arguments`。
- 与现有的 `<jarvis-tool>`、`<tool_call>`、`<tool_calls>` 协议并存。

### 2. 新增测试

修改文件：

- `shadowlink-ai/tests/unit/jarvis/test_tool_runtime.py`

新增测试：

- `test_strip_tool_like_blocks_accepts_invoke_xml`

验证点：

- `<invoke>` 会被识别并剥离出最终用户文本。
- 其中的参数会被转成工具调用参数。

### 3. 接口说明同步

修改文件：

- `docs/解耦接口说明/private-chat-real-steps-interface.md`

新增说明：

- 后端当前兼容的工具协议包含 `<jarvis-tool>`、`<tool_calls>` / `<tool_call>`、`<invoke>`。
- 这些都是后端 runtime 内部协议，不是前端给用户展示的最终回复内容。

## 接口影响

请求体不变，响应字段不变，前端接口不需要新增。

前端仍然只负责展示最终自然语言和结构化结果，不应该把 `<invoke>` 当成用户回复渲染出来。

## 测试记录

待验证命令：

```powershell
python -m py_compile shadowlink-ai/app/jarvis/tool_runtime.py
python -m pytest shadowlink-ai/tests/unit/jarvis/test_tool_runtime.py -q
```

