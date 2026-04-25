"""SupervisorExecutor — streaming wrapper for the Supervisor MultiAgent graph.

Converts SupervisorGraph execution into ShadowLink StreamEvents,
providing real-time expert delegation visibility and token streaming.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, AsyncIterator

import structlog
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool

from app.agent.engine import MODE_SYSTEM_PROMPTS
from app.agent.multi_agent.supervisor import SupervisorGraph
from app.config import settings
from app.models.agent import AgentRequest, AgentResponse, AgentStep, AgentStrategy
from app.models.common import StreamEvent, StreamEventType

if TYPE_CHECKING:
    from app.llm.client import LLMClient

logger = structlog.get_logger("agent.supervisor.executor")


class ExpertAgent:
    """A specialized expert agent that uses LLM + tools for a specific domain."""

    def __init__(self, name: str, description: str, llm: Any, tools: list[BaseTool] | None = None) -> None:
        self.name = name
        self.description = description
        self.llm = llm
        self.tools = tools or []

    async def run(self, task: str, context: str = "") -> str:
        """Execute the expert's task using LLM reasoning + optional tools."""
        system = (
            f"You are {self.name}, a specialized expert. {self.description}\n\n"
            f"Previous context:\n{context}\n\n"
            "Provide a thorough, expert-level response."
        )
        messages = [SystemMessage(content=system), HumanMessage(content=task)]

        if self.tools:
            llm_with_tools = self.llm.bind_tools(self.tools)
            response = await llm_with_tools.ainvoke(messages)

            # Handle tool calls if any
            if hasattr(response, "tool_calls") and response.tool_calls:
                results = []
                for tc in response.tool_calls:
                    tool_name = tc.get("name", "")
                    matching = [t for t in self.tools if t.name == tool_name]
                    if matching:
                        result = await matching[0].ainvoke(tc.get("args", {}))
                        results.append(f"[{tool_name}]: {result}")
                # Follow up with tool results
                tool_context = "\n".join(results)
                follow_up = await self.llm.ainvoke([
                    SystemMessage(content=system),
                    HumanMessage(content=f"{task}\n\nTool results:\n{tool_context}\n\nPlease synthesize a final answer."),
                ])
                return follow_up.content

            return response.content
        else:
            response = await self.llm.ainvoke(messages)
            return response.content


def build_expert_agents(llm: Any, tools: list[BaseTool]) -> dict[str, ExpertAgent]:
    """Build the default set of expert agents for the Supervisor pattern."""
    code_tools = [t for t in tools if t.name in ("code_executor", "file_reader")]
    search_tools = [t for t in tools if t.name in ("web_search", "knowledge_search")]

    return {
        "coder": ExpertAgent(
            name="Coder Agent",
            description="Expert in writing, analyzing, and debugging code. Uses code execution tools.",
            llm=llm,
            tools=code_tools,
        ),
        "researcher": ExpertAgent(
            name="Research Agent",
            description="Expert in finding information, searching the web and knowledge base.",
            llm=llm,
            tools=search_tools,
        ),
        "writer": ExpertAgent(
            name="Writer Agent",
            description="Expert in writing reports, summaries, documentation, and creative content.",
            llm=llm,
        ),
        "analyst": ExpertAgent(
            name="Analyst Agent",
            description="Expert in data analysis, comparison, evaluation, and logical reasoning.",
            llm=llm,
            tools=[t for t in tools if t.name == "calculator"],
        ),
    }


