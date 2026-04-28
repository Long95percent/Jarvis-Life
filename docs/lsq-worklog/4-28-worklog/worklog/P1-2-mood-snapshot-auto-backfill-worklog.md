# P1-2 mood snapshot 自动调度与 backfill worklog

## 对应原始设计

- 对应 `docs/lsq-worklog/待完成/05-心理关怀模块架构.md` 中“心理快照/趋势层”：日级 mood snapshot 需要自动形成，并作为心理趋势、关怀触发和用户解释的基础。
- 对照 `docs/lsq-worklog/4-28-worklog/原始设计完成度-checklist.md`：推进 mood snapshot 从手动聚合 MVP 进入自动维护，但不把心理模块标记为全量完成。

## 完成范围

- 新增 mood snapshot 自动维护入口：服务启动检查、后台 routine 检查都会执行最近日期维护。
- 支持最近 N 天缺失 snapshot backfill：已有历史快照不重复生成，当天因证据持续累计允许刷新。
- 日级聚合继续包含 emotion、behavior、stress，并补入任务/计划/workbench 完成情况。
- `positive_events` 新增正向来源：完成任务、完成计划、完成工作台事项、开心/放松表达、按时休息、减少任务负载。
- 允许“只有正向完成事件”的日期生成 snapshot，避免完成任务但没有负面情绪时被误判为无数据。

## 代码文件

- `shadowlink-ai/app/jarvis/mood_snapshot.py`：扩展 `build_snapshot_payload()` 与 `aggregate_mood_snapshot()` 的正向事件来源与摘要。
- `shadowlink-ai/app/jarvis/mood_snapshot_maintenance.py`：新增 `ensure_mood_snapshots()`，负责启动/例行 backfill 与当天刷新。
- `shadowlink-ai/app/jarvis/proactive_routines.py`：例行检查中接入 `mood_snapshot_maintenance`。
- `shadowlink-ai/app/core/lifespan.py`：服务启动时执行 mood snapshot 检查。
- `shadowlink-ai/tests/unit/jarvis/test_mood_snapshots.py`：补 backfill、tracking 开关、正向事件聚合测试。
- `shadowlink-ai/tests/unit/jarvis/test_proactive_routines.py`：补 routine 自动执行测试，并让现有 async 测试不依赖缺失的 pytest-asyncio 插件。

## 表与接口

- 读取/写入 `jarvis_mood_snapshots`：自动 upsert 当天或缺失日期 snapshot。
- 读取 `jarvis_emotion_observations`、`jarvis_behavior_observations`、`jarvis_stress_signals` 作为基础证据。
- 读取 `background_task_days`、`jarvis_plan_days`、`maxwell_workbench_items` 作为任务完成正向来源。
- 本步骤不新增前端接口；通过启动生命周期和 proactive routine 自动生成，现有心理趋势/关怀读取接口可继续消费快照。

## 前端影响

- 用户不需要手动访问 `/care/snapshots` 或点击调试按钮。
- 正常使用 Mira、完成任务/计划、重启或等待后台例行检查后，心理趋势/关怀中心可以看到当天或最近缺失日期的 snapshot。
- 前端验证文档已补：`docs/lsq-worklog/4-28-worklog/test/P1-2-mood-snapshot-auto-backfill-frontend-validation.md`。

## 测试

- 已通过：`python -m py_compile app\jarvis\mood_snapshot.py app\jarvis\mood_snapshot_maintenance.py app\jarvis\proactive_routines.py app\core\lifespan.py`。
- 已通过：`pytest tests\unit\jarvis\test_mood_snapshots.py tests\unit\jarvis\test_proactive_routines.py tests\unit\jarvis\test_mood_care_observations.py tests\unit\jarvis\test_care_triggers.py -q`，结果 `30 passed`。
- 测试环境仍有既存 warning：`asyncio_mode` 配置未识别、部分 `datetime.utcnow()` deprecation，不影响本步功能结论。

## 完成度变化

- P1-2 从“未完成”推进为“已完成”：mood snapshot 已具备启动检查、例行维护、最近 N 天 backfill、当天刷新、正向事件来源聚合。
- 心理模块整体仍未全量完成，不能标记为 complete。

## 剩余缺口

- P1-3：心理趋势 day detail 解释链路仍未完成，需要把 snapshot 背后的 observation/stress/care trigger 明细返回给前端。
- P2-1：行为采集可靠性与桌面端策略仍需继续。
- P2-2：日程压力全来源与计划联动仍需继续完善。
- P2-3：心理中心产品化入口仍需继续。
