# StepC3 圆桌 Brainstorm 模式 Worklog

## 完成范围

本步按 `4-28plan.md` Phase 8 执行，完成圆桌 C3 Brainstorm 模式 MVP 闭环：

- Brainstorm 圆桌结束后生成并持久化结构化 `brainstorm_result`。
- `brainstorm_result` 包含 `themes`、`ideas`、`tensions`、`followup_questions`、`save_as_memory`。
- 默认只保存 result，不写 calendar、不写 plan。
- 用户点击“保存灵感”后才写 `jarvis_memories`。
- 用户点击“转成计划”后才生成 Maxwell `pending_actions` 待确认计划卡。
- 前端 Brainstorm 结果卡展示主题、想法、张力，并提供保存灵感、继续讨论、转成计划按钮。

## 代码文件

后端：

- `shadowlink-ai/app/api/v1/jarvis_router.py`
- `shadowlink-ai/app/jarvis/persistence.py`（复用 `roundtable_results`、`jarvis_memories`、`pending_actions`）

前端：

- `shadowlink-web/src/services/jarvisApi.ts`
- `shadowlink-web/src/components/jarvis/RoundtableStage.tsx`

测试：

- `shadowlink-ai/tests/unit/jarvis/test_roundtable_brainstorm.py`

文档：

- `docs/lsq-worklog/4-28-worklog/原始设计完成度-checklist.md`
- `docs/lsq-worklog/4-28-worklog/test/StepC3-圆桌Brainstorm模式-前端验证方法.md`

## 表

复用并写入：

- `roundtable_results`
  - mode=`brainstorm`
  - status=`draft|saved|handoff_pending`
  - options_json 存 themes MVP
  - tradeoffs_json 存 tensions MVP
  - context_json 存 ideas、followup_questions、save_as_memory、topic
- `jarvis_memories`
  - 用户点击“保存灵感”后写入 `memory_kind=brainstorm_inspiration`
- `pending_actions`
  - 用户点击“转成计划”后写入 `action_type=task.plan`

未直接写入：

- calendar
- background_tasks
- background_task_days

## 接口

新增：

- `GET /api/v1/jarvis/roundtable/{session_id}/brainstorm-result`
- `POST /api/v1/jarvis/roundtable/{session_id}/save`
- `POST /api/v1/jarvis/roundtable/{session_id}/plan`

增强：

- `POST /api/v1/jarvis/roundtable/start`
  - Brainstorm executor 流结束后返回 `brainstorm_result` SSE 事件。
  - Brainstorm turns 同步写入 roundtable session transcript。

## 前端

- `RoundtableStage` 支持 `brainstorm_result` SSE 事件。
- 新增 Brainstorm 结果卡：主题、候选想法、不会自动写计划/日程提示。
- “保存灵感”调用 save 接口，成功后展示 memory id。
- “转成计划”调用 plan 接口，成功后展示 Maxwell pending action。
- “继续讨论”预填输入框，让用户继续发散。

## 测试

新增单元测试覆盖：

- 点击保存前不会写 memory；调用 save 后才写 `brainstorm_inspiration`。
- save 不直接写 calendar / plan。
- 转计划后生成 pending action，且 `direct_plan_mutation=false`。
- pending action 交给 Maxwell，类型为 `task.plan`。

验证命令：

```powershell
cd D:\github_desktop\Jarvis-Life\shadowlink-ai
Remove-Item Env:SSLKEYLOGFILE -ErrorAction SilentlyContinue
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
pytest tests\unit\jarvis\test_roundtable_brainstorm.py -q
```

前端类型验证：

```powershell
cd D:\github_desktop\Jarvis-Life\shadowlink-web
npm.cmd run type-check
```

## 完成度变化

Checklist 变化：

- 圆桌 C Brainstorm：`[TODO] -> [MVP]`
- 圆桌 D save/plan 接口：`[TODO] -> [MVP]`
- 圆桌 E brainstorm 结果按钮：`[TODO] -> [MVP]`

整体完成度按 plan 口径：圆桌 55% -> 70% 的 Brainstorm MVP 闭环已补齐。

## 剩余缺口

这些缺口不在本步内假装完成，后续继续按 plan 执行：

- 圆桌一次 LLM 生成整轮 JSON 仍未完成，属于 Phase 9。
- timing span：context_prepare、roundtable_llm、result_persist 仍未完成，属于 Phase 9。
- 舞台席位、主持总结卡、角色发言长度控制和模式视觉差异仍需 Phase 9 深化。
- `return` 接口仍未产品化。
- Brainstorm memory 后续可补更细分类、检索和二次引用策略。
