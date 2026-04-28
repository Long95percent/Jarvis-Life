# StepB2 行为采集层 MVP Worklog

## 0. 阶段边界

本阶段是 MVP，不是心理关怀模块全量完成。

本阶段只完成“聊天活跃行为采集”的最小闭环：把用户在前端与 Agent 对话形成的活跃时间，转成心理机制可使用的行为 observation。深夜使用、超过 bedtime 只作为疲劳/风险信号，不做医学或心理诊断。

## 1. 对应原始设计文件

- `docs/lsq-worklog/待完成/05-心理关怀模块架构.md`
- 对应心理机制 B2：行为采集层。

## 2. 对应 checklist 条目

- `docs/lsq-worklog/4-28-worklog/原始设计完成度-checklist.md`
- 五、05 心理关怀模块 Checklist / B. 行为采集层。

## 3. 本次完成范围

- 新增聊天行为 observation 存储表 `jarvis_behavior_observations`。
- 新增行为采集 DAO：保存和查询 behavior observations。
- 新增聊天活跃采集规则：首次活跃、最后活跃、深夜使用、超过 bedtime。
- 新增前端生命周期行为事件：heartbeat、关闭私聊、切后台、回前台。
- 新增 behavior observation 查询 API，支持前端 MVP 调试展示。
- 将 behavior observations 汇入每日心理快照，影响 `sleep_risk_score` 和 `risk_flags`。
- 接入用户资料中的 `bedtime` / `wake`。
- 接入 `/v1/jarvis/chat` 聊天流程：用户消息落库后记录行为 observation。
- 接入 Agent 私聊面板，前端可直接看到最近行为采集信号。
- 补充单元测试验证 B2 MVP 行为。

## 4. 修改代码文件

- `shadowlink-ai/app/jarvis/persistence.py`
  - 新增 `jarvis_behavior_observations` schema 和索引。
  - 新增 `save_behavior_observation()`。
  - 新增 `list_behavior_observations()`。
- `shadowlink-ai/app/jarvis/behavior_observation.py`
  - 新增 `BehaviorObservationPayload`。
  - 新增 `build_chat_activity_observations()`。
  - 新增 `record_chat_activity_observations()`。
  - 新增 `record_behavior_event()`。
- `shadowlink-ai/app/jarvis/mood_snapshot.py`
  - 日级快照聚合纳入 behavior observations。
- `shadowlink-ai/app/api/v1/jarvis_router.py`
  - 在聊天用户消息落库后记录聊天活跃 behavior observation。
  - 新增 behavior observation 查询和前端生命周期事件记录接口。
- `shadowlink-web/src/services/jarvisApi.ts`
  - 新增 `BehaviorObservation` 类型。
  - 新增 `recordBehaviorEvent()`。
  - 新增 `listBehaviorObservations()`。
- `shadowlink-web/src/components/jarvis/AgentChatPanel.tsx`
  - 新增 heartbeat / visibility / close 生命周期上报。
  - 新增“行为采集层 MVP”前端可视化小面板。
- `shadowlink-ai/tests/unit/jarvis/test_behavior_observations.py`
  - 新增 B2 行为采集层 MVP 单元测试。
- `shadowlink-ai/tests/unit/jarvis/test_mood_snapshots.py`
  - 新增 behavior observations 汇入每日快照测试。
- `docs/lsq-worklog/4-28-worklog/原始设计完成度-checklist.md`
  - 将 B 行为采集层相关条目从 `[TODO]` 更新为 `[MVP]`，并保留未完成缺口。

## 5. 新增或修改数据表

新增表：`jarvis_behavior_observations`

字段：
- `id`
- `date`
- `session_id`
- `agent_id`
- `observation_type`
- `expected_bedtime`
- `expected_wake`
- `actual_first_active_at`
- `actual_last_active_at`
- `deviation_minutes`
- `duration_minutes`
- `source`
- `created_at`

