# 2026-05-04 日程多候选澄清展示日志

## 背景

现在 `jarvis_schedule_editor` 已经能在多候选时返回 `needs_disambiguation`，避免误改或误删。

但只返回结构化候选还不够，私聊智能体需要把候选清楚地转成用户能理解的问题，而不是继续猜。

## 本阶段目标

- 工具结果中出现 `needs_disambiguation` 时，私聊回复要明确告诉用户匹配到了多条。
- 回复中要列出候选项的标题、时间、ID。
- 智能体应询问用户要操作哪一条，或是否要对全部执行。
- 不允许在多候选情况下继续瞎猜执行写操作。

## 验收场景

- 删除 meeting 时匹配两条，智能体应问用户选择哪条或是否全部删除。
- 更新 meeting 时匹配两条，智能体应列候选，不应说“已更新”。
- 前端不需要改请求入口。

## 已完成

- `format_tool_results` 在识别到 `code=needs_disambiguation` 时，会追加“多候选澄清”段落。
- 澄清段落会列出候选 ID、标题和时间。
- 澄清段落明确要求模型不要说“已删除/已更新”，而是询问用户选择哪条或是否全部执行。
- 已新增私聊测试，验证候选信息会进入模型第二轮提示。
- 已同步接口说明：`docs/解耦接口说明/private-chat-real-steps-interface.md`。

## 验证

已运行：

```powershell
Push-Location shadowlink-ai
python -m pytest tests/unit/jarvis/test_agent_intent_pipeline.py::test_private_chat_formats_schedule_disambiguation_candidates -q
Pop-Location
```

结果：通过。
