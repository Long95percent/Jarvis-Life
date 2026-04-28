# P2-1 行为采集可靠性与桌面端策略 worklog

## 对应原始设计

- 对应 `docs/lsq-worklog/待完成/05-心理关怀模块架构.md` 中“行为采集层”：记录首次打开、最后活跃、深夜使用、超过 bedtime、打开/关闭程序、连续在线等行为信号。
- 对照 `docs/lsq-worklog/4-28-worklog/原始设计完成度-checklist.md`：本步把行为采集从 heartbeat MVP 推进为可聚合的 activity session window 和生命周期事件链路。

## 完成范围

- heartbeat 合并为 `activity_window`：同一天、同 agent、同 session 的 heartbeat/可见/激活/恢复事件会更新同一条窗口记录。
- 支持刷新、关闭、切后台、恢复：前端使用 `visibilitychange`、`pagehide`、`focus`、`blur`、`online`，关闭时通过 `sendBeacon`/`keepalive` 兜底。
- 支持 idle：前端 5 分钟无操作写 `idle_start`，恢复操作写 `idle_end` 并继续更新 activity window。
- 支持 Electron 桌面端事件：主进程转发 app opened/minimized/activated/restored/closed，preload 暴露安全 listener，渲染层统一上报。
- 关闭心理追踪后，后端 `/care/behavior-events` 不再写 behavior observation。

## 代码文件

- `shadowlink-ai/app/jarvis/persistence.py`：新增 `upsert_behavior_activity_window()`，复用 `jarvis_behavior_observations` 存储 activity window。
- `shadowlink-ai/app/jarvis/behavior_observation.py`：`record_behavior_event()` 支持窗口聚合、occurred_at、session_started_at。
- `shadowlink-ai/app/api/v1/jarvis_router.py`：扩展 `BehaviorEventRequest` 与允许的生命周期事件。
- `shadowlink-web/src/services/jarvisApi.ts`：新增 `BehaviorEventType`、`recordBehaviorEventBeacon()`、时间戳字段。
- `shadowlink-web/src/components/jarvis/AgentChatPanel.tsx`：新增 activity window 上报、idle 检测、关闭兜底、Electron 生命周期监听。
- `shadowlink-electron/src/main/index.ts`：转发主窗口 opened/minimized/activated/restored/closed 事件。
- `shadowlink-electron/src/preload/index.ts`：暴露 `onJarvisBehaviorLifecycle()` 给渲染层。
- `shadowlink-ai/tests/unit/jarvis/test_behavior_observations.py`：补窗口合并、idle/恢复/桌面事件、关闭追踪测试。

## 表与接口

- 复用表：`jarvis_behavior_observations`。
- 新窗口类型：`activity_window`，字段使用 `actual_first_active_at`、`actual_last_active_at`、`duration_minutes` 表示 session window。
- 新增/扩展事件类型：`idle_start`、`idle_end`、`sleep`、`resume`、`app_opened`、`app_closed`、`app_minimized`、`app_activated`、`app_restored`。
- 接口：`POST /api/v1/jarvis/care/behavior-events` 支持 `occurred_at` 和 `session_started_at`。

## 前端影响

- 用户不需要看到任何 MVP/debug 面板。
- 正常使用聊天页、切后台、关闭、恢复、桌面端最小化/激活都会形成行为证据。
- 心理趋势某日详情可展示这些行为信号，帮助解释能量低、晚睡或连续在线风险。
- 前端验证文档：`docs/lsq-worklog/4-28-worklog/test/P2-1-behavior-collection-frontend-validation.md`。

## 测试

- 已通过：`python -m py_compile app\jarvis\behavior_observation.py app\jarvis\persistence.py app\api\v1\jarvis_router.py tests\unit\jarvis\test_behavior_observations.py`。
- 已通过：`pytest tests\unit\jarvis\test_behavior_observations.py tests\unit\jarvis\test_mood_snapshots.py tests\unit\jarvis\test_care_trends.py -q`，结果 `21 passed`。
- 已通过：`npm.cmd run type-check`（shadowlink-web）。
- 已通过：`npm.cmd run typecheck`（shadowlink-electron）。
- 仍有既存 warning：pytest 配置中的 `asyncio_mode` 未识别、部分 `datetime.utcnow()` deprecation，不影响本步功能结论。

## 完成度变化

- P2-1 从“未完成”推进为“已完成”：行为采集已有 window 聚合、刷新/异常关闭兜底、idle/恢复、Electron 桌面端生命周期、安全追踪开关。
- 心理模块整体仍未全量完成，不能标记为 complete。

## 剩余缺口

- P2-2：日程压力完整来源与计划联动仍需继续完善，包括连续高压天数、计划重排日志、逾期/未完成任务接入。
- P2-3：心理中心产品化入口仍需继续。
