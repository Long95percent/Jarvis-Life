# 2026-05-03 日程模块 bug 修复日志

## 目标
- 移除打开日历时的待确认安排展示与无关加载。
- 让日/周/月视图点击日程后在右侧显示详情，并可直接编辑。
- 确保修改写回后端数据库，并同步更新投影。
- 不通过 LLM 做重新写入。

## 已完成
- 后端新增了日程事件更新后的 plan_day 同步逻辑，更新 `PUT /api/v1/jarvis/calendar/events/{event_id}` 时会同步对应 `jarvis_plan_days.calendar_event_id` 记录。
- 日历更新接口现在会刷新 `active_events`，避免前端看到旧投影。
- 前端日历页移除了“待确认安排”区域及其加载请求，避免打开日历就出现一堆待确认项。
- 前端日/周/月视图中的日程点击现在统一进入右侧详情区，详情区支持编辑。
- 保存后会重新拉取后端数据，保证投影和右侧列表都回到数据库最新状态。
- 更新了前端 `jarvisApi` 的返回类型，补充 `plan_day` 可选字段。
- 在接口契约 `CALENDAR_MODULE_INTERFACE_CONTRACT.md` 中补充了“日程事件更新同步”说明。

## 验证
- 后端单测：`test_manual_calendar_event_creates_short_term_plan_day_but_calendar_items_are_deduped`
- 后端单测：`test_manual_calendar_event_update_syncs_backing_plan_day_and_calendar_projection`
- 后端单测：`test_plan_day_move_complete_and_cancel_sync_calendar_event`
- 前端类型检查：`npm.cmd run type-check`

## 涉及文件
- `shadowlink-ai/app/api/v1/jarvis_router.py`
- `shadowlink-ai/app/jarvis/persistence.py`
- `shadowlink-ai/tests/unit/jarvis/test_unified_planner.py`
- `shadowlink-web/src/components/jarvis/CalendarPanel.tsx`
- `shadowlink-web/src/services/jarvisApi.ts`
- `CALENDAR_MODULE_INTERFACE_CONTRACT.md`

## 追加说明：正式前端交接
- 当前 `CalendarPanel.tsx` 修改只作为本地展示和验证用，后续正式前端可以由同事替换。
- 已在 `CALENDAR_MODULE_INTERFACE_CONTRACT.md` 的 `Calendar Event Update Sync` 下补充前端接入注意事项。
- 正式前端需要复用现有后端更新接口，保存后重新查询后端 calendar/planner items，不要只改本地状态。
- 正式前端不要在打开日历时自动展示无关 pending actions，应放到显式确认入口。
