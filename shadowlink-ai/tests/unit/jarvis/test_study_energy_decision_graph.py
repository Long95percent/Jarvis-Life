import json

import pytest

from app.api.v1 import jarvis_router
from app.jarvis.study_energy_decision_graph import StudyEnergyDecisionGraphExecutor


class FakeStudyEnergyLLM:
    async def chat_stream(self, message: str, *, system_prompt: str | None = None, temperature: float | None = None, **kwargs):
        if "Mira" in (system_prompt or ""):
            chunks = ["现在先看疲惫是不是过载，", "不要用自责推动学习。"]
        elif "Maxwell" in (system_prompt or ""):
            chunks = ["任务可以压到一个最小学习块，", "剩下交给明天或待确认调整。"]
        elif "Athena" in (system_prompt or ""):
            chunks = ["如果保留学习，", "只做收益最高的复习动作。"]
        else:
            chunks = ["建议降强度，", "保留一点连续性但保护恢复。"]
        for chunk in chunks:
            yield chunk

    async def chat(self, message: str, *, system_prompt: str | None = None, temperature: float | None = None, **kwargs):
        if "minutes, consensus" in message:
            return json.dumps(
                {
                    "minutes": [
                        {"agent_id": "mira", "summary": "疲惫下先保护恢复边界"},
                        {"agent_id": "maxwell", "summary": "学习任务压缩为最小块"},
                    ],
                    "consensus": ["降低学习强度", "只保留最小可完成动作"],
                    "disagreements": ["今晚完全休息还是保留 20 分钟连续性"],
                    "questions_for_user": ["你今晚还剩多少真实精力？"],
                    "next_round_focus": ["按精力回答决定学习块长度"],
                },
                ensure_ascii=False,
            )
        return json.dumps(
            {
                "summary": "建议今晚只做 20 分钟低强度复习，然后进入恢复；接受后只生成待确认调整。",
                "recommended_option": "20 分钟低强度学习 + 立即恢复",
                "options": [
                    {"id": "light_study", "title": "低强度学习", "description": "保留连续性但降低负荷"},
                    {"id": "recover_first", "title": "先恢复", "description": "不再追加学习压力"},
                ],
                "tradeoffs": [
                    {"option": "低强度学习", "pros": ["保留连续性"], "cons": ["仍会消耗一点精力"]},
                ],
                "actions": [
                    {"title": "由 Maxwell 生成待确认学习与恢复安排", "owner": "maxwell", "requires_confirmation": True},
                ],
            },
            ensure_ascii=False,
        )


@pytest.mark.asyncio
async def test_study_energy_graph_streams_roles_then_checkpoint():
    executor = StudyEnergyDecisionGraphExecutor(llm_client=FakeStudyEnergyLLM())
    events = []

    async for event in executor.start_round(
        session_id="rt-study-1",
        user_goal="我很累但今晚还要学习",
        context={"psychological_snapshot": {"stress_score": 7, "energy_score": 3}, "today_tasks": []},
    ):
        events.append(event)

    names = [event["event"] for event in events]
    completed_payloads = [json.loads(event["data"]) for event in events if event["event"] == "role_completed"]

    assert names[0] == "round_started"
    assert names.count("role_started") == 4
    assert names.count("role_delta") >= 8
    assert [payload["agent_id"] for payload in completed_payloads] == ["mira", "maxwell", "athena", "alfred"]
    assert names[-2:] == ["round_summary", "user_checkpoint"]


@pytest.mark.asyncio
async def test_study_energy_finalize_emits_decision_result_and_done():
    executor = StudyEnergyDecisionGraphExecutor(llm_client=FakeStudyEnergyLLM())
    events = []

    async for event in executor.finalize(
        session_id="rt-study-1",
        user_goal="我很累但今晚还要学习",
        context={"date": "2026-04-30"},
        feedback_history=["我还有一点精力，但不想崩掉"],
    ):
        events.append(event)

    names = [event["event"] for event in events]
    result = json.loads(next(event["data"] for event in events if event["event"] == "decision_result"))

    assert names == ["final_result", "decision_result", "done"]
    assert result["mode"] == "decision"
    assert result["handoff_target"] == "maxwell"
    assert result["context"]["graph_executor"] == "study_energy_decision_langgraph_v1"


def test_graph_round_dispatch_includes_study_energy_decision():
    assert jarvis_router._graph_roundtable_scenario_id("study_energy_decision") == "study_energy_decision"
