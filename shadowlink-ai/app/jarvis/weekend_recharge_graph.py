from __future__ import annotations

import json
from typing import Any, AsyncIterator, TypedDict

from langgraph.graph import END, START, StateGraph

from app.jarvis.agents import get_agent
from app.jarvis.roundtable_graph import (
    RoundtableGraphState,
    RoundtableRoleOutput,
    RoundtableRoundSummary,
    roundtable_content_deltas,
    round_event,
    run_roundtable_agent_turn,
)
from app.jarvis.roundtable_protocols import (
    final_roundtable_phase,
    format_roundtable_protocol_block,
    get_roundtable_protocol,
    protocol_context,
)


WEEKEND_RECHARGE_PARTICIPANTS = ["leo", "nora", "mira", "alfred"]
GRAPH_EXECUTOR_ID = "weekend_recharge_langgraph_v1"


class WeekendRechargeState(TypedDict, total=False):
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


class WeekendRechargeGraphExecutor:
    """LangGraph-backed meeting protocol for weekend recovery planning."""

    def __init__(self, llm_client: Any) -> None:
        self.llm_client = llm_client
        self.graph = self._build_graph()

    def _build_graph(self) -> Any:
        graph = StateGraph(WeekendRechargeState)
        graph.add_node("prepare_round", self._prepare_round_node)
        graph.add_node("leo", self._pass_node)
        graph.add_node("nora", self._pass_node)
        graph.add_node("mira", self._pass_node)
        graph.add_node("alfred", self._pass_node)
        graph.add_node("summarize", self._summarize_node)
        graph.add_node("checkpoint", self._checkpoint_node)
        graph.add_edge(START, "prepare_round")
        graph.add_edge("prepare_round", "leo")
        graph.add_edge("leo", "nora")
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
            scenario_id="weekend_recharge",
            user_goal=user_goal,
            participants=list(participants or WEEKEND_RECHARGE_PARTICIPANTS),
            round_index=round_index,
            context=context,
            user_feedback_history=feedback_history or [],
        )
        state_data: WeekendRechargeState = await self.graph.ainvoke(self._to_graph_state(state))
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
        yield round_event("brainstorm_result", result)
        yield round_event("done", {"phase": "round_complete", "session_id": session_id, "scenario_id": "weekend_recharge"})

    async def _run_role(self, state: RoundtableGraphState, agent_id: str) -> AsyncIterator[dict[str, str]]:
        agent = get_agent(agent_id)
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
        turn_result = await run_roundtable_agent_turn(
            agent_id=agent_id,
            llm_client=self.llm_client,
            message=self._role_prompt(state, agent_id),
            system_prompt=agent["system_prompt"],
            temperature=0.4,
            session_id=state.session_id,
            enable_tools=True,
        )
        for delta in roundtable_content_deltas(turn_result.content):
            yield round_event("role_delta", {"agent_id": agent_id, "delta": delta, "round_index": state.round_index})

        output = RoundtableRoleOutput(
            agent_id=agent_id,
            agent_name=agent["name"],
            role=agent["role"],
            content=turn_result.content,
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
                "tool_results": turn_result.tool_results,
                "action_results": turn_result.action_results,
                "round_index": output.round_index,
            },
        )

    def _role_prompt(self, state: RoundtableGraphState, agent_id: str) -> str:
        protocol = get_roundtable_protocol("weekend_recharge")
        protocol_block = format_roundtable_protocol_block(
            protocol,
            turn_index=len(state.role_outputs),
            agent_id=agent_id,
        )
        feedback = "\n".join(f"- {item}" for item in state.user_feedback_history) or "无"
        previous = "\n\n".join(f"{item.agent_name}: {item.content}" for item in state.role_outputs) or "无"
        role_tasks = {
            "leo": "规划周末轻户外、社交或本地生活活动；优先低负担、可取消、能带来生活感的选择。",
            "nora": "安排周末饮食节奏、补水、咖啡因和活动前后的身体支持，避免休息日反而透支。",
            "mira": "保护恢复边界、留白和独处窗口，防止把周末排成任务表。",
            "alfred": "把活动、饮食和恢复边界综合成一个周末恢复节奏，并指出需要用户判断的问题。",
        }
        return (
            "## 周末恢复规划圆桌\n"
            f"用户诉求: {state.user_goal}\n\n"
            f"{protocol_block}\n\n"
            f"结构化上下文: {json.dumps(state.context, ensure_ascii=False, default=str)[:5000]}\n\n"
            f"用户上一轮反馈:\n{feedback}\n\n"
            f"前面角色公开发言:\n{previous}\n\n"
            f"你的基础职责: {role_tasks.get(agent_id, '从你的角色视角给出建议。')}\n"
            "请优先遵守场景协议里的 current_phase 和 current_role_instruction。\n"
            "请输出面向用户公开展示的会议发言，3-5 句。"
            "不要把周末排满；必须保留恢复留白。"
            "可以使用本地生活缓存，但不要声称已经实时搜索。不要展示隐藏思维链。"
        )

    async def _summarize_round(self, state: RoundtableGraphState) -> RoundtableRoundSummary:
        protocol = get_roundtable_protocol("weekend_recharge")
        final_phase = final_roundtable_phase(protocol)
        prompt = (
            "请把周末恢复规划圆桌本轮讨论整理成严格 JSON。"
            "字段必须为 minutes, consensus, disagreements, questions_for_user, next_round_focus。"
            "minutes 是对象数组，每项至少包含 agent_id 和 summary。不要输出 Markdown。\n\n"
            f"场景协议阶段: {', '.join(phase.id for phase in protocol.phases)}\n"
            f"最终收敛阶段: {final_phase.id} - {final_phase.objective}\n\n"
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
        protocol = get_roundtable_protocol("weekend_recharge")
        final_phase = final_roundtable_phase(protocol)
        prompt = (
            "请基于周末恢复规划圆桌，输出严格 JSON，字段为 summary, themes, ideas, tensions, followup_questions。"
            "ideas 是周末恢复安排候选，每项包含 id, title, source_agent；不要表示已经写入日程。\n\n"
            f"场景协议: {protocol.scenario_id}\n"
            f"最终阶段: {final_phase.id} - {final_phase.objective}\n"
            f"结果契约: {json.dumps(protocol.result_contract, ensure_ascii=False, default=str)}\n"
            f"用户诉求: {user_goal}\n"
            f"用户反馈: {json.dumps(feedback_history, ensure_ascii=False)}\n"
            f"上下文: {json.dumps(context, ensure_ascii=False, default=str)[:5000]}"
        )
        raw = await self.llm_client.chat(message=prompt, system_prompt=get_agent("alfred")["system_prompt"], temperature=0.25)
        data = self._load_json_object(raw)
        summary = str(data.get("summary") or "圆桌建议用半天轻活动、半天恢复留白的方式规划周末；可转给 Maxwell 做待确认安排。")
        themes = data.get("themes") if isinstance(data.get("themes"), list) else [
            {"title": "半天活动半天恢复", "summary": "兼顾生活感和真正恢复，避免把周末排满。"}
        ]
        ideas = data.get("ideas") if isinstance(data.get("ideas"), list) else [
            {"id": "light_outdoor_block", "title": "半天轻户外", "source_agent": "leo", "round": 1},
            {"id": "blank_recovery_block", "title": "无安排恢复窗口", "source_agent": "mira", "round": 1},
        ]
        tensions = data.get("tensions") if isinstance(data.get("tensions"), list) else [
            {"title": "想出去 vs 需要恢复", "description": "活动要服务恢复，而不是继续透支。"}
        ]
        followup_questions = data.get("followup_questions") if isinstance(data.get("followup_questions"), list) else [
            "周末哪一天更适合外出，哪一天更适合安静恢复？"
        ]
        return {
            "id": f"rt_result_{session_id}",
            "session_id": session_id,
            "mode": "brainstorm",
            "status": "draft",
            "summary": summary,
            "themes": themes,
            "ideas": ideas,
            "tensions": tensions,
            "followup_questions": followup_questions,
            "save_as_memory": False,
            "handoff_target": "maxwell",
            "context": {
                **context,
                **protocol_context(protocol),
                "topic": user_goal,
                "scenario_id": "weekend_recharge",
                "graph_executor": GRAPH_EXECUTOR_ID,
                "user_feedback_history": feedback_history,
                "round_summaries": [summary_item.to_dict() for summary_item in round_summaries],
                "themes": themes,
                "ideas": ideas,
                "tensions": tensions,
                "followup_questions": followup_questions,
                "save_as_memory": False,
            },
        }

    async def _prepare_round_node(self, state: WeekendRechargeState) -> WeekendRechargeState:
        return {
            **state,
            "scenario_id": "weekend_recharge",
            "participants": list(state.get("participants") or WEEKEND_RECHARGE_PARTICIPANTS),
            "status": "running",
        }

    async def _pass_node(self, state: WeekendRechargeState) -> WeekendRechargeState:
        return state

    async def _summarize_node(self, state: WeekendRechargeState) -> WeekendRechargeState:
        return state

    async def _checkpoint_node(self, state: WeekendRechargeState) -> WeekendRechargeState:
        return {**state, "status": "waiting_for_user"}

    def _to_graph_state(self, state: RoundtableGraphState) -> WeekendRechargeState:
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

    def _from_graph_state(self, state: WeekendRechargeState, *, fallback: RoundtableGraphState) -> RoundtableGraphState:
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
