import asyncio
from pathlib import Path
from uuid import uuid4

from app.jarvis import persistence
from app.jarvis.memory_extractor import (
    build_memory_recall_prefix,
    extract_and_save_chat_memories,
    extract_memory_candidates_with_llm,
    extract_memory_candidates,
)


class FakeLLM:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error

    async def chat(self, **kwargs):
        if self.error is not None:
            raise self.error
        return self.response


def reset_temp_db():
    base_dir = Path.cwd() / '.pytest_tmp'
    base_dir.mkdir(exist_ok=True)
    tmpdir = base_dir / uuid4().hex
    tmpdir.mkdir(parents=True, exist_ok=True)
    persistence._DB_PATH = tmpdir / 'jarvis_memory_test.db'
    persistence._initialized = False


def test_extract_memory_candidates_detects_real_signals():
    candidates = extract_memory_candidates('我最近备考雅思压力很大，别太频繁提醒我，我昨晚又熬夜了。')
    kinds = {item.memory_kind for item in candidates}
    assert 'preference' in kinds
    assert 'mood_signal' in kinds
    assert 'rhythm_signal' in kinds
    assert 'long_term_goal' in kinds


def test_real_memory_closed_loop_without_llm():
    async def run():
        reset_temp_db()
        saved = await extract_and_save_chat_memories(
            user_message='我最近备考雅思压力很大，别太频繁提醒我，我昨晚又熬夜了。',
            agent_reply='我会降低打扰频率。',
            source_agent='mira',
            session_id='chat-real-1',
        )
        assert len(saved) >= 4
        prefix = await build_memory_recall_prefix('mira', limit=6)
        assert '长期记忆' in prefix
        assert '低打扰' in prefix or '别太频繁提醒' in prefix
        memories = await persistence.list_jarvis_memories(limit=10)
        assert any(item['last_used_at'] is not None for item in memories)

    asyncio.run(run())


def test_llm_memory_extractor_merges_json_and_rules():
    async def run():
        llm = FakeLLM(
            '{"memories":[{"memory_kind":"relationship","content":"小王是用户的同事，技术问题常找小王。","sensitivity":"normal","confidence":0.86,"importance":0.74,"payload":{"person":"小王"}}]}'
        )
        candidates = await extract_memory_candidates_with_llm(
            user_message='小王是我的同事，技术问题我通常找他；我最近备考雅思压力很大。',
            agent_reply='我记住了。',
            llm_client=llm,
        )
        kinds = {item.memory_kind for item in candidates}
        assert 'relationship' in kinds
        assert 'long_term_goal' in kinds
        assert any(item.content.startswith('小王是用户的同事') for item in candidates)

    asyncio.run(run())


def test_llm_memory_extractor_falls_back_to_rules_on_error():
    async def run():
        candidates = await extract_memory_candidates_with_llm(
            user_message='我昨晚又熬夜了，备考雅思压力很大。',
            agent_reply='我会温和一点提醒。',
            llm_client=FakeLLM(error=RuntimeError('llm down')),
        )
        kinds = {item.memory_kind for item in candidates}
        assert 'rhythm_signal' in kinds
        assert 'long_term_goal' in kinds

    asyncio.run(run())