新增索引：
- `idx_behavior_observations_date`
- `idx_behavior_observations_session`
- `idx_behavior_observations_type`

## 6. 新增或修改接口

新增接口：

- `GET /v1/jarvis/care/behavior-observations`
  - 查询 behavior observations。
  - Gateway 前缀下对应路径为 `/api/v1/jarvis/care/behavior-observations`。
- `POST /v1/jarvis/care/behavior-events`
  - 记录前端生命周期事件：heartbeat、closed、visibility_hidden、visibility_visible。
  - Gateway 前缀下对应路径为 `/api/v1/jarvis/care/behavior-events`。

已修改现有接口行为：
- `POST /v1/jarvis/chat`
  - 用户发起聊天后，后端自动写入行为 observation。
  - Gateway 前缀下对应路径为 `/api/v1/jarvis/chat`。

## 7. 前端影响

- 前端不需要新增独立页面就能触发 B2 MVP：只要用户在 Agent 私聊页发送消息，后端就会记录行为 observation。
- Agent 私聊面板底部新增“行为采集层 MVP”小面板，可看到最近 observation 标签。
- 前端每 30 秒发送一次 heartbeat，关闭私聊时发送 closed，切后台/回前台发送 visibility 事件。
- 如果要最大化 Demo 效果，可以把用户作息设置为较早 bedtime，例如 `23:00`，然后在接近或超过 bedtime 的本地时间发送消息，后端会记录 `late_night_usage` / `beyond_bedtime`。
- 当前仍不是完整趋势页；如需产品化展示，应后续新增心理趋势/日历热力图页面。

## 8. 测试与验证

新增测试文件：
- `shadowlink-ai/tests/unit/jarvis/test_behavior_observations.py`

覆盖点：
- 第一次聊天记录 `first_active` 和 `last_active`。
- 同一天同 session 第二次聊天只追加 `last_active`，并计算 `duration_minutes`。
- 23:45 聊天记录 `late_night_usage` 和 `beyond_bedtime`，偏离 bedtime 45 分钟。
- 验证 observation 包含 bedtime/wake，且不包含诊断字段。
- 前端生命周期 API 可记录 `heartbeat` 和 `closed`。
- behavior observations 可汇入每日心理快照，生成 `beyond_bedtime` risk flag。

实际运行结果：

- `pytest tests\unit\jarvis\test_behavior_observations.py tests\unit\jarvis\test_mood_snapshots.py -q`：`8 passed`。
- `pytest tests\unit\jarvis\test_mood_care_observations.py tests\unit\jarvis\test_mood_snapshots.py tests\unit\jarvis\test_behavior_observations.py -q`：`14 passed`。
- `npm.cmd run type-check`：通过。
- 仍有既有 warning：pytest `asyncio_mode` 配置 warning、`datetime.utcnow()` deprecation warning。

建议运行：

```powershell
cd D:\github_desktop\Jarvis-Life\shadowlink-ai
Remove-Item Env:SSLKEYLOGFILE -ErrorAction SilentlyContinue
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
pytest tests\unit\jarvis\test_behavior_observations.py tests\unit\jarvis\test_mood_snapshots.py -q
```

## 9. 完成度变化

- 心理关怀模块 / B 行为采集层：`[TODO]` -> `[MVP]`。
- 该变化只代表行为采集层具备聊天触发型最小采集能力，不代表心理关怀模块完成。

## 10. 距离全量设计仍有缺口

- 前端 heartbeat / 关闭事件已实现 MVP，但没有高精度在线会话合并算法。
- behavior observation 已汇入 `jarvis_mood_snapshots`，但只影响 sleep risk / risk_flags，尚未做复杂长期趋势权重。
- 已提供 behavior observation 查询 API 和私聊面板 MVP 展示，但尚未做独立心理趋势页面。
- 尚未做跨天睡眠窗口、长期晚睡趋势、连续晚睡触发规则。
- 尚未结合任务、日程压力、完成情况做综合解释。
