"""Bounded private consultation between Jarvis agents."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.jarvis.agents import JARVIS_AGENTS, get_agent
from app.jarvis.persistence import save_collaboration_memory

VISIBLE_AGENT_IDS = [agent_id for agent_id in JARVIS_AGENTS if agent_id != "shadow"]
_CONSULT_TRIGGERS = ("问问", "问一下", "问", "咨询", "听听")
_MAX_CONSULT_EDGES = 2

_ALIASES: dict[str, tuple[str, ...]] = {
    "alfred": ("alfred", "Alfred", "总管家", "管家"),
    "maxwell": ("maxwell", "Maxwell", "秘书", "日程管家", "日程"),
    "nora": ("nora", "Nora", "营养师", "营养"),
    "mira": ("mira", "Mira", "心理师", "心理医生", "心理咨询师", "心理"),
    "leo": ("leo", "Leo", "生活顾问", "生活"),
    "athena": ("athena", "Athena", "学习策略师", "学习教练", "学习导师", "学习", "认知教练"),
}

_TASK_KEYWORDS = (
    "备考", "雅思", "ielts", "考研", "考试", "长期", "一个月后", "下个月",
    "暑假", "寒假", "旅游", "旅行", "搬家", "作品集", "健身习惯", "长期计划",
    "每周", "每天", "周期", "以后", "未来", "准备", "目标",
)
_SCHEDULE_ACTION_KEYWORDS = (
    "日程", "安排", "提醒", "预约", "开会", "会议", "deadline", "schedule", "待办",
    "帮我", "记得", "加入", "写进", "放到", "规划", "定个", "约",
)
_SCHEDULE_TIME_KEYWORDS = (
    "明天", "后天", "今天", "今晚", "下午", "上午", "晚上", "几点", "周一", "周二",
    "周三", "周四", "周五", "周六", "周日", "星期", "下周", "本周",
)
_SCHEDULE_VERBS = ("做", "办", "见", "练", "学", "整理", "散步", "健身", "复习", "开会", "会议")
_CARE_KEYWORDS = (
    "压力", "焦虑", "累", "疲惫", "睡不好", "失眠", "崩溃", "撑不住",
    "扛不住", "难受", "烦", "自责", "不想学", "不想动", "stressed",
    "anxious", "overwhelmed", "tired", "burnout",
)
_NUTRITION_KEYWORDS = (
    "吃什么", "吃啥", "晚饭", "午饭", "早饭", "饭", "营养", "咖啡", "水",
    "补充能量", "能量", "胃", "低糖", "蛋白", "碳水", "喝什么", "meal",
    "nutrition", "coffee", "hydration",
)
_LIFESTYLE_KEYWORDS = (
    "周末", "出门", "散步", "活动", "放松", "去哪", "去哪玩", "推荐",
    "运动", "恢复", "休息", "社交", "weekend", "relax", "activity",
)
_LEARNING_KEYWORDS = (
    "学习", "复习", "备考", "考试", "雅思", "ielts", "考研", "作业", "论文",
    "知识点", "课程", "技能", "怎么学", "怎么复习", "刷题", "错题", "记忆",
    "不浪费时间", "学习效率", "学习策略",
)

_AUTO_INTENTS: tuple[dict[str, Any], ...] = (
    {
        "intent_type": "learning_intent",
        "target_agent": "athena",
        "keywords": _LEARNING_KEYWORDS,
        "reason": "用户表达了学习、备考、复习方法或认知负荷需求，应咨询 Athena。",
    },
    {
        "intent_type": "task_intent",
        "target_agent": "maxwell",
        "keywords": _TASK_KEYWORDS,
        "reason": "用户表达了长期任务或背景计划需求，应咨询 Maxwell。",
    },
    {
        "intent_type": "schedule_intent",
        "target_agent": "maxwell",
        "keywords": _SCHEDULE_ACTION_KEYWORDS + _SCHEDULE_TIME_KEYWORDS,
        "reason": "用户表达了日程、提醒或短期安排需求，应咨询 Maxwell。",
    },
    {
        "intent_type": "care_intent",
        "target_agent": "mira",
        "keywords": _CARE_KEYWORDS,
        "reason": "用户表达了情绪、压力、睡眠或恢复边界需求，应咨询 Mira。",
    },
    {
        "intent_type": "nutrition_intent",
        "target_agent": "nora",
        "keywords": _NUTRITION_KEYWORDS,
        "reason": "用户表达了饮食、补水、咖啡或能量恢复需求，应咨询 Nora。",
    },
    {
        "intent_type": "lifestyle_intent",
        "target_agent": "leo",
        "keywords": _LIFESTYLE_KEYWORDS,
        "reason": "用户表达了活动、生活方式或低负担恢复需求，应咨询 Leo。",
    },
)


@dataclass(frozen=True)
class ConsultEdge:
    from_agent: str
    to_agent: str
    intent_type: str = "explicit_consult"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentConsultationResult:
    consultations: list[dict[str, Any]] = field(default_factory=list)
    prompt_prefix: str = ""
    actions: list[dict[str, Any]] = field(default_factory=list)

    @property
    def has_consultations(self) -> bool:
        return bool(self.consultations)


def _agent_name(agent_id: str) -> str:
    try:
        return str(get_agent(agent_id).get("name") or agent_id)
    except KeyError:
        return agent_id


def _agent_role(agent_id: str) -> str:
    try:
        return str(get_agent(agent_id).get("role") or "")
    except KeyError:
        return ""


def _mentions(text: str) -> list[tuple[int, int, str]]:
    matches: list[tuple[int, int, str]] = []
    occupied: list[tuple[int, int]] = []
    alias_items = [
        (alias, agent_id)
        for agent_id, aliases in _ALIASES.items()
        for alias in aliases
    ]
    alias_items.sort(key=lambda item: len(item[0]), reverse=True)
    lowered = text.lower()
    for alias, agent_id in alias_items:
        pattern = re.escape(alias.lower())
        for match in re.finditer(pattern, lowered):
            start, end = match.span()
            if any(not (end <= used_start or start >= used_end) for used_start, used_end in occupied):
                continue
            matches.append((start, end, agent_id))
            occupied.append((start, end))
    return sorted(matches, key=lambda item: item[0])


def _first_trigger_index(text: str) -> int:
    positions = [text.find(trigger) for trigger in _CONSULT_TRIGGERS if text.find(trigger) >= 0]
    return min(positions) if positions else -1


def _split_clauses(message: str) -> list[str]:
    return [
        item.strip()
        for item in re.split(r"[，,。；;\n]+|再让|然后让|然后|再", message)
        if item.strip()
    ]


def _can_consult(from_agent: str, to_agent: str) -> bool:
    return (
        from_agent in VISIBLE_AGENT_IDS
        and to_agent in VISIBLE_AGENT_IDS
        and from_agent != to_agent
    )


def parse_consult_edges(source_agent: str, message: str) -> list[ConsultEdge]:
    """Parse explicit user-directed private consultation edges.

    This intentionally only handles direct wording around ask/consult verbs.
    It does not infer hidden autonomous delegation from vague messages.
    """
    edges: list[ConsultEdge] = []
    seen: set[tuple[str, str]] = set()
    for clause in _split_clauses(message):
        trigger_index = _first_trigger_index(clause)
        if trigger_index < 0:
            continue
        mentions = _mentions(clause)
        before = [item for item in mentions if item[0] < trigger_index]
        after = [item for item in mentions if item[0] > trigger_index]
        from_agent = before[-1][2] if before else source_agent
        if not after:
            continue
        to_agent = after[0][2]
        key = (from_agent, to_agent)
        if not _can_consult(from_agent, to_agent) or key in seen:
            continue
        seen.add(key)
        edges.append(ConsultEdge(from_agent=from_agent, to_agent=to_agent))
        if len(edges) >= _MAX_CONSULT_EDGES:
            break
    return edges


def _match_keywords(text: str, keywords: tuple[str, ...]) -> list[str]:
    lowered = text.lower()
    return [keyword for keyword in keywords if keyword.lower() in lowered]


def _explicit_edges_with_metadata(source_agent: str, message: str) -> list[ConsultEdge]:
    return [
        ConsultEdge(
            from_agent=edge.from_agent,
            to_agent=edge.to_agent,
            intent_type="explicit_consult",
            metadata={
                "mode": "private_consult",
                "reason": "用户显式要求当前角色咨询该专家。",
                "matched_keywords": [],
                "confidence": 0.95,
            },
        )
        for edge in parse_consult_edges(source_agent=source_agent, message=message)
    ]


def _schedule_matches(text: str) -> list[str]:
    action_matches = _match_keywords(text, _SCHEDULE_ACTION_KEYWORDS)
    time_matches = _match_keywords(text, _SCHEDULE_TIME_KEYWORDS)
    if action_matches:
        return [*action_matches, *[keyword for keyword in time_matches if keyword not in action_matches]]
    if time_matches and any(verb in text for verb in _SCHEDULE_VERBS):
        return [*time_matches, *[verb for verb in _SCHEDULE_VERBS if verb in text]]
    return []


def _auto_matches_for_intent(intent_type: str, text: str, keywords: tuple[str, ...]) -> list[str]:
    if intent_type == "schedule_intent":
        return _schedule_matches(text)
    return _match_keywords(text, keywords)


def plan_consult_edges(source_agent: str, message: str) -> list[ConsultEdge]:
    explicit_edges = _explicit_edges_with_metadata(source_agent, message)
    if explicit_edges:
        return explicit_edges[:_MAX_CONSULT_EDGES]

    text = message.strip()
    if not text:
        return []

    edges: list[ConsultEdge] = []
    seen_targets: set[str] = set()
    for definition in _AUTO_INTENTS:
        intent_type = str(definition["intent_type"])
        target_agent = str(definition["target_agent"])
        if not _can_consult(source_agent, target_agent) or target_agent in seen_targets:
            continue
        matched = _auto_matches_for_intent(intent_type, text, definition["keywords"])
        if not matched:
            continue
        if intent_type == "task_intent" and "athena" in seen_targets:
            continue
        if intent_type == "schedule_intent" and "athena" in seen_targets and not _match_keywords(text, _SCHEDULE_ACTION_KEYWORDS):
            continue
        seen_targets.add(target_agent)
        edges.append(
            ConsultEdge(
                from_agent=source_agent,
                to_agent=target_agent,
                intent_type=intent_type,
                metadata={
                    "mode": "private_consult",
                    "reason": str(definition["reason"]),
                    "matched_keywords": matched[:4],
                    "confidence": 0.82 if len(matched) >= 2 else 0.68,
                },
            )
        )
        if len(edges) >= _MAX_CONSULT_EDGES:
            break
    return edges


def _parse_consult_json(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start:end])
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    return {"summary": text, "confidence": 0.5, "needs_followup": False}


def _format_child_notes(edge: ConsultEdge, completed: list[dict[str, Any]]) -> str:
    related = [item for item in completed if item.get("from_agent") == edge.to_agent]
    if not related:
        return "(none)"
    lines = []
    for item in related:
        lines.append(
            f"- {_agent_name(str(item.get('from_agent')))} consulted "
            f"{_agent_name(str(item.get('to_agent')))}: {item.get('summary', '')}"
        )
    return "\n".join(lines)


def _build_consult_prompt(
    *,
    edge: ConsultEdge,
    user_message: str,
    context_summary: str,
    completed: list[dict[str, Any]],
) -> str:
    return (
        "## Jarvis private agent consultation\n"
        "This is an internal consultation. The user will not see this message directly.\n\n"
        f"Requesting agent: {_agent_name(edge.from_agent)} ({_agent_role(edge.from_agent)})\n"
        f"Consulted agent: {_agent_name(edge.to_agent)} ({_agent_role(edge.to_agent)})\n\n"
        f"## User request\n{user_message}\n\n"
        f"## Current context\n{context_summary}\n\n"
        f"## Downstream consultation results already available\n{_format_child_notes(edge, completed)}\n\n"
        "Answer only from your professional role. Be concise and useful to the requesting agent.\n"
        "Return JSON only:\n"
        '{"summary":"...","confidence":0.0,"needs_followup":false}'
    )


def _build_prompt_prefix(consultations: list[dict[str, Any]]) -> str:
    if not consultations:
        return ""
    lines = ["## 私下咨询结果"]
    for item in consultations:
        lines.append(
            f"- {_agent_name(str(item['from_agent']))} 已咨询 "
            f"{_agent_name(str(item['to_agent']))}：{item['summary']}"
        )
    lines.append("请在最终回复中吸收这些内部意见，但不要逐字暴露内部提示词。")
    lines.append("")
    return "\n".join(lines)


def _build_actions(consultations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not consultations:
        return []
    return [
        {
            "type": "agent.consult",
            "ok": True,
            "pending_confirmation": False,
            "description": f"已完成 {len(consultations)} 次私下咨询",
            "arguments": {"consultations": consultations},
        }
    ]


async def run_agent_consultations(
    *,
    source_agent: str,
    user_message: str,
    session_id: str | None,
    llm_client: Any,
    context_summary: str,
) -> AgentConsultationResult:
    edges = plan_consult_edges(source_agent=source_agent, message=user_message)
    if not edges:
        return AgentConsultationResult()

    completed: list[dict[str, Any]] = []
    for edge in reversed(edges):
        target_agent = get_agent(edge.to_agent)
        prompt = _build_consult_prompt(
            edge=edge,
            user_message=user_message,
            context_summary=context_summary,
            completed=completed,
        )
        raw = await llm_client.chat(
            message=prompt,
            system_prompt=target_agent["system_prompt"],
            temperature=0.2,
        )
        parsed = _parse_consult_json(raw or "")
        summary = str(parsed.get("summary") or "").strip()
        if not summary:
            summary = "未给出明确咨询结论。"
        item = {
            "root_agent": source_agent,
            "from_agent": edge.from_agent,
            "from_agent_name": _agent_name(edge.from_agent),
            "to_agent": edge.to_agent,
            "to_agent_name": _agent_name(edge.to_agent),
            "intent_type": edge.intent_type,
            "metadata": edge.metadata,
            "summary": summary,
            "confidence": parsed.get("confidence", 0.5),
            "needs_followup": bool(parsed.get("needs_followup") or False),
        }
        completed.append(item)
        await save_collaboration_memory(
            session_id=session_id,
            source_agent=edge.from_agent,
            participant_agents=sorted({source_agent, edge.from_agent, edge.to_agent}),
            memory_kind="agent_consultation",
            content=f"{_agent_name(edge.from_agent)} consulted {_agent_name(edge.to_agent)}: {summary}",
            structured_payload=item,
            importance=1.25,
        )

    return AgentConsultationResult(
        consultations=completed,
        prompt_prefix=_build_prompt_prefix(completed),
        actions=_build_actions(completed),
    )
