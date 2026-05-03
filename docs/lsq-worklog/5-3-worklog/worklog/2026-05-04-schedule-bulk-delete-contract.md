# 2026-05-04 日程批量删除工具契约日志

## 背景

前面已经完成：

- 缺 `event_id` 时的 ReAct 修复。
- 唯一匹配时的自然语言式 update。
- 显式 `allow_multiple=true` 的批量 update / 时间平移。

接下来要补齐删除能力：用户自然语言经常说“删除所有 Python 相关日程”或“清掉所有 reading 安排”。这类操作不应该要求模型自己列出所有 ID。

## 本阶段目标

- `jarvis_schedule_editor` 的 delete 支持安全批量契约。
- 多条匹配时，如果未显式 `allow_multiple=true`，返回 `needs_disambiguation`，不误删。
- 显式 `allow_multiple=true` 时，删除所有匹配项。
- 继续清理普通日历事件、计划日、后台任务日、父计划、父任务等投影来源。

## 验收场景

- “删除所有 reading 日程”在 `allow_multiple=true` 时应删除所有匹配事件。
- “删除 meeting 日程”匹配多条且未允许批量时，应返回候选，不删除。
- 前端不需要参与 ID 拼接或循环删除。

## 已完成

- `jarvis_schedule_editor` 的 delete 现在支持 `allow_multiple` 安全开关。
- 多条匹配且没有 `allow_multiple=true` 时，返回 `needs_disambiguation`，不会删除。
- 显式 `allow_multiple=true` 时，会批量删除匹配项，并返回 `bulk=true`。
- 精确 `event_ids` 删除不受 `allow_multiple` 限制。
- 已重建接口说明文档，避免旧文档乱码：`docs/解耦接口说明/private-chat-real-steps-interface.md`。

## 验证

已运行：

```powershell
Push-Location shadowlink-ai
python -m pytest tests/unit/jarvis/test_unified_planner.py::test_schedule_editor_delete_requires_disambiguation_for_multiple_matches_without_allow_multiple tests/unit/jarvis/test_unified_planner.py::test_schedule_editor_bulk_deletes_multiple_keyword_matches_when_allowed -q
Pop-Location
```

结果：通过。
