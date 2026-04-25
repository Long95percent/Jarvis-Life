"""Unified Agent Engine — routes tasks to the optimal strategy.

The TaskComplexityRouter analyzes incoming requests and dispatches to:
  - Direct LLM call (simple queries)
  - ReAct loop (moderate, tool-augmented tasks)
  - Plan-and-Execute (complex multi-step tasks)
  - MultiAgent supervisor (multi-domain tasks)

Memory integration:
  - Injects short-term, long-term, and episodic context before execution
  - Records episodes after execution for experience-based learning
  - Persists conversation messages to short-term memory
"""

from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING, Any, AsyncIterator

import structlog
from langchain_core.messages import AIMessage, HumanMessage

from app.config import settings
from app.core.dependencies import get_resource
from app.models.agent import AgentRequest, AgentResponse, AgentStep, AgentStrategy, TaskComplexity
from app.models.common import StreamEvent, StreamEventType

if TYPE_CHECKING:
    from app.llm.client import LLMClient

logger = structlog.get_logger("agent.engine")

# ── Mode-specific system prompts (ambient work mode isolation) ──
MODE_SYSTEM_PROMPTS: dict[str, str] = {
    "general": (
        "You are ShadowLink AI, a helpful and versatile assistant. "
        "Answer questions clearly and concisely."
    ),
    "code-dev": (
        "You are ShadowLink AI in Code Development mode. "
        "You are an expert software engineer. Write clean, well-structured code. "
        "Explain technical concepts precisely. Follow best practices and design patterns. "
        "When analyzing code, consider performance, security, and maintainability."
    ),
    "paper-reading": (
        "You are ShadowLink AI in Paper Reading mode. "
        "You are an academic research assistant. Help analyze, summarize, and explain "
        "research papers. Extract key findings, methodology, and implications. "
        "Use formal academic language and cite relevant concepts."
    ),
    "creative-writing": (
        "You are ShadowLink AI in Creative Writing mode. "
        "You are a creative writing assistant. Help with storytelling, content creation, "
        "copywriting, and creative expression. Be imaginative and inspiring. "
        "Adapt your writing style to match the user's needs."
    ),
    "data-analysis": (
        "You are ShadowLink AI in Data Analysis mode. "
        "You are a data analyst. Help interpret data, suggest analysis approaches, "
        "write queries, and explain statistical concepts clearly. "
        "Be precise with numbers and methodology."
    ),
    "project-management": (
        "You are ShadowLink AI in Project Management mode. "
        "You help organize tasks, plan projects, track progress, and manage workflows. "
        "Be structured, action-oriented, and focus on deliverables. "
        "Break down complex goals into actionable steps."
    ),
}

# ── Mode-specific strategy preferences ──
MODE_STRATEGY_OVERRIDES: dict[str, dict[TaskComplexity, AgentStrategy]] = {
    "code-dev": {
        TaskComplexity.MODERATE: AgentStrategy.REACT,  # Always use tools for code
    },
    "data-analysis": {
        TaskComplexity.MODERATE: AgentStrategy.REACT,  # Calculator + code executor
    },
    "project-management": {
        TaskComplexity.MODERATE: AgentStrategy.PLAN_EXECUTE,  # PM tasks benefit from planning
        TaskComplexity.COMPLEX: AgentStrategy.PLAN_EXECUTE,
    },
}

# ── Mode-specific tool restrictions ──
MODE_PREFERRED_TOOLS: dict[str, list[str]] = {
    "code-dev": ["code_executor", "file_reader", "web_search", "knowledge_search"],
    "paper-reading": ["knowledge_search", "web_search", "file_reader"],
    "creative-writing": ["web_search", "knowledge_search"],
    "data-analysis": ["code_executor", "calculator", "knowledge_search", "file_reader"],
    "project-management": ["current_time", "calculator", "knowledge_search"],
    "general": [],  # All tools available
}


