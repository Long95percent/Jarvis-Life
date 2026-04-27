import tempfile
import time
from pathlib import Path

import pytest

from app.api.v1 import jarvis_router
from app.api.v1.jarvis_router import AgentChatRequest
from app.jarvis import persistence
from app.jarvis.memory_compactor import compact_old_raw_memories, maybe_compact_old_raw_memories
from app.jarvis.memory_recall import build_bounded_memory_recall_prefix


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    tmp = Path(tempfile.mkdtemp()) / "jarvis.db"
    monkeypatch.setattr(persistence, "_DB_PATH", tmp)
    persistence._initialized = False
    yield tmp
    persistence._initialized = False


@pytest.mark.asyncio
async def test_save_jarvis_memory_persists_lifecycle_metadata():
    item = await persistence.save_jarvis_memory(
        memory_kind="mood_signal",
        content="用户最近压力偏高，但不希望被频繁追问。",
        source_agent="mira",
        session_id="session-memory-meta",
        source_text="最近压力大，别一直问我。",
        sensitivity="private",
        confidence=0.8,
        importance=0.9,
        memory_tier="raw",
        visibility="private_raw",
        owner_agent_id="mira",
        allowed_agent_ids=["mira"],
        decay_score=0.2,
    )

    assert item["memory_tier"] == "raw"
    assert item["visibility"] == "private_raw"
    assert item["owner_agent_id"] == "mira"
    assert item["allowed_agent_ids"] == ["mira"]
    assert item["compressed_from_ids"] == []
    assert item["access_count"] == 0
    assert item["last_accessed_at"] is None


@pytest.mark.asyncio
async def test_bounded_recall_shares_global_and_summary_but_not_private_raw():
    await persistence.save_jarvis_memory(
        memory_kind="mood_signal",
        content="心理倾诉原文：我最近压力大到崩溃，不想见任何人。",
        source_agent="mira",
        sensitivity="private",
        importance=0.99,
        memory_tier="raw",
        visibility="private_raw",
        owner_agent_id="mira",
        allowed_agent_ids=["mira"],
    )
    await persistence.save_jarvis_memory(
        memory_kind="mood_signal",
        content="近期压力偏高，跨角色建议只使用低刺激、低负担支持。",
        source_agent="mira",
        sensitivity="private",
        importance=0.9,
        memory_tier="condensed",
        visibility="sensitive_summary",
        owner_agent_id="mira",
        allowed_agent_ids=["mira", "nora"],
    )
    await persistence.save_jarvis_memory(
        memory_kind="constraint",
        content="用户不吃海鲜。",
        source_agent="nora",
        sensitivity="normal",
        importance=0.86,
        memory_tier="raw",
        visibility="global",
        owner_agent_id="nora",
    )

    prefix = await build_bounded_memory_recall_prefix("nora", "我今天压力大，晚饭吃什么？", limit=6)

    assert "用户不吃海鲜" in prefix
    assert "近期压力偏高" in prefix
    assert "心理倾诉原文" not in prefix


@pytest.mark.asyncio
async def test_bounded_recall_prefers_agent_relevant_memories():
    await persistence.save_jarvis_memory(
        memory_kind="preference",
        content="用户压力大时偏好温热、低刺激、简单食物。",
        source_agent="nora",
        importance=0.9,
        memory_tier="raw",
        visibility="agent_scoped",
        owner_agent_id="nora",
        allowed_agent_ids=["nora"],
    )
    await persistence.save_jarvis_memory(
        memory_kind="preference",
        content="用户偏好上午安排学习任务，晚上只做轻量复盘。",
        source_agent="maxwell",
        importance=0.82,
        memory_tier="raw",
        visibility="agent_scoped",
        owner_agent_id="maxwell",
        allowed_agent_ids=["maxwell"],
    )

    nora_prefix = await build_bounded_memory_recall_prefix("nora", "压力大吃什么？", limit=3)
    maxwell_prefix = await build_bounded_memory_recall_prefix("maxwell", "帮我安排明天学习。", limit=3)

    assert "温热、低刺激" in nora_prefix
    assert "上午安排学习任务" not in nora_prefix
    assert "上午安排学习任务" in maxwell_prefix
    assert "温热、低刺激" not in maxwell_prefix


