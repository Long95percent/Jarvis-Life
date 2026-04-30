import json

import pytest

from app.api.v1 import jarvis_router
from app.jarvis.emotional_care_graph import EmotionalCareGraphExecutor


class FakeEmotionalCareLLM:
    async def chat_stream(self, message: str, *, system_prompt: str | None = None, temperature: float | None = None, **kwargs):
        if "Mira" in (system_prompt or ""):
            chunks = ["先把情绪温度降下来，", "只做一个很小的恢复动作。"]
        elif "Nora" in (system_prompt or ""):
            chunks = ["身体支持要温和一点，", "先补水和简单进食。"]
        elif "Leo" in (system_prompt or ""):
            chunks = ["活动不要刺激过强，", "可以选安静散步或短暂停留。"]
        else:
            chunks = ["今晚重点是减负，", "不是逼自己立刻高效。"]
        for chunk in chunks:
            yield chunk

    async def chat(self, message: str, *, system_prompt: str | None = None, temperature: float | None = None, **kwargs):
        if "minutes, consensus" in message:
            return json.dumps(
                {
                    "minutes": [
                        {"agent_id": "mira", "summary": "先降情绪强度"},
                        {"agent_id": "nora", "summary": "用补水和轻食托住身体"},
                    ],
                    "consensus": ["降低刺激", "先做小恢复动作"],
                    "disagreements": ["是否需要外出取决于用户当前能量"],
                    "questions_for_user": ["你现在更想安静独处还是轻微走动？"],
                    "next_round_focus": ["按用户状态细化恢复清单"],
                },
                ensure_ascii=False,
            )
        return json.dumps(
            {
                "summary": "建议先做一个低刺激恢复清单：补水、放慢呼吸、减少输入，再决定是否短暂走动。",
                "themes": [{"title": "低刺激恢复", "summary": "先降低情绪负荷，再恢复一点身体稳定感"}],
                "ideas": [
                    {"id": "breathing_reset", "title": "三分钟呼吸复位", "source_agent": "mira"},
                    {"id": "warm_water_snack", "title": "补水和轻食", "source_agent": "nora"},
                ],
                "tensions": [{"title": "安静独处 vs 轻微走动", "description": "两者都可以恢复，但取决于用户当下能量"}],
                "followup_questions": ["现在压力更像焦躁、疲惫，还是空掉？"],
            },
            ensure_ascii=False,
        )


@pytest.mark.asyncio
async def test_emotional_care_graph_streams_roles_then_checkpoint():
    executor = EmotionalCareGraphExecutor(llm_client=FakeEmotionalCareLLM())
    events = []

    async for event in executor.start_round(
        session_id="rt-care-1",
        user_goal="我现在压力很大，想缓一下",
        context={"psychological_snapshot": {"stress_score": 8, "energy_score": 3}},
    ):
        events.append(event)

    names = [event["event"] for event in events]
    completed_payloads = [json.loads(event["data"]) for event in events if event["event"] == "role_completed"]

    assert names[0] == "round_started"
    assert names.count("role_started") == 4
    assert names.count("role_delta") >= 8
    assert [payload["agent_id"] for payload in completed_payloads] == ["mira", "nora", "leo", "alfred"]
    assert names[-2:] == ["round_summary", "user_checkpoint"]


@pytest.mark.asyncio
async def test_emotional_care_finalize_emits_brainstorm_result_and_done():
    executor = EmotionalCareGraphExecutor(llm_client=FakeEmotionalCareLLM())
    events = []

    async for event in executor.finalize(
        session_id="rt-care-1",
        user_goal="我现在压力很大，想缓一下",
        context={"psychological_snapshot": {"stress_score": 8, "energy_score": 3}},
        feedback_history=["我想安静一点"],
    ):
        events.append(event)

    names = [event["event"] for event in events]
    result = json.loads(next(event["data"] for event in events if event["event"] == "brainstorm_result"))

    assert names == ["final_result", "brainstorm_result", "done"]
    assert result["mode"] == "brainstorm"
    assert result["handoff_target"] == "mira"
    assert result["context"]["graph_executor"] == "emotional_care_langgraph_v1"


def test_graph_round_dispatch_includes_emotional_care():
    assert jarvis_router._graph_roundtable_scenario_id("emotional_care") == "emotional_care"
