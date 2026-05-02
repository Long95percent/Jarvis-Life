from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class RoundtableProtocolPhase:
    id: str
    title: str
    owner_agent: str | None
    objective: str
    role_instructions: dict[str, str]


@dataclass(frozen=True)
class ScenarioProtocol:
    scenario_id: str
    mode: Literal["decision", "brainstorm"]
    phases: list[RoundtableProtocolPhase]
    tool_policy: dict[str, Any]
    result_contract: dict[str, Any]
    safety_rules: list[str]
    handoff_target: str


def _phase(
    phase_id: str,
    title: str,
    owner_agent: str | None,
    objective: str,
    role_instructions: dict[str, str],
) -> RoundtableProtocolPhase:
    return RoundtableProtocolPhase(
        id=phase_id,
        title=title,
        owner_agent=owner_agent,
        objective=objective,
        role_instructions=role_instructions,
    )


_SCENARIO_PROTOCOLS: dict[str, ScenarioProtocol] = {
    "schedule_coord": ScenarioProtocol(
        scenario_id="schedule_coord",
        mode="decision",
        phases=[
            _phase(
                "context_scan",
                "上下文扫描",
                "maxwell",
                "先读今日日程、任务和必须保护的时间块，找出最明显的冲突。",
                {
                    "maxwell": "用日程和时间约束先做扫描，列出今天最关键的冲突和缓冲需求。",
                    "nora": "只从体力、饮食、补水和疲劳角度补充日程约束。",
                    "mira": "只从压力、恢复边界和情绪负担角度补充日程约束。",
                    "alfred": "先保持观察，不要过早收敛。",
                },
            ),
            _phase(
                "conflict_check",
                "冲突检查",
                "nora",
                "确认哪些时间冲突、能量冲突和恢复冲突必须先被标红。",
                {
                    "maxwell": "把最容易冲突的时间块和任务顺序说清楚。",
                    "nora": "检查饮食、咖啡因、补水和体力是否和安排冲突。",
                    "mira": "检查压力是否让今天的安排不可持续。",
                    "alfred": "记录分歧，不急着给最终答案。",
                },
            ),
            _phase(
                "role_proposal",
                "角色提案",
                "mira",
                "在冲突被标出来后，各角色提出自己的可执行方案或限制条件。",
                {
                    "maxwell": "给出最小可行的时间重排方案。",
                    "nora": "给出能量和饮食层面的支持方案。",
                    "mira": "给出恢复边界和必须保留的留白。",
                    "alfred": "把提案整理成可比较的候选方向。",
                },
            ),
            _phase(
                "crossfire",
                "交叉质询",
                "alfred",
                "围绕提案互相回应，明确哪些方案可行、哪些方案会透支。",
                {
                    "maxwell": "回应前面提案里最关键的时间冲突。",
                    "nora": "回应前面提案里最关键的体力或饮食冲突。",
                    "mira": "回应前面提案里最关键的恢复边界冲突。",
                    "alfred": "推动讨论收敛到一个可确认的方向。",
                },
            ),
            _phase(
                "alfred_decision",
                "最终收敛",
                "alfred",
                "输出一个可确认的调整建议和待确认动作，不直接修改日程。",
                {
                    "maxwell": "用最小改动原则支持最终决策。",
                    "nora": "只保留能量和健康相关的最终约束。",
                    "mira": "只保留恢复和压力边界相关的最终约束。",
                    "alfred": "收敛为推荐方案、取舍和待确认动作。",
                },
            ),
        ],
        tool_policy={
            "enabled_agents": ["maxwell", "nora", "mira", "alfred"],
            "write_mode": "pending_confirmation_only",
            "read_only_first": True,
        },
        result_contract={
            "mode": "decision",
            "fields": ["summary", "recommended_option", "options", "tradeoffs", "actions"],
            "semantic_fields": ["calendar_adjustment_candidates", "protected_blocks", "pending_actions"],
        },
        safety_rules=[
            "不直接修改日历",
            "不声称已执行待确认动作",
        ],
        handoff_target="maxwell",
    ),
    "study_energy_decision": ScenarioProtocol(
        scenario_id="study_energy_decision",
        mode="decision",
        phases=[
            _phase(
                "energy_gate",
                "能量门控",
                "mira",
                "先判断当前是否值得继续施压学习。",
                {
                    "mira": "优先保护恢复边界，不要用自责推动学习。",
                    "maxwell": "只从时间窗口和任务压力角度补充。",
                    "athena": "先不要着急给学习方案，先判断值不值得继续。",
                    "alfred": "先记录门控结论。",
                },
            ),
            _phase(
                "task_value_check",
                "任务价值检查",
                "athena",
                "判断学习任务的收益、紧急度和材料依赖。",
                {
                    "mira": "如果疲惫过载，就明确指出停止学习更合理。",
                    "maxwell": "补充任务和日程压力。",
                    "athena": "从学习收益、遗忘风险和材料依赖解释是否值得继续。",
                    "alfred": "记录继续或暂停的分歧。",
                },
            ),
            _phase(
                "minimum_viable_study",
                "最小学习块",
                "maxwell",
                "若仍要学，只保留最低有效学习块和最小压力方案。",
                {
                    "mira": "如果继续学会伤害恢复，就明确反对。",
                    "maxwell": "给出最低可执行学习块和结束条件。",
                    "athena": "给出收益最高的复习动作。",
                    "alfred": "把最小学习块和恢复窗口放在一起比较。",
                },
            ),
            _phase(
                "crossfire",
                "交叉质询",
                "alfred",
                "围绕继续、降强度、恢复、延期做取舍。",
                {
                    "mira": "回应为什么恢复优先或为什么可以继续。",
                    "maxwell": "回应时间上为什么能塞入最小学习块。",
                    "athena": "回应学习收益是否真的值得今晚继续。",
                    "alfred": "推动收敛到一个可接受决定。",
                },
            ),
            _phase(
                "decision",
                "最终决策",
                "alfred",
                "输出一个明确推荐，只生成待确认动作，不直接改日程。",
                {
                    "mira": "保留恢复边界的最终判断。",
                    "maxwell": "保留日程和任务约束。",
                    "athena": "保留学习收益和风险判断。",
                    "alfred": "收敛成推荐决策和待确认动作。",
                },
            ),
        ],
        tool_policy={
            "enabled_agents": ["mira", "maxwell", "athena", "alfred"],
            "text_document_support": True,
            "write_mode": "pending_confirmation_only",
        },
        result_contract={
            "mode": "decision",
            "fields": ["summary", "recommended_option", "options", "tradeoffs", "actions"],
            "semantic_fields": ["continue_or_recover_decision", "minimum_study_block", "recovery_boundary", "reschedule_option"],
        },
        safety_rules=[
            "不做诊断",
            "不直接承诺修改日程",
        ],
        handoff_target="maxwell",
    ),
    "local_lifestyle": ScenarioProtocol(
        scenario_id="local_lifestyle",
        mode="brainstorm",
        phases=[
            _phase(
                "collect_constraints",
                "收集约束",
                "alfred",
                "收集位置、时间、预算、偏好和体力约束。",
                {
                    "leo": "先询问或推断活动类型偏好，不急着推荐。",
                    "maxwell": "关注可用时间和往返缓冲。",
                    "nora": "关注体力、饮食和恢复负担。",
                    "alfred": "把用户约束整理成筛选条件。",
                },
            ),
            _phase(
                "discover_candidates",
                "发现候选",
                "leo",
                "基于上下文提出本地活动候选。",
                {
                    "leo": "优先提出今天或近期仍有效的本地活动候选。",
                    "maxwell": "只补充时间窗口和往返缓冲。",
                    "nora": "只补充体力和饮食负担。",
                    "alfred": "记录候选，不急着排序。",
                },
            ),
            _phase(
                "enrich_candidates",
                "补全候选事实",
                "leo",
                "补全候选的天气、距离、时效、交通和耗时事实。",
                {
                    "leo": "补足候选活动的关键事实；不确定时明确说明缺失。",
                    "maxwell": "标记交通和耗时信息是否足够。",
                    "nora": "标记体力和饮食信息是否足够。",
                    "alfred": "记录哪些事实还需要用户补充。",
                },
            ),
            _phase(
                "feasibility_score",
                "可行性评分",
                "maxwell",
                "按时间窗口和往返缓冲给候选打可行性分。",
                {
                    "leo": "保留仍然可去的活动。",
                    "maxwell": "优先筛掉时间不可行的活动。",
                    "nora": "标记会明显耗体力的活动。",
                    "alfred": "收集过滤依据。",
                },
            ),
            _phase(
                "energy_filter",
                "体力过滤",
                "nora",
                "过滤掉当前能量状态明显不匹配的活动。",
                {
                    "leo": "不要把用户推向高消耗活动。",
                    "maxwell": "继续保留时间可行性判断。",
                    "nora": "从体力、补水、饮食节奏筛选活动。",
                    "alfred": "记录体力冲突。",
                },
            ),
            _phase(
                "rank_options",
                "候选排序",
                "alfred",
                "把候选按生活感、恢复友好度和可行性排序。",
                {
                    "leo": "支持最有生活感的候选。",
                    "maxwell": "支持最稳定可执行的候选。",
                    "nora": "支持最不透支身体的候选。",
                    "alfred": "收敛为排序结果和需要用户补充的偏好。",
                },
            ),
            _phase(
                "plan_candidate",
                "计划候选",
                "maxwell",
                "把首选候选整理成可选待确认安排。",
                {
                    "leo": "保留活动体验结论。",
                    "maxwell": "把首选活动整理成可确认安排，但不要直接写日程。",
                    "nora": "保留活动前后的身体支持建议。",
                    "alfred": "给出最终推荐、拒绝原因和后续问题。",
                },
            ),
        ],
        tool_policy={
            "enabled_agents": ["leo", "maxwell", "nora", "alfred"],
            "local_life_read_only": True,
            "write_mode": "optional_pending_confirmation",
        },
        result_contract={
            "mode": "brainstorm",
            "fields": ["summary", "themes", "ideas", "tensions", "followup_questions"],
            "semantic_fields": ["ranked_activities", "rejected_reasons", "fit_scores", "optional_plan_action"],
        },
        safety_rules=[
            "不声称已经实时搜索",
            "不直接写入日程",
        ],
        handoff_target="maxwell",
    ),
    "emotional_care": ScenarioProtocol(
        scenario_id="emotional_care",
        mode="brainstorm",
        phases=[
            _phase(
                "safety_check",
                "安全检查",
                "mira",
                "先判断是否需要现实支持或专业帮助。",
                {
                    "mira": "先判断安全风险，不做诊断。",
                    "nora": "只补充身体状态，不制造压力。",
                    "leo": "只补充低刺激支持，不推高消耗活动。",
                    "alfred": "先记录安全边界。",
                },
            ),
            _phase(
                "emotional_validation",
                "情绪承接",
                "mira",
                "先降低情绪温度，确认用户被接住。",
                {
                    "mira": "优先承接情绪，不要说教。",
                    "nora": "只做温和支持，不增加任务感。",
                    "leo": "只补充安静、低刺激的动作。",
                    "alfred": "不要过早收敛为计划。",
                },
            ),
            _phase(
                "body_support",
                "身体支持",
                "nora",
                "给出最轻量的身体支持动作。",
                {
                    "mira": "继续保护恢复边界。",
                    "nora": "优先补水、轻食、放慢节奏。",
                    "leo": "只建议可随时停止的动作。",
                    "alfred": "记录哪些动作真的低门槛。",
                },
            ),
            _phase(
                "low_stimulation_options",
                "低刺激选项",
                "leo",
                "只保留短时、低刺激、可暂停的支持方案。",
                {
                    "mira": "不要让方案变得紧迫。",
                    "nora": "不要让方案变得负担很重。",
                    "leo": "只提供低刺激、短时长、可停止的选项。",
                    "alfred": "收集能真正落地的选项。",
                },
            ),
            _phase(
                "care_summary",
                "关怀总结",
                "alfred",
                "收敛为轻恢复清单和下一步问题。",
                {
                    "mira": "保留安全与情绪承接结论。",
                    "nora": "保留身体支持结论。",
                    "leo": "保留低刺激支持结论。",
                    "alfred": "输出轻恢复清单和下一步问题。",
                },
            ),
        ],
        tool_policy={
            "enabled_agents": ["mira", "nora", "leo", "alfred"],
            "minimal_tool_use": True,
            "write_mode": "no_direct_write",
        },
        result_contract={
            "mode": "brainstorm",
            "fields": ["summary", "themes", "ideas", "tensions", "followup_questions"],
            "semantic_fields": ["care_summary", "low_barrier_actions", "safety_note", "what_to_avoid"],
        },
        safety_rules=[
            "不制造紧迫感",
            "不自动创建任务",
        ],
        handoff_target="mira",
    ),
    "weekend_recharge": ScenarioProtocol(
        scenario_id="weekend_recharge",
        mode="brainstorm",
        phases=[
            _phase(
                "recovery_goal",
                "恢复目标",
                "mira",
                "先确认这个周末最重要的是恢复、生活感还是社交。",
                {
                    "leo": "提出生活感强但负担低的周末活动方向。",
                    "nora": "提出能配合恢复节奏的饮食和补水方向。",
                    "mira": "先明确恢复目标，不要把周末排满。",
                    "alfred": "先锁定恢复目标。",
                },
            ),
            _phase(
                "available_blocks",
                "可用时间块",
                "maxwell",
                "找出周末可用时间块和必须留白的块。",
                {
                    "leo": "只挑选能落进可用时间块的活动。",
                    "nora": "只挑选不打乱饮食节奏的活动。",
                    "mira": "优先保留留白。",
                    "alfred": "记录可用时间块。",
                },
            ),
            _phase(
                "activity_rest_balance",
                "活动与休息平衡",
                "leo",
                "平衡活动、饮食和留白，不让周末变成任务表。",
                {
                    "leo": "建议半天活动、半天恢复的组合。",
                    "nora": "补充饮食和补水节奏。",
                    "mira": "保护至少一个无安排窗口。",
                    "alfred": "记录活动和恢复的平衡。",
                },
            ),
            _phase(
                "crossfire",
                "交叉质询",
                "alfred",
                "围绕想出去和需要恢复的冲突收敛。",
                {
                    "leo": "回应为什么活动不会透支。",
                    "nora": "回应为什么身体还能承受。",
                    "mira": "回应为什么留白必须保留。",
                    "alfred": "推动收敛到周末节奏方案。",
                },
            ),
            _phase(
                "weekend_rhythm",
                "周末节奏",
                "alfred",
                "输出最终周末节奏、空档和可选待确认计划。",
                {
                    "leo": "保留可执行的活动块。",
                    "nora": "保留饮食和补水节奏。",
                    "mira": "保留恢复留白。",
                    "alfred": "收敛成周末节奏方案。",
                },
            ),
        ],
        tool_policy={
            "enabled_agents": ["leo", "nora", "mira", "alfred"],
            "local_life_read_only": True,
            "write_mode": "optional_pending_confirmation",
        },
        result_contract={
            "mode": "brainstorm",
            "fields": ["summary", "themes", "ideas", "tensions", "followup_questions"],
            "semantic_fields": ["weekend_rhythm", "activity_blocks", "blank_blocks", "energy_budget", "optional_pending_plan"],
        },
        safety_rules=[
            "不要把周末排满",
            "必须保留恢复留白",
        ],
        handoff_target="maxwell",
    ),
    "work_brainstorm": ScenarioProtocol(
        scenario_id="work_brainstorm",
        mode="brainstorm",
        phases=[
            _phase(
                "frame_problem",
                "框定问题",
                "moderator",
                "先把问题拆成可讨论的边界和主线。",
                {
                    "moderator": "框定问题和边界，不要直接发散到所有方向。",
                    "explorer": "准备发散候选，但先围绕问题边界。",
                    "critic": "先盯住风险和假设，不要急着否定。",
                    "synthesizer": "先观察，不要过早收敛。",
                },
            ),
            _phase(
                "ingest_context",
                "吸收上下文",
                "moderator",
                "吸收用户文档、历史讨论和当前限制，决定本轮发散边界。",
                {
                    "moderator": "把上下文转成问题边界和讨论约束。",
                    "explorer": "只基于已确认上下文准备发散。",
                    "critic": "记录可能影响可行性的限制。",
                    "synthesizer": "记录后续需要合并的主线。",
                },
            ),
            _phase(
                "divergent_ideas",
                "发散想法",
                "explorer",
                "提出尽可能有区分度的候选想法。",
                {
                    "moderator": "保持问题边界清晰。",
                    "explorer": "提出 2-3 个具体候选。",
                    "critic": "准备指出风险和验证成本。",
                    "synthesizer": "准备合并候选。",
                },
            ),
            _phase(
                "cluster_ideas",
                "想法分组",
                "explorer",
                "把发散想法分组，避免后续批判阶段只看到散点。",
                {
                    "moderator": "确认分组仍围绕原问题。",
                    "explorer": "把候选按主题或价值主线分组。",
                    "critic": "准备按分组评估风险。",
                    "synthesizer": "记录每组的共同主线。",
                },
            ),
            _phase(
                "critic_review",
                "批判审视",
                "critic",
                "找出风险、隐藏假设和最小验证方式。",
                {
                    "moderator": "不要让问题跑偏。",
                    "explorer": "接受批判并保留好的候选。",
                    "critic": "明确风险和验证成本。",
                    "synthesizer": "记录哪些想法还能保留。",
                },
            ),
            _phase(
                "synthesis",
                "合并收敛",
                "synthesizer",
                "合并强想法，找出共同主线。",
                {
                    "moderator": "继续保留主问题。",
                    "explorer": "保留最强候选。",
                    "critic": "确认风险是否已经被纳入。",
                    "synthesizer": "合并成一条可继续验证的主线。",
                },
            ),
            _phase(
                "validation_plan",
                "验证计划",
                "synthesizer",
                "形成最小验证步骤和下一轮问题。",
                {
                    "moderator": "保留验证边界。",
                    "explorer": "保留发散留下的潜力方向。",
                    "critic": "保留最关键的风险检查。",
                    "synthesizer": "输出最小验证步骤和下一轮问题。",
                },
            ),
        ],
        tool_policy={
            "enabled_agents": ["moderator", "explorer", "critic", "synthesizer"],
            "life_tools_enabled": False,
            "text_document_support": True,
            "write_mode": "no_direct_write",
        },
        result_contract={
            "mode": "brainstorm",
            "fields": ["summary", "themes", "ideas", "tensions", "followup_questions"],
            "semantic_fields": ["themes", "ideas", "risks", "minimum_validation_steps", "followup_questions"],
        },
        safety_rules=[
            "不调用 Jarvis 生活工具",
            "允许文本类文档上下文",
        ],
        handoff_target="maxwell",
    ),
}