class TaskComplexityRouter:
    """Classifies task complexity and selects the optimal agent strategy.

    Classification is done CPU-only in <5ms using heuristics:
    - Token count and structural analysis
    - Keyword detection (multi-step indicators, tool references)
    - Mode-specific routing rules
    """

    COMPLEXITY_STRATEGY_MAP: dict[TaskComplexity, AgentStrategy] = {
        TaskComplexity.SIMPLE: AgentStrategy.DIRECT,
        TaskComplexity.MODERATE: AgentStrategy.REACT,
        TaskComplexity.COMPLEX: AgentStrategy.PLAN_EXECUTE,
        TaskComplexity.MULTI_DOMAIN: AgentStrategy.SUPERVISOR,
    }

    PLAN_INDICATORS = frozenset({
        "step by step", "first", "then", "finally", "plan", "analyze",
        "compare", "research", "report", "summarize multiple", "逐步", "分析",
        "对比", "研究", "报告", "计划", "详细",
    })

    MULTI_DOMAIN_INDICATORS = frozenset({
        "code and write", "review and fix", "search and summarize",
        "代码", "写作", "搜索", "分析并", "既要", "同时",
    })

    TOOL_INDICATORS = frozenset({
        "search", "calculate", "run code", "execute", "file", "read",
        "搜索", "计算", "执行", "运行", "文件",
    })

    def classify(self, request: AgentRequest) -> TaskComplexity:
        """Classify task complexity based on message content and mode."""
        message = request.message.lower()
        word_count = len(message.split())

        # Short, simple queries
        if word_count < 15 and not any(kw in message for kw in self.PLAN_INDICATORS):
            # Even short queries may need tools
            if any(kw in message for kw in self.TOOL_INDICATORS):
                return TaskComplexity.MODERATE
            return TaskComplexity.SIMPLE

        # Multi-domain detection
        if any(kw in message for kw in self.MULTI_DOMAIN_INDICATORS):
            return TaskComplexity.MULTI_DOMAIN

        # Plan-level complexity
        if any(kw in message for kw in self.PLAN_INDICATORS) or word_count > 80:
            return TaskComplexity.COMPLEX

        return TaskComplexity.MODERATE

    def select_strategy(self, request: AgentRequest) -> AgentStrategy:
        """Select the best strategy, respecting explicit overrides and mode preferences."""
        if request.strategy is not None:
            return request.strategy

        if not settings.agent.complexity_router_enabled:
            return AgentStrategy(settings.agent.default_strategy)

        complexity = self.classify(request)

        # Check mode-specific overrides
        mode_overrides = MODE_STRATEGY_OVERRIDES.get(request.mode_id, {})
        if complexity in mode_overrides:
            return mode_overrides[complexity]

        return self.COMPLEXITY_STRATEGY_MAP[complexity]


