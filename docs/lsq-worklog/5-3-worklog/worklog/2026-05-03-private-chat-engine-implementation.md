# 2026-05-03 私聊工具链接引擎能力实施日志

## 目标

在不打乱各角色边界的前提下，让所有私聊智能体获得更强的执行能力。

本次优先做私聊工具链增强，不改圆桌，不改前端请求入口。

## 实施原则

- 角色定义仍来自 `shadowlink-ai/app/jarvis/agents.py`。
- 工具权限仍由 `tool_whitelist` 控制。
- 私聊链路只增强执行策略，不合并角色职责。
- 前端继续读取后端返回，不参与工具补参和数据库写入。
- 所有接口说明同步更新 `docs/解耦接口说明`。

## 本次最小范围

1. 在 Jarvis 私聊工具链中加入策略标记。
2. 让工具调用失败后可以进入一次 ReAct 式修复。
3. 第一类修复场景：`jarvis_schedule_editor` update/delete 缺 `event_id`。
4. 修复时先 query 候选，再在唯一命中时自动补 `event_id` 继续执行。
5. 返回真实工具结果和步骤信息，供前端展示。

## 计划修改文件

- `shadowlink-ai/app/jarvis/tool_runtime.py`
- `shadowlink-ai/tests/unit/jarvis/test_agent_intent_pipeline.py`
- `docs/解耦接口说明/private-chat-real-steps-interface.md`
- `docs/解耦接口说明/frontend-decoupling-developer-guide.md`

## 当前状态

- 第一阶段已完成。
- 已按 TDD 添加失败测试，并实现最小 ReAct 修复层。

## 已完成内容

- 在 `shadowlink-ai/app/jarvis/tool_runtime.py` 增加 `jarvis_schedule_editor` 缺 `event_id` 的 ReAct 修复。
- 私聊模型如果调用 update/delete 漏传 `event_id`，后端会自动 query 候选。
- 唯一命中时，后端会自动补齐 `event_id` 并再次执行 update/delete。
- 工具结果会标记：`auto_resolved`、`auto_resolved_event_id`、`repair_strategy=REACT`。
- 新增测试覆盖 Maxwell 私聊缺参修复链路。
- 同步更新 `docs/解耦接口说明/private-chat-real-steps-interface.md`。

## 验证

已运行：

```powershell
Push-Location shadowlink-ai
python -m pytest tests/unit/jarvis/test_agent_intent_pipeline.py::test_private_chat_react_repairs_schedule_editor_missing_event_id -q
python -m pytest tests/unit/jarvis/test_agent_intent_pipeline.py::test_private_delete_schedule_routes_to_maxwell_from_other_agent tests/unit/jarvis/test_unified_planner.py::test_calendar_delete_and_update_tools_execute_without_pending_confirmation -q
Pop-Location
```

结果：全部通过。

## 后续建议

- 第二阶段可以把 ReAct 修复扩展到多个候选项的澄清选择。
- 第三阶段再考虑把策略选择字段更完整地返回给前端步骤面板。
- 暂时不动圆桌，避免混淆圆桌协作链路和私聊链路。
