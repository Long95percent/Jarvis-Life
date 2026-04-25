"""ReactExecutor — bridges AgentEngine with the LangGraph ReAct graph.

Converts LangGraph streaming events into ShadowLink StreamEvents,
providing real-time token streaming, tool call visibility, and
reflection status to the frontend.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, AsyncIterator

import structlog
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool

from app.agent.engine import MODE_SYSTEM_PROMPTS
from app.agent.react.graph import ReactGraph
from app.config import settings
from app.models.agent import AgentRequest, AgentResponse, AgentStep, AgentStrategy
from app.models.common import StreamEvent, StreamEventType

if TYPE_CHECKING:
    from app.llm.client import LLMClient

logger = structlog.get_logger("agent.react.executor")


class ReactExecutor:
    """Wraps ReactGraph for use by AgentEngine.

    Handles:
    - Converting AgentRequest into LangGraph initial state
    - Streaming LangGraph events as ShadowLink StreamEvents
    - Token-level streaming via astream_events
    """

    def __init__(self, llm_client: LLMClient, tools: list[BaseTool]) -> None:
        self.llm_client = llm_client
        self.tools = tools

    def _get_system_prompt(self, request: AgentRequest) -> str:
        # 1. Check if user configured a custom system prompt in the frontend mode settings
        custom_prompt = (request.context or {}).get("system_prompt")
        if custom_prompt and str(custom_prompt).strip():
            base = str(custom_prompt).strip()
        else:
            base = MODE_SYSTEM_PROMPTS.get(request.mode_id, MODE_SYSTEM_PROMPTS["general"])
            
        tool_names = ", ".join(t.name for t in self.tools)
        return (
            f"{base}\n\n"
            f"You have access to the following tools: {tool_names}.\n"
            "Use tools when needed to provide accurate, up-to-date information. "
            "Think step by step before answering."
        )

    def _build_graph(self) -> Any:
        """Build the compiled LangGraph graph."""
        llm = self.llm_client.get_langchain_llm()
        if llm is None:
            raise RuntimeError("LLM not initialized")

        react = ReactGraph(
            llm=llm,
            tools=self.tools,
            reflection_enabled=settings.agent.reflection_enabled,
        )
        return react.build()

    async def execute(self, request: AgentRequest) -> AgentResponse:
        """Non-streaming execution — run graph to completion."""
        start = time.perf_counter()
        graph = self._build_graph()

        initial_state = {
            "messages": [
                SystemMessage(content=self._get_system_prompt(request)),
                HumanMessage(content=request.message),
            ],
            "mode_id": request.mode_id,
            "tools_available": [t.name for t in self.tools],
            "memory_context": {},
            "rag_context": "",
            "iteration_count": 0,
            "max_iterations": request.max_iterations,
            "reflection_notes": [],
        }

        result = await graph.ainvoke(initial_state)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Extract final answer from last AI message
        answer = ""
        steps = []
        for msg in result.get("messages", []):
            if isinstance(msg, AIMessage):
                if msg.content:
                    answer = msg.content
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        steps.append(AgentStep(
                            step_type="tool_call",
                            tool_name=tc.get("name", ""),
                            tool_input=tc.get("args", {}),
                        ))

        return AgentResponse(
            session_id=request.session_id,
            answer=answer,
            strategy=AgentStrategy.REACT,
            steps=steps,
            total_latency_ms=round(elapsed_ms, 2),
        )

    async def execute_stream(self, request: AgentRequest) -> AsyncIterator[StreamEvent]:
        """Streaming execution — yield events as the graph progresses."""
        graph = self._build_graph()

        initial_state = {
            "messages": [
                SystemMessage(content=self._get_system_prompt(request)),
                HumanMessage(content=request.message),
            ],
            "mode_id": request.mode_id,
            "tools_available": [t.name for t in self.tools],
            "memory_context": {},
            "rag_context": "",
            "iteration_count": 0,
            "max_iterations": request.max_iterations,
            "reflection_notes": [],
        }

        yield StreamEvent(
            event=StreamEventType.THOUGHT,
            data={"content": "Analyzing your request..."},
            session_id=request.session_id,
        )

        token_count = 0
        start = time.perf_counter()

        try:
            async for event in graph.astream_events(initial_state, version="v2"):
                kind = event.get("event", "")

                # ── LLM token streaming ──
                if kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        token_count += 1
                        yield StreamEvent(
                            event=StreamEventType.TOKEN,
                            data={"content": chunk.content},
                            session_id=request.session_id,
                        )

                # ── Tool call start ──
                elif kind == "on_tool_start":
                    tool_name = event.get("name", "unknown")
                    tool_input = event.get("data", {}).get("input", {})
                    yield StreamEvent(
                        event=StreamEventType.TOOL_CALL,
                        data={
                            "content": f"Calling tool: {tool_name}",
                            "tool_name": tool_name,
                            "tool_input": tool_input,
                        },
                        session_id=request.session_id,
                    )

                # ── Tool call result ──
                elif kind == "on_tool_end":
                    tool_name = event.get("name", "unknown")
                    output = event.get("data", {}).get("output", "")
                    output_str = str(output.content) if hasattr(output, "content") else str(output)
                    yield StreamEvent(
                        event=StreamEventType.TOOL_RESULT,
                        data={
                            "content": output_str[:500],
                            "tool_name": tool_name,
                            "output": output_str,
                        },
                        session_id=request.session_id,
                    )

                # ── Chain/Node start — show thought process ──
                elif kind == "on_chain_start" and event.get("name") == "reflect":
                    yield StreamEvent(
                        event=StreamEventType.THOUGHT,
                        data={"content": "Reflecting on reasoning quality..."},
                        session_id=request.session_id,
                    )

        except Exception as e:
            await logger.aerror("react_executor_error", error=str(e))
            yield StreamEvent(
                event=StreamEventType.ERROR,
                data={"content": f"Agent execution failed: {e}"},
                session_id=request.session_id,
            )
            return

        elapsed_ms = (time.perf_counter() - start) * 1000
        yield StreamEvent(
            event=StreamEventType.DONE,
            data={
                "strategy": AgentStrategy.REACT.value,
                "token_count": token_count,
                "latency_ms": round(elapsed_ms, 2),
            },
            session_id=request.session_id,
        )
