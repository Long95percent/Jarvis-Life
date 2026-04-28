"""Lightweight Mira mood-care detection and persistence helpers.

This module is intentionally rule-based for the Step 2 MVP: it records
supportive state and follow-up actions without making medical diagnoses.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from app.jarvis.context_bus import get_life_context_bus
from app.jarvis.models import ProactiveMessage


LLM_ANALYSIS_MIN_CHARS = 28
LLM_ANALYSIS_MAX_TEXT_CHARS = 1600


@dataclass(slots=True)
class MoodSnapshot:
    mood_label: str = "neutral"
    stress_level: float = 3.0
    energy_level: float = 6.0
    risk_level: str = "low"
    support_need: str = "companionship"
    next_checkin_at: datetime | None = None
    signals: list[str] = field(default_factory=list)
    analysis_source: str = "rules"
    llm_payload: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mood_label": self.mood_label,
            "stress_level": self.stress_level,
            "energy_level": self.energy_level,
            "risk_level": self.risk_level,
            "support_need": self.support_need,
            "next_checkin_at": self.next_checkin_at.isoformat() if self.next_checkin_at else None,
            "signals": self.signals,
            "analysis_source": self.analysis_source,
            "llm_payload": self.llm_payload or {},
        }

    def to_observation_payload(self) -> dict[str, Any]:
        valence = -0.75 if self.risk_level == "high" else -0.45 if self.risk_level == "medium" else -0.1
        arousal = 0.85 if self.risk_level == "high" else 0.65 if self.stress_level >= 6 else 0.35
        secondary = [signal for signal in self.signals if signal != self.mood_label]
        return {
            "primary_emotion": self.mood_label,
            "secondary_emotions": secondary,
            "valence": valence,
            "arousal": arousal,
            "stress_score": self.stress_level,
            "fatigue_score": max(0.0, min(10.0, 10.0 - self.energy_level)),
            "risk_level": self.risk_level,
            "confidence": 0.72 if self.signals else 0.0,
            "evidence_summary": build_evidence_summary(self),
            "signals": self.signals,
            "analysis_source": self.analysis_source,
            "llm_payload": self.llm_payload or {},
        }


def _clamp_float(value: Any, low: float, high: float, fallback: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    return max(low, min(high, number))


def _safe_str(value: Any, fallback: str = "") -> str:
    return value if isinstance(value, str) and value.strip() else fallback


def _safe_str_list(value: Any, *, limit: int = 6) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            result.append(item.strip()[:40])
        if len(result) >= limit:
            break
    return result


def detect_mood_snapshot(message: str) -> MoodSnapshot | None:
    text = message.strip().lower()
    if not text:
        return None

    signals: list[str] = []
    stress = 3.0
    energy = 6.0
    mood = "neutral"
    support_need = "companionship"

    tired_keywords = ("累", "疲惫", "没力气", "不想动", "不想学", "energy low", "tired")
    stress_keywords = ("压力", "焦虑", "烦", "崩", "撑不住", "扛不住", "透不过气", "自责", "难受")
    sleep_keywords = ("睡不好", "失眠", "睡眠", "熬夜")
    checkin_keywords = ("提醒我", "回访", "晚点问我", "稍后", "今晚", "明天")
    high_risk_keywords = ("不想活", "自杀", "伤害自己", "结束生命", "活不下去")

    if any(keyword in text for keyword in tired_keywords):
        signals.append("low_energy")
        energy = 2.5
        mood = "tired"
        support_need = "rest_or_reduce_load"
    if any(keyword in text for keyword in stress_keywords):
        signals.append("stress_signal")
        stress = max(stress, 7.0)
        if mood == "neutral":
            mood = "stressed"
        support_need = "emotional_support"
    if any(keyword in text for keyword in sleep_keywords):
        signals.append("sleep_signal")
        energy = min(energy, 4.0)
        stress = max(stress, 6.0)
    if any(keyword in text for keyword in checkin_keywords):
        signals.append("followup_requested")
    if any(keyword in text for keyword in high_risk_keywords):
        signals.append("safety_risk_signal")
        mood = "crisis_signal"
        stress = 9.0
        energy = min(energy, 2.0)
        support_need = "safety_support"

    if not signals:
        return None

    if "safety_risk_signal" in signals:
        risk = "high"
    elif stress >= 7.0 or energy <= 3.0:
        risk = "medium"
    else:
        risk = "low"

    next_checkin_at = None
    if "followup_requested" in signals or risk in {"medium", "high"}:
        next_checkin_at = datetime.utcnow() + timedelta(hours=2 if risk == "medium" else 1)

    return MoodSnapshot(
        mood_label=mood,
        stress_level=stress,
        energy_level=energy,
        risk_level=risk,
        support_need=support_need,
        next_checkin_at=next_checkin_at,
        signals=signals,
    )


def _should_use_llm_analysis(message: str, rules_snapshot: MoodSnapshot | None) -> bool:
    text = message.strip()
    if len(text) >= LLM_ANALYSIS_MIN_CHARS and rules_snapshot is None:
        return True
    if rules_snapshot is None:
        return False
    if "safety_risk_signal" in rules_snapshot.signals:
        return False
    if "stress_signal" in rules_snapshot.signals:
        return True
    if len(rules_snapshot.signals) >= 2:
        return True
    if len(text) >= 80:
        return True
    if any(marker in text for marker in ("说不清", "不知道", "有点", "复杂", "一方面", "另一方面", "又", "但是")):
        return True
    return False


def _extract_json_object(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                parsed = json.loads(text[start:end + 1])
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}
    return {}


def _snapshot_from_llm_payload(payload: dict[str, Any], fallback: MoodSnapshot | None = None) -> MoodSnapshot | None:
    primary = _safe_str(payload.get("primary_emotion"), fallback.mood_label if fallback else "")
    if not primary:
        return fallback
    risk = _safe_str(payload.get("risk_level"), fallback.risk_level if fallback else "low").lower()
    if risk not in {"low", "medium", "high"}:
        risk = fallback.risk_level if fallback else "low"
    stress = _clamp_float(payload.get("stress_score"), 0.0, 10.0, fallback.stress_level if fallback else 4.0)
    fatigue = _clamp_float(payload.get("fatigue_score"), 0.0, 10.0, max(0.0, 10.0 - fallback.energy_level) if fallback else 4.0)
    confidence = _clamp_float(payload.get("confidence"), 0.0, 1.0, 0.62)
    signals = list(dict.fromkeys([*(fallback.signals if fallback else []), "llm_structured_analysis"]))
    secondary = _safe_str_list(payload.get("secondary_emotions"))
    for emotion in secondary:
        if emotion not in signals:
            signals.append(emotion)
    next_checkin_at = None
    if risk in {"medium", "high"}:
        next_checkin_at = datetime.utcnow() + timedelta(hours=2 if risk == "medium" else 1)
    return MoodSnapshot(
        mood_label=primary[:40],
        stress_level=stress,
        energy_level=max(0.0, min(10.0, 10.0 - fatigue)),
        risk_level=risk,
        support_need=fallback.support_need if fallback else ("safety_support" if risk == "high" else "emotional_support"),
        next_checkin_at=next_checkin_at or (fallback.next_checkin_at if fallback else None),
        signals=signals,
        analysis_source="llm",
        llm_payload={
            "primary_emotion": primary[:40],
            "secondary_emotions": secondary,
            "valence": _clamp_float(payload.get("valence"), -1.0, 1.0, -0.2),
            "arousal": _clamp_float(payload.get("arousal"), 0.0, 1.0, 0.45),
            "stress_score": stress,
            "fatigue_score": fatigue,
            "risk_level": risk,
            "confidence": confidence,
            "evidence_summary": _safe_str(payload.get("evidence_summary"), "LLM 基于用户表达提取了结构化情绪线索。")[:240],
        },
    )


async def detect_mood_snapshot_enhanced(message: str, llm_client: Any | None = None) -> MoodSnapshot | None:
    rules_snapshot = detect_mood_snapshot(message)
    if not _should_use_llm_analysis(message, rules_snapshot):
        return rules_snapshot
    if llm_client is None:
        return rules_snapshot
    prompt = (
        "你是 Jarvis 的心理关怀结构化分析器。只做情绪线索归纳，不做诊断，不给医疗结论。\n"
        "只输出 JSON，不要输出解释文字。JSON 字段必须包含："
        "primary_emotion, secondary_emotions, valence, arousal, stress_score, fatigue_score, risk_level, confidence, evidence_summary。\n"
        "risk_level 只能是 low/medium/high。evidence_summary 必须是概括，不要复制用户原文全文。\n"
        f"用户表达（仅供本次分析，不要复述全文）：{message[:LLM_ANALYSIS_MAX_TEXT_CHARS]}"
    )
    try:
        raw = await llm_client.chat(prompt, temperature=0.0)
    except TypeError:
        try:
            raw = await llm_client.chat(messages=[{"role": "user", "content": prompt}], temperature=0.0)
        except Exception:
            return rules_snapshot
    except Exception:
        return rules_snapshot
    payload = _extract_json_object(str(raw))
    enhanced = _snapshot_from_llm_payload(payload, rules_snapshot)
    if enhanced is None:
        return rules_snapshot
    if rules_snapshot and "safety_risk_signal" in rules_snapshot.signals:
        return rules_snapshot
    return enhanced


def build_evidence_summary(snapshot: MoodSnapshot) -> str:
    if not snapshot.signals:
        return "未识别到明显情绪信号。"
    labels = {
        "low_energy": "低能量/疲惫表达",
        "stress_signal": "压力或自责表达",
        "sleep_signal": "睡眠相关表达",
        "followup_requested": "用户要求后续提醒",
        "safety_risk_signal": "高风险安全相关表达",
    }
    readable = [labels.get(signal, signal) for signal in snapshot.signals]
    return "；".join(readable)


def build_care_actions(snapshot: MoodSnapshot, *, session_id: str, source_agent: str) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = [
        {
            "type": "mood.snapshot",
            "ok": True,
            "pending_confirmation": False,
            "title": "Mira 状态记录",
            "description": "已记录这次对话中的状态信号，用于后续更温和地陪伴和提醒。",
            "arguments": snapshot.to_dict(),
        }
    ]
    if snapshot.risk_level in {"medium", "high"}:
        suggestion = "先暂停非必要任务，喝点水，做 3 分钟呼吸/拉伸，然后只保留一个最小下一步。"
        if snapshot.risk_level == "high":
            suggestion = "请先保证安全：如果你可能伤害自己或已经无法独处，请立刻联系身边可信任的人或当地紧急求助渠道。"
        actions.append(
            {
                "type": "care.intervention",
                "ok": True,
                "pending_confirmation": False,
                "title": "Mira 关怀建议",
                "description": suggestion,
                "arguments": {
                    **snapshot.to_dict(),
                    "session_id": session_id,
                    "source_agent": source_agent,
                },
            }
        )
    if snapshot.next_checkin_at is not None:
        actions.append(
            {
                "type": "care.followup",
                "ok": True,
                "pending_confirmation": False,
                "title": "Mira 后续回访",
                "description": "已生成轻量回访提醒，会出现在 proactive 消息流中。",
                "arguments": {
                    "next_checkin_at": snapshot.next_checkin_at.isoformat(),
                    "session_id": session_id,
                    "source_agent": source_agent,
                },
            }
        )
    return actions


async def persist_mood_care(snapshot: MoodSnapshot, *, user_message: str, session_id: str, source_agent: str, turn_id: int | None = None) -> list[dict[str, Any]]:
    from app.jarvis.user_settings import is_psychological_tracking_enabled

    if not is_psychological_tracking_enabled():
        return []

    observation: dict[str, Any] | None = None
    try:
        from app.jarvis.persistence import save_emotion_observation

        observation_payload = snapshot.to_observation_payload()
        persistable_payload = {key: observation_payload[key] for key in (
            "primary_emotion",
            "secondary_emotions",
            "valence",
            "arousal",
            "stress_score",
            "fatigue_score",
            "risk_level",
            "confidence",
            "evidence_summary",
            "signals",
        )}
        observation = await save_emotion_observation(
            session_id=session_id,
            turn_id=turn_id,
            agent_id=source_agent,
            source="chat_llm_structured" if snapshot.analysis_source == "llm" else "chat_rule_mvp",
            **persistable_payload,
        )
    except Exception:
        observation = None

    mood_trend = "negative" if snapshot.risk_level in {"medium", "high"} else "neutral"
    sleep_quality = 4.0 if "sleep_signal" in snapshot.signals else 7.0
    await get_life_context_bus().update_fields(
        {
            "stress_level": snapshot.stress_level,
            "sleep_quality": sleep_quality,
            "mood_trend": mood_trend,
        },
        source="mira_mood_care",
    )

    actions = build_care_actions(snapshot, session_id=session_id, source_agent=source_agent)
    if observation:
        for action in actions:
            arguments = action.get("arguments") if isinstance(action.get("arguments"), dict) else {}
            action["arguments"] = {**arguments, "emotion_observation_id": observation.get("id")}
    if snapshot.next_checkin_at is not None:
        from app.jarvis.persistence import save_proactive_message

        content = (
            "Mira 想轻轻回访一下：刚才你提到状态有点吃紧。"
            "现在先不用证明什么，只确认一下：你有没有稍微休息、喝水，或者把任务缩小一点？"
        )
        if snapshot.risk_level == "high":
            content = (
                "Mira 关心你的安全：如果你现在有伤害自己的冲动，请优先联系身边可信任的人或当地紧急求助渠道。"
                "你也可以先回复我一个字，我会陪你把当下这几分钟稳住。"
            )
        saved = await save_proactive_message(
            ProactiveMessage(
                id=f"care-{uuid4().hex}",
                agent_id="mira",
                agent_name="Mira",
                content=content,
                trigger="mood_care_followup",
                priority="high" if snapshot.risk_level == "high" else "normal",
                status="pending",
            )
        )
        for action in actions:
            if action.get("type") == "care.followup":
                action["proactive_message_id"] = saved.get("id")
                action["arguments"] = {**action.get("arguments", {}), "proactive_message_id": saved.get("id")}

    try:
        from app.jarvis.mood_snapshot import aggregate_mood_snapshot

        daily_snapshot = await aggregate_mood_snapshot()
        if daily_snapshot:
            for action in actions:
                arguments = action.get("arguments") if isinstance(action.get("arguments"), dict) else {}
                action["arguments"] = {**arguments, "daily_mood_snapshot_date": daily_snapshot.get("date")}
    except Exception:
        pass

    return actions
