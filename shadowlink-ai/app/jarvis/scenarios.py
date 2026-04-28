"""Jarvis scenarios — preset roundtable discussions for life situations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AgentRoster = Literal["jarvis", "brainstorm"]


@dataclass(frozen=True)
class Scenario:
    id: str
    name: str
    name_en: str
    icon: str
    description: str
    agents: list[str]
    opening_prompt: str
    agent_roster: AgentRoster


JARVIS_SCENARIOS: dict[str, Scenario] = {
    "schedule_coord": Scenario(
        id="schedule_coord",
        name="今日日程协调",
        name_en="Daily Schedule Coordination",
        icon="📅",
        description="根据今日日程,各领域 agent 协商分工",
        agents=["maxwell", "nora", "mira", "alfred"],
        opening_prompt=(
            "根据用户今日的日程安排,请每位专家从自己领域（秘书/营养/心理/总管家）"
            "分析并提出建议,最后由 Alfred 总结统筹。"
        ),
        agent_roster="jarvis",
    ),
    "local_lifestyle": Scenario(
        id="local_lifestyle",
        name="本地生活活动推荐",
        name_en="Local Lifestyle Recommendations",
        icon="🌟",
        description="结合天气/空档/体力,推荐今天可做的活动",
        agents=["leo", "maxwell", "nora", "alfred"],
        opening_prompt=(
            "Leo 请基于天气与用户位置先提出 3 个活动选项,Maxwell 评估时间可行性,"
            "Nora 评估体力匹配,最后 Alfred 推荐最优方案。"
        ),
        agent_roster="jarvis",
    ),
    "emotional_care": Scenario(
        id="emotional_care",
        name="情绪压力疏导",
        name_en="Emotional Care",
        icon="🌸",
        description="多 agent 协作帮助用户缓解压力",
        agents=["mira", "nora", "leo", "alfred"],
        opening_prompt=(
            "用户最近压力偏大。Mira 请先开导并引导呼吸,Nora 推荐抗压饮食,"
            "Leo 推荐放松活动,Alfred 综合为一份恢复清单。"
        ),
        agent_roster="jarvis",
    ),
    "study_energy_decision": Scenario(
        id="study_energy_decision",
        name="疲惫学习决策",
        name_en="Study Energy Decision",
        icon="⚖️",
        description="当用户很累但还有学习任务时，Mira/Maxwell/Athena 给出可执行决策",
        agents=["mira", "maxwell", "athena", "alfred"],
        opening_prompt=(
            "这是 decision 圆桌，不做诊断、不直接改日程。Mira 评估情绪与恢复边界，"
            "Maxwell 评估任务与日程可行性，Athena 评估学习收益与取舍，"
            "Alfred 汇总为一个可接受或继续讨论的结构化建议。"
        ),
        agent_roster="jarvis",
    ),
    "weekend_recharge": Scenario(
        id="weekend_recharge",
        name="周末恢复规划",
        name_en="Weekend Recharge Plan",
        icon="🌴",
        description="以周末空档为锚,规划一个恢复精力的周末",
        agents=["leo", "nora", "mira", "alfred"],
        opening_prompt=(
            "周末将至。Leo 规划户外/社交活动,Nora 安排饮食节奏,"
            "Mira 安排冥想或独处时段,Alfred 综合为时间表。"
        ),
        agent_roster="jarvis",
    ),
    "work_brainstorm": Scenario(
        id="work_brainstorm",
        name="工作难题头脑风暴",
        name_en="Work Problem Brainstorm",
        icon="💡",
        description="复用原 Brainstorm 角色进行发散收敛讨论",
        agents=["moderator", "explorer", "critic", "synthesizer"],
        opening_prompt="(由 BrainstormExecutor 完整流程接管,此字段仅作展示)",
        agent_roster="brainstorm",
    ),
}


def get_scenario(scenario_id: str) -> Scenario:
    if scenario_id not in JARVIS_SCENARIOS:
        raise KeyError(f"Unknown scenario: {scenario_id!r}")
    return JARVIS_SCENARIOS[scenario_id]


def list_scenarios() -> list[dict]:
    return [
        {
            "id": s.id,
            "name": s.name,
            "name_en": s.name_en,
            "icon": s.icon,
            "description": s.description,
            "agents": s.agents,
            "agent_roster": s.agent_roster,
        }
        for s in JARVIS_SCENARIOS.values()
    ]
