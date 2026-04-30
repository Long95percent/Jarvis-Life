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


SCHEDULE_COORD_PARTICIPANTS = ["maxwell", "nora", "mira", "alfred"]
GRAPH_EXECUTOR_ID = "schedule_coord_langgraph_v1"


class ScheduleCoordState(TypedDict, total=False):
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


class ScheduleCoordGraphExecutor:
    """LangGraph-backed meeting protocol for the schedule coordination preset."""

    def __init__(self, llm_client: Any) -> None:
        self.llm_client = llm_client
        self.graph = self._build_graph()

    def _build_graph(self) -> Any:
        graph = StateGraph(ScheduleCoordState)
        graph.add_node("prepare_round", self._prepare_round_node)
        graph.add_node("maxwell", self._pass_node)
        graph.add_node("nora", self._pass_node)
        graph.add_node("mira", self._pass_node)
        graph.add_node("alfred", self._pass_node)
        graph.add_node("summarize", self._summarize_node)
        graph.add_node("checkpoint", self._checkpoint_node)
        graph.add_edge(START, "prepare_round")
        graph.add_edge("prepare_round", "maxwell")
        graph.add_edge("maxwell", "nora")
        graph.add_edge("nora", "mira")
        graph.add_edge("mira", "alfred")
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
            scenario_id="schedule_coord",
            user_goal=user_goal,
            participants=list(participants or SCHEDULE_COORD_PARTICIPANTS),
            round_index=round_index,
            context=context,
            user_feedback_history=feedback_history or [],
        )

        state_data: ScheduleCoordState = await self.graph.ainvoke(self._to_graph_state(state))
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
        yield round_event("done", {"phase": "round_complete", "session_id": session_id, "scenario_id": "schedule_coord"})

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
            "maxwell": "评估今日时间窗口、任务冲突、缓冲和执行顺序。请指出最该保护的时间块。",
            "nora": "评估饮食、补水、咖啡因和身体能量对日程安排的影响。",
            "mira": "评估压力、恢复边界、过载风险和情绪负担。",
            "alfred": "综合各方，指出共识、分歧和需要用户判断的问题。",
        }
        return (
            "## 今日日程协调圆桌\n"
            f"用户诉求: {state.user_goal}\n\n"
            f"结构化上下文: {json.dumps(state.context, ensure_ascii=False, default=str)[:4000]}\n\n"
            f"用户上一轮反馈:\n{feedback}\n\n"
            f"前面角色公开发言:\n{previous}\n\n"
            f"你的职责: {role_tasks.get(agent_id, '从你的角色视角给出建议。')}\n"
            "请输出面向用户公开展示的会议发言，3-5 句。"
            "只展示结论、依据和取舍，不要展示隐藏思维链，不要直接修改日程。"
        )

    async def _summarize_round(self, state: RoundtableGraphState) -> RoundtableRoundSummary:
        prompt = (
            "请把今日日程协调圆桌本轮讨论整理成严格 JSON。"
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
            "请基于今日日程协调圆桌，输出严格 JSON，字段为 summary, recommended_option, options, tradeoffs, actions。"
            "actions 必须是待确认动作，不要表示已经修改日程。\n\n"
            f"用户诉求: {user_goal}\n"
            f"用户反馈: {json.dumps(feedback_history, ensure_ascii=False)}\n"
            f"上下文: {json.dumps(context, ensure_ascii=False, default=str)[:4000]}"
        )
        raw = await self.llm_client.chat(message=prompt, system_prompt=get_agent("alfred")["system_prompt"], temperature=0.2)
        data = self._load_json_object(raw)
        summary = str(data.get("summary") or "圆桌建议先保护今天最关键的时间块，再安排必要缓冲；接受后只生成待确认动作，不会直接改动日程。")
        recommended = str(data.get("recommended_option") or "保护关键任务 + 安排恢复缓冲")
        options = data.get("options") if isinstance(data.get("options"), list) else [
            {"id": "protect_focus", "title": "保护关键任务", "description": "先完成今天最重要的一件事。"},
            {"id": "rebalance_day", "title": "重排日程", "description": "把低优先级事项移动到更合适的时间。"},
        ]
        tradeoffs = data.get("tradeoffs") if isinstance(data.get("tradeoffs"), list) else [
            {"option": recommended, "pros": ["降低过载风险"], "cons": ["部分事项需要延后"]},
        ]
        actions = data.get("actions") if isinstance(data.get("actions"), list) else [
            {"title": "由 Maxwell 生成待确认日程调整卡", "owner": "maxwell", "requires_confirmation": True},
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
                "scenario_id": "schedule_coord",
                "graph_executor": GRAPH_EXECUTOR_ID,
                "user_feedback_history": feedback_history,
                "round_summaries": [summary_item.to_dict() for summary_item in round_summaries],
            },
        }

    async def _prepare_round_node(self, state: ScheduleCoordState) -> ScheduleCoordState:
        return {
            **state,
            "scenario_id": "schedule_coord",
            "participants": list(state.get("participants") or SCHEDULE_COORD_PARTICIPANTS),
            "status": "running",
        }

    async def _pass_node(self, state: ScheduleCoordState) -> ScheduleCoordState:
        return state

    async def _summarize_node(self, state: ScheduleCoordState) -> ScheduleCoordState:
        return state

    async def _checkpoint_node(self, state: ScheduleCoordState) -> ScheduleCoordState:
        return {**state, "status": "waiting_for_user"}

    def _to_graph_state(self, state: RoundtableGraphState) -> ScheduleCoordState:
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

    def _from_graph_state(self, state: ScheduleCoordState, *, fallback: RoundtableGraphState) -> RoundtableGraphState:
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