def get_roundtable_protocol(scenario_id: str) -> ScenarioProtocol:
    try:
        return _SCENARIO_PROTOCOLS[scenario_id]
    except KeyError as exc:
        raise KeyError(f"Unknown roundtable scenario: {scenario_id!r}") from exc


def select_roundtable_phase(protocol: ScenarioProtocol, turn_index: int) -> RoundtableProtocolPhase:
    index = min(max(turn_index, 0), len(protocol.phases) - 1)
    return protocol.phases[index]


def final_roundtable_phase(protocol: ScenarioProtocol) -> RoundtableProtocolPhase:
    return protocol.phases[-1]


def format_roundtable_protocol_block(
    protocol: ScenarioProtocol,
    *,
    turn_index: int,
    agent_id: str,
    stage_id: str | None = None,
) -> str:
    phase = next((item for item in protocol.phases if item.id == stage_id), None) if stage_id else None
    if phase is None:
        phase = select_roundtable_phase(protocol, turn_index)
    role_instruction = phase.role_instructions.get(agent_id, "从你的角色职责回应当前阶段目标。")
    lines = [
        "## 场景协议",
        f"protocol_id: {protocol.scenario_id}",
        f"protocol_mode: {protocol.mode}",
        "phase_sequence: " + ", ".join(item.id for item in protocol.phases),
        f"current_phase: {phase.id}",
        f"current_phase_title: {phase.title}",
        f"current_phase_owner: {phase.owner_agent or 'shared'}",
        f"current_phase_objective: {phase.objective}",
        f"current_role_instruction: {role_instruction}",
        "tool_policy: " + json.dumps(protocol.tool_policy, ensure_ascii=False, default=str),
        "safety_rules: " + "；".join(protocol.safety_rules),
        "result_contract: " + json.dumps(protocol.result_contract, ensure_ascii=False, default=str),
    ]
    if phase.id == "crossfire":
        lines.append("crossfire_rule: 必须回应前面发言中的至少一个共识、分歧、风险或约束。")
    return "\n".join(lines)


def protocol_context(protocol: ScenarioProtocol) -> dict[str, Any]:
    return {
        "scenario_protocol_id": protocol.scenario_id,
        "scenario_protocol_mode": protocol.mode,
        "scenario_protocol_phases": [phase.id for phase in protocol.phases],
        "scenario_protocol_handoff_target": protocol.handoff_target,
        "scenario_protocol_result_contract": protocol.result_contract,
    }
