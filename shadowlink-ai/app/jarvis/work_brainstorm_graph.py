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
    round_event,
)


WORK_BRAINSTORM_PARTICIPANTS = ["moderator", "explorer", "critic", "synthesizer"]
GRAPH_EXECUTOR_ID = "work_brainstorm_langgraph_v1"


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
        content_parts: list[str] = []
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
        async for delta in self.llm_client.chat_stream(
            message=self._role_prompt(state, agent_id),
            system_prompt=agent["system_prompt"],
            temperature=agent.get("temperature", 0.7),
        ):
            content_parts.append(delta)
            yield round_event("role_delta", {"agent_id": agent_id, "delta": delta, "round_index": state.round_index})

        content = "".join(content_parts).strip()
        state.role_outputs.append(
            RoundtableRoleOutput(
                agent_id=agent_id,
                agent_name=agent["name_zh"],
                role=agent["name"],
                content=content,
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
                "content": content,
                "round_index": state.round_index,
            },
        )

    def _role_prompt(self, state: RoundtableGraphState, agent_id: str) -> str:
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
            f"结构化上下文: {json.dumps(state.context, ensure_ascii=False, default=str)[:5000]}\n\n"
            f"用户上一轮反馈:\n{feedback}\n\n"
            f"前面角色公开发言:\n{previous}\n\n"
            f"你的职责: {role_tasks.get(agent_id, '从你的角色视角给出建议。')}\n"
            "请输出面向用户公开展示的会议发言，保持具体、可讨论。不要展示隐藏思维链。"
        )

    async def _summarize_round(self, state: RoundtableGraphState) -> RoundtableRoundSummary:
        prompt = (
            "请把工作头脑风暴本轮讨论整理成严格 JSON。"
            "字段必须为 minutes, consensus, disagreements, questions_for_user, next_round_focus。"
            "minutes 是对象数组，每项至少包含 agent_id 和 summary。不要输出 Markdown。\n\n"
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
        prompt = (
            "请基于工作头脑风暴工作坊，输出严格 JSON，字段为 summary, themes, ideas, tensions, followup_questions。"
            "ideas 是候选想法数组，每项包含 id, title, source_agent。不要输出 Markdown。\n\n"
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
                "topic": user_goal,
                "scenario_id": "work_brainstorm",
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
