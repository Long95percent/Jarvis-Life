import json

import pytest

from app.api.v1 import jarvis_router
from app.jarvis.work_brainstorm_graph import WorkBrainstormGraphExecutor


class FakeWorkBrainstormLLM:
    def __init__(self):
        self.messages: list[str] = []

    async def chat_stream(self, message: str, *, system_prompt: str | None = None, temperature: float | None = None, **kwargs):
        if "Moderator" in (system_prompt or ""):
            chunks = ["先把问题拆成体验、技术和叙事三条线，", "再让团队分别发散。"]
        elif "Creative Explorer" in (system_prompt or ""):
            chunks = ["1. 做一条完整演示主线，", "2. 加一个反直觉亮点。"]
        elif "Critical Analyst" in (system_prompt or ""):
            chunks = ["最大风险是范围太散，", "需要先定义最小可验证 demo。"]
        else:
            chunks = ["可以把强想法合并成一条方案，", "再留两个实验方向。"]
        for chunk in chunks:
            yield chunk

    async def chat(self, message: str, *, system_prompt: str | None = None, temperature: float | None = None, **kwargs):
        self.messages.append(message)
        if "minutes, consensus" in message:
            return json.dumps(
                {
                    "minutes": [
                        {"agent_id": "moderator", "summary": "拆出体验、技术、叙事三条线"},
                        {"agent_id": "critic", "summary": "提醒范围不能太散"},
                    ],
                    "consensus": ["先做最小可验证 demo", "保留一条完整主线"],
                    "disagreements": ["亮点数量和实现范围需要取舍"],
                    "questions_for_user": ["你更想突出产品体验还是技术能力？"],
                    "next_round_focus": ["围绕用户选择继续发散或收敛"],
                },
                ensure_ascii=False,
            )
        return json.dumps(
            {
                "summary": "建议把 brainstorm 收敛成一条可演示主线，并保留两个后续实验方向。",
                "themes": [{"title": "最小可验证 demo", "summary": "先证明核心体验成立"}],
                "ideas": [
                    {"id": "demo_storyline", "title": "从用户痛点到自动计划的演示主线", "source_agent": "explorer"},
                    {"id": "risk_guardrail", "title": "限制范围并定义验收指标", "source_agent": "critic"},
                ],
                "tensions": [{"title": "创意亮点 vs 可交付范围", "description": "亮点要服务演示，不扩大不可控范围"}],
                "followup_questions": ["先演示哪条主线？"],
            },
            ensure_ascii=False,
        )


@pytest.mark.asyncio
async def test_work_brainstorm_graph_streams_roles_then_checkpoint():
    executor = WorkBrainstormGraphExecutor(llm_client=FakeWorkBrainstormLLM())
    events = []

    async for event in executor.start_round(
        session_id="rt-work-1",
        user_goal="帮我头脑风暴一个 Jarvis demo",
        context={"previous_discussion": ""},
    ):
        events.append(event)

    names = [event["event"] for event in events]
    completed_payloads = [json.loads(event["data"]) for event in events if event["event"] == "role_completed"]

    assert names[0] == "round_started"
    assert names.count("role_started") == 4
    assert names.count("role_delta") >= 8
    assert [payload["agent_id"] for payload in completed_payloads] == ["moderator", "explorer", "critic", "synthesizer"]
    assert names[-2:] == ["round_summary", "user_checkpoint"]


@pytest.mark.asyncio
async def test_work_brainstorm_c_state_emits_workshop_artifacts():
    executor = WorkBrainstormGraphExecutor(llm_client=FakeWorkBrainstormLLM())
    events = []

    async for event in executor.start_round(
        session_id="rt-work-c",
        user_goal="帮我头脑风暴一个 Jarvis demo",
        context={"previous_discussion": ""},
    ):
        events.append(event)

    names = [event["event"] for event in events]
    stage_payloads = [json.loads(event["data"]) for event in events if event["event"] == "scenario_stage"]
    state_payload = json.loads(next(event["data"] for event in events if event["event"] == "scenario_state"))

    assert names.count("scenario_stage") == 7
    assert [payload["stage_id"] for payload in stage_payloads] == [
        "frame_problem",
        "ingest_context",
        "divergent_ideas",
        "cluster_ideas",
        "critic_review",
        "synthesis",
        "validation_plan",
    ]
    assert state_payload["state_type"] == "work_brainstorm_c"
    assert state_payload["graph_executor"] == "work_brainstorm_c_v1"
    assert "problem_frame" in state_payload["artifacts"]
    assert "idea_pool" in state_payload["artifacts"]
    assert "critique_matrix" in state_payload["artifacts"]
    assert "validation_plan" in state_payload["artifacts"]


@pytest.mark.asyncio
async def test_work_brainstorm_prompt_uses_workshop_protocol_phases():
    llm = FakeWorkBrainstormLLM()
    executor = WorkBrainstormGraphExecutor(llm_client=llm)

    async for _event in executor.start_round(
        session_id="rt-work-protocol",
        user_goal="帮我头脑风暴一个 Jarvis demo",
        context={"previous_discussion": ""},
    ):
        pass

    assert any("frame_problem" in message for message in llm.messages)
    assert any("critic_review" in message for message in llm.messages)
    assert any("validation_plan" in message for message in llm.messages)


@pytest.mark.asyncio
async def test_work_brainstorm_finalize_emits_brainstorm_result_and_done():
    executor = WorkBrainstormGraphExecutor(llm_client=FakeWorkBrainstormLLM())
    events = []

    async for event in executor.finalize(
        session_id="rt-work-1",
        user_goal="帮我头脑风暴一个 Jarvis demo",
        context={},
        feedback_history=["先突出产品体验"],
    ):
        events.append(event)

    names = [event["event"] for event in events]
    result = json.loads(next(event["data"] for event in events if event["event"] == "brainstorm_result"))

    assert names == ["final_result", "brainstorm_result", "done"]
    assert result["mode"] == "brainstorm"
    assert result["handoff_target"] == "maxwell"
    assert result["context"]["graph_executor"] == "work_brainstorm_c_v1"
    assert result["context"]["c_artifacts"]["state_type"] == "work_brainstorm_c"
    assert "minimum_validation_steps" in result["context"]


def test_graph_round_dispatch_includes_work_brainstorm():
    assert jarvis_router._graph_roundtable_scenario_id("work_brainstorm") == "work_brainstorm"
