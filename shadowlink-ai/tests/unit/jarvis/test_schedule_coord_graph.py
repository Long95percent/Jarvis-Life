import json

import pytest

from app.api.v1 import jarvis_router
from app.jarvis.roundtable_graph import RoundtableGraphState, round_event
from app.jarvis.schedule_coord_graph import ScheduleCoordGraphExecutor


class FakeStreamingLLM:
    def __init__(self):
        self.messages: list[str] = []

    async def chat_stream(self, message: str, *, system_prompt: str | None = None, temperature: float | None = None, **kwargs):
        if "Maxwell" in (system_prompt or ""):
            chunks = ["先保护上午深度工作，", "再处理会议准备。"]
        elif "Nora" in (system_prompt or ""):
            chunks = ["午餐和补水要提前安排，", "避免下午能量下滑。"]
        elif "Mira" in (system_prompt or ""):
            chunks = ["今天需要留恢复边界，", "不要把每个空档塞满。"]
        else:
            chunks = ["共识是保留关键任务，", "分歧是上午优先级还要你判断。"]
        for chunk in chunks:
            yield chunk

    async def chat(self, message: str, *, system_prompt: str | None = None, temperature: float | None = None, **kwargs):
        self.messages.append(message)
        if "严格 JSON" in message:
            return json.dumps(
                {
                    "minutes": [
                        {"agent_id": "maxwell", "summary": "上午适合保护深度工作"},
                        {"agent_id": "nora", "summary": "饮食和补水要前置"},
                    ],
                    "consensus": ["保留深度工作", "安排恢复缓冲"],
                    "disagreements": ["上午先工作还是先准备会议"],
                    "questions_for_user": ["上午最不能被打断的是哪件事？"],
                    "next_round_focus": ["按用户回答重排时间块"],
                },
                ensure_ascii=False,
            )
        return json.dumps(
            {
                "summary": "今天建议保护上午深度工作，午后安排会议准备和恢复缓冲。",
                "recommended_option": "保护上午深度工作 + 午后会议准备",
                "options": [
                    {"id": "protect_morning", "title": "保护上午", "description": "上午做最关键任务"},
                    {"id": "prep_first", "title": "先准备会议", "description": "先降低会议风险"},
                ],
                "tradeoffs": [
                    {"option": "保护上午", "pros": ["产出更稳"], "cons": ["会议准备更晚"]},
                ],
                "actions": [
                    {"title": "生成待确认日程调整", "owner": "maxwell", "requires_confirmation": True},
                ],
            },
            ensure_ascii=False,
        )


def test_round_event_serializes_payload_as_json_string():
    event = round_event("round_started", {"session_id": "rt-schedule-1", "round_index": 1})

    assert event["event"] == "round_started"
    assert '"round_index": 1' in event["data"]


def test_roundtable_graph_state_defaults_to_first_round():
    state = RoundtableGraphState(
        session_id="rt-schedule-1",
        scenario_id="schedule_coord",
        user_goal="帮我协调今天日程",
        participants=["maxwell", "nora", "mira", "alfred"],
    )

    assert state.round_index == 1
    assert state.status == "running"
    assert state.role_outputs == []
    assert state.user_feedback_history == []


@pytest.mark.asyncio
async def test_schedule_coord_graph_streams_roles_then_checkpoint():
    executor = ScheduleCoordGraphExecutor(llm_client=FakeStreamingLLM())
    events = []

    async for event in executor.start_round(
        session_id="rt-schedule-1",
        user_goal="帮我协调今天日程",
        context={"calendar_events": [], "today_tasks": []},
    ):
        events.append(event)

    names = [event["event"] for event in events]
    completed_payloads = [json.loads(event["data"]) for event in events if event["event"] == "role_completed"]

    assert names[0] == "round_started"
    assert names.count("role_started") == 4
    assert names.count("role_delta") >= 8
    assert names.count("role_completed") == 4
    assert [payload["agent_id"] for payload in completed_payloads] == ["maxwell", "nora", "mira", "alfred"]
    assert names[-2:] == ["round_summary", "user_checkpoint"]


