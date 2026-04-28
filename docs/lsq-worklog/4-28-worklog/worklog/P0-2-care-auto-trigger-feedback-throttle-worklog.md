# P0-2 心理关怀自动触发、类型降频与反馈去重 Worklog

## 对应原始设计
- 对应 `心理与圆桌全量完成指令.md` 的 P0-2：关怀触发需要自动运行、按类型降频，并检查 CareCard 是否重复发送反馈请求。
- 对应心理模块 B1/B2 的关怀闭环：情绪/压力信号不只在后端手动测试时生效，而要进入日常主动关怀链路。
- 本次仍是心理关怀触发链路补强，不声明心理模块全量完成。

## 完成范围
- `evaluate_care_triggers()` 已接入 `ProactiveRoutineScheduler.check_routines()`，非静默时段日常例行检查会自动跑心理关怀触发。
- 在全局 7 天负反馈预算之外，新增按 `trigger_type` 的 14 天负反馈统计；同类型收到 `too_frequent` / `not_needed` 后，后续同类型触发冷却时间扩大 3 倍。
- 修复 CareCard 在私聊 action 卡片中重复发送反馈请求的问题：私聊父组件负责提交反馈，CareCard 可通过 `submitFeedback={false}` 只更新 UI；主动消息流仍由 CareCard 自己提交。

## 代码文件
- `shadowlink-ai/app/jarvis/proactive_routines.py`
  - 日常例行检查中自动调用 `evaluate_care_triggers()`。
- `shadowlink-ai/app/jarvis/care_triggers.py`
  - 引入按类型负反馈降频，调整同类型触发冷却。
- `shadowlink-ai/app/jarvis/persistence.py`
  - 新增 `recent_negative_care_feedback_count_by_type()`，按干预关联触发类型统计负反馈。
- `shadowlink-web/src/components/jarvis/CareCard.tsx`
  - 新增 `submitFeedback?: boolean`，避免重复请求。
- `shadowlink-web/src/components/jarvis/AgentChatPanel.tsx`
  - 私聊中的 care action 卡片传入 `submitFeedback={false}`。
- `shadowlink-ai/tests/unit/jarvis/test_care_triggers.py`
  - 新增自动触发与按类型降频测试。

## 表 / 接口
- 表：复用 `jarvis_care_triggers`、`jarvis_care_interventions`、`proactive_messages`，无新增表。
- 查询：通过 `jarvis_care_interventions.trigger_id -> jarvis_care_triggers.id` 聚合 `trigger_type` 负反馈。
- 接口：未新增 HTTP 接口；继续复用 `POST /api/v1/jarvis/messages/{message_id}/care-feedback`。

## 前端影响
- 用户在私聊中看到 Mira 关怀卡片并点“有帮助 / 稍后提醒 / 太频繁 / 不需要这类”时，只提交一次反馈。
- 用户在主动消息 feed 中操作关怀卡片时，仍可正常提交反馈并触发隐藏、已读、稍后提醒等状态。
- 这不是展示后台逻辑的面板，而是保证正常使用页里的关怀反馈不会重复。

## 测试
- `python -m py_compile app\jarvis\persistence.py app\jarvis\care_triggers.py app\jarvis\proactive_routines.py`
- `pytest tests\unit\jarvis\test_care_triggers.py -q`：7 passed。
- `npm.cmd run type-check`：通过。

## 完成度变化
- P0-2 从“手动触发 + 反馈可能重复”提升为“日常例行自动触发 + 同类型反馈降频 + 前端反馈去重”。
- 心理关怀链路完成度提升：主动触发链路更接近真实可用，但仍不标记为心理模块全量完成。

## 剩余缺口
- 还需要真实系统级调度入口持续调用 `ProactiveRoutineScheduler.check_routines()`，本次完成的是例行检查函数内部自动触发。
- 关怀策略还未做更细的用户偏好学习，例如按时间段、语气、Agent 单独降频。
- 前端还需要补充路演式用户使用手册，说明怎样通过真实页面演示关怀触发与反馈闭环。
