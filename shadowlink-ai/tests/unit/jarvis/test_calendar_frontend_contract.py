from pathlib import Path


def _frontend_source() -> str:
    return (Path(__file__).parents[4] / "shadowlink-web" / "src" / "services" / "jarvisApi.ts").read_text(encoding="utf-8")


def _method_block(source: str, method_name: str) -> str:
    start = source.index(f"async {method_name}")
    next_method = source.find("\n  async ", start + 1)
    return source[start:] if next_method == -1 else source[start:next_method]


def test_calendar_loading_apis_throw_instead_of_returning_empty_data_on_http_failure() -> None:
    source = _frontend_source()
    for method_name in [
        "listPendingActions",
        "listBackgroundTasks",
        "listBackgroundTaskDays",
        "listPlans",
        "listPlanDays",
        "listPlannerTasks",
        "createPlan",
        "updatePlan",
        "mergePlans",
        "splitPlan",
        "bulkUpdatePlanDays",
        "updateBackgroundTask",
        "cleanupDuplicatePlannerTasks",
        "projectPlanToCalendar",
        "reschedulePlan",
        "runPlannerDailyMaintenanceOnce",
        "markOverduePlannerDaysMissed",
        "listMaxwellWorkbenchItems",
        "pushDailyTasksToMaxwellWorkbench",
        "getPlannerCalendar",
    ]:
        block = _method_block(source, method_name)
        assert "if (!res.ok) throw await errorFromResponse" in block, method_name
        assert "if (!res.ok) return []" not in block, method_name
        assert "if (!res.ok) return { items: [], conflicts: [], free_windows: [] }" not in block, method_name


def test_calendar_panel_reports_named_load_steps() -> None:
    component_path = Path(__file__).parents[4] / "shadowlink-web" / "src" / "components" / "jarvis" / "CalendarPanel.tsx"
    source = component_path.read_text(encoding="utf-8")

    assert "日程数据加载失败" in source
    for label in ["日历项", "待确认安排", "统一任务清单", "后台任务", "后台任务日", "长期计划", "计划日"]:
        assert label in source


def test_calendar_panel_exposes_overdue_scan_flow() -> None:
    component_path = Path(__file__).parents[4] / "shadowlink-web" / "src" / "components" / "jarvis" / "CalendarPanel.tsx"
    source = component_path.read_text(encoding="utf-8")

    assert "逾期计划扫描" in source
    assert "markOverduePlannerDaysMissed" in source
    assert "扫描完成：已标记" in source


def test_calendar_panel_exposes_maxwell_workbench_view() -> None:
    component_path = Path(__file__).parents[4] / "shadowlink-web" / "src" / "components" / "jarvis" / "CalendarPanel.tsx"
    source = component_path.read_text(encoding="utf-8")

    assert 'type PanelTab = "calendar" | "tasks" | "workbench"' in source
    assert "Maxwell 工作台" in source
    assert "listMaxwellWorkbenchItems" in source
    assert "pushDailyTasksToMaxwellWorkbench" in source
    assert "推送今日任务" in source


def test_calendar_panel_exposes_manual_plan_form() -> None:
    component_path = Path(__file__).parents[4] / "shadowlink-web" / "src" / "components" / "jarvis" / "CalendarPanel.tsx"
    source = component_path.read_text(encoding="utf-8")

    assert "新建长期计划" in source
    assert "编辑计划信息" in source
    assert "savePlanForm" in source
    assert "createPlan" in source
    assert "updatePlan" in source


def test_calendar_panel_exposes_manual_merge_split_controls() -> None:
    component_path = Path(__file__).parents[4] / "shadowlink-web" / "src" / "components" / "jarvis" / "CalendarPanel.tsx"
    source = component_path.read_text(encoding="utf-8")

    assert "合并到当前计划" in source
    assert "拆分选中计划日" in source
    assert "mergePlans" in source
    assert "splitPlan" in source


def test_calendar_panel_exposes_conflict_resolution_flow() -> None:
    component_path = Path(__file__).parents[4] / "shadowlink-web" / "src" / "components" / "jarvis" / "CalendarPanel.tsx"
    source = component_path.read_text(encoding="utf-8")

    assert "冲突处理" in source
    assert "冲突原因" in source
    assert "移动到空闲窗口" in source
    assert "忽略本次冲突" in source
    assert "resolveConflictWithFreeWindow" in source