class AgentEngine:
    """Top-level agent engine that dispatches to strategy-specific executors.

    Integrates memory systems:
    - Before execution: injects context from short/long/episodic memory
    - After execution: records conversation and episodes
    """

    def __init__(self) -> None:
        self.router = TaskComplexityRouter()
        self._strategy_executors: dict[AgentStrategy, Any] = {}

    def register_strategy(self, strategy: AgentStrategy, executor: Any) -> None:
        """Register a strategy executor (called during lifespan startup)."""
        self._strategy_executors[strategy] = executor

    def _get_memory_context(self, request: AgentRequest) -> dict[str, Any]:
        """Gather context from all memory systems for the request."""
        context: dict[str, Any] = {}

        short_term = get_resource("short_term_memory")
        if short_term:
            ctx = short_term.to_context(request.session_id)
            context.update(ctx)

        long_term = get_resource("long_term_memory")
        if long_term:
            ctx = long_term.to_context(query=request.message)
            context.update(ctx)

        episodic = get_resource("episodic_memory")
        if episodic:
            ctx = episodic.to_context(task=request.message)
            context.update(ctx)

        return context

    def _record_message(self, request: AgentRequest) -> None:
        """Record the user message in short-term memory."""
        short_term = get_resource("short_term_memory")
        if short_term:
            short_term.add(request.session_id, HumanMessage(content=request.message))

    def _record_response(self, request: AgentRequest, answer: str) -> None:
        """Record the assistant response in short-term memory."""
        short_term = get_resource("short_term_memory")
        if short_term:
            short_term.add(request.session_id, AIMessage(content=answer[:500]))

    def _record_episode(self, request: AgentRequest, strategy: AgentStrategy, answer: str, success: bool, latency_ms: float) -> None:
        """Record execution episode for experience-based learning."""
        episodic = get_resource("episodic_memory")
        if episodic:
            from app.agent.memory.episodic import Episode
            episode = Episode(
                episode_id=f"ep-{uuid.uuid4().hex[:8]}",
                task=request.message[:300],
                strategy=strategy.value,
                steps=[],
                outcome=answer[:200],
                success=success,
                metadata={"mode_id": request.mode_id, "latency_ms": latency_ms},
            )
            episodic.record(episode)

    def _get_llm_client(self, request: AgentRequest) -> LLMClient:
        """Get LLM client with potential overrides from request context."""
        client: LLMClient = get_resource("llm_client")
        
        # If frontend passed explicit LLM config, create a temporary provider
        llm_config = (request.context or {}).get("llm_config")
        if llm_config and client:
            from app.llm.providers.openai import OpenAIProvider
            # Create a one-off provider with the user's config
            custom_provider = OpenAIProvider(
                base_url=llm_config.get("baseUrl"),
                api_key=llm_config.get("apiKey"),
                default_model=llm_config.get("model"),
            )
            # Create a thin wrapper client that uses this provider
            from app.llm.client import LLMClient as ClientClass
            temp_client = ClientClass()
            temp_client._default_provider = custom_provider
            temp_client._providers["openai"] = custom_provider
            return temp_client
            
        return client

    def _inject_resources_to_tools(self, executor: Any, request: AgentRequest):
        """Inject mode resources into tools like local_search."""
        resources = (request.context or {}).get("resources", [])
        if hasattr(executor, "tools"):
            for tool in executor.tools:
                if tool.name == "local_search":
                    tool.context_resources = resources

    async def execute(self, request: AgentRequest) -> AgentResponse:
        """Execute agent task with memory integration."""
        strategy = self.router.select_strategy(request)
        await logger.ainfo(
            "agent_execute",
            session_id=request.session_id,
            strategy=strategy.value,
            mode_id=request.mode_id,
        )

        self._record_message(request)

        executor = self._strategy_executors.get(strategy)
        if executor is None:
            return AgentResponse(
                session_id=request.session_id,
                answer=f"[{strategy.value}] Strategy not registered.",
                strategy=strategy,
                steps=[AgentStep(step_type="error", content=f"Strategy {strategy.value} not available")],
            )

        # Inject custom LLM client if configured
        llm_client = self._get_llm_client(request)
        if hasattr(executor, "llm_client"):
            executor.llm_client = llm_client
            
        # Filter tools if enabled_tools is explicitly passed from frontend
        enabled_tools = (request.context or {}).get("enabled_tools")
        if enabled_tools is not None and hasattr(executor, "tools"):
            # Only keep tools that are in the enabled_tools list (and always keep local_search if we have resources)
            filtered_tools = [t for t in getattr(executor, "tools", []) if t.name in enabled_tools or t.name == "local_search"]
            executor.tools = filtered_tools

        # Inject resources into tools
        self._inject_resources_to_tools(executor, request)

        start = time.perf_counter()
        response = await executor.execute(request)
        latency = (time.perf_counter() - start) * 1000

        self._record_response(request, response.answer)
        self._record_episode(request, strategy, response.answer, True, latency)

        return response

    async def execute_stream(self, request: AgentRequest) -> AsyncIterator[StreamEvent]:
        """Execute agent task with streaming and memory integration."""
        strategy = self.router.select_strategy(request)
        await logger.ainfo(
            "agent_stream_start",
            session_id=request.session_id,
            strategy=strategy.value,
            mode_id=request.mode_id,
        )

        self._record_message(request)

        # Inject memory context into request
        memory_context = self._get_memory_context(request)
        if memory_context:
            request.context = {**(request.context or {}), "memory": memory_context}

        executor = self._strategy_executors.get(strategy)
        if executor is None:
            yield StreamEvent(
                event=StreamEventType.THOUGHT,
                data={"content": f"Routed to {strategy.value} strategy"},
                session_id=request.session_id,
            )
            yield StreamEvent(
                event=StreamEventType.TOKEN,
                data={"content": f"Strategy [{strategy.value}] not yet registered."},
                session_id=request.session_id,
            )
            yield StreamEvent(
                event=StreamEventType.DONE,
                data={"strategy": strategy.value},
                session_id=request.session_id,
            )
            return

        # Inject custom LLM client if configured
        llm_client = self._get_llm_client(request)
        if hasattr(executor, "llm_client"):
            executor.llm_client = llm_client
            
        # Filter tools if enabled_tools is explicitly passed from frontend
        enabled_tools = (request.context or {}).get("enabled_tools")
        if enabled_tools is not None and hasattr(executor, "tools"):
            # Only keep tools that are in the enabled_tools list (and always keep local_search if we have resources)
            filtered_tools = [t for t in getattr(executor, "tools", []) if t.name in enabled_tools or t.name == "local_search"]
            executor.tools = filtered_tools

        # Inject resources into tools
        self._inject_resources_to_tools(executor, request)

        full_answer = ""
        start = time.perf_counter()

        # Execute and yield events directly
        try:
            async for event in executor.execute_stream(request):
                # Collect answer for memory recording
                if event.event == StreamEventType.TOKEN:
                    full_answer += event.data.get("content", "")
                yield event
                
            latency = (time.perf_counter() - start) * 1000
            self._record_response(request, full_answer)
            self._record_episode(request, strategy, full_answer, True, latency)
            
        except Exception as e:
            logger.error(f"Stream execution failed: {e}")
            yield StreamEvent(
                event=StreamEventType.ERROR,
                data={"content": f"Stream failed: {e}"},
                session_id=request.session_id,
            )


