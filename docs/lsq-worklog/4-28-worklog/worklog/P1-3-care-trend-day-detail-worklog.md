# P1-3 心理趋势 day detail 解释链路 worklog

## 对应原始设计

- 对应 `docs/lsq-worklog/待完成/05-心理关怀模块架构.md` 中“趋势分析层”和“关怀触发层”的解释闭环：用户不仅看到分数，还要能理解分数来自哪些情绪、行为、压力和关怀触发证据。
- 对照 `docs/lsq-worklog/4-28-worklog/原始设计完成度-checklist.md`：本步推进心理趋势从基础图表进入“某日可解释详情”，但不等于心理模块全量完成。

## 完成范围

- 新增某日详情构建：按日期聚合 snapshot、emotion observations、behavior observations、stress signals、care triggers。
- 新增可读解释：任务/日程压力、晚睡/超过 bedtime、低能量表达、高压表达、正向事件、负向来源、关怀触发、连续高压提示。
- `/care/trends` 的 `details` 复用同一套 day detail 结构。
- 新增 `/care/days/{date}`，前端点击某天时可刷新当天详情。
- 关闭心理追踪时，趋势与某日详情均返回空证据和“心理趋势追踪已关闭”，避免展示伪数据。

## 代码文件

- `shadowlink-ai/app/jarvis/care_trends.py`：重构趋势聚合与新增 `build_care_day_detail()`。
- `shadowlink-ai/app/jarvis/persistence.py`：新增 `list_care_triggers_for_day()`，支持按创建日期或 evidence date 关联 care trigger。
- `shadowlink-ai/app/api/v1/jarvis_router.py`：新增 `GET /care/days/{day}`。
- `shadowlink-web/src/services/jarvisApi.ts`：补 `EmotionObservation`、`CareTrigger`、扩展 `CareTrendDetail`，新增 `getCareDayDetail()`。
- `shadowlink-web/src/components/jarvis/CareTrendsPanel.tsx`：点击日期时调用 day detail 接口，并展示情绪证据、关怀触发、正向/负向事件。
- `shadowlink-ai/tests/unit/jarvis/test_care_trends.py`：补 P1-3 day detail 和关闭追踪测试。

## 表与接口

- 读取 `jarvis_mood_snapshots`：当天快照、summary、positive_events、negative_events、risk_flags。
- 读取 `jarvis_emotion_observations`：当天情绪证据、压力/疲劳分、主要情绪。
- 读取 `jarvis_behavior_observations`：晚睡、超过 bedtime 等行为证据。
- 读取 `jarvis_stress_signals`：任务密度、日程压力、休息窗口不足等压力来源。
- 读取 `jarvis_care_triggers`：当天创建或 evidence date 指向当天的关怀触发。
- 新增接口：`GET /api/v1/jarvis/care/days/{date}`。
- 复用接口：`GET /api/v1/jarvis/care/trends`。

## 前端影响

- 心理趋势中心不新增 MVP/debug 面板，只在正常趋势卡片中增强点击某天后的解释区域。
- 用户点击某天后，会加载真实 day detail，看到压力来源、行为信号、情绪证据、关怀触发和正负事件。
- 前端验证文档：`docs/lsq-worklog/4-28-worklog/test/P1-3-care-trend-day-detail-frontend-validation.md`。

## 测试

- 已通过：`python -m py_compile app\jarvis\care_trends.py app\jarvis\persistence.py app\api\v1\jarvis_router.py`。
- 已通过：`pytest tests\unit\jarvis\test_care_trends.py tests\unit\jarvis\test_mood_snapshots.py tests\unit\jarvis\test_care_triggers.py -q`，结果 `21 passed`。
- 已通过：`npm.cmd run type-check`。
- 仍有既存 warning：pytest 配置中的 `asyncio_mode` 未识别、部分 `datetime.utcnow()` deprecation，不影响本步功能结论。

## 完成度变化

- P1-3 从“未完成”推进为“已完成”：用户可从心理趋势中心点击某天查看真实证据链和可读解释。
- 心理模块整体仍未全量完成，不能标记为 complete。

## 剩余缺口

- P2-1：行为采集可靠性与桌面端策略仍需继续。
- P2-2：日程压力全来源与计划联动仍需继续完善。
- P2-3：心理中心产品化入口仍需继续。
