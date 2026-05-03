from __future__ import annotations

import json
import re
from typing import Any, AsyncIterator, TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from app.agent.brainstorm.agents import AGENTS
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


WORK_BRAINSTORM_PARTICIPANTS = ["moderator", "explorer", "critic", "synthesizer"]
GRAPH_EXECUTOR_ID = "work_brainstorm_c_v1"
WORK_BRAINSTORM_STAGE_BY_AGENT = {
    "moderator": "frame_problem",
    "explorer": "divergent_ideas",
    "critic": "critic_review",
    "synthesizer": "synthesis",
}
WORK_BRAINSTORM_C_STAGE_TITLES = {
    "frame_problem": "框定问题",
    "ingest_context": "吸收上下文",
    "divergent_ideas": "发散想法",
    "cluster_ideas": "想法分组",
    "critic_review": "批判审视",
    "synthesis": "合并收敛",
    "validation_plan": "验证计划",
}


class WorkBrainstormState(TypedDict, total=False):
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


class WorkBrainstormGraphExecutor:
    """LangGraph-backed human-in-the-loop workshop for work brainstorms."""

    def __init__(self, llm_client: Any) -> None:
        self.llm_client = llm_client
        self.graph = self._build_graph()

    def _build_graph(self) -> Any:
        graph = StateGraph(WorkBrainstormState)
        graph.add_node("prepare_round", self._prepare_round_node)
        graph.add_node("moderator", self._pass_node)
        graph.add_node("explorer", self._pass_node)
        graph.add_node("critic", self._pass_node)
        graph.add_node("synthesizer", self._pass_node)
        graph.add_node("summarize", self._summarize_node)
        graph.add_node("checkpoint", self._checkpoint_node)
        graph.add_edge(START, "prepare_round")
        graph.add_edge("prepare_round", "moderator")
        graph.add_edge("moderator", "explorer")
        graph.add_edge("explorer", "critic")
        graph.add_edge("critic", "synthesizer")
        graph.add_edge("synthesizer", "summarize")
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
            scenario_id="work_brainstorm",
            user_goal=user_goal,
            participants=list(participants or WORK_BRAINSTORM_PARTICIPANTS),
            round_index=round_index,
            context=context,
            user_feedback_history=feedback_history or [],
        )
        state_data: WorkBrainstormState = await self.graph.ainvoke(self._to_graph_state(state))
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
        yield round_event("scenario_stage", self._build_stage_payload(state, "synthesizer", stage_id="validation_plan"))
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
        yield round_event("done", {"phase": "round_complete", "session_id": session_id, "scenario_id": "work_brainstorm"})

    async def _run_role(self, state: RoundtableGraphState, agent_id: str) -> AsyncIterator[dict[str, str]]:
        agent = AGENTS[agent_id]
        yield round_event("scenario_stage", self._build_stage_payload(state, agent_id))
        yield round_event(
            "role_started",
            {
                "agent_id": agent_id,
                "agent_name": agent["name_zh"],
                "agent_role": agent["name"],
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
            temperature=agent.get("temperature", 0.7),
            session_id=state.session_id,
            enable_tools=False,
        )
        for delta in roundtable_content_deltas(turn_result.content):
            yield round_event("role_delta", {"agent_id": agent_id, "delta": delta, "round_index": state.round_index})

        state.role_outputs.append(
            RoundtableRoleOutput(
                agent_id=agent_id,
                agent_name=agent["name_zh"],
                role=agent["name"],
                content=turn_result.content,
                round_index=state.round_index,
            )
        )
        yield round_event(
            "role_completed",
            {
                "agent_id": agent_id,
                "agent_name": agent["name_zh"],
                "agent_role": agent["name"],
                "agent_icon": agent.get("icon"),
                "agent_color": agent.get("color"),
                "content": turn_result.content,
                "tool_results": turn_result.tool_results,
                "action_results": turn_result.action_results,
                "round_index": state.round_index,
            },
        )
        if agent_id == "moderator":
            yield round_event("scenario_stage", self._build_stage_payload(state, agent_id, stage_id="ingest_context"))
        if agent_id == "explorer":
            yield round_event("scenario_stage", self._build_stage_payload(state, agent_id, stage_id="cluster_ideas"))

    def _build_stage_payload(self, state: RoundtableGraphState, agent_id: str, *, stage_id: str | None = None) -> dict[str, Any]:
        protocol = get_roundtable_protocol("work_brainstorm")
        stage_id = stage_id or WORK_BRAINSTORM_STAGE_BY_AGENT.get(agent_id, "synthesis")
        phase = next((item for item in protocol.phases if item.id == stage_id), protocol.phases[0])
        title = WORK_BRAINSTORM_C_STAGE_TITLES.get(stage_id, phase.title)
        objective_by_stage = {
            "ingest_context": "吸收用户文档、历史讨论和当前限制，决定本轮发散边界。",
            "cluster_ideas": "把发散想法分组，避免后续批判阶段只看到散点。",
            "validation_plan": "把保留下来的想法压缩成最小验证步骤。",
        }
        return {
            "scenario_id": state.scenario_id,
            "graph_executor": GRAPH_EXECUTOR_ID,
            "state_type": "work_brainstorm_c",
            "stage_id": stage_id,
            "stage_title": title,
            "owner_agent": agent_id,
            "round_index": state.round_index,
            "objective": objective_by_stage.get(stage_id, phase.objective),
            "artifact_keys": ["problem_frame", "idea_pool", "clusters", "critique_matrix", "selected_concepts", "validation_plan"],
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
        ideas = data.get("ideas") if isinstance(data.get("ideas"), list) else self._ideas_from_context(
            user_goal,
            feedback_history + [output_by_agent.get("explorer", "")],
        )
        themes = data.get("themes") if isinstance(data.get("themes"), list) else [
            {"title": "最小可验证主线", "summary": "先把最强想法压缩成可演示或可验证的版本。"}
        ]
        risks = data.get("risks") if isinstance(data.get("risks"), list) else [
            {"title": "范围过散", "description": output_by_agent.get("critic", "需要控制范围并先验证核心假设。")}
        ]
        validation_steps = data.get("minimum_validation_steps") if isinstance(data.get("minimum_validation_steps"), list) else [
            "明确目标用户和成功标准",
            "选择一个主想法做最小 demo",
            "用一次短评审验证风险是否可控",
        ]
        selected_concepts = data.get("selected_concepts") if isinstance(data.get("selected_concepts"), list) else ideas[:2]
        clusters = data.get("clusters") if isinstance(data.get("clusters"), list) else [
            {"title": str(theme.get("title") or "候选方向"), "ideas": [idea.get("title") for idea in ideas[:3] if isinstance(idea, dict)]}
            for theme in themes[:3]
            if isinstance(theme, dict)
        ]
        return {
            "state_type": "work_brainstorm_c",
            "problem_frame": data.get("problem_frame") if isinstance(data.get("problem_frame"), dict) else {
                "goal": user_goal,
                "constraints": feedback_history[-3:],
                "context_available": bool(context.get("document_context") or context.get("previous_discussion")),
            },
            "idea_pool": ideas,
            "clusters": clusters,
            "critique_matrix": risks,
            "selected_concepts": selected_concepts,
            "validation_plan": validation_steps,
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
            "state_type": "work_brainstorm_c",
            "round_index": state.round_index,
            "artifacts": artifacts,
            "next_routes": [
                {"label": "继续发散", "target_stage": "divergent_ideas", "prompt": "再大胆一点，继续发散。"},
                {"label": "压缩范围", "target_stage": "critic_review", "prompt": "这个太大了，帮我压缩范围。"},
                {"label": "形成验证", "target_stage": "validation_plan", "prompt": "选一个方向，给我最小验证步骤。"},
            ],
        }

    def _role_prompt(self, state: RoundtableGraphState, agent_id: str) -> str:
        protocol = get_roundtable_protocol("work_brainstorm")
        protocol_block = format_roundtable_protocol_block(
            protocol,
            turn_index=len(state.role_outputs),
            agent_id=agent_id,
            stage_id=WORK_BRAINSTORM_STAGE_BY_AGENT.get(agent_id),
        )
        feedback = "\n".join(f"- {item}" for item in state.user_feedback_history) or "无"
        previous = "\n\n".join(f"{item.agent_name}: {item.content}" for item in state.role_outputs) or "无"
        role_tasks = {
            "moderator": "框定问题，拆出 2-3 个值得探索的方向，并指出本轮发散边界。",
            "explorer": "提出大胆但可讨论的新想法，尽量用编号列出 2-3 个候选。",
            "critic": "评估可行性、风险、隐藏假设和最小验证方式，批判但保持建设性。",
            "synthesizer": "合并强想法，找共同主线，提出可以进入下一轮或收敛的候选方案。",
        }
        return (
            "## 工作难题头脑风暴工作坊\n"
            f"用户主题: {state.user_goal}\n\n"
            f"{protocol_block}\n\n"
            f"结构化上下文: {json.dumps(state.context, ensure_ascii=False, default=str)[:5000]}\n\n"
            f"用户上一轮反馈:\n{feedback}\n\n"
            f"前面角色公开发言:\n{previous}\n\n"
            f"你的基础职责: {role_tasks.get(agent_id, '从你的角色视角给出建议。')}\n"
            "请优先遵守场景协议里的 current_phase 和 current_role_instruction。\n"
            "请输出面向用户公开展示的会议发言，保持具体、可讨论。不要展示隐藏思维链。"
        )

    async def _summarize_round(self, state: RoundtableGraphState) -> RoundtableRoundSummary:
        protocol = get_roundtable_protocol("work_brainstorm")
        final_phase = final_roundtable_phase(protocol)
        prompt = (
            "请把工作头脑风暴本轮讨论整理成严格 JSON。"
            "字段必须为 minutes, consensus, disagreements, questions_for_user, next_round_focus。"
            "minutes 是对象数组，每项至少包含 agent_id 和 summary。不要输出 Markdown。\n\n"
            f"场景协议阶段: {', '.join(phase.id for phase in protocol.phases)}\n"
            f"最终收敛阶段: {final_phase.id} - {final_phase.objective}\n\n"
            + "\n\n".join(f"{item.agent_id}: {item.content}" for item in state.role_outputs)
        )
        raw = await self.llm_client.chat(message=prompt, system_prompt=AGENTS["moderator"]["system_prompt"], temperature=0.2)
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
        protocol = get_roundtable_protocol("work_brainstorm")
        final_phase = final_roundtable_phase(protocol)
        prompt = (
            "请基于工作头脑风暴工作坊，输出严格 JSON，字段为 summary, themes, ideas, tensions, followup_questions, "
            "problem_frame, clusters, risks, selected_concepts, minimum_validation_steps。"
            "ideas 是候选想法数组，每项包含 id, title, source_agent。不要输出 Markdown。\n\n"
            f"场景协议: {protocol.scenario_id}\n"
            f"最终阶段: {final_phase.id} - {final_phase.objective}\n"
            f"结果契约: {json.dumps(protocol.result_contract, ensure_ascii=False, default=str)}\n"
            f"用户主题: {user_goal}\n"
            f"用户反馈: {json.dumps(feedback_history, ensure_ascii=False)}\n"
            f"上下文: {json.dumps(context, ensure_ascii=False, default=str)[:5000]}"
        )
        raw = await self.llm_client.chat(message=prompt, system_prompt=AGENTS["synthesizer"]["system_prompt"], temperature=0.25)
        data = self._load_json_object(raw)
        summary = str(data.get("summary") or "头脑风暴已收敛为一组可继续验证的候选方向，可保存为灵感或交给 Maxwell 转成计划。")
        themes = data.get("themes") if isinstance(data.get("themes"), list) else [
            {"title": "最小可验证方向", "summary": "先验证最核心的价值和可交付路径。"}
        ]
        ideas = data.get("ideas") if isinstance(data.get("ideas"), list) else self._ideas_from_context(user_goal, feedback_history)
        tensions = data.get("tensions") if isinstance(data.get("tensions"), list) else [
            {"title": "创意空间 vs 可交付范围", "description": "需要保留新意，同时避免扩散到不可执行。"}
        ]
        followup_questions = data.get("followup_questions") if isinstance(data.get("followup_questions"), list) else [
            "你想先验证哪一个方向？"
        ]
        c_artifacts = self._build_c_artifacts(
            user_goal=user_goal,
            context=context,
            feedback_history=feedback_history,
            role_outputs=[],
            data={
                **data,
                "ideas": ideas,
                "themes": themes,
            },
        )
        risks = c_artifacts["critique_matrix"]
        minimum_validation_steps = c_artifacts["validation_plan"]
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
            "risks": risks,
            "minimum_validation_steps": minimum_validation_steps,
            "save_as_memory": False,
            "handoff_target": "maxwell",
            "context": {
                **context,
                **protocol_context(protocol),
                "topic": user_goal,
                "scenario_id": "work_brainstorm",
                "graph_executor": GRAPH_EXECUTOR_ID,
                "c_artifacts": c_artifacts,
                "risks": risks,
                "minimum_validation_steps": minimum_validation_steps,
                "user_feedback_history": feedback_history,
                "round_summaries": [summary_item.to_dict() for summary_item in round_summaries],
                "themes": themes,
                "ideas": ideas,
                "tensions": tensions,
                "followup_questions": followup_questions,
                "save_as_memory": False,
            },
        }

    async def _prepare_round_node(self, state: WorkBrainstormState) -> WorkBrainstormState:
        return {
            **state,
            "scenario_id": "work_brainstorm",
            "participants": list(state.get("participants") or WORK_BRAINSTORM_PARTICIPANTS),
            "status": "running",
        }

    async def _pass_node(self, state: WorkBrainstormState) -> WorkBrainstormState:
        return state

    async def _summarize_node(self, state: WorkBrainstormState) -> WorkBrainstormState:
        return state

    async def _checkpoint_node(self, state: WorkBrainstormState) -> WorkBrainstormState:
        return {**state, "status": "waiting_for_user"}

    def _to_graph_state(self, state: RoundtableGraphState) -> WorkBrainstormState:
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

    def _from_graph_state(self, state: WorkBrainstormState, *, fallback: RoundtableGraphState) -> RoundtableGraphState:
        fallback.scenario_id = str(state.get("scenario_id") or fallback.scenario_id)
        fallback.participants = list(state.get("participants") or fallback.participants)
        fallback.status = state.get("status") or fallback.status  # type: ignore[assignment]
        return fallback

    def _ideas_from_context(self, user_goal: str, feedback_history: list[str]) -> list[dict[str, Any]]:
        text = "\n".join([user_goal, *feedback_history])
        ideas: list[dict[str, Any]] = []
        for match in re.finditer(r"(?:^|\n)\s*\d+[\.\)]\s*(.+)", text):
            title = match.group(1).strip()
            if len(title) >= 8:
                ideas.append({"id": f"idea-{uuid4().hex[:8]}", "title": title[:120], "source_agent": "user"})
        return ideas or [{"id": f"idea-{uuid4().hex[:8]}", "title": "先做一条最小可验证主线", "source_agent": "synthesizer"}]

    @staticmethod
    def _load_json_object(raw: str) -> dict[str, Any]:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}
