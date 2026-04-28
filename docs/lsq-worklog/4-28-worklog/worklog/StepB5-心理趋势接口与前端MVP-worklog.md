# StepB5 心理趋势接口与前端 MVP Worklog

## 0. 阶段边界

本阶段是 MVP，不是心理关怀模块全量完成。

本阶段只完成“后端趋势接口 + 前端轻量心理趋势入口”的最小闭环：趋势数据来自 `jarvis_mood_snapshots`，并能点击某一天查看压力解释。它不是完整心理中心，也不是诊断页面。

## 1. 对应原始设计文件

- `docs/lsq-worklog/待完成/05-心理关怀模块架构.md`
- 对应心理机制 B5：长期趋势层。

## 2. 对应 checklist 条目

- `docs/lsq-worklog/4-28-worklog/原始设计完成度-checklist.md`
- 五、05 心理关怀模块 Checklist / E. 长期趋势层。

## 3. 本次完成范围

- 新增 `GET /v1/jarvis/care/trends?range=week|month|year`。
- 返回 mood、stress、energy、sleep risk、schedule pressure 时间序列。
- 返回每一天的 details：snapshot、stress_signals、behavior_observations、explanations。
- 新增前端“心理趋势中心 MVP”入口。
- 前端支持 week/month/year 切换。
- 前端以周/月柱状、全年热力网格形式展示趋势。
- 前端支持指标切换：心情、压力、能量、睡眠风险、日程压力。
- 点击某一天可查看压力来源解释。
- 新增心理追踪开关，关闭后后端停止写入情绪、行为、压力信号，趋势接口返回空序列。
- 新增心理数据清除入口，真实删除 emotion observations、behavior observations、stress signals、mood snapshots。

## 4. 修改代码文件

- `shadowlink-ai/app/jarvis/care_trends.py`
  - 新增 `build_care_trends()`。
  - 新增 `empty_care_trends()`，用于追踪关闭时返回空趋势。
  - 新增 week/month/year 范围聚合。
  - 读取 mood snapshots、stress signals、behavior observations。
- `shadowlink-ai/app/api/v1/jarvis_router.py`
  - 新增 `GET /care/trends`。
  - 新增 `GET /care/settings`。
  - 新增 `PATCH /care/settings/tracking`。
  - 新增 `DELETE /care/data`。
- `shadowlink-ai/app/jarvis/user_settings.py`
  - 新增 `psychological_tracking_enabled` 设置。
  - 新增 `is_psychological_tracking_enabled()`。
- `shadowlink-ai/app/jarvis/mood_care.py`
  - 追踪关闭时不写入 emotion observation / proactive care action。
- `shadowlink-ai/app/jarvis/behavior_observation.py`
  - 追踪关闭时不写入 behavior observation。
- `shadowlink-ai/app/jarvis/stress_observation.py`
  - 追踪关闭时不写入 stress signal。
- `shadowlink-ai/app/jarvis/persistence.py`
  - 新增 `clear_psychological_care_data()`。
- `shadowlink-ai/tests/unit/jarvis/test_care_trends.py`
  - 新增 B5 趋势接口单元测试。
- `shadowlink-web/src/services/jarvisApi.ts`
  - 新增 `CareTrendPoint`、`CareTrendDetail`、`CareTrendsResponse` 类型。
  - 新增 `getCareTrends()`。
  - 新增 `getCareSettings()`、`setPsychologicalTracking()`、`clearCareData()`。
- `shadowlink-web/src/components/jarvis/CareTrendsPanel.tsx`
  - 新增心理趋势中心 MVP 面板。
- `shadowlink-web/src/components/jarvis/JarvisHome.tsx`
  - 将心理趋势中心挂到 Jarvis 右侧栏。
- `docs/lsq-worklog/4-28-worklog/原始设计完成度-checklist.md`
  - 将 E 长期趋势层相关条目从 `[TODO]` 更新为 `[MVP]`，并保留未完成缺口。

## 5. 新增或修改数据表

本阶段未新增数据表。

新增设置字段：
- `JarvisSettings.psychological_tracking_enabled`

读取已有表：
- `jarvis_mood_snapshots`
- `jarvis_stress_signals`
- `jarvis_behavior_observations`

## 6. 新增或修改接口

新增接口：

- `GET /v1/jarvis/care/trends`
  - 参数：`range=week|month|year`，可选 `end=YYYY-MM-DD`。
  - Gateway 前缀下对应路径为 `/api/v1/jarvis/care/trends`。
- `GET /v1/jarvis/care/settings`
  - 查询心理追踪开关。
- `PATCH /v1/jarvis/care/settings/tracking`
  - 开启/关闭心理追踪。
- `DELETE /v1/jarvis/care/data`
  - 清除心理趋势相关数据。

返回结构：
- `range`
- `start`
- `end`
- `series[]`
- `details[date]`

## 7. 前端影响

- Jarvis 首页右侧栏新增“心理趋势中心 MVP”。
- 用户可以切换周/月/年。
- 用户可以切换心情、压力、能量、睡眠风险、日程压力指标。
- 用户可以点击某一天查看压力解释。
- 用户可以关闭心理追踪；关闭后不会继续写入心理相关 observation/signal。
- 用户可以清除心理数据；清除后趋势图回到空序列。
- 数据来自后端 snapshot，不是前端临时猜测。

## 8. 测试与验证

新增测试文件：

- `shadowlink-ai/tests/unit/jarvis/test_care_trends.py`

覆盖点：
- week 范围返回 7 天序列。
- series 返回 mood/stress/energy/schedule pressure。
- details 返回 stress signals 和 explanations。
- router 直接使用后端 snapshot 数据。
- 追踪关闭后趋势接口返回空序列。
- 清除数据后 snapshots/signals/observations 被真实删除。

建议运行：

```powershell
cd D:\github_desktop\Jarvis-Life\shadowlink-ai
Remove-Item Env:SSLKEYLOGFILE -ErrorAction SilentlyContinue
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
pytest tests\unit\jarvis\test_care_trends.py -q
```

前端建议运行：

```powershell
cd D:\github_desktop\Jarvis-Life\shadowlink-web
npm.cmd run type-check
```

实际运行结果：

- `pytest tests\unit\jarvis\test_care_trends.py -q`：`4 passed`。
- `pytest tests\unit\jarvis\test_mood_care_observations.py tests\unit\jarvis\test_behavior_observations.py tests\unit\jarvis\test_stress_observations.py tests\unit\jarvis\test_mood_snapshots.py tests\unit\jarvis\test_care_trends.py -q`：`21 passed`。
- `npm.cmd run type-check`：通过。
- 仍有既有 warning：pytest `asyncio_mode` 配置 warning、`datetime.utcnow()` deprecation warning。

## 9. 完成度变化

- 心理关怀模块 / E 长期趋势层：`[TODO]` -> `[MVP]`。
- 该变化只代表趋势接口与前端轻量入口可用，不代表完整心理中心完成。

## 10. 距离全量设计仍有缺口

- 仍未引入第三方折线图库，当前使用自研轻量柱状/热力网格。
- 仍未把“点击某天”与任务/日程详情页深度联动。
- 仍未提供数据导出。
