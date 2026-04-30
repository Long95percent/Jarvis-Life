from __future__ import annotations

import json
from typing import Any, AsyncIterator, TypedDict

from langgraph.graph import END, START, StateGraph

from app.jarvis.agents import get_agent
from app.jarvis.roundtable_graph import (
    RoundtableGraphState,
    RoundtableRoleOutput,
    RoundtableRoundSummary,
    round_event,
)


STUDY_ENERGY_PARTICIPANTS = ["mira", "maxwell", "athena", "alfred"]
GRAPH_EXECUTOR_ID = "study_energy_decision_langgraph_v1"


class StudyEnergyDecisionState(TypedDict, total=False):
    session_id: str
    scenario_id: str
    user_goal: str
    participants: list[str]
    round_index: int
    context: dict[str, Any]
    user_feedback_history: list[str]
    role_outputs: list[RoundtableRoleOutput]
    round_summaries: list[RoundtableRoundSummary]
    final_result: dict[str, Any] | None
    status: str


class StudyEnergyDecisionGraphExecutor:
    """LangGraph-backed meeting protocol for tired-study decisions."""

    def __init__(self, llm_client: Any) -> None:
        self.llm_client = llm_client
        self.graph = self._build_graph()

    def _build_graph(self) -> Any:
        graph = StateGraph(StudyEnergyDecisionState)
        graph.add_node("prepare_round", self._prepare_round_node)
        graph.add_node("mira", self._pass_node)
        graph.add_node("maxwell", self._pass_node)
        graph.add_node("athena", self._pass_node)
        graph.add_node("alfred", self._pass_node)
        graph.add_node("summarize", self._summarize_node)
        graph.add_node("checkpoint", self._checkpoint_node)
        graph.add_edge(START, "prepare_round")
        graph.add_edge("prepare_round", "mira")
        graph.add_edge("mira", "maxwell")
        graph.add_edge("maxwell", "athena")
        graph.add_edge("athena", "alfred")
        graph.add_edge("alfred", "summarize")
        graph.add_edge("summarize", "checkpoint")
        graph.add_edge("checkpoint", END)
        return graph.compile()

    async def start_round(
        self,
        *,
        session_id: str,
        user_goal: str,
        context: dict[str, Any],
        round_index: int = 1,
        feedback_history: list[str] | None = None,
        participants: list[str] | None = None,
    ) -> AsyncIterator[dict[str, str]]:
        state = RoundtableGraphState(
            session_id=session_id,
            scenario_id="study_energy_decision",
            user_goal=user_goal,
            participants=list(participants or STUDY_ENERGY_PARTICIPANTS),
            round_index=round_index,
            context=context,
            user_feedback_history=feedback_history or [],
        )
        state_data: StudyEnergyDecisionState = await self.graph.ainvoke(self._to_graph_state(state))
        state = self._from_graph_state(state_data, fallback=state)

        yield round_event(
            "round_started",
            {
                "session_id": state.session_id,
                "scenario_id": state.scenario_id,
                "round_index": state.round_index,
                "participants": state.participants,
            },
        )
        for agent_id in state.participants:
            async for event in self._run_role(state, agent_id):
                yield event

        summary = await self._summarize_round(state)
        state.round_summaries.append(summary)
        state.status = "waiting_for_user"
        yield round_event("round_summary", summary.to_dict())
        yield round_event(
            "user_checkpoint",
            {
                "round_index": state.round_index,
                "allowed_actions": ["continue", "comment", "finalize", "redirect"],
            },
        )

    async def continue_round(
        self,
        *,
        session_id: str,
        user_goal: str,
        context: dict[str, Any],
        feedback_history: list[str] | None = None,
        round_index: int = 1,
        participants: list[str] | None = None,
    ) -> AsyncIterator[dict[str, str]]:
        async for event in self.start_round(
            session_id=session_id,
            user_goal=user_goal,
            context=context,
            round_index=round_index,
            feedback_history=feedback_history,
            participants=participants,
        ):
            yield event

    async def finalize(
        self,
        *,
        session_id: str,
        user_goal: str,
        context: dict[str, Any],
        feedback_history: list[str] | None = None,
        round_summaries: list[RoundtableRoundSummary] | None = None,
    ) -> AsyncIterator[dict[str, str]]:
        result = await self._build_final_result(
            session_id=session_id,
            user_goal=user_goal,
            context=context,
            feedback_history=feedback_history or [],
            round_summaries=round_summaries or [],
        )
        yield round_event("final_result", result)
        yield round_event("decision_result", result)
        yield round_event("done", {"phase": "round_complete", "session_id": session_id, "scenario_id": "study_energy_decision"})

    async def _run_role(self, state: RoundtableGraphState, agent_id: str) -> AsyncIterator[dict[str, str]]:
        agent = get_agent(agent_id)
        content_parts: list[str] = []
        yield round_event(
            "role_started",
            {
                "agent_id": agent_id,
                "agent_name": agent["name"],
                "agent_role": agent["role"],
                "agent_icon": agent.get("icon"),
                "agent_color": agent.get("color"),
                "round_index": state.round_index,
            },
        )
        async for delta in self.llm_client.chat_stream(
            message=self._role_prompt(state, agent_id),
            system_prompt=agent["system_prompt"],
            temperature=0.35,
        ):
            content_parts.append(delta)
            yield round_event("role_delta", {"agent_id": agent_id, "delta": delta, "round_index": state.round_index})

        content = "".join(content_parts).strip()
        output = RoundtableRoleOutput(
            agent_id=agent_id,
            agent_name=agent["name"],
            role=agent["role"],
            content=content,
            round_index=state.round_index,
        )
        state.role_outputs.append(output)
        yield round_event(
            "role_completed",
            {
                "agent_id": output.agent_id,
                "agent_name": output.agent_name,
                "agent_role": output.role,
                "agent_icon": agent.get("icon"),
                "agent_color": agent.get("color"),
                "content": output.content,
                "round_index": output.round_index,
            },
        )

    def _role_prompt(self, state: RoundtableGraphState, agent_id: str) -> str:
        feedback = "\n".join(f"- {item}" for item in state.user_feedback_history) or "无"
        previous = "\n\n".join(f"{item.agent_name}: {item.content}" for item in state.role_outputs) or "无"
        role_tasks = {
            "mira": "评估疲惫、情绪压力和恢复边界；不要用自责驱动用户学习。",
            "maxwell": "评估任务剩余量、日程窗口和最小可执行学习块；不要直接改日程。",
            "athena": "评估学习收益、遗忘风险、复习优先级和今晚最低有效动作。",
            "alfred": "综合为可接受的决策：继续、降强度、先恢复或改到明天，并指出用户需要判断的问题。",
        }
        return (
            "## 疲惫学习决策圆桌\n"
            f"用户诉求: {state.user_goal}\n\n"
            f"结构化上下文: {json.dumps(state.context, ensure_ascii=False, default=str)[:5000]}\n\n"
            f"用户上一轮反馈:\n{feedback}\n\n"
            f"前面角色公开发言:\n{previous}\n\n"
            f"你的职责: {role_tasks.get(agent_id, '从你的角色视角给出建议。')}\n"
            "请输出面向用户公开展示的会议发言，3-5 句。"
            "只展示结论、依据和取舍，不要展示隐藏思维链，不要诊断，不要直接承诺修改日程。"
        )

    async def _summarize_round(self, state: RoundtableGraphState) -> RoundtableRoundSummary:
        prompt = (
            "请把疲惫学习决策圆桌本轮讨论整理成严格 JSON。"
            "字段必须为 minutes, consensus, disagreements, questions_for_user, next_round_focus。"
            "minutes 是对象数组，每项至少包含 agent_id 和 summary。不要输出 Markdown。\n\n"
            + "\n\n".join(f"{item.agent_id}: {item.content}" for item in state.role_outputs)
        )
        raw = await self.llm_client.chat(message=prompt, system_prompt=get_agent("alfred")["system_prompt"], temperature=0.2)
        data = self._load_json_object(raw)
        fallback_minutes = [item.to_minutes_item() for item in state.role_outputs]
        return RoundtableRoundSummary(
            round_index=state.round_index,
            minutes=data.get("minutes") if isinstance(data.get("minutes"), list) else fallback_minutes,
            consensus=data.get("consensus") if isinstance(data.get("consensus"), list) else [],
            disagreements=data.get("disagreements") if isinstance(data.get("disagreements"), list) else [],
            questions_for_user=data.get("questions_for_user") if isinstance(data.get("questions_for_user"), list) else [],
            next_round_focus=data.get("next_round_focus") if isinstance(data.get("next_round_focus"), list) else [],
        )

    async def _build_final_result(
        self,
        *,
        session_id: str,
        user_goal: str,
        context: dict[str, Any],
        feedback_history: list[str],
        round_summaries: list[RoundtableRoundSummary],
    ) -> dict[str, Any]:
        prompt = (
            "请基于疲惫学习决策圆桌，输出严格 JSON，字段为 summary, recommended_option, options, tradeoffs, actions。"
            "actions 必须是待确认动作，不要表示已经修改日程或已经完成学习。\n\n"
            f"用户诉求: {user_goal}\n"
            f"用户反馈: {json.dumps(feedback_history, ensure_ascii=False)}\n"
            f"上下文: {json.dumps(context, ensure_ascii=False, default=str)[:5000]}"
        )
        raw = await self.llm_client.chat(message=prompt, system_prompt=get_agent("alfred")["system_prompt"], temperature=0.2)
        data = self._load_json_object(raw)
        summary = str(data.get("summary") or "圆桌建议今晚降低学习强度，只保留一个最低有效学习块，然后进入恢复；接受后只生成待确认动作。")
        recommended = str(data.get("recommended_option") or "低强度学习 + 立即恢复")
        options = data.get("options") if isinstance(data.get("options"), list) else [
            {"id": "light_study", "title": "低强度学习", "description": "只做最低有效复习块，保留学习连续性。"},
            {"id": "recover_first", "title": "先恢复", "description": "今晚不再追加学习压力，明天再接续。"},
            {"id": "reschedule", "title": "改到明天", "description": "交给 Maxwell 生成待确认调整。"},
        ]
        tradeoffs = data.get("tradeoffs") if isinstance(data.get("tradeoffs"), list) else [
            {"option": recommended, "pros": ["保留连续性"], "cons": ["仍会消耗少量精力"]},
        ]
        actions = data.get("actions") if isinstance(data.get("actions"), list) else [
            {"title": "由 Maxwell 生成待确认学习与恢复安排", "owner": "maxwell", "requires_confirmation": True},
        ]
        return {
            "id": f"rt_result_{session_id}",
            "session_id": session_id,
            "mode": "decision",
            "status": "draft",
            "summary": summary,
            "options": options,
            "recommended_option": recommended,
            "tradeoffs": tradeoffs,
            "actions": actions,
            "handoff_target": "maxwell",
            "context": {
                **context,
                "user_input": user_goal,
                "scenario_id": "study_energy_decision",
                "graph_executor": GRAPH_EXECUTOR_ID,
                "user_feedback_history": feedback_history,
                "round_summaries": [summary_item.to_dict() for summary_item in round_summaries],
            },
        }

    async def _prepare_round_node(self, state: StudyEnergyDecisionState) -> StudyEnergyDecisionState:
        return {
            **state,
            "scenario_id": "study_energy_decision",
            "participants": list(state.get("participants") or STUDY_ENERGY_PARTICIPANTS),
            "status": "running",
        }

    async def _pass_node(self, state: StudyEnergyDecisionState) -> StudyEnergyDecisionState:
        return state

    async def _summarize_node(self, state: StudyEnergyDecisionState) -> StudyEnergyDecisionState:
        return state

    async def _checkpoint_node(self, state: StudyEnergyDecisionState) -> StudyEnergyDecisionState:
        return {**state, "status": "waiting_for_user"}

    def _to_graph_state(self, state: RoundtableGraphState) -> StudyEnergyDecisionState:
        return {
            "session_id": state.session_id,
            "scenario_id": state.scenario_id,
            "user_goal": state.user_goal,
            "participants": state.participants,
            "round_index": state.round_index,
            "context": state.context,
            "user_feedback_history": state.user_feedback_history,
            "role_outputs": state.role_outputs,
            "round_summaries": state.round_summaries,
            "final_result": state.final_result,
            "status": state.status,
        }

    def _from_graph_state(self, state: StudyEnergyDecisionState, *, fallback: RoundtableGraphState) -> RoundtableGraphState:
        fallback.scenario_id = str(state.get("scenario_id") or fallback.scenario_id)
        fallback.participants = list(state.get("participants") or fallback.participants)
        fallback.status = state.get("status") or fallback.status  # type: ignore[assignment]
        return fallback

    @staticmethod
    def _load_json_object(raw: str) -> dict[str, Any]:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}
