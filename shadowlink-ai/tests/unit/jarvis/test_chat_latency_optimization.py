import asyncio
import tempfile
import time
from pathlib import Path

import pytest

from app.api.v1 import jarvis_router
from app.core import lifespan
from app.api.v1.jarvis_router import AgentChatRequest
from app.core.dependencies import set_resource
from app.jarvis import persistence
from app.jarvis.agent_consultation import AgentConsultationResult


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    tmp = Path(tempfile.mkdtemp()) / "jarvis.db"
    monkeypatch.setattr(persistence, "_DB_PATH", tmp)
    persistence._initialized = False
    persistence._ensure_initialized()
    set_resource("background_llm_client", None)
    yield tmp
    set_resource("background_llm_client", None)
    persistence._initialized = False


class FastLLM:
    def __init__(self):
        self.calls: list[dict] = []

    async def chat(self, *args, **kwargs):
        self.calls.append({"args": args, "kwargs": kwargs})
        return "已处理。"


class SidecarLLM:
    def __init__(self):
        self.calls: list[dict] = []

    async def chat(self, *args, **kwargs):
        self.calls.append({"args": args, "kwargs": kwargs})
        return '{"memories":[]}'


@pytest.mark.asyncio
async def test_chat_context_prefetch_runs_memory_sources_in_parallel(monkeypatch):
    async def slow_collaboration(*args, **kwargs):
        await asyncio.sleep(0.05)
        return "collaboration"

    async def slow_memory(*args, **kwargs):
        await asyncio.sleep(0.05)
        return "memory"

    async def slow_preferences(*args, **kwargs):
        await asyncio.sleep(0.05)
        return "preferences"

    async def no_consultations(**kwargs):
        return AgentConsultationResult([], "", [])

    monkeypatch.setattr(jarvis_router, "build_collaboration_memory_prefix", slow_collaboration)
    monkeypatch.setattr(jarvis_router, "build_bounded_memory_recall_prefix", slow_memory)
    monkeypatch.setattr(jarvis_router, "build_preference_profile_prefix", slow_preferences)
    monkeypatch.setattr(jarvis_router, "run_agent_consultations", no_consultations)

    response = await jarvis_router.chat_with_agent(
        AgentChatRequest(agent_id="nora", session_id="latency-parallel", message="你好呀，今天还不错"),
        llm_client=FastLLM(),
    )

    memory_span = next(span for span in response.timing["spans"] if span["name"] == "memory_context")
    assert memory_span["duration_ms"] < 110


@pytest.mark.asyncio
async def test_chat_returns_before_background_memory_and_preference_work_finishes(monkeypatch):
    sidecar = SidecarLLM()
    set_resource("background_llm_client", sidecar)
    background_finished = asyncio.Event()

    async def no_consultations(**kwargs):
        return AgentConsultationResult([], "", [])

    async def slow_memory_extract(**kwargs):
        assert kwargs["llm_client"] is sidecar
        await asyncio.sleep(0.08)
        background_finished.set()
        return []

    async def no_compaction(**kwargs):
        return {"skipped": True}

    class SlowPreferenceLearner:
        async def observe(self, **kwargs):
            await asyncio.sleep(0.08)

    monkeypatch.setattr(jarvis_router, "run_agent_consultations", no_consultations)
    monkeypatch.setattr(jarvis_router, "extract_and_save_chat_memories", slow_memory_extract)
    monkeypatch.setattr(jarvis_router, "maybe_compact_old_raw_memories", no_compaction)
    monkeypatch.setattr(jarvis_router, "get_background_llm_client", lambda: sidecar, raising=False)
    monkeypatch.setattr(lifespan, "_preference_learner", SlowPreferenceLearner())

    started = time.perf_counter()
    response = await jarvis_router.chat_with_agent(
        AgentChatRequest(agent_id="nora", session_id="latency-background", message="你好呀，今天还不错"),
        llm_client=FastLLM(),
    )
    elapsed_ms = (time.perf_counter() - started) * 1000

    assert response.content == "已处理。"
    assert elapsed_ms < 80
    assert background_finished.is_set() is False

    await asyncio.wait_for(background_finished.wait(), timeout=1)


@pytest.mark.asyncio
async def test_chat_stream_events_emit_real_step_events_before_result(monkeypatch):
    async def no_consultations(**kwargs):
        return AgentConsultationResult([], "", [])

    async def no_background(**kwargs):
        return None

    monkeypatch.setattr(jarvis_router, "run_agent_consultations", no_consultations)
    monkeypatch.setattr(jarvis_router, "_run_chat_background_tasks", no_background)

    events = []
    async for event in jarvis_router._chat_stream_events(
        AgentChatRequest(agent_id="nora", session_id="latency-stream", message="你好呀，今天还不错"),
        FastLLM(),
    ):
        events.append(event)

    event_names = [item["event"] for item in events]
    assert event_names[0] == "chat_status"
    assert "chat_step" in event_names
    assert event_names[-2:] == ["chat_result", "chat_done"]
    step_events = [item for item in events if item["event"] == "chat_step"]
    assert '"status": "running"' in step_events[0]["data"]
    assert '"id": "route_decided"' in step_events[0]["data"]
    route_done = next(item for item in step_events if '"id": "route_decided"' in item["data"] and '"status": "done"' in item["data"])
    assert '"duration_ms"' in route_done["data"]
    assert '"label"' in route_done["data"]
    result_event = next(item for item in events if item["event"] == "chat_result")
    assert "已处理" in result_event["data"]
