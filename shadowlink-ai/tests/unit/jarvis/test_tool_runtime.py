from app.core.dependencies import get_resource, set_resource
from datetime import datetime

from app.jarvis.tool_runtime import execute_tool_calls, run_agent_turn, strip_tool_like_blocks
from app.mcp.adapters import calendar_adapter
from app.models.mcp import ToolCategory, ToolInfo


def test_strip_tool_like_blocks_accepts_model_tool_calls_xml():
    text = '''好的，我先检查日程。

<tool_calls>
<tool_call name="jarvis_calendar_upcoming">{"start":"2026-05-02T14:00:00+08:00","end":"2026-05-02T16:00:00+08:00"}</tool_call>
</tool_calls>'''

    clean, calls = strip_tool_like_blocks(text)

    assert "<tool_calls>" not in clean
    assert clean == "好的，我先检查日程。"
    assert calls == [{
        "tool_name": "jarvis_calendar_upcoming",
        "arguments": {"start": "2026-05-02T14:00:00+08:00", "end": "2026-05-02T16:00:00+08:00"},
    }]


def test_strip_tool_like_blocks_accepts_invoke_xml():
    text = '''好的，我先安排更新。
<invoke name="jarvis_schedule_editor">
  <parameter name="operation">update</parameter>
  <parameter name="scope">all</parameter>
  <parameter name="keyword">reading</parameter>
  <parameter name="shift_minutes">60</parameter>
</invoke>'''

    clean, calls = strip_tool_like_blocks(text)

    assert "<invoke" not in clean
    assert clean == "好的，我先安排更新。"
    assert calls == [{
        "tool_name": "jarvis_schedule_editor",
        "arguments": {
            "operation": "update",
            "scope": "all",
            "keyword": "reading",
            "shift_minutes": "60",
        },
    }]


def test_run_agent_turn_executes_model_tool_calls_xml(monkeypatch):
    import asyncio

    class FakeLLM:
        def __init__(self):
            self.calls = []

        async def chat(self, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                return '''好的，我先检查明天下午的日程情况。
<tool_calls>
<tool_call name="jarvis_calendar_upcoming">{"start":"2026-05-02T14:00:00+08:00","end":"2026-05-02T16:00:00+08:00"}</tool_call>
</tool_calls>'''
            assert "## 工具结果" in kwargs["message"]
            return "明天下午 3 点没有冲突，我会继续为你安排提醒。"

    class FakeTool:
        requires_confirmation = False

        async def safe_aexecute(self, **kwargs):
            assert kwargs["start"] == "2026-05-02T14:00:00+08:00"
            return [{"title": "已有空档", "start": kwargs["start"], "end": kwargs["end"]}]

    class FakeRegistry:
        def get_tool(self, tool_name):
            if tool_name != "jarvis_calendar_upcoming":
                return None
            return (
                ToolInfo(name=tool_name, description="List calendar events", category=ToolCategory.SYSTEM),
                FakeTool(),
            )

    async def scenario():
        previous_registry = get_resource("tool_registry")
        set_resource("tool_registry", FakeRegistry())
        try:
            return await run_agent_turn(
                agent_id="maxwell",
                llm_client=FakeLLM(),
                message="明天下午三点提醒我和产品同学开一个路演复盘会，提前半小时准备材料。",
                system_prompt="You are Maxwell.",
            )
        finally:
            set_resource("tool_registry", previous_registry)

    reply, tool_results = asyncio.run(scenario())
    assert "明天下午 3 点没有冲突" in reply
    assert len(tool_results) == 1
    assert tool_results[0]["success"] is True


def test_calendar_add_confirmation_guard_handles_aware_existing_events(monkeypatch):
    import asyncio

    class FakeCalendarAddTool:
        requires_confirmation = True

    class FakeRegistry:
        def get_tool(self, tool_name):
            if tool_name != "jarvis_calendar_add":
                return None
            return (
                ToolInfo(name=tool_name, description="Add calendar event", category=ToolCategory.SYSTEM),
                FakeCalendarAddTool(),
            )

    async def scenario():
        previous_registry = get_resource("tool_registry")
        calendar_adapter._events.clear()
        calendar_adapter.add_event(
            "已有无锡行程",
            datetime.fromisoformat("2026-05-04T13:00:00+08:00"),
            datetime.fromisoformat("2026-05-04T14:00:00+08:00"),
        )
        set_resource("tool_registry", FakeRegistry())
        try:
            return await execute_tool_calls("maxwell", [{
                "tool_name": "jarvis_calendar_add",
                "arguments": {
                    "title": "鼋头渚（太湖+仙岛）",
                    "start": "2026-05-04T14:00:00+08:00",
                    "end": "2026-05-04T16:30:00+08:00",
                },
            }])
        finally:
            calendar_adapter._events.clear()
            set_resource("tool_registry", previous_registry)

    results = asyncio.run(scenario())

    assert results[0]["success"] is True
    assert results[0]["requires_confirmation"] is True
    assert "schedule_guard" in results[0]["arguments"]