class SupervisorExecutor:
    """Wraps SupervisorGraph for use by AgentEngine.

    Builds real expert agents (coder, researcher, writer, analyst) and
    delegates tasks via the Supervisor pattern.
    """

    def __init__(self, llm_client: LLMClient, tools: list[BaseTool]) -> None:
        self.llm_client = llm_client
        self.tools = tools

    def _get_system_prompt(self, request: AgentRequest) -> str:
        custom_prompt = (request.context or {}).get("system_prompt")
        if custom_prompt and str(custom_prompt).strip():
            return str(custom_prompt).strip()
        return MODE_SYSTEM_PROMPTS.get(request.mode_id, MODE_SYSTEM_PROMPTS["general"])

    def _build_graph(self, request: AgentRequest) -> tuple[Any, dict[str, ExpertAgent]]:
        llm = self.llm_client.get_langchain_llm()
        if llm is None:
            raise RuntimeError("LLM not initialized")

        experts = build_expert_agents(llm, self.tools)
        system_prompt = self._get_system_prompt(request)

        # Build the graph with real expert agents
        graph = SupervisorGraph(
            llm=llm,
            expert_agents={name: agent for name, agent in experts.items()},
            max_iterations=settings.agent.max_iterations,
        )
        
        # Override supervisor node system prompt if possible, or just append it to task
        # For simplicity, we just inject it into the graph context or node

        # Patch the expert node factory to use real agents
        compiled = self._build_with_real_experts(graph, experts, system_prompt)
        return compiled, experts

    def _build_with_real_experts(self, graph_obj: SupervisorGraph, experts: dict[str, ExpertAgent], system_prompt: str) -> Any:
        """Build the graph with real expert execution nodes."""
        from langgraph.graph import END, START, StateGraph
        from app.agent.state import SupervisorState

        graph = StateGraph(SupervisorState)
        graph.add_node("supervisor", graph_obj._supervisor_node)

        for name, agent in experts.items():
            graph.add_node(name, self._make_real_expert_node(name, agent))

        expert_names = list(experts.keys())
        routing = {n: n for n in expert_names}
        routing["FINISH"] = END

        graph.add_edge(START, "supervisor")
        graph.add_conditional_edges("supervisor", graph_obj._route, routing)
        for name in expert_names:
            graph.add_edge(name, "supervisor")

        return graph.compile()

    @staticmethod
    def _make_real_expert_node(name: str, agent: ExpertAgent) -> Any:
        """Create a real expert execution node."""
        async def node(state: dict) -> dict:
            task = state["task"]
            # Build context from previous results
            prev_results = state.get("agent_results", {})
            context = "\n".join(f"{k}: {v[:300]}" for k, v in prev_results.items()) if prev_results else ""

            result = await agent.run(task, context=context)

            agent_results = dict(state.get("agent_results", {}))
            agent_results[name] = result

            history = list(state.get("delegation_history", []))
            history.append({
                "from_agent": "supervisor",
                "to_agent": name,
                "task": task[:200],
                "result": result[:300],
            })

            return {
                "agent_results": agent_results,
                "delegation_history": history,
                "messages": [AIMessage(content=f"[{name}] {result}")],
            }

        return node

    async def execute(self, request: AgentRequest) -> AgentResponse:
        """Non-streaming supervisor execution."""
        start = time.perf_counter()
        compiled, _ = self._build_graph(request)

        initial_state = {
            "task": request.message,
            "current_agent": None,
            "agent_results": {},
            "delegation_history": [],
            "next_action": "",
            "iteration_count": 0,
            "messages": [HumanMessage(content=request.message)],
        }

        result = await compiled.ainvoke(initial_state)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Aggregate results
        answers = result.get("agent_results", {})
        combined = "\n\n".join(f"**{k}**:\n{v}" for k, v in answers.items())

        steps = []
        for d in result.get("delegation_history", []):
            steps.append(AgentStep(
                step_type="delegation",
                content=f"{d['from_agent']} → {d['to_agent']}: {d['result'][:200]}",
            ))

        return AgentResponse(
            session_id=request.session_id,
            answer=combined or "Task completed by expert team.",
            strategy=AgentStrategy.SUPERVISOR,
            steps=steps,
            total_latency_ms=round(elapsed_ms, 2),
        )

    async def execute_stream(self, request: AgentRequest) -> AsyncIterator[StreamEvent]:
        """Streaming supervisor execution."""
        compiled, experts = self._build_graph(request)

        initial_state = {
            "task": request.message,
            "current_agent": None,
            "agent_results": {},
            "delegation_history": [],
            "next_action": "",
            "iteration_count": 0,
            "messages": [HumanMessage(content=request.message)],
        }

        yield StreamEvent(
            event=StreamEventType.THOUGHT,
            data={"content": f"Supervisor analyzing task, available experts: {', '.join(experts.keys())}"},
            session_id=request.session_id,
        )

        token_count = 0
        start = time.perf_counter()
        seen_delegations: set[str] = set()

        try:
            async for event in compiled.astream_events(initial_state, version="v2"):
                kind = event.get("event", "")
                name = event.get("name", "")

                # ── Supervisor deciding ──
                if kind == "on_chain_start" and name == "supervisor":
                    yield StreamEvent(
                        event=StreamEventType.THOUGHT,
                        data={"content": "Supervisor deciding next expert..."},
                        session_id=request.session_id,
                    )

                # ── Expert delegation start ──
                elif kind == "on_chain_start" and name in experts:
                    delegation_key = f"{name}_{time.time()}"
                    if delegation_key not in seen_delegations:
                        seen_delegations.add(delegation_key)
                        yield StreamEvent(
                            event=StreamEventType.ACTION,
                            data={
                                "content": f"Delegating to {name}: {experts[name].description}",
                                "agent": name,
                            },
                            session_id=request.session_id,
                        )

                # ── Expert result ──
                elif kind == "on_chain_end" and name in experts:
                    output = event.get("data", {}).get("output", {})
                    results = output.get("agent_results", {})
                    if name in results:
                        yield StreamEvent(
                            event=StreamEventType.OBSERVATION,
                            data={
                                "content": results[name][:500],
                                "agent": name,
                            },
                            session_id=request.session_id,
                        )

                # ── LLM token streaming ──
                elif kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        token_count += 1
                        yield StreamEvent(
                            event=StreamEventType.TOKEN,
                            data={"content": chunk.content},
                            session_id=request.session_id,
                        )

                # ── Tool calls within experts ──
                elif kind == "on_tool_start":
                    yield StreamEvent(
                        event=StreamEventType.TOOL_CALL,
                        data={
                            "tool_name": event.get("name", "unknown"),
                            "tool_input": event.get("data", {}).get("input", {}),
                            "content": f"Expert using tool: {event.get('name', 'unknown')}",
                        },
                        session_id=request.session_id,
                    )
                elif kind == "on_tool_end":
                    output = event.get("data", {}).get("output", "")
                    output_str = str(output.content) if hasattr(output, "content") else str(output)
                    yield StreamEvent(
                        event=StreamEventType.TOOL_RESULT,
                        data={"tool_name": event.get("name", "unknown"), "output": output_str[:500], "content": output_str[:500]},
                        session_id=request.session_id,
                    )

        except Exception as e:
            await logger.aerror("supervisor_error", error=str(e))
            yield StreamEvent(
                event=StreamEventType.ERROR,
                data={"content": f"Supervisor execution failed: {e}"},
                session_id=request.session_id,
            )
            return

        elapsed_ms = (time.perf_counter() - start) * 1000
        yield StreamEvent(
            event=StreamEventType.DONE,
            data={
                "strategy": AgentStrategy.SUPERVISOR.value,
                "token_count": token_count,
                "latency_ms": round(elapsed_ms, 2),
            },
            session_id=request.session_id,
        )
