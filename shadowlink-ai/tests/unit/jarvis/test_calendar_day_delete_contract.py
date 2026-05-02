from pathlib import Path


def test_calendar_day_view_exposes_keyboard_and_context_delete() -> None:
    component_path = Path(__file__).parents[4] / "shadowlink-web" / "src" / "components" / "jarvis" / "CalendarPanel.tsx"
    source = component_path.read_text(encoding="utf-8")

    assert "handleDeleteKey" in source
    assert "handleContextDelete" in source
    assert "onKeyDown={(keyEvent) => handleDeleteKey" in source
    assert "onContextMenu={(mouseEvent) => handleContextDelete" in source
    assert "右键/Delete 删除" in source


def test_calendar_day_view_can_delete_all_day_item_types() -> None:
    component_path = Path(__file__).parents[4] / "shadowlink-web" / "src" / "components" / "jarvis" / "CalendarPanel.tsx"
    api_path = Path(__file__).parents[4] / "shadowlink-web" / "src" / "services" / "jarvisApi.ts"
    component_source = component_path.read_text(encoding="utf-8")
    api_source = api_path.read_text(encoding="utf-8")

    assert "removeEvent(event)" in component_source
    assert "removePlanDay(day)" in component_source
    assert "removeTaskDay(day)" in component_source
    assert "async deletePlanDay" in api_source
    assert "async deleteBackgroundTaskDay" in api_source
    assert "method: \"DELETE\"" in api_source


def test_calendar_month_view_exposes_clickable_delete_controls() -> None:
    component_path = Path(__file__).parents[4] / "shadowlink-web" / "src" / "components" / "jarvis" / "CalendarPanel.tsx"
    source = component_path.read_text(encoding="utf-8")

    assert "renderDeleteButton" in source
    assert "删除日程「${event.title}」" in source
    assert "删除计划日「${day.title}」" in source
    assert "删除任务日「${day.title}」" in source
    assert "renderEventButton(event, true)" in source
    assert "renderPlanDayButton(planDay, true)" in source
    assert "renderTaskDayButton(taskDay, true)" in source
