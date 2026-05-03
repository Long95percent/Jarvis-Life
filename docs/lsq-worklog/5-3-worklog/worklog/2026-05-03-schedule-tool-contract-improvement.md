# 2026-05-03 日程工具契约改进日志

## 背景

私聊智能体在更新会议时漏传 `event_id`，说明问题不只是模型能力不足，也和后端工具契约有关。

当前 `jarvis_schedule_editor` 对模型不够友好：

- update 必须通过 `patches[].event_id`。
- 但自然语言用户常说“把会议改到下午三点”，不会提供 ID。
- 模型容易把 `title`、`start`、`end` 放在顶层参数，而不是组织成 patches。
- 后端工具没有把这种自然语言式参数规范化，导致一次调用失败后需要额外 ReAct 修复。

## 本阶段目标

让 `jarvis_schedule_editor` 更适合智能体调用：

- 支持顶层 `title/start/end/location/notes/status` 作为 update/delete 的自然语言式参数。
- 当没有 `patches` 但有 `keyword/title` 时，工具内部先匹配候选。
- 唯一命中时自动补 `event_id` 并执行。
- 多个候选时返回 `needs_disambiguation`，不要误改。
- 仍然保持前后端解耦，前端不参与补参。

## 约束

- 不改变现有前端接口。
- 不绕过角色工具白名单。
- 不让模型只口头承诺写入。
- 所有接口变化同步写入 `docs/解耦接口说明/private-chat-real-steps-interface.md`。

## 已完成

- `jarvis_schedule_editor` 的 update 现在支持顶层自然语言式入参：`title/start/end/stress_weight/location/notes/status/route_required`。
- 当没有 `patches` 但有 `keyword` 且唯一命中日程时，工具会自动补齐 `event_id` 并更新。
- 当命中 0 条或多条时，返回 `code=needs_disambiguation` 和候选列表，不误改。
- 新增测试覆盖唯一命中自动更新、多候选要求澄清。
- 已同步接口说明：`docs/解耦接口说明/private-chat-real-steps-interface.md`。

## 验证

已运行：

```powershell
Push-Location shadowlink-ai
python -m pytest tests/unit/jarvis/test_unified_planner.py::test_schedule_editor_updates_unique_keyword_match_without_patch_event_id tests/unit/jarvis/test_unified_planner.py::test_schedule_editor_requires_disambiguation_for_multiple_update_matches -q
Pop-Location
```

结果：通过。
