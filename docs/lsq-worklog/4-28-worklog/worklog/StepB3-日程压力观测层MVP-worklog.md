# StepB3 日程压力观测层 MVP Worklog

## 0. 阶段边界

本阶段是 MVP，不是心理关怀模块全量完成。

本阶段只完成“日程/任务压力信号”的最小闭环：从内存日历、后台任务 day、Maxwell workbench、missed tasks 中生成可解释 stress signals，并汇入每日心理快照。它只解释压力来源，不做心理诊断。

## 1. 对应原始设计文件

- `docs/lsq-worklog/待完成/05-心理关怀模块架构.md`
- 对应心理机制 B3：日程压力观测层。

## 2. 对应 checklist 条目

- `docs/lsq-worklog/4-28-worklog/原始设计完成度-checklist.md`
- 五、05 心理关怀模块 Checklist / C. 日程压力观测层。

## 3. 本次完成范围

- 新增 `jarvis_stress_signals` 表。
- 新增 stress signal 保存、替换、查询 DAO。
- 新增日程压力观测模块 `stress_observation.py`。
- 从 `calendar_adapter.get_events_between()` 读取当天日历。
- 从 `background_task_days` 读取当天计划 day。
- 从 `maxwell_workbench_items` 读取 Maxwell 工作台 backlog。
- 识别 missed tasks。
- 计算 schedule density、task load、missed tasks、workbench backlog、rest window insufficient、evening load。
- 每个 signal 写入 reason 和 source_refs。
- 新增 `GET /v1/jarvis/care/stress-signals` 调试接口。
- 将 stress signals 汇入 `jarvis_mood_snapshots.schedule_pressure_score` 和 `risk_flags`。

## 4. 修改代码文件

- `shadowlink-ai/app/jarvis/persistence.py`
  - 新增 `jarvis_stress_signals` schema 和索引。
  - 新增 `replace_stress_signals()`。
  - 新增 `list_stress_signals()`。
- `shadowlink-ai/app/jarvis/stress_observation.py`
  - 新增 `build_schedule_pressure_signals()`。
  - 新增 `aggregate_schedule_pressure_signals()`。
- `shadowlink-ai/app/jarvis/mood_snapshot.py`
  - 日级快照聚合纳入 stress signals。
- `shadowlink-ai/app/api/v1/jarvis_router.py`
  - 新增 `GET /care/stress-signals`。
- `shadowlink-ai/tests/unit/jarvis/test_stress_observations.py`
  - 新增 B3 日程压力观测层 MVP 单元测试。
- `docs/lsq-worklog/4-28-worklog/原始设计完成度-checklist.md`
  - 将 C 日程压力观测层相关条目从 `[TODO]` 更新为 `[MVP]`，并保留未完成缺口。

## 5. 新增或修改数据表

新增表：`jarvis_stress_signals`

字段：
- `id`
- `date`
- `signal_type`
- `severity`
- `score`
- `reason`
- `source_refs`
- `source`
- `created_at`

新增索引：
- `idx_stress_signals_date`
- `idx_stress_signals_type`

## 6. 新增或修改接口

新增接口：

- `GET /v1/jarvis/care/stress-signals`
  - 参数：`date`、`signal_type`、`refresh`、`limit`。
  - `refresh=true&date=YYYY-MM-DD` 时重新计算当天 stress signals。
  - Gateway 前缀下对应路径为 `/api/v1/jarvis/care/stress-signals`。

已修改现有聚合行为：

- `GET /v1/jarvis/care/snapshots`
  - 返回的 snapshot 可包含由 stress signals 聚合出的 `schedule_pressure_score` 和 pressure `risk_flags`。

## 7. 前端影响

- 本阶段没有新增前端页面。
- 前端如需调试，可调用 `/api/v1/jarvis/care/stress-signals?date=YYYY-MM-DD&refresh=true` 查看压力来源。
- 后续 B5 心理趋势中心应展示这些 reason 和 source_refs，让用户理解“今天为什么压力高”。

## 8. 测试与验证

新增测试文件：

- `shadowlink-ai/tests/unit/jarvis/test_stress_observations.py`

覆盖点：

- 高密度日程生成 `schedule_density_high`。
- 晚间任务生成 `evening_load_high`。
- 多任务计划生成 `task_load_high`。
- missed task 生成 `missed_tasks`。
- Maxwell workbench backlog 可参与压力信号。
- 每个 signal 都有 `reason` 和 `source_refs`。
- 调试 API 支持 refresh 和 query。
- stress signals 汇入每日心理快照。

建议运行：

```powershell
cd D:\github_desktop\Jarvis-Life\shadowlink-ai
Remove-Item Env:SSLKEYLOGFILE -ErrorAction SilentlyContinue
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
pytest tests\unit\jarvis\test_stress_observations.py -q
```

实际运行结果：

- `pytest tests\unit\jarvis\test_stress_observations.py -q`：`3 passed`。
- `pytest tests\unit\jarvis\test_mood_care_observations.py tests\unit\jarvis\test_behavior_observations.py tests\unit\jarvis\test_stress_observations.py tests\unit\jarvis\test_mood_snapshots.py -q`：`17 passed`。
- 仍有既有 warning：pytest `asyncio_mode` 配置 warning、`datetime.utcnow()` deprecation warning。

## 9. 完成度变化

- 心理关怀模块 / C 日程压力观测层：`[TODO]` -> `[MVP]`。
- 该变化只代表日程压力观测层具备最小信号生成与快照汇入能力，不代表心理关怀模块完成。

## 10. 距离全量设计仍有缺口

- 尚未接入独立 `jarvis_plan_days`，当前使用已有 `background_task_days`。
- 尚未接入重排日志，因此无法解释“频繁重排导致压力”。
- 尚未实现连续高压天数。
- 尚未在前端做压力来源拆解 UI。
- 尚未让圆桌 decision 显式预取 stress signals；当前先通过 mood snapshot 间接提供 schedule pressure。