class DirectExecutor:
    """DIRECT strategy — simple LLM call without agent loop or tools.

    Used for straightforward queries that don't need planning or tool use.
    Streams tokens as they arrive from the LLM provider.
    """

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm_client = llm_client

    def _get_system_prompt(self, request: AgentRequest) -> str:
        # 1. Check if user configured a custom system prompt in the frontend mode settings
        custom_prompt = (request.context or {}).get("system_prompt")
        if custom_prompt and str(custom_prompt).strip():
            return str(custom_prompt).strip()
            
        # 2. Fallback to the built-in default prompt for the mode
        return MODE_SYSTEM_PROMPTS.get(request.mode_id, MODE_SYSTEM_PROMPTS["general"])

    def _build_prompt_with_memory(self, request: AgentRequest) -> str:
        """Build system prompt enhanced with memory context."""
        base = self._get_system_prompt(request)

        memory = (request.context or {}).get("memory", {})
        if not memory:
            return base

        parts = [base, "\n\n--- Relevant Context ---"]
        if "short_term" in memory:
            parts.append(f"Recent conversation:\n{memory['short_term']}")
        if "long_term" in memory:
            parts.append(f"Remembered knowledge:\n{memory['long_term']}")
        if "episodic" in memory:
            parts.append(f"Past experience:\n{memory['episodic']}")
        parts.append("--- End Context ---")
        return "\n".join(parts)

    async def execute(self, request: AgentRequest) -> AgentResponse:
        """Non-streaming direct LLM call."""
        start = time.perf_counter()
        response = await self.llm_client.chat(
            message=request.message,
            system_prompt=self._build_prompt_with_memory(request),
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        return AgentResponse(
            session_id=request.session_id,
            answer=response,
            strategy=AgentStrategy.DIRECT,
            steps=[AgentStep(step_type="answer", content=response)],
            total_latency_ms=round(elapsed_ms, 2),
        )

    async def execute_stream(self, request: AgentRequest) -> AsyncIterator[StreamEvent]:
        """Streaming direct LLM call — yields TOKEN events as they arrive."""
        yield StreamEvent(
            event=StreamEventType.THOUGHT,
            data={"content": "Processing your request..."},
            session_id=request.session_id,
        )

        full_content = ""
        token_count = 0
        start = time.perf_counter()

        try:
            async for token in self.llm_client.chat_stream(
                message=request.message,
                system_prompt=self._build_prompt_with_memory(request),
            ):
                full_content += token
                token_count += 1
                yield StreamEvent(
                    event=StreamEventType.TOKEN,
                    data={"content": token},
                    session_id=request.session_id,
                )
        except Exception as e:
            await logger.aerror("direct_executor_error", error=str(e))
            yield StreamEvent(
                event=StreamEventType.ERROR,
                data={"content": f"LLM call failed: {e}"},
                session_id=request.session_id,
            )
            return

        elapsed_ms = (time.perf_counter() - start) * 1000
        yield StreamEvent(
            event=StreamEventType.DONE,
            data={
                "strategy": AgentStrategy.DIRECT.value,
                "token_count": token_count,
                "latency_ms": round(elapsed_ms, 2),
            },
            session_id=request.session_id,
        )