@pytest.mark.asyncio
async def test_compact_old_raw_memories_archives_raw_and_creates_condensed():
    first = await persistence.save_jarvis_memory(
        memory_kind="mood_signal",
        content="用户连续几天备考压力大，晚上睡不好。",
        source_agent="mira",
        sensitivity="private",
        importance=0.82,
        memory_tier="raw",
        visibility="private_raw",
        owner_agent_id="mira",
        allowed_agent_ids=["mira"],
    )
    second = await persistence.save_jarvis_memory(
        memory_kind="rhythm_signal",
        content="用户最近常熬夜，早上起床困难。",
        source_agent="mira",
        sensitivity="private",
        importance=0.78,
        memory_tier="raw",
        visibility="private_raw",
        owner_agent_id="mira",
        allowed_agent_ids=["mira"],
    )
    old_timestamp = time.time() - 10 * 24 * 60 * 60
    with persistence._conn() as con:
        con.execute("UPDATE jarvis_memories SET created_at = ?, updated_at = ? WHERE id IN (?, ?)", (old_timestamp, old_timestamp, first["id"], second["id"]))
        con.commit()

    result = await compact_old_raw_memories(cutoff_days=7)
    active_memories = await persistence.list_jarvis_memories(limit=20)

    assert result["compacted_count"] == 2
    assert result["condensed_count"] == 1
    assert [item["memory_tier"] for item in active_memories] == ["condensed"]
    assert active_memories[0]["visibility"] == "sensitive_summary"
    assert set(active_memories[0]["compressed_from_ids"]) == {first["id"], second["id"]}
    assert "备考压力" in active_memories[0]["content"]


@pytest.mark.asyncio
async def test_maybe_compact_old_raw_memories_is_interval_limited():
    item = await persistence.save_jarvis_memory(
        memory_kind="long_term_goal",
        content="用户正在准备长期考试。",
        source_agent="maxwell",
        importance=0.8,
        memory_tier="raw",
        visibility="global",
        owner_agent_id="maxwell",
    )
    old_timestamp = time.time() - 10 * 24 * 60 * 60
    with persistence._conn() as con:
        con.execute("UPDATE jarvis_memories SET created_at = ?, updated_at = ? WHERE id = ?", (old_timestamp, old_timestamp, item["id"]))
        con.commit()

    first = await maybe_compact_old_raw_memories(cutoff_days=7, min_interval_seconds=3600, force=True)
    second = await maybe_compact_old_raw_memories(cutoff_days=7, min_interval_seconds=3600)

    assert first["skipped"] is False
    assert first["compacted_count"] == 1
    assert second["skipped"] is True


@pytest.mark.asyncio
async def test_chat_pipeline_uses_bounded_memory_recall(monkeypatch):
    class CapturingLLM:
        def __init__(self):
            self.calls = []

        async def chat(self, **kwargs):
            self.calls.append(kwargs)
            if "严格只输出 JSON" in kwargs.get("message", ""):
                return '{"memories":[]}'
            return "我会按当前可共享记忆来建议。"

    async def no_memory_extract(**kwargs):
        return []

    await persistence.save_jarvis_memory(
        memory_kind="mood_signal",
        content="心理倾诉原文：用户最近压力大到崩溃。",
        source_agent="mira",
        sensitivity="private",
        importance=0.99,
        memory_tier="raw",
        visibility="private_raw",
        owner_agent_id="mira",
        allowed_agent_ids=["mira"],
    )
    await persistence.save_jarvis_memory(
        memory_kind="constraint",
        content="用户不吃海鲜。",
        source_agent="nora",
        sensitivity="normal",
        importance=0.8,
        memory_tier="raw",
        visibility="global",
        owner_agent_id="nora",
    )
    monkeypatch.setattr(jarvis_router, "extract_and_save_chat_memories", no_memory_extract)
    llm = CapturingLLM()

    await jarvis_router.chat_with_agent(
        AgentChatRequest(
            agent_id="nora",
            session_id="session-bounded-memory",
            message="今天压力大，晚饭吃什么？",
        ),
        llm_client=llm,
    )

    final_prompt = llm.calls[-1]["message"]
    assert "长期记忆（有边界共享" in final_prompt
    assert "用户不吃海鲜" in final_prompt
    assert "心理倾诉原文" not in final_prompt
