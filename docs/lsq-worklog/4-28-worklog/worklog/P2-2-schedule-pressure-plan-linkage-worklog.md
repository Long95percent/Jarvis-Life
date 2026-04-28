# P2-2 日程压力完整来源与计划联动 worklog

## 对应原始设计

- 对应 `docs/lsq-worklog/待完成/05-心理关怀模块架构.md` 中“压力评估层”：读取 `jarvis_plan_days`、calendar events、workbench items、逾期/重排日志，计算日程密度、任务逾期、未完成任务、休息窗口不足、晚上负载和连续高压。
- 对照 `docs/lsq-worklog/4-28-worklog/原始设计完成度-checklist.md`：本步补齐计划联动压力来源和连续高压，不把心理模块整体标为完成。

## 完成范围

- 确认并保留现有真实来源：calendar events、`background_task_days`、`jarvis_plan_days`、`maxwell_workbench_items`、missed tasks、rest window。
- 新增计划重排压力来源：读取 `jarvis_agent_events` 中的 `plan.rescheduled` 和 `plan.reschedule.skipped`，生成 `plan_reschedule_pressure` stress signal。
- 新增连续高压计算：读取最近 7 天 `jarvis_mood_snapshots`，连续至少 3 天 `stress_score` 或 `schedule_pressure_score >= 7` 时生成 `continuous_high_pressure`。
- stress signals 继续进入 mood snapshot 和 care day detail，因此心理趋势可解释“为什么今天压力高”。
- Decision 圆桌已有上下文预取心理 snapshot、压力信号、今日任务、日程事件、Maxwell workbench，本步保证压力信号里包含计划负载和重排日志。

## 代码文件

- `shadowlink-ai/app/jarvis/stress_observation.py`：新增 `plan_reschedule_pressure`、`continuous_high_pressure`，并读取 `list_agent_events()` / `list_mood_snapshots()`。
- `shadowlink-ai/tests/unit/jarvis/test_stress_observations_p2.py`：新增 P2-2 专项测试。
- `docs/lsq-worklog/4-28-worklog/test/P2-2-schedule-pressure-plan-linkage-frontend-validation.md`：新增前端路演验证方法。

## 表与接口

- 读取 `jarvis_plan_days`：当天计划负载、missed/rescheduled 状态。
- 读取 `background_task_days`：旧长期任务日计划兼容来源。
- 读取 `maxwell_workbench_items`：todo/doing 工作台积压。
- 读取 `jarvis_agent_events`：计划重排、重排失败、missed 后维护日志。
- 读取 `jarvis_mood_snapshots`：连续高压天数。
- 写入 `jarvis_stress_signals`：`plan_reschedule_pressure`、`continuous_high_pressure` 与既有压力信号。
- 复用接口：`GET /api/v1/jarvis/care/stress-signals?refresh=true`、`GET /api/v1/jarvis/care/trends`、圆桌 start/continue 上下文链路。

## 前端影响

- 心理趋势某日详情会通过已有 day detail 展示计划负载、重排日志、连续高压解释。
- Decision 圆桌读取到的 stress signals 更完整，能体现计划负载与重排压力。
- 不新增 MVP/debug 面板。

## 测试

- 已通过：`python -m py_compile app\jarvis\stress_observation.py tests\unit\jarvis\test_stress_observations_p2.py`。
- 已通过：`pytest tests\unit\jarvis\test_stress_observations.py tests\unit\jarvis\test_stress_observations_p2.py tests\unit\jarvis\test_mood_snapshots.py tests\unit\jarvis\test_care_trends.py tests\unit\jarvis\test_unified_planner.py -q`，结果 `29 passed`。
- 仍有既存 warning：pytest 配置中的 `asyncio_mode` 未识别、部分 `datetime.utcnow()` deprecation，不影响本步功能结论。

## 完成度变化

- P2-2 从“未完成”推进为“已完成”：日程压力来源覆盖计划日、日程、工作台、missed、重排日志、连续高压，并能进入心理趋势和圆桌上下文。
- 心理模块整体仍未全量完成，不能标记为 complete。

## 剩余缺口

- P2-3：心理中心产品化入口仍需继续，需在正常页面整合今日状态、趋势图、最近关怀、详情解释、隐私开关和清除数据。
