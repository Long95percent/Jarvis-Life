import json

import pytest

from app.api.v1 import jarvis_router
from app.jarvis.local_lifestyle_graph import LocalLifestyleGraphExecutor


class FakeLocalLifestyleLLM:
    async def chat_stream(self, message: str, *, system_prompt: str | None = None, temperature: float | None = None, **kwargs):
        if "Leo" in (system_prompt or ""):
            chunks = ["附近可以选一个轻户外活动，", "优先步行可达和低负担。"]
        elif "Maxwell" in (system_prompt or ""):
            chunks = ["时间上适合放在傍晚空档，", "往返和缓冲要控制在九十分钟内。"]
        elif "Nora" in (system_prompt or ""):
            chunks = ["体力匹配上要避开太晚进食，", "最好带水并安排轻食。"]
        else:
            chunks = ["推荐选低刺激活动，", "再由 Maxwell 变成待确认安排。"]
        for chunk in chunks:
            yield chunk

    async def chat(self, message: str, *, system_prompt: str | None = None, temperature: float | None = None, **kwargs):
        if "minutes, consensus" in message:
            return json.dumps(
                {
                    "minutes": [
                        {"agent_id": "leo", "summary": "推荐轻户外或低刺激本地活动"},
                        {"agent_id": "maxwell", "summary": "傍晚空档最可行"},
                    ],
                    "consensus": ["选择近距离低负担活动", "保留往返缓冲"],
                    "disagreements": ["活动趣味性和恢复强度需要平衡"],
                    "questions_for_user": ["你更想安静恢复还是稍微社交？"],
                    "next_round_focus": ["按用户偏好收窄活动类型"],
                },
                ensure_ascii=False,
            )
        return json.dumps(
            {
                "summary": "建议选择一个近距离、低刺激、可在傍晚完成的本地活动。",
                "themes": [{"title": "低负担本地活动", "summary": "近距离、时间短、恢复友好"}],
                "ideas": [
                    {"id": "quiet_walk", "title": "附近安静散步", "source_agent": "leo"},
                    {"id": "light_cafe", "title": "低刺激咖啡馆休息", "source_agent": "nora"},
                ],
                "tensions": [{"title": "恢复 vs 新鲜感", "description": "活动不能为了新鲜感压缩恢复边界"}],
                "followup_questions": ["你更想户外、展览还是安静咖啡馆？"],
            },
            ensure_ascii=False,
        )


@pytest.mark.asyncio
async def test_local_lifestyle_graph_streams_roles_then_checkpoint():
    executor = LocalLifestyleGraphExecutor(llm_client=FakeLocalLifestyleLLM())
    events = []

    async for event in executor.start_round(
        session_id="rt-local-1",
        user_goal="今天附近有什么轻松活动",
        context={"local_life_context": "附近近期活动缓存"},
    ):
        events.append(event)

    names = [event["event"] for event in events]
    completed_payloads = [json.loads(event["data"]) for event in events if event["event"] == "role_completed"]

    assert names[0] == "round_started"
    assert names.count("role_started") == 4
    assert names.count("role_delta") >= 8
    assert [payload["agent_id"] for payload in completed_payloads] == ["leo", "maxwell", "nora", "alfred"]
    assert names[-2:] == ["round_summary", "user_checkpoint"]


@pytest.mark.asyncio
async def test_local_lifestyle_c_state_emits_activity_artifacts():
    executor = LocalLifestyleGraphExecutor(llm_client=FakeLocalLifestyleLLM())
    events = []

    async for event in executor.start_round(
        session_id="rt-local-c",
        user_goal="今天附近有什么轻松活动",
        context={"local_life_context": "附近近期活动缓存"},
    ):
        events.append(event)

    names = [event["event"] for event in events]
    stage_payloads = [json.loads(event["data"]) for event in events if event["event"] == "scenario_stage"]
    state_payload = json.loads(next(event["data"] for event in events if event["event"] == "scenario_state"))

    assert names.count("scenario_stage") == 7
    assert [payload["stage_id"] for payload in stage_payloads] == [
        "collect_constraints",
        "discover_candidates",
        "enrich_candidates",
        "feasibility_score",
        "energy_filter",
        "rank_options",
        "plan_candidate",
    ]
    assert state_payload["state_type"] == "local_lifestyle_c"
    assert state_payload["graph_executor"] == "local_lifestyle_c_v1"
    assert "user_constraints" in state_payload["artifacts"]
    assert "candidate_pool" in state_payload["artifacts"]
    assert "scorecards" in state_payload["artifacts"]
    assert "ranked_activities" in state_payload["artifacts"]


@pytest.mark.asyncio
async def test_local_lifestyle_finalize_emits_brainstorm_result_and_done():
    executor = LocalLifestyleGraphExecutor(llm_client=FakeLocalLifestyleLLM())
    events = []

    async for event in executor.finalize(
        session_id="rt-local-1",
        user_goal="今天附近有什么轻松活动",
        context={"local_life_context": "附近近期活动缓存"},
        feedback_history=["我想要低刺激一点"],
    ):
        events.append(event)

    names = [event["event"] for event in events]
    result = json.loads(next(event["data"] for event in events if event["event"] == "brainstorm_result"))

    assert names == ["final_result", "brainstorm_result", "done"]
    assert result["mode"] == "brainstorm"
    assert result["handoff_target"] == "maxwell"
    assert result["context"]["graph_executor"] == "local_lifestyle_c_v1"
    assert result["context"]["c_artifacts"]["state_type"] == "local_lifestyle_c"
    assert "ranked_activities" in result["context"]


def test_graph_round_dispatch_includes_local_lifestyle():
    assert jarvis_router._graph_roundtable_scenario_id("schedule_coord") == "schedule_coord"
    assert jarvis_router._graph_roundtable_scenario_id("local_lifestyle") == "local_lifestyle"
    assert jarvis_router._graph_roundtable_scenario_id("unknown_scenario") is None
