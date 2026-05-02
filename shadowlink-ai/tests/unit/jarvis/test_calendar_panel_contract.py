from pathlib import Path


def test_calendar_panel_declares_hooks_before_open_guard() -> None:
    """CalendarPanel must not add hooks after `if (!open) return null`.

    React relies on hooks being called in the same order on every render.
    The calendar panel is initially rendered with `open=false`; declaring a
    hook after that early return crashes when the user clicks "打开日历".
    """

    component_path = Path(__file__).parents[4] / "shadowlink-web" / "src" / "components" / "jarvis" / "CalendarPanel.tsx"
    source = component_path.read_text(encoding="utf-8")

    open_guard_index = source.index("if (!open) return null;")
    after_open_guard = source[open_guard_index:]

    assert "useEffect(" not in after_open_guard
    assert "useMemo(" not in after_open_guard
    assert "useState(" not in after_open_guard
