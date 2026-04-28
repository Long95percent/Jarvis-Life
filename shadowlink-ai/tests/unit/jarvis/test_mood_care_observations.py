import asyncio
from pathlib import Path
from uuid import uuid4

import pytest

from app.jarvis import persistence
from app.jarvis.mood_care import detect_mood_snapshot, detect_mood_snapshot_enhanced, persist_mood_care


class FakeMoodLLM:
    def __init__(self, raw: str | Exception):
        self.raw = raw
        self.calls = 0

    async def chat(self, *args, **kwargs):
        self.calls += 1
        if isinstance(self.raw, Exception):
            raise self.raw
        return self.raw


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    db_dir = Path("data") / "test_dbs"
    db_dir.mkdir(parents=True, exist_ok=True)
    tmp = db_dir / f"jarvis-{uuid4().hex}.db"
    monkeypatch.setattr(persistence, "_DB_PATH", tmp)
    persistence._initialized = False
    yield tmp
    persistence._initialized = False


def test_detect_low_energy_observation_payload():
    snapshot = detect_mood_snapshot("我今天特别累，不想学了，也有点自责。")

    assert snapshot is not None
    payload = snapshot.to_observation_payload()
    assert payload["primary_emotion"] == "tired"
    assert payload["risk_level"] == "medium"
    assert payload["stress_score"] >= 7
    assert payload["fatigue_score"] > 7
    assert "低能量" in payload["evidence_summary"]


def test_detect_anxiety_or_stress_signal():
    snapshot = detect_mood_snapshot("我压力很大，焦虑到透不过气。")

    assert snapshot is not None
    payload = snapshot.to_observation_payload()
    assert "stress_signal" in payload["signals"]
    assert payload["risk_level"] == "medium"
    assert payload["valence"] < 0


def test_detect_sleep_signal():
    snapshot = detect_mood_snapshot("我最近睡不好，还经常熬夜。")

    assert snapshot is not None
    payload = snapshot.to_observation_payload()
    assert "sleep_signal" in payload["signals"]
    assert payload["fatigue_score"] >= 6
    assert "睡眠" in payload["evidence_summary"]


def test_detect_high_risk_signal():
    snapshot = detect_mood_snapshot("我有点活不下去了，不知道该怎么办。")

    assert snapshot is not None
    payload = snapshot.to_observation_payload()
    assert payload["risk_level"] == "high"
    assert payload["primary_emotion"] == "crisis_signal"
    assert "safety_risk_signal" in payload["signals"]


def test_no_signal_returns_none():
    assert detect_mood_snapshot("今天早餐吃了面包。") is None


def test_persist_mood_care_saves_emotion_observation_without_raw_text():
    user_text = "我今天特别累，不想学了，也有点自责。"
    snapshot = detect_mood_snapshot(user_text)
    assert snapshot is not None

    actions = asyncio.run(persist_mood_care(
        snapshot,
        user_message=user_text,
        session_id="s-emotion-1",
        source_agent="mira",
    ))

    observations = asyncio.run(persistence.list_emotion_observations(session_id="s-emotion-1"))
    assert len(observations) == 1
    observation = observations[0]
    assert observation["agent_id"] == "mira"
    assert observation["primary_emotion"] == "tired"
    assert observation["risk_level"] == "medium"
    assert observation["evidence_summary"]
    assert user_text not in observation["evidence_summary"]
    assert any(
        action.get("arguments", {}).get("emotion_observation_id") == observation["id"]
        for action in actions
    )





def test_persist_mood_care_links_real_chat_turn_id():
    snapshot = detect_mood_snapshot("我压力很大，焦虑到透不过气。")

    async def scenario():
        turn_id = await persistence.save_chat_turn(agent_id="mira", role="user", content="I feel anxious and exhausted today", session_id="s-turn-link")
        await persist_mood_care(
            snapshot,
            user_message="I feel anxious and exhausted today",
            session_id="s-turn-link",
            source_agent="mira",
            turn_id=turn_id,
        )
        return turn_id, await persistence.list_emotion_observations(session_id="s-turn-link")

    turn_id, observations = asyncio.run(scenario())
    assert turn_id is not None
    assert observations
    assert observations[0]["turn_id"] == turn_id


def test_enhanced_mood_analysis_uses_llm_for_mixed_expression_without_raw_text():
    user_text = "我说不清楚，今天一方面有点期待，另一方面又很焦虑，也觉得累，担心自己撑不住但还想把事情做好。"
    llm = FakeMoodLLM('''{
      "primary_emotion": "anxious_hopeful",
      "secondary_emotions": ["anxiety", "hope", "fatigue"],
      "valence": -0.25,
      "arousal": 0.7,
      "stress_score": 7.5,
      "fatigue_score": 6.5,
      "risk_level": "medium",
      "confidence": 0.86,
      "evidence_summary": "用户表达了期待、焦虑和疲惫并存，需要降低负荷。"
    }''')

    snapshot = asyncio.run(detect_mood_snapshot_enhanced(user_text, llm_client=llm))

    assert llm.calls == 1
    assert snapshot is not None
    payload = snapshot.to_observation_payload()
    assert payload["analysis_source"] == "llm"
    assert payload["primary_emotion"] == "anxious_hopeful"
    assert "anxiety" in payload["secondary_emotions"]
    assert payload["risk_level"] == "medium"
    assert user_text not in payload["llm_payload"]["evidence_summary"]


def test_enhanced_mood_analysis_falls_back_to_rules_when_llm_fails():
    llm = FakeMoodLLM(RuntimeError("provider unavailable"))

    snapshot = asyncio.run(detect_mood_snapshot_enhanced("我压力很大，焦虑到透不过气。", llm_client=llm))

    assert llm.calls == 1
    assert snapshot is not None
    assert snapshot.analysis_source == "rules"
    assert snapshot.risk_level == "medium"
    assert "stress_signal" in snapshot.signals


def test_enhanced_mood_analysis_keeps_high_risk_rule_boundary_without_llm():
    llm = FakeMoodLLM('{"primary_emotion":"sad","risk_level":"low","confidence":0.9}')

    snapshot = asyncio.run(detect_mood_snapshot_enhanced("我有点活不下去了，不知道该怎么办。", llm_client=llm))

    assert llm.calls == 0
    assert snapshot is not None
    assert snapshot.analysis_source == "rules"
    assert snapshot.risk_level == "high"
    assert "safety_risk_signal" in snapshot.signals
