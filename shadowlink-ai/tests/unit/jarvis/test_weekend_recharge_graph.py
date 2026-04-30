import json

import pytest

from app.api.v1 import jarvis_router
from app.jarvis.weekend_recharge_graph import WeekendRechargeGraphExecutor


class FakeWeekendRechargeLLM:
    async def chat_stream(self, message: str, *, system_prompt: str | None = None, temperature: float | None = None, **kwargs):
        if "Leo" in (system_prompt or ""):
            chunks = ["周末可以安排一个轻户外窗口，", "不要把两天都塞满。"]
        elif "Nora" in (system_prompt or ""):
            chunks = ["饮食节奏要稳，", "把补水和轻食放在活动前后。"]
        elif "Mira" in (system_prompt or ""):
            chunks = ["恢复需要留白，", "至少保留一个无安排时段。"]
        else:
            chunks = ["推荐做半天活动半天恢复，", "再留一段完全自由时间。"]
        for chunk in chunks:
            yield chunk

    async def chat(self, message: str, *, system_prompt: str | None = None, temperature: float | None = None, **kwargs):
        if "minutes, consensus" in message:
            return json.dumps(
                {
                    "minutes": [
                        {"agent_id": "leo", "summary": "安排轻户外但不塞满周末"},
                        {"agent_id": "nora", "summary": "活动前后要有饮食和补水节奏"},
                    ],
                    "consensus": ["保留恢复留白", "活动要低负担"],
                    "disagreements": ["周六外出还是周日外出需要用户偏好"],
                    "questions_for_user": ["你更想周六外出还是周日外出？"],
                    "next_round_focus": ["按周末空档排出恢复节奏"],
                },
                ensure_ascii=False,
            )
        return json.dumps(
            {
                "summary": "建议周末采用半天轻活动、半天恢复留白的节奏，避免把休息日变成任务表。",
                "themes": [{"title": "半天活动半天恢复", "summary": "兼顾生活感和真正恢复"}],
                "ideas": [
                    {"id": "light_outdoor_block", "title": "半天轻户外", "source_agent": "leo"},
                    {"id": "blank_recovery_block", "title": "无安排恢复窗口", "source_agent": "mira"},
                ],
                "tensions": [{"title": "想出去 vs 需要恢复", "description": "活动要服务恢复，而不是继续透支"}],
                "followup_questions": ["周末哪一天更适合外出？"],
            },
            ensure_ascii=False,
        )


@pytest.mark.asyncio
async def test_weekend_recharge_graph_streams_roles_then_checkpoint():
    executor = WeekendRechargeGraphExecutor(llm_client=FakeWeekendRechargeLLM())
    events = []

    async for event in executor.start_round(
        session_id="rt-weekend-1",
        user_goal="帮我规划一个能恢复精力的周末",
        context={"calendar_events": [], "local_life_context": "周末附近活动缓存"},
    ):
        events.append(event)

    names = [event["event"] for event in events]
    completed_payloads = [json.loads(event["data"]) for event in events if event["event"] == "role_completed"]

    assert names[0] == "round_started"
    assert names.count("role_started") == 4
    assert names.count("role_delta") >= 8
    assert [payload["agent_id"] for payload in completed_payloads] == ["leo", "nora", "mira", "alfred"]
    assert names[-2:] == ["round_summary", "user_checkpoint"]


@pytest.mark.asyncio
async def test_weekend_recharge_finalize_emits_brainstorm_result_and_done():
    executor = WeekendRechargeGraphExecutor(llm_client=FakeWeekendRechargeLLM())
    events = []

    async for event in executor.finalize(
        session_id="rt-weekend-1",
        user_goal="帮我规划一个能恢复精力的周末",
        context={"calendar_events": []},
        feedback_history=["我想周六轻松出门，周日安静一点"],
    ):
        events.append(event)

    names = [event["event"] for event in events]
    result = json.loads(next(event["data"] for event in events if event["event"] == "brainstorm_result"))

    assert names == ["final_result", "brainstorm_result", "done"]
    assert result["mode"] == "brainstorm"
    assert result["handoff_target"] == "maxwell"
    assert result["context"]["graph_executor"] == "weekend_recharge_langgraph_v1"


def test_graph_round_dispatch_includes_weekend_recharge():
    assert jarvis_router._graph_roundtable_scenario_id("weekend_recharge") == "weekend_recharge"
