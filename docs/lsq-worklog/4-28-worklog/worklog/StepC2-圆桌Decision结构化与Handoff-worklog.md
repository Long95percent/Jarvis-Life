# StepC2 圆桌 Decision 结构化与 Handoff Worklog

## 完成范围

本步按 `4-28plan.md` Phase 7 执行，补齐圆桌 C1/C2 Decision 模式 MVP 闭环：

- 新增“疲惫学习决策”场景，覆盖验收句：`我很累但还有学习任务，要不要继续？`
- Decision 圆桌启动前预取心理快照、日程压力、今日任务、日程事件、Maxwell 工作台和 MVP RAG 摘要。
- Decision 讨论阶段 prompt 明确默认不调用工具，不做心理诊断，不直接改日程。
- 生成并持久化结构化 `decision_result`。
- 用户接受后交给 Maxwell 生成 `pending_actions` 待确认卡，不直接写 calendar。
- 前端圆桌舞台展示 Decision 结果卡，并提供接受建议、返回私聊、让 Maxwell 执行按钮。

## 代码文件

后端：

- `shadowlink-ai/app/jarvis/persistence.py`
- `shadowlink-ai/app/jarvis/roundtable_sessions.py`
- `shadowlink-ai/app/jarvis/scenarios.py`
- `shadowlink-ai/app/api/v1/jarvis_router.py`

前端：

- `shadowlink-web/src/services/jarvisApi.ts`
- `shadowlink-web/src/components/jarvis/RoundtableStage.tsx`

测试：

- `shadowlink-ai/tests/unit/jarvis/test_roundtable_decision.py`

文档：

- `docs/lsq-worklog/4-28-worklog/原始设计完成度-checklist.md`
- `docs/lsq-worklog/4-28-worklog/test/StepC2-圆桌Decision结构化与Handoff-前端验证方法.md`

## 表结构

新增：

- `roundtable_results`
  - `id`
  - `session_id`
  - `mode`
  - `status`
  - `summary`
  - `options_json`
  - `recommended_option`
  - `tradeoffs_json`
  - `actions_json`
  - `handoff_target`
  - `context_json`
  - `source_session_id`
  - `source_agent_id`
  - `pending_action_id`
  - `created_at`
  - `updated_at`

补齐：

- `roundtable_sessions`
  - `mode`
  - `source_session_id`
  - `source_agent_id`
  - `status`

复用：

- `pending_actions`
  - 用户 accept 后写入 Maxwell 待确认动作。
  - 当前不直接写 `calendar_events`。

## 接口

新增 / 补齐：

- `GET /api/v1/jarvis/roundtable/{session_id}/decision-result`
- `POST /api/v1/jarvis/roundtable/{session_id}/accept`

已有接口增强：

- `POST /api/v1/jarvis/roundtable/start`
  - 支持 source_session_id / source_agent_id。
  - Decision 场景会预取上下文并在 SSE 中返回 `decision_result`。
- `POST /api/v1/jarvis/roundtable/continue`
  - Decision 场景继续讨论后也会刷新 `decision_result`。

## 前端能力

- `RoundtableStage` 支持 `decision_result` SSE 事件。
- 右侧 Decision 卡展示：推荐方案、利弊、下一步动作、状态。
- “接受建议”和“让 Maxwell 执行”调用 accept 接口。
- accept 成功后显示已生成待确认卡，并提示不会直接改日程。

## 测试

新增单元测试覆盖：

- roundtable session 可保存 `mode/source_session_id/source_agent_id/status`。
- `roundtable_results` 可保存并读取结构化 Decision 字段。
- accept Decision 后生成 `pending_actions`，且 `direct_calendar_mutation=false`。

待本地验证命令：

```powershell
cd D:\github_desktop\Jarvis-Life\shadowlink-ai
Remove-Item Env:SSLKEYLOGFILE -ErrorAction SilentlyContinue
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
pytest tests\unit\jarvis\test_roundtable_decision.py -q
```

前端类型验证：

```powershell
cd D:\github_desktop\Jarvis-Life\shadowlink-web
npm.cmd run type-check
```

## 完成度变化

Checklist 变化：

- 圆桌 A 数据结构：`[TODO] -> [MVP]`
- 圆桌 B Decision：`[TODO] -> [MVP]`
- 圆桌 D accept 接口：`[TODO] -> [MVP]`
- 圆桌 E decision 按钮：`[TODO] -> [MVP]`

整体完成度按 plan 口径：圆桌 35% -> 55% 的 Decision MVP 闭环已补齐。

## 剩余缺口

这些缺口不在本步内“假装完成”，后续应继续按 plan 执行：

- Brainstorm 模式结构化输出仍未完成，属于 Phase 8。
- 圆桌默认一次 LLM 生成整轮 JSON、timing span、性能边界仍未完成，属于 Phase 9。
- `POST /roundtable/{id}/return`、`POST /roundtable/{id}/save` 仍未完成。
- `roundtable_results` 的 user_choice / handoff_status 目前由 status / pending_action_id MVP 表达，后续可进一步规范。
- 从 Mira 私聊自动升级到 Decision 圆桌的统一入口仍需放到轻量管家团队闭环阶段完善。
