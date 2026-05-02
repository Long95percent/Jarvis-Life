from pathlib import Path


def test_agent_chat_panel_shows_named_progress_steps_while_waiting() -> None:
    component_path = Path(__file__).parents[4] / "shadowlink-web" / "src" / "components" / "jarvis" / "AgentChatPanel.tsx"
    source = component_path.read_text(encoding="utf-8")

    assert "CHAT_PROGRESS_STEPS" in source
    for label in [
        "正在理解你的请求…",
        "正在判断是否需要查看日程或调用工具…",
        "正在检查相关上下文和日程冲突…",
        "正在让秘书整理执行结果…",
        "正在生成最终回复…",
    ]:
        assert label in source
    assert "setInterval" in source
    assert "progressStep" in source
