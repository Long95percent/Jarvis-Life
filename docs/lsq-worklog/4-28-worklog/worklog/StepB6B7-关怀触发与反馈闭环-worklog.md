# StepB6B7 关怀触发与反馈闭环 Worklog

## 0. 阶段边界

本阶段是 MVP，不是心理关怀模块全量完成。

本阶段完成真实可用的关怀触发与反馈闭环：基于 snapshot、behavior observation、stress signal 生成 care trigger，落盘 proactive message / intervention，前端 CareCard 操作会真实回写后端并影响后续频率。高风险场景只做安全提示，不做诊断。

## 1. 对应原始设计文件

- `docs/lsq-worklog/待完成/05-心理关怀模块架构.md`
- 对应心理机制 B6/B7：关怀触发层、关怀交互层、安全边界。

## 2. 对应 checklist 条目

- `docs/lsq-worklog/4-28-worklog/原始设计完成度-checklist.md`
- 五、05 心理关怀模块 Checklist / F、G、H。

## 3. 本次完成范围

- 新增 `jarvis_care_triggers` 表。
- 新增 `jarvis_care_interventions` 表。
- `proactive_messages` 新增 `snoozed_until`。
- 新增 care trigger rules：连续 3 天高压力、连续晚睡、任务过载、高风险关键词。
- 增加 cooldown 和 daily care budget。
- 用户反馈 `too_frequent` / `not_needed` 后触发降频。
- proactive message 关联 trigger / intervention / evidence。
- 新增真实 care feedback 接口。
- 新增真实 snooze 逻辑，snooze 后消息在到期前不返回列表。
- 抽出前端 `CareCard` 组件。
- 私聊 action 和 proactive feed 都使用 `CareCard`。

## 4. 修改代码文件

- `shadowlink-ai/app/jarvis/persistence.py`
  - 新增 `jarvis_care_triggers`、`jarvis_care_interventions`。
  - `proactive_messages` 新增 `snoozed_until`。
  - 新增 trigger/intervention 保存、反馈更新、snooze、负反馈计数、daily budget 查询 DAO。
- `shadowlink-ai/app/jarvis/care_triggers.py`
  - 新增 `build_care_trigger_candidates()`。
  - 新增 `evaluate_care_triggers()`。
- `shadowlink-ai/app/jarvis/mood_snapshot.py`
  - snapshot 聚合后自动评估 care triggers。
- `shadowlink-ai/app/api/v1/jarvis_router.py`
  - 新增 `POST /messages/{message_id}/care-feedback`。
- `shadowlink-ai/tests/unit/jarvis/test_care_triggers.py`
  - 新增 B6/B7 单元测试。
- `shadowlink-web/src/services/jarvisApi.ts`
  - 新增 `sendCareFeedback()`。
- `shadowlink-web/src/components/jarvis/CareCard.tsx`
  - 新增独立关怀卡组件。
- `shadowlink-web/src/components/jarvis/AgentChatPanel.tsx`
  - care action 改用 `CareCard` 并真实回写反馈。
- `shadowlink-web/src/components/jarvis/ProactiveMessageFeed.tsx`
  - care proactive message 使用 `CareCard`。

## 5. 新增或修改数据表

新增表：`jarvis_care_triggers`

字段：
- `id`
- `trigger_type`
- `severity`
- `reason`
- `evidence_ids_json`
- `status`
- `cooldown_until`
- `message_id`
- `created_at`
- `resolved_at`

新增表：`jarvis_care_interventions`

字段：
- `id`
- `trigger_id`
- `message_id`
- `agent_id`
- `intervention_type`
- `content`
- `suggested_action_json`
- `status`
- `user_feedback`
- `shown_at`
- `acted_at`
- `snoozed_until`
- `created_at`

修改表：`proactive_messages`

- 新增 `snoozed_until`。

## 6. 新增或修改接口

新增接口：

- `POST /v1/jarvis/messages/{message_id}/care-feedback`
  - Gateway 前缀下对应路径为 `/api/v1/jarvis/messages/{message_id}/care-feedback`。
  - 支持 feedback：`helpful`、`too_frequent`、`not_needed`、`snooze`、`handled`。
  - `snooze` 支持 `snooze_minutes`。

修改接口行为：

- `GET /v1/jarvis/messages`
  - 不返回尚未到期的 snoozed message。

## 7. 前端影响

- 新增独立 `CareCard`。
- 私聊中的 care action 使用 `CareCard`。
- 主动提醒 feed 中的 care message 使用 `CareCard`。
- 用户点击“有帮助 / 太频繁 / 稍后提醒 / 不需要这类 / 我已处理”都会真实回写后端。

## 8. 测试与验证

新增测试文件：

- `shadowlink-ai/tests/unit/jarvis/test_care_triggers.py`

覆盖点：

- 任务过载生成 care trigger、intervention、proactive message。
- 同一天不会无限重复关怀提醒。
- “太频繁”反馈后触发 daily budget 降频。
- 高风险文案不做诊断，提示可信任的人和当地紧急渠道。
- snooze 反馈会隐藏 proactive message，直到到期后才应重新出现。

实际运行结果：

- `pytest tests\unit\jarvis\test_care_triggers.py -q`：`5 passed`。
- `pytest tests\unit\jarvis\test_care_triggers.py tests\unit\jarvis\test_mood_care_observations.py tests\unit\jarvis\test_behavior_observations.py tests\unit\jarvis\test_stress_observations.py tests\unit\jarvis\test_mood_snapshots.py tests\unit\jarvis\test_care_trends.py -q`：`26 passed`。
- `npm.cmd run type-check`：通过。
- 仍有既有 warning：pytest `asyncio_mode` 配置 warning、`datetime.utcnow()` / `utcfromtimestamp()` deprecation warning。

## 9. 完成度变化

- 心理关怀模块 / F 关怀触发层：`[TODO]` -> `[MVP]`。
- 心理关怀模块 / G 关怀交互层：`[TODO]` -> `[MVP]`。
- 心理关怀模块 / H 安全边界：关键高风险边界 `[TODO]` -> `[MVP]`。
- 该变化不代表心理关怀模块全量完成。

## 10. 距离全量设计仍有缺口

- 用户主动求助触发仍沿用 B1 关怀 action，尚未统一进 care trigger rule。
- 危机分级仍是 low/medium/high，未细分明确自伤意图和紧急风险。
- 尚未把 feedback 转成长期个性化频率偏好画像。
- 尚未把 suggested action 直接生成 Maxwell 待确认日程调整卡。