@pytest.mark.asyncio
async def test_schedule_coord_graph_respects_filtered_participants():
    executor = ScheduleCoordGraphExecutor(llm_client=FakeStreamingLLM())
    events = []

    async for event in executor.start_round(
        session_id="rt-schedule-filtered",
        user_goal="帮我协调今天日程",
        context={"calendar_events": []},
        participants=["maxwell", "alfred"],
    ):
        events.append(event)

    completed_payloads = [json.loads(event["data"]) for event in events if event["event"] == "role_completed"]

    assert [payload["agent_id"] for payload in completed_payloads] == ["maxwell", "alfred"]


@pytest.mark.asyncio
async def test_schedule_coord_prompt_uses_protocol_phase_context():
    llm = FakeStreamingLLM()
    executor = ScheduleCoordGraphExecutor(llm_client=llm)

    async for _event in executor.start_round(
        session_id="rt-schedule-protocol",
        user_goal="帮我协调今天日程",
        context={"calendar_events": [], "today_tasks": []},
    ):
        pass

    assert any("context_scan" in message for message in llm.messages)
    assert any("conflict_check" in message for message in llm.messages)
    assert any("alfred_decision" in message for message in llm.messages)


@pytest.mark.asyncio
async def test_schedule_coord_continue_feedback_runs_next_round():
    executor = ScheduleCoordGraphExecutor(llm_client=FakeStreamingLLM())
    events = []

    async for event in executor.continue_round(
        session_id="rt-schedule-1",
        user_goal="帮我协调今天日程",
        context={"calendar_events": []},
        feedback_history=["我更想保护上午深度工作"],
        round_index=2,
    ):
        events.append(event)

    payload = json.loads(events[0]["data"])
    assert events[0]["event"] == "round_started"
    assert payload["round_index"] == 2
    assert events[-1]["event"] == "user_checkpoint"


@pytest.mark.asyncio
async def test_schedule_coord_finalize_emits_decision_result_and_done():
    executor = ScheduleCoordGraphExecutor(llm_client=FakeStreamingLLM())
    events = []

    async for event in executor.finalize(
        session_id="rt-schedule-1",
        user_goal="帮我协调今天日程",
        context={"date": "2026-04-30"},
        feedback_history=["直接收敛"],
    ):
        events.append(event)

    names = [event["event"] for event in events]
    result = json.loads(next(event["data"] for event in events if event["event"] == "decision_result"))

    assert names == ["final_result", "decision_result", "done"]
    assert result["mode"] == "decision"
    assert result["handoff_target"] == "maxwell"
    assert result["context"]["graph_executor"] == "schedule_coord_langgraph_v1"


def test_schedule_coord_finalize_intent_detection():
    assert jarvis_router._is_schedule_coord_finalize_request("直接收敛")
    assert jarvis_router._is_schedule_coord_finalize_request("/finalize")
    assert jarvis_router._is_schedule_coord_finalize_request("finalize")
    assert not jarvis_router._is_schedule_coord_finalize_request("我更想保护上午深度工作")


def test_graph_round_context_preserves_prior_agent_discussion():
    from app.jarvis.roundtable_sessions import create_session

    session = create_session(
        session_id="rt-context-preserve",
        scenario_id="schedule_coord",
        scenario_name="今日日程协调",
        participants=["maxwell", "alfred"],
    )
    session.add_turn("user", "You", "帮我协调今天")
    session.add_turn("maxwell", "Maxwell（秘书）", "上午需要保护深度工作。")
    session.add_turn("alfred", "Alfred（总管家）", "分歧是会议准备是否前置。")

    context = jarvis_router._build_graph_round_context(
        session=session,
        decision_context={"date": "2026-04-30"},
        context_prefix="生活状态",
        opening_prompt="场景引导",
        profile_prefix="profile",
        scenario_name="今日日程协调",
        scenario_icon="📅",
    )

    assert "previous_discussion" in context
    assert "上午需要保护深度工作" in context["previous_discussion"]
    assert "分歧是会议准备是否前置" in context["previous_discussion"]
