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


LOCAL_LIFESTYLE_PARTICIPANTS = ["leo", "maxwell", "nora", "alfred"]
GRAPH_EXECUTOR_ID = "local_lifestyle_c_v1"
LOCAL_LIFESTYLE_STAGE_BY_AGENT = {
    "leo": "discover_candidates",
    "maxwell": "feasibility_score",
    "nora": "energy_filter",
    "alfred": "rank_options",
}
LOCAL_LIFESTYLE_C_STAGE_TITLES = {
    "collect_constraints": "收集约束",
    "discover_candidates": "发现候选",
    "enrich_candidates": "补全候选事实",
    "feasibility_score": "可行性评分",
    "energy_filter": "体力过滤",
    "rank_options": "候选排序",
    "plan_candidate": "计划候选",
}


class LocalLifestyleState(TypedDict, total=False):
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


class LocalLifestyleGraphExecutor:
    """LangGraph-backed meeting protocol for local lifestyle recommendations."""

    def __init__(self, llm_client: Any) -> None:
        self.llm_client = llm_client
        self.graph = self._build_graph()

    def _build_graph(self) -> Any:
        graph = StateGraph(LocalLifestyleState)
        graph.add_node("prepare_round", self._prepare_round_node)
        graph.add_node("leo", self._pass_node)
        graph.add_node("maxwell", self._pass_node)
        graph.add_node("nora", self._pass_node)
        graph.add_node("alfred", self._pass_node)
        graph.add_node("summarize", self._summarize_node)
        graph.add_node("checkpoint", self._checkpoint_node)
        graph.add_edge(START, "prepare_round")
        graph.add_edge("prepare_round", "leo")
        graph.add_edge("leo", "maxwell")
        graph.add_edge("maxwell", "nora")
        graph.add_edge("nora", "alfred")
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
            scenario_id="local_lifestyle",
            user_goal=user_goal,
            participants=list(participants or LOCAL_LIFESTYLE_PARTICIPANTS),
            round_index=round_index,
            context=context,
            user_feedback_history=feedback_history or [],
        )
        state_data: LocalLifestyleState = await self.graph.ainvoke(self._to_graph_state(state))
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
        yield round_event("scenario_stage", self._build_stage_payload(state, "alfred", stage_id="collect_constraints"))
        for agent_id in state.participants:
            async for event in self._run_role(state, agent_id):
                yield event

        summary = await self._summarize_round(state)
        state.round_summaries.append(summary)
        state.status = "waiting_for_user"
        yield round_event("scenario_stage", self._build_stage_payload(state, "maxwell", stage_id="plan_candidate"))
        yield round_event("scenario_state", self._build_c_state_payload(state))
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
        yield round_event("done", {"phase": "round_complete", "session_id": session_id, "scenario_id": "local_lifestyle"})

    async def _run_role(self, state: RoundtableGraphState, agent_id: str) -> AsyncIterator[dict[str, str]]:
        agent = get_agent(agent_id)
        yield round_event("scenario_stage", self._build_stage_payload(state, agent_id))
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
            temperature=0.45,
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
        if agent_id == "leo":
            yield round_event("scenario_stage", self._build_stage_payload(state, agent_id, stage_id="enrich_candidates"))

    def _build_stage_payload(self, state: RoundtableGraphState, agent_id: str, *, stage_id: str | None = None) -> dict[str, Any]:
        protocol = get_roundtable_protocol("local_lifestyle")
        stage_id = stage_id or LOCAL_LIFESTYLE_STAGE_BY_AGENT.get(agent_id, "rank_options")
        phase = next((item for item in protocol.phases if item.id == stage_id), protocol.phases[0])
        objective_by_stage = {
            "collect_constraints": "收集位置、时间、预算、偏好和体力约束。",
            "discover_candidates": "基于上下文提出本地活动候选。",
            "enrich_candidates": "补全候选的天气、距离、时效、交通和耗时事实。",
            "feasibility_score": "按时间窗口和往返缓冲给候选打可行性分。",
            "energy_filter": "按体力、饮食和恢复负担过滤候选。",
            "rank_options": "按生活感、恢复友好度和可执行性排序。",
            "plan_candidate": "把首选候选整理成可选待确认安排。",
        }
        return {
            "scenario_id": state.scenario_id,
            "graph_executor": GRAPH_EXECUTOR_ID,
            "state_type": "local_lifestyle_c",
            "stage_id": stage_id,
            "stage_title": LOCAL_LIFESTYLE_C_STAGE_TITLES.get(stage_id, phase.title),
            "owner_agent": agent_id,
            "round_index": state.round_index,
            "objective": objective_by_stage.get(stage_id, phase.objective),
            "artifact_keys": ["user_constraints", "candidate_pool", "candidate_facts", "scorecards", "rejected_candidates", "ranked_activities", "plan_candidate"],
        }

    def _build_c_artifacts(
        self,
        *,
        user_goal: str,
        context: dict[str, Any],
        feedback_history: list[str],
        role_outputs: list[RoundtableRoleOutput],
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        data = data or {}
        output_by_agent = {item.agent_id: item.content for item in role_outputs}
        ideas = data.get("ideas") if isinstance(data.get("ideas"), list) else [
            {"id": "nearby_light_activity", "title": "附近轻量活动", "source_agent": "leo", "round": 1}
        ]
        ranked_activities = data.get("ranked_activities") if isinstance(data.get("ranked_activities"), list) else [
            {
                "id": str(item.get("id") or f"activity-{index + 1}"),
                "title": str(item.get("title") or "候选活动"),
                "rank": index + 1,
                "reason": "综合时间、体力和恢复友好度后保留。",
            }
            for index, item in enumerate(ideas[:5])
            if isinstance(item, dict)
        ]
        scorecards = data.get("scorecards") if isinstance(data.get("scorecards"), list) else [
            {
                "activity_id": item.get("id"),
                "time_fit": "medium",
                "energy_load": "low",
                "recovery_fit": "high",
                "notes": "默认按低负担活动处理，等待用户补充偏好后可重排。",
            }
            for item in ranked_activities
            if isinstance(item, dict)
        ]
        rejected = data.get("rejected_candidates") if isinstance(data.get("rejected_candidates"), list) else []
        return {
            "state_type": "local_lifestyle_c",
            "user_constraints": data.get("user_constraints") if isinstance(data.get("user_constraints"), dict) else {
                "request": user_goal,
                "feedback": feedback_history[-3:],
                "has_local_context": bool(context.get("local_life_context") or context.get("context_prefix")),
            },
            "candidate_pool": ideas,
            "candidate_facts": data.get("candidate_facts") if isinstance(data.get("candidate_facts"), list) else [
                {"source": "roundtable_context", "summary": output_by_agent.get("leo", "等待 Leo 给出候选。")}
            ],
            "scorecards": scorecards,
            "rejected_candidates": rejected,
            "ranked_activities": ranked_activities,
            "plan_candidate": data.get("plan_candidate") if isinstance(data.get("plan_candidate"), dict) else {
                "enabled": bool(ranked_activities),
                "activity_id": ranked_activities[0].get("id") if ranked_activities and isinstance(ranked_activities[0], dict) else None,
                "requires_confirmation": True,
            },
        }

    def _build_c_state_payload(self, state: RoundtableGraphState) -> dict[str, Any]:
        artifacts = self._build_c_artifacts(
            user_goal=state.user_goal,
            context=state.context,
            feedback_history=state.user_feedback_history,
            role_outputs=state.role_outputs,
        )
        return {
            "scenario_id": state.scenario_id,
            "graph_executor": GRAPH_EXECUTOR_ID,
            "state_type": "local_lifestyle_c",
            "round_index": state.round_index,
            "artifacts": artifacts,
            "next_routes": [
                {"label": "换成室内", "target_stage": "energy_filter", "prompt": "不要户外，换室内低负担活动。"},
                {"label": "只有一小时", "target_stage": "feasibility_score", "prompt": "我只有一小时，重新筛选。"},
                {"label": "安排第一项", "target_stage": "plan_candidate", "prompt": "安排第一个候选，但先生成待确认卡。"},
            ],
        }

    def _role_prompt(self, state: RoundtableGraphState, agent_id: str) -> str:
        protocol = get_roundtable_protocol("local_lifestyle")
        protocol_block = format_roundtable_protocol_block(
            protocol,
            turn_index=len(state.role_outputs),
            agent_id=agent_id,
            stage_id=LOCAL_LIFESTYLE_STAGE_BY_AGENT.get(agent_id),
        )
        feedback = "\n".join(f"- {item}" for item in state.user_feedback_history) or "无"
        previous = "\n\n".join(f"{item.agent_name}: {item.content}" for item in state.role_outputs) or "无"
        role_tasks = {
            "leo": "提出附近可做的活动选项，优先使用上下文里的本地生活机会；注意距离、天气、时间有效性和体验感。",
            "maxwell": "评估活动是否能放进今天或近期空档，给出时间窗口、往返缓冲和是否适合交给日程。",
            "nora": "评估体力、饮食、补水、咖啡因和恢复负担，过滤不适合当前能量的活动。",
            "alfred": "综合活动候选、可行性和体力边界，收敛成推荐方向和需要用户判断的问题。",
        }
        return (
            "## 本地生活活动推荐圆桌\n"
            f"用户诉求: {state.user_goal}\n\n"
            f"{protocol_block}\n\n"
            f"结构化上下文: {json.dumps(state.context, ensure_ascii=False, default=str)[:5000]}\n\n"
            f"用户上一轮反馈:\n{feedback}\n\n"
            f"前面角色公开发言:\n{previous}\n\n"
            f"你的基础职责: {role_tasks.get(agent_id, '从你的角色视角给出建议。')}\n"
            "请优先遵守场景协议里的 current_phase 和 current_role_instruction。\n"
            "请输出面向用户公开展示的会议发言，3-5 句。"
            "只推荐今天或近期仍有效的本地信息；如果上下文不足，要说明需要偏好或位置补充。"
            "不要展示隐藏思维链，不要声称已经实时搜索。"
        )

    async def _summarize_round(self, state: RoundtableGraphState) -> RoundtableRoundSummary:
        protocol = get_roundtable_protocol("local_lifestyle")
        final_phase = final_roundtable_phase(protocol)
        prompt = (
            "请把本地生活活动推荐圆桌本轮讨论整理成严格 JSON。"
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
        protocol = get_roundtable_protocol("local_lifestyle")
        final_phase = final_roundtable_phase(protocol)
        prompt = (
            "请基于本地生活活动推荐圆桌，输出严格 JSON，字段为 summary, themes, ideas, tensions, followup_questions, "
            "user_constraints, ranked_activities, rejected_candidates, scorecards, candidate_facts, plan_candidate。"
            "ideas 是候选活动数组，每项包含 id, title, source_agent；不要表示已经写入日程。\n\n"
            f"场景协议: {protocol.scenario_id}\n"
            f"最终阶段: {final_phase.id} - {final_phase.objective}\n"
            f"结果契约: {json.dumps(protocol.result_contract, ensure_ascii=False, default=str)}\n"
            f"用户诉求: {user_goal}\n"
            f"用户反馈: {json.dumps(feedback_history, ensure_ascii=False)}\n"
            f"上下文: {json.dumps(context, ensure_ascii=False, default=str)[:5000]}"
        )
        raw = await self.llm_client.chat(message=prompt, system_prompt=get_agent("alfred")["system_prompt"], temperature=0.25)
        data = self._load_json_object(raw)
        summary = str(data.get("summary") or "圆桌建议选择近距离、低负担、时间仍有效的本地活动；可继续收窄偏好，也可以转给 Maxwell 做待确认计划。")
        themes = data.get("themes") if isinstance(data.get("themes"), list) else [
            {"title": "低负担本地活动", "summary": "优先选择近距离、短时长、恢复友好的活动。"}
        ]
        ideas = data.get("ideas") if isinstance(data.get("ideas"), list) else [
            {"id": "nearby_light_activity", "title": "附近轻量活动", "source_agent": "leo", "round": 1}
        ]
        tensions = data.get("tensions") if isinstance(data.get("tensions"), list) else [
            {"title": "新鲜感 vs 恢复负担", "description": "活动要有生活感，但不能挤压恢复和晚间节奏。"}
        ]
        followup_questions = data.get("followup_questions") if isinstance(data.get("followup_questions"), list) else [
            "你更想户外、展览、市集，还是安静咖啡馆？"
        ]
        c_artifacts = self._build_c_artifacts(
            user_goal=user_goal,
            context=context,
            feedback_history=feedback_history,
            role_outputs=[],
            data={
                **data,
                "ideas": ideas,
            },
        )
        ranked_activities = c_artifacts["ranked_activities"]
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
            "ranked_activities": ranked_activities,
            "save_as_memory": False,
            "handoff_target": "maxwell",
            "context": {
                **context,
                **protocol_context(protocol),
                "topic": user_goal,
                "scenario_id": "local_lifestyle",
                "graph_executor": GRAPH_EXECUTOR_ID,
                "c_artifacts": c_artifacts,
                "ranked_activities": ranked_activities,
                "user_feedback_history": feedback_history,
                "round_summaries": [summary_item.to_dict() for summary_item in round_summaries],
                "themes": themes,
                "ideas": ideas,
                "tensions": tensions,
                "followup_questions": followup_questions,
                "save_as_memory": False,
            },
        }

    async def _prepare_round_node(self, state: LocalLifestyleState) -> LocalLifestyleState:
        return {
            **state,
            "scenario_id": "local_lifestyle",
            "participants": list(state.get("participants") or LOCAL_LIFESTYLE_PARTICIPANTS),
            "status": "running",
        }

    async def _pass_node(self, state: LocalLifestyleState) -> LocalLifestyleState:
        return state

    async def _summarize_node(self, state: LocalLifestyleState) -> LocalLifestyleState:
        return state

    async def _checkpoint_node(self, state: LocalLifestyleState) -> LocalLifestyleState:
        return {**state, "status": "waiting_for_user"}

    def _to_graph_state(self, state: RoundtableGraphState) -> LocalLifestyleState:
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

    def _from_graph_state(self, state: LocalLifestyleState, *, fallback: RoundtableGraphState) -> RoundtableGraphState:
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
