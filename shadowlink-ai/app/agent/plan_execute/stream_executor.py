"""PlanExecuteExecutor — streaming wrapper for the Plan-and-Execute graph.

Converts PlanExecuteGraph execution into ShadowLink StreamEvents,
providing real-time plan visibility, step progress, and token streaming.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, AsyncIterator

import structlog
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool

from app.agent.engine import MODE_SYSTEM_PROMPTS
from app.agent.plan_execute.graph import PlanExecuteGraph
from app.config import settings
from app.models.agent import AgentRequest, AgentResponse, AgentStep, AgentStrategy, PlanStep
from app.models.common import StreamEvent, StreamEventType

if TYPE_CHECKING:
    from app.llm.client import LLMClient

logger = structlog.get_logger("agent.plan_execute.stream")


class PlanExecuteExecutor:
    """Wraps PlanExecuteGraph for use by AgentEngine.

    Streams events:
      THOUGHT  — "Analyzing task complexity..."
      PLAN     — Full plan with steps
      STEP_START — Step N begins
      TOKEN    — LLM output tokens during step execution
      TOOL_CALL / TOOL_RESULT — Tool invocations within steps
      STEP_RESULT — Step N complete
      DONE     — All steps finished, final answer
    """

    def __init__(self, llm_client: LLMClient, tools: list[BaseTool]) -> None:
        self.llm_client = llm_client
        self.tools = tools

    def _get_system_prompt(self, request: AgentRequest) -> str:
        custom_prompt = (request.context or {}).get("system_prompt")
        if custom_prompt and str(custom_prompt).strip():
            return str(custom_prompt).strip()
        return MODE_SYSTEM_PROMPTS.get(request.mode_id, MODE_SYSTEM_PROMPTS["general"])

    def _build_graph(self, request: AgentRequest) -> Any:
        llm = self.llm_client.get_langchain_llm()
        if llm is None:
            raise RuntimeError("LLM not initialized")
        
        system_prompt = self._get_system_prompt(request)
        # We can pass system_prompt to PlanExecuteGraph if we update it later.
        graph = PlanExecuteGraph(llm=llm, tools=self.tools)
        return graph.build()

    async def execute(self, request: AgentRequest) -> AgentResponse:
        """Non-streaming plan-and-execute."""
        start = time.perf_counter()
        graph = self._build_graph(request)

        initial_state = {
            "input": request.message,
            "plan": [],
            "step_index": 0,
            "step_results": [],
            "completed_steps": [],
            "current_issue": None,
            "final_answer": "",
            "messages": [HumanMessage(content=request.message)],
        }

        result = await graph.ainvoke(initial_state)
        elapsed_ms = (time.perf_counter() - start) * 1000

        answer = result.get("final_answer", "")
        steps = []
        for s in result.get("completed_steps", []):
            steps.append(AgentStep(step_type="step_result", content=str(s)))

        return AgentResponse(
            session_id=request.session_id,
            answer=answer,
            strategy=AgentStrategy.PLAN_EXECUTE,
            steps=steps,
            total_latency_ms=round(elapsed_ms, 2),
        )

    async def execute_stream(self, request: AgentRequest) -> AsyncIterator[StreamEvent]:
        """Streaming plan-and-execute via astream_events."""
        graph = self._build_graph(request)

        initial_state = {
            "input": request.message,
            "plan": [],
            "step_index": 0,
            "step_results": [],
            "completed_steps": [],
            "current_issue": None,
            "final_answer": "",
            "messages": [HumanMessage(content=request.message)],
        }

        yield StreamEvent(
            event=StreamEventType.THOUGHT,
            data={"content": "Analyzing task and creating execution plan..."},
            session_id=request.session_id,
        )

        token_count = 0
        start = time.perf_counter()
        plan_emitted = False
        current_step = -1

        try:
            async for event in graph.astream_events(initial_state, version="v2"):
                kind = event.get("event", "")
                name = event.get("name", "")

                # ── Plan generated (planner node completes) ──
                if kind == "on_chain_end" and name == "planner":
                    output = event.get("data", {}).get("output", {})
                    plan_data = output.get("plan", [])
                    if plan_data and not plan_emitted:
                        plan_emitted = True
                        plan_steps = []
                        for i, s in enumerate(plan_data):
                            desc = s.get("description", s) if isinstance(s, dict) else str(s)
                            tool = s.get("tool") if isinstance(s, dict) else None
                            plan_steps.append({
                                "index": i,
                                "description": desc,
                                "tool": tool,
                                "status": "pending",
                            })
                        yield StreamEvent(
                            event=StreamEventType.PLAN,
                            data={"steps": plan_steps, "total": len(plan_steps)},
                            session_id=request.session_id,
                        )

                # ── Step execution starts ──
                elif kind == "on_chain_start" and name == "executor":
                    current_step += 1
                    yield StreamEvent(
                        event=StreamEventType.STEP_START,
                        data={"step_index": current_step, "status": "running"},
                        session_id=request.session_id,
                    )

                # ── Step execution completes ──
                elif kind == "on_chain_end" and name == "executor":
                    output = event.get("data", {}).get("output", {})
                    results = output.get("step_results", [])
                    last_result = results[-1] if results else {}
                    success = last_result.get("success", True) if isinstance(last_result, dict) else True
                    out_text = last_result.get("output", "") if isinstance(last_result, dict) else str(last_result)
                    yield StreamEvent(
                        event=StreamEventType.STEP_RESULT,
                        data={
                            "step_index": current_step,
                            "success": success,
                            "output": out_text[:500],
                            "status": "completed" if success else "failed",
                        },
                        session_id=request.session_id,
                    )

                # ── Replanning ──
                elif kind == "on_chain_start" and name == "replanner":
                    yield StreamEvent(
                        event=StreamEventType.THOUGHT,
                        data={"content": "Step failed, replanning remaining steps..."},
                        session_id=request.session_id,
                    )

                # ── LLM token streaming (from any node) ──
                elif kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        token_count += 1
                        yield StreamEvent(
                            event=StreamEventType.TOKEN,
                            data={"content": chunk.content},
                            session_id=request.session_id,
                        )

                # ── Tool calls within steps ──
                elif kind == "on_tool_start":
                    tool_name = event.get("name", "unknown")
                    tool_input = event.get("data", {}).get("input", {})
                    yield StreamEvent(
                        event=StreamEventType.TOOL_CALL,
                        data={"tool_name": tool_name, "tool_input": tool_input, "content": f"Calling {tool_name}"},
                        session_id=request.session_id,
                    )

                elif kind == "on_tool_end":
                    tool_name = event.get("name", "unknown")
                    output = event.get("data", {}).get("output", "")
                    output_str = str(output.content) if hasattr(output, "content") else str(output)
                    yield StreamEvent(
                        event=StreamEventType.TOOL_RESULT,
                        data={"tool_name": tool_name, "output": output_str[:500], "content": output_str[:500]},
                        session_id=request.session_id,
                    )

                # ── Reporter generates final answer ──
                elif kind == "on_chain_start" and name == "reporter":
                    yield StreamEvent(
                        event=StreamEventType.THOUGHT,
                        data={"content": "Synthesizing final report from all step results..."},
                        session_id=request.session_id,
                    )

        except Exception as e:
            await logger.aerror("plan_execute_error", error=str(e))
            yield StreamEvent(
                event=StreamEventType.ERROR,
                data={"content": f"Plan execution failed: {e}"},
                session_id=request.session_id,
            )
            return

        elapsed_ms = (time.perf_counter() - start) * 1000
        yield StreamEvent(
            event=StreamEventType.DONE,
            data={
                "strategy": AgentStrategy.PLAN_EXECUTE.value,
                "token_count": token_count,
                "latency_ms": round(elapsed_ms, 2),
            },
            session_id=request.session_id,
        )