def test_calendar_panel_exposes_plan_day_bulk_actions() -> None:
    component_path = Path(__file__).parents[4] / "shadowlink-web" / "src" / "components" / "jarvis" / "CalendarPanel.tsx"
    source = component_path.read_text(encoding="utf-8")

    assert "计划日批量操作" in source
    assert "批量延期" in source
    assert "批量完成" in source
    assert "批量取消" in source
    assert "bulkUpdatePlanDays" in source


def test_calendar_panel_exposes_background_task_archive_delete_controls() -> None:
    component_path = Path(__file__).parents[4] / "shadowlink-web" / "src" / "components" / "jarvis" / "CalendarPanel.tsx"
    source = component_path.read_text(encoding="utf-8")

    assert "归档历史任务" in source
    assert "删除历史任务" in source
    assert "updateBackgroundTask" in source


def test_calendar_panel_exposes_top_level_plan_delete_control() -> None:
    component_path = Path(__file__).parents[4] / "shadowlink-web" / "src" / "components" / "jarvis" / "CalendarPanel.tsx"
    api_path = Path(__file__).parents[4] / "shadowlink-web" / "src" / "services" / "jarvisApi.ts"
    component_source = component_path.read_text(encoding="utf-8")
    api_source = api_path.read_text(encoding="utf-8")

    assert "删除任务" in component_source
    assert "deletePlan" in component_source
    assert "async deletePlan" in api_source
    assert 'method: "DELETE"' in api_source


def test_calendar_panel_project_button_reflects_projection_state() -> None:
    component_path = Path(__file__).parents[4] / "shadowlink-web" / "src" / "components" / "jarvis" / "CalendarPanel.tsx"
    source = component_path.read_text(encoding="utf-8")

    assert "getPlanProjectionSummary" in source
    assert "selectedPlanProjection.isFullyProjected" in source
    assert "补写入日历" in source
    assert "已写入日历" in source


def test_frontend_formats_duplicate_calendar_event_errors() -> None:
    api_path = Path(__file__).parents[4] / "shadowlink-web" / "src" / "services" / "jarvisApi.ts"
    source = api_path.read_text(encoding="utf-8")

    assert "duplicate_calendar_event" in source
    assert "已存在同名日程" in source
    assert "为避免重复安排，本次没有写入" in source
    assert "delete event HTTP" in source and "errorFromResponse" in _method_block(source, "deleteCalendarEvent")
    assert "update event HTTP" in source and "errorFromResponse" in _method_block(source, "updateCalendarEvent")


def test_calendar_panel_no_longer_computes_plus_one_day_reschedules() -> None:
    component_path = Path(__file__).parents[4] / "shadowlink-web" / "src" / "components" / "jarvis" / "CalendarPanel.tsx"
    source = component_path.read_text(encoding="utf-8")

    assert "new Date(`${day.plan_date}T00:00:00`)" not in source
    assert "toDateInput(addDays(localDateFromKey(day.plan_date), 1))" not in source
    assert "shift_days: action === \"postpone\" ? 1" not in source
    assert "requestSecretaryReschedule" in source


def test_calendar_panel_separates_plan_day_detail_click_from_bulk_selection() -> None:
    component_path = Path(__file__).parents[4] / "shadowlink-web" / "src" / "components" / "jarvis" / "CalendarPanel.tsx"
    source = component_path.read_text(encoding="utf-8")

    assert "bulkPlanDaySelectMode" in source
    assert "openBulkPlanDaySelection" in source
    assert "closeBulkPlanDaySelection" in source
    assert "onClick={() => selectPlanDayForDetail(day)}" in source
    assert "setSelectedPlanDayIds((current) => current.includes(day.id)" in source
    assert "onChange={() => togglePlanDaySelection(day)}" in source
    assert "onClick={() => togglePlanDaySelection(day)}" not in source


def test_calendar_panel_uses_secretary_plan_api_for_reschedule_intent() -> None:
    component_path = Path(__file__).parents[4] / "shadowlink-web" / "src" / "components" / "jarvis" / "CalendarPanel.tsx"
    api_path = Path(__file__).parents[4] / "shadowlink-web" / "src" / "services" / "jarvisApi.ts"
    component_source = component_path.read_text(encoding="utf-8")
    api_source = api_path.read_text(encoding="utf-8")

    assert "async createSecretaryPlan" in api_source
    assert "/planner/secretary-plan" in api_source
    assert "requestSecretaryReschedule" in component_source
    assert "让秘书重排" in component_source
    assert "延期到明天" not in component_source
    assert "整体顺延一天" not in component_source
