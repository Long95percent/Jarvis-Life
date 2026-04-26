"""Application lifespan management: startup and shutdown hooks.

Initializes all core subsystems in order:
  1. LLM Client
  2. Tool Registry (6 built-in tools)
  3. MCP Client (external tool servers)
  4. Memory Systems (short-term, long-term, episodic, semantic)
  5. RAG Engine (embeddings + FAISS + reranker)
  6. Agent Engine (DIRECT + REACT + PLAN_EXECUTE + SUPERVISOR strategies)
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, AsyncIterator

import structlog
from fastapi import FastAPI

from app.config import settings
from app.core.dependencies import set_resource

if TYPE_CHECKING:
    from app.jarvis.preference_learner import PreferenceLearner
    from app.jarvis.proactive_engine import ProactiveTriggerEngine

logger = structlog.get_logger("lifespan")

# Module-level proactive engine singleton (initialized during startup).
_proactive_engine: "ProactiveTriggerEngine | None" = None
# Module-level Shadow preference-learner singleton (initialized during startup).
_preference_learner: "PreferenceLearner | None" = None


def get_proactive_engine() -> "ProactiveTriggerEngine | None":
    """Return the active ProactiveTriggerEngine, or None before startup."""
    return _proactive_engine


def get_preference_learner() -> "PreferenceLearner | None":
    """Return the active PreferenceLearner, or None before startup."""
    return _preference_learner


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan context manager."""
    await logger.ainfo("startup_begin", env=settings.env, version=settings.version)

    # ── Ensure data directories ──
    for dir_path in [
        settings.data_dir,
        settings.rag.faiss_index_path,
        settings.memory.long_term_storage_path,
        settings.file_processing.upload_dir,
    ]:
        Path(dir_path).mkdir(parents=True, exist_ok=True)

    # ── 1. Initialize LLM Client ──
    try:
        from app.api.v1.settings_router import _load_providers

        provider_data = _load_providers()
        active_id = provider_data.get("active_id")
        active_provider = next(
            (provider for provider in provider_data.get("providers", []) if provider.get("id") == active_id),
            None,
        )
        if active_provider is not None:
            settings.llm.base_url = active_provider["base_url"]
            settings.llm.api_key = active_provider.get("api_key", "")
            settings.llm.model = active_provider["model"]
            settings.llm.temperature = active_provider.get("temperature", settings.llm.temperature)
            settings.llm.max_tokens = active_provider.get("max_tokens", settings.llm.max_tokens)
            await logger.ainfo(
                "llm_active_provider_loaded",
                provider=active_provider.get("name"),
                provider_id=active_id,
                model=settings.llm.model,
                base_url=settings.llm.base_url,
            )
    except Exception as exc:
        await logger.awarning("llm_active_provider_load_failed", error=str(exc))

    from app.llm.client import LLMClient

    llm_client = LLMClient()
    llm_client.initialize()
    set_resource("llm_client", llm_client)
    await logger.ainfo("llm_client_ready", model=settings.llm.model, base_url=settings.llm.base_url)

    # ── 2. Initialize Tool Registry ──
    from app.mcp.registry import ToolRegistry
    from app.tools.code_executor import CodeExecutorTool
    from app.tools.file_ops import FileReadTool
    from app.tools.jarvis_tools import (
        JarvisActivitiesTool,
        JarvisActivityRankByEnergyTool,
        JarvisCalendarAddTool,
        JarvisCalendarDeleteTool,
        JarvisCalendarFindFreeSlotTool,
        JarvisCalendarUpcomingTool,
        JarvisCalendarUpdateTool,
        JarvisBreathingProtocolTool,
        JarvisBurnoutRiskAssessTool,
        JarvisCheckinScheduleTool,
        JarvisContextUpdateTool,
        JarvisContextSnapshotTool,
        JarvisCaffeineCutoffGuardTool,
        JarvisDailyBriefingTool,
        JarvisDeadlineCheckTool,
        JarvisHydrationPlanTool,
        JarvisMealPlanTool,
        JarvisMeetingBriefTool,
        JarvisMoodJournalTool,
        JarvisNewsDigestTool,
        JarvisNutritionLookupTool,
        JarvisPlanActivitySlotTool,
        JarvisRouteEstimateTool,
        JarvisSpecialistOrchestrateTool,
        JarvisTaskPlanDecomposeTool,
        JarvisTaskPrioritizeTool,
        JarvisWeatherTool,
    )
    from app.tools.knowledge_search import KnowledgeSearchTool
    from app.tools.local_search import LocalSearchTool
    from app.tools.system_tools import CalculatorTool, CurrentTimeTool
    from app.tools.web_search import WebSearchTool

    tool_registry = ToolRegistry()

    builtin_tools = [
        CurrentTimeTool(),
        CalculatorTool(),
        WebSearchTool(),
        CodeExecutorTool(),
        FileReadTool(),
        KnowledgeSearchTool(),
        LocalSearchTool(),
        JarvisContextSnapshotTool(),
        JarvisCalendarUpcomingTool(),
        JarvisCalendarAddTool(),
        JarvisCalendarDeleteTool(),
        JarvisCalendarUpdateTool(),
        JarvisMeetingBriefTool(),
        JarvisTaskPlanDecomposeTool(),
        JarvisTaskPrioritizeTool(),
        JarvisDeadlineCheckTool(),
        JarvisCalendarFindFreeSlotTool(),
        JarvisCheckinScheduleTool(),
        JarvisBreathingProtocolTool(),
        JarvisMoodJournalTool(),
        JarvisBurnoutRiskAssessTool(),
        JarvisContextUpdateTool(),
        JarvisMealPlanTool(),
        JarvisNutritionLookupTool(),
        JarvisHydrationPlanTool(),
        JarvisCaffeineCutoffGuardTool(),
        JarvisDailyBriefingTool(),
        JarvisWeatherTool(),
        JarvisActivitiesTool(),
        JarvisActivityRankByEnergyTool(),
        JarvisRouteEstimateTool(),
        JarvisPlanActivitySlotTool(),
        JarvisNewsDigestTool(),
        JarvisSpecialistOrchestrateTool(),
    ]

    for tool in builtin_tools:
        tool_registry.register(tool.to_tool_info(), tool)

    set_resource("tool_registry", tool_registry)
    await logger.ainfo("tool_registry_ready", tools=tool_registry.tool_count)

    # ── 3. Initialize MCP Client ──
    from app.mcp.client import MCPClient

    mcp_client = MCPClient()
    set_resource("mcp_client", mcp_client)
    await logger.ainfo("mcp_client_ready")

    # ── 4. Initialize Memory Systems (Letta-inspired 3-layer + semantic) ──
    from app.agent.memory.short_term import ShortTermMemory
    from app.agent.memory.long_term import LongTermMemory
    from app.agent.memory.episodic import EpisodicMemory
    from app.agent.memory.semantic import SemanticMemory

    short_term_memory = ShortTermMemory(
        max_messages=settings.memory.short_term_max_messages,
    )
    long_term_memory = LongTermMemory(
        storage_path=settings.memory.long_term_storage_path,
    )
    episodic_memory = EpisodicMemory(
        storage_path=settings.memory.long_term_storage_path,
    )
    semantic_memory = SemanticMemory(
        storage_path=settings.memory.long_term_storage_path,
    )

    set_resource("short_term_memory", short_term_memory)
    set_resource("long_term_memory", long_term_memory)
    set_resource("episodic_memory", episodic_memory)
    set_resource("semantic_memory", semantic_memory)
    await logger.ainfo(
        "memory_ready",
        short_term_max=settings.memory.short_term_max_messages,
        long_term_entries=len(long_term_memory._memories),
        episodic_episodes=len(episodic_memory._episodes),
        semantic_nodes=semantic_memory.node_count,
    )

    # ── 5. Initialize RAG Engine ──
    from app.rag.engine import RAGEngine

    rag_engine = RAGEngine()
    set_resource("rag_engine", rag_engine)
    await logger.ainfo("rag_engine_ready")

    # ── 6. Initialize Agent Engine — all 4 strategies ──
    from app.agent.engine import AgentEngine, DirectExecutor
    from app.agent.react.executor import ReactExecutor
    from app.agent.plan_execute.stream_executor import PlanExecuteExecutor
    from app.agent.multi_agent.executor import SupervisorExecutor
    from app.models.agent import AgentStrategy

    agent_engine = AgentEngine()

    # DIRECT: simple LLM call (fast, no tools)
    direct_executor = DirectExecutor(llm_client=llm_client)
    agent_engine.register_strategy(AgentStrategy.DIRECT, direct_executor)

    # REACT: reasoning loop with tools
    react_executor = ReactExecutor(llm_client=llm_client, tools=builtin_tools)
    agent_engine.register_strategy(AgentStrategy.REACT, react_executor)

    # PLAN_EXECUTE: plan → step-by-step execution → replan on failure
    plan_executor = PlanExecuteExecutor(llm_client=llm_client, tools=builtin_tools)
    agent_engine.register_strategy(AgentStrategy.PLAN_EXECUTE, plan_executor)

    # SUPERVISOR: multi-agent expert delegation
    supervisor_executor = SupervisorExecutor(llm_client=llm_client, tools=builtin_tools)
    agent_engine.register_strategy(AgentStrategy.SUPERVISOR, supervisor_executor)

    set_resource("agent_engine", agent_engine)
    await logger.ainfo(
        "agent_engine_ready",
        strategies=list(agent_engine._strategy_executors.keys()),
    )

    # ── 7. Initialize JARVIS Proactive Trigger Engine ──
    global _proactive_engine
    from app.jarvis.context_bus import get_life_context_bus
    from app.jarvis.proactive_engine import ProactiveTriggerEngine
    from app.jarvis.shadow_roundtable import ShadowRoundtable

    _proactive_engine = ProactiveTriggerEngine(
        roundtable=ShadowRoundtable(llm_client=llm_client),
        context_bus=get_life_context_bus(),
    )
    asyncio.create_task(_proactive_engine.start())
    await logger.ainfo("jarvis_proactive_engine_ready")

    # ── 8. Initialize Shadow Preference Learner ──
    global _preference_learner
    from app.jarvis.preference_learner import PreferenceLearner

    _preference_learner = PreferenceLearner(llm_client=llm_client)
    await logger.ainfo("jarvis_preference_learner_ready")

    # ── 9. Rehydrate Jarvis state from SQLite ──
    # Restore LifeContext to its last-known value + reload recent roundtable
    # sessions so /roundtable/continue works for IDs from before the restart.
    try:
        from app.jarvis.persistence import latest_context
        from app.jarvis.roundtable_sessions import rehydrate_from_disk

        snap = await latest_context()
        if snap:
            await get_life_context_bus().update_fields(
                {
                    "stress_level": snap["stress_level"],
                    "schedule_density": snap["schedule_density"],
                    "sleep_quality": snap["sleep_quality"],
                    "mood_trend": snap["mood_trend"],
                },
                source="rehydrate",
            )
            await logger.ainfo(
                "jarvis_context_rehydrated",
                stress=snap["stress_level"],
                mood=snap["mood_trend"],
            )

        restored = await rehydrate_from_disk(limit=50)
        await logger.ainfo("jarvis_sessions_rehydrated", count=restored)
    except Exception as exc:
        await logger.awarning("jarvis_rehydrate_failed", error=str(exc))

    await logger.ainfo("startup_complete", message="All resources initialized")

    yield  # ── Application runs here ──

    # ── Shutdown ──
    await logger.ainfo("shutdown_begin")

    # Stop JARVIS proactive engine
    if _proactive_engine is not None:
        _proactive_engine.stop()

    # Persist RAG indices
    if rag_engine and rag_engine._index_manager:
        rag_engine._index_manager.save_all()
        await logger.ainfo("rag_indices_saved")

    # Persist long-term memory
    long_term_memory._save()
    episodic_memory._save()

    # Disconnect MCP servers
    await mcp_client.disconnect_all()

    await logger.ainfo("shutdown_complete")
