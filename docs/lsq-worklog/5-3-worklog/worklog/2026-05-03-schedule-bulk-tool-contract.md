# 2026-05-03 日程批量工具契约日志

## 背景

前一阶段已经让 `jarvis_schedule_editor` 支持唯一命中时自动补 `event_id`。

但自然语言里还有更常见的批量需求：

- 删除所有包含某关键词的日程。
- 把每天的阅读时间推迟一小时。
- 把某类日程统一改成另一个标题或状态。

这些不应该要求模型自己拼一堆 ID。后端工具应该提供更自然、更安全的批量契约。

## 本阶段目标

- 支持 `allow_multiple=true` 时，对所有匹配日历事件执行 update。
- 支持 `shift_minutes`，用于把匹配事件整体前移或后移。
- 默认仍然保护安全：多个候选且未显式允许批量时，返回 `needs_disambiguation`。
- 继续保持前后端解耦，前端不参与批量匹配和冲突判断。

## 验收场景

- “把所有 reading 日程推迟 60 分钟”应由工具直接完成。
- 未显式允许批量时，多个 meeting 命中仍然不误改。
- 工具返回 `updated_count` 和更新后的事件列表。

## 已完成

- `jarvis_schedule_editor` 新增 `allow_multiple`。
- `jarvis_schedule_editor` 新增 `shift_minutes`。
- update 在 `allow_multiple=true` 时可对所有匹配日历事件批量执行。
- 不传 `allow_multiple=true` 时，多候选仍返回 `needs_disambiguation`。
- 已同步接口说明：`docs/解耦接口说明/private-chat-real-steps-interface.md`。

## 验证

已运行：

```powershell
Push-Location shadowlink-ai
python -m pytest tests/unit/jarvis/test_unified_planner.py::test_schedule_editor_bulk_shifts_multiple_keyword_matches_when_allowed -q
Pop-Location
```

结果：通过。
