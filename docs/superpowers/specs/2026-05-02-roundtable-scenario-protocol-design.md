# Roundtable Scenario Protocol Design

Date: 2026-05-02

## Goal

六个预设圆桌不再共用一套单一的“角色依次发言 -> 总结 -> 等用户反馈 -> finalize”流程。保留共享圆桌底座，但为每个场景加入中度特化的会议协议，让场景在阶段、角色职责、工具策略、产物结构上有明确差异。

本阶段选择 B 方案：每个场景有自己的阶段协议，但不拆成六套完全独立状态机。后续再从六个场景中挑两个高价值场景升级到 C 方案。

## Non-Goals

- 不改圆桌对外 URL。
- 不改变 start / continue / accept / save / plan / return 的主接口。
- 不让圆桌直接修改日历、计划、记忆或关怀数据。
- 不把六个场景拆成六套无法共享的 executor。
- 不在本阶段重做前端视觉。

## Current Problem

当前六个圆桌虽然已有不同 agent、prompt 和 result schema，但核心流程仍然相似：

1. 准备上下文。
2. 角色按顺序发言。
3. Alfred 或 Synthesizer 总结。
4. 等用户继续、评论、finalize 或 redirect。

这能保证稳定，但会让圆桌体验变成“换皮讨论”。例如：

- 日程协调应该先查冲突，再讨论调整方案。
- 疲惫学习应该先做能量门控，再决定是否继续学。
- 情绪关怀不应该强行产出计划。
- 工作脑暴应该有发散、批判、收敛和验证路径。

## Architecture

新增共享的 `ScenarioProtocol` 配置层，放在圆桌后端内部。每个场景通过 protocol 描述自己的会议结构，executor 读取 protocol 来生成阶段、角色任务、总结要求和 final result 约束。

建议结构：

```python
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
```

执行层保留现有 `RoundtableGraphState`、SSE、agent-turn 工具决策、pending action 持久化和结果保存。变化集中在：

- `_role_prompt()` 从 protocol 读取当前场景职责和阶段目标。
- `_summarize_round()` 从 protocol 读取本轮要总结的分歧、共识和下一轮焦点。
- `_build_final_result()` 从 protocol 读取 result contract。
- `crossfire` 作为轻量阶段进入 prompt 约束：后发言角色必须回应前面至少一个共识、分歧或风险。

## Shared Rules

- Jarvis 角色仍使用共享 agent-turn 工具决策入口。
- 写操作仍只生成 pending action，不直接落业务数据。
- 前端继续兼容现有 SSE event；新增字段必须可选。
- `role_completed.tool_results` 和 `role_completed.action_results` 继续可选。
- `work_brainstorm` 默认不开放 Jarvis 生活工具，但允许文本类文档上下文进入讨论。
- 场景协议属于圆桌内部实现，不要求主私聊知道每个阶段细节。

## Scenario Protocols

### schedule_coord

定位：日程协调会。

阶段：

1. `context_scan`：Maxwell 读取今日时间、任务和约束。
2. `conflict_check`：找出冲突、过密时间段、必须保护的关键时间块。
3. `role_proposal`：Nora/Mira 从体力和压力角度补充限制。
4. `crossfire`：角色回应冲突点，例如“计划可行但恢复不足”。
5. `alfred_decision`：Alfred 收敛成可确认的调整方案。

工具策略：

- Maxwell 优先使用日程、计划、时间相关只读能力。
- Nora/Mira 可使用能量、压力、关怀上下文。
- 写入日程只能生成 pending action。

产物：

- `recommended_option`
- `calendar_adjustment_candidates`
- `protected_blocks`
- `tradeoffs`
- `pending_actions`

### study_energy_decision

定位：疲惫状态下的学习决策会。

阶段：

1. `energy_gate`：Mira 判断是否适合继续施压。
2. `task_value_check`：Athena 判断学习任务价值、紧急度和材料依赖。
3. `minimum_viable_study`：Athena/Maxwell 给出最低有效学习块。
4. `crossfire`：围绕继续、降强度、恢复、延期做取舍。
5. `decision`：Alfred 输出一个推荐决策。

工具策略：

- Athena 可使用文本类文档读取和学习材料上下文。
- Maxwell 可评估日程窗口。
- Mira 的恢复边界优先级高于学习连续性。
- 写入学习计划或日程只生成 pending action。

产物：

- `continue_or_recover_decision`
- `minimum_study_block`
- `recovery_boundary`
- `reschedule_option`
- `pending_actions`

### local_lifestyle

定位：本地活动推荐评审会。

阶段：

1. `candidate_discovery`：Leo 提出活动候选。
2. `feasibility_filter`：Maxwell 按时间窗口和交通缓冲过滤。
3. `energy_filter`：Nora 按体力、饮食和恢复负担过滤。
4. `ranking`：Alfred 综合排序。
5. `recommendation`：输出推荐和需要用户补充的偏好。

工具策略：

- Leo 优先使用本地生活、天气、位置相关只读能力。
- Maxwell 使用时间窗口信息。
- Nora 使用体力和饮食上下文。
- 不声称实时搜索，除非工具结果明确来自实时查询。

产物：

- `ranked_activities`
- `rejected_reasons`
- `fit_scores`
- `followup_questions`
- `optional_plan_action`

### emotional_care

定位：低刺激支持会。

阶段：

1. `safety_check`：识别明显安全风险，必要时建议现实支持或专业帮助。
2. `emotional_validation`：Mira 先降低情绪温度，不诊断。
3. `body_support`：Nora 给低负担身体支持。
4. `low_stimulation_options`：Leo 只给短时、可停止、低刺激活动。
5. `care_summary`：Alfred 总结为轻恢复清单，不强行计划化。

工具策略：

- 默认少工具，避免把情绪场景变成任务系统。
- 可以读取已有压力、心情、关怀趋势。
- 不自动创建任务，不制造紧迫感。

产物：

- `care_summary`
- `low_barrier_actions`
- `safety_note`
- `what_to_avoid`
- `followup_question`

### weekend_recharge

定位：周末恢复节奏规划会。

阶段：

1. `recovery_goal`：明确周末主要目标是恢复、生活感还是社交。
2. `available_blocks`：Maxwell 识别可用时间块。
3. `activity_rest_balance`：Leo/Nora/Mira 平衡活动、饮食和留白。
4. `crossfire`：处理“想出去”和“需要恢复”的冲突。
5. `weekend_rhythm`：Alfred 输出节奏方案。

工具策略：

- Leo 可使用本地生活缓存或查询能力。
- Maxwell 可使用日程窗口。
- Mira 有权保护留白，避免周末被排满。
- 计划写入只生成 pending action。

产物：

- `weekend_rhythm`
- `activity_blocks`
- `blank_blocks`
- `energy_budget`
- `optional_pending_plan`

### work_brainstorm

定位：创意工作坊。

阶段：

1. `frame_problem`：Moderator 框定问题和边界。
2. `divergent_ideas`：Explorer 发散候选想法。
3. `critic_review`：Critic 找风险、假设和验证成本。
4. `synthesis`：Synthesizer 合并强想法。
5. `validation_plan`：形成最小验证步骤。

工具策略：

- 默认不开放 Jarvis 生活工具。
- 可以接受文本类文档上下文，例如用户要求读取本地研究文档后讨论。
- 不生成日程修改，除非用户后续选择转计划。

产物：

- `themes`
- `ideas`
- `risks`
- `minimum_validation_steps`
- `followup_questions`

## Data Flow

1. `start_roundtable` 或 `continue_roundtable` 解析 `scenario_id`。
2. router 继续复用共享意图识别，处理文档读取、只读工具上下文、待确认动作。
3. graph executor 根据 `scenario_id` 读取 `ScenarioProtocol`。
4. 每个 agent turn 的 prompt 包含当前 scenario protocol、阶段目标、前序发言和用户反馈。
5. 角色发言仍通过 `run_roundtable_agent_turn()`，工具决策保持 agent-turn-centered。
6. round summary 记录共识、分歧、问题和下一轮焦点。
7. finalize 根据 scenario result contract 生成 decision 或 brainstorm result。
8. 结果通过现有接口保存、接受、转计划或返回私聊。

## Error Handling

- protocol 缺失时回退到现有通用 roundtable 流程。
- 单个阶段或 agent 失败时继续发 `agent_degraded`，不让整轮白屏。
- final result JSON 解析失败时使用场景专属 fallback。
- 工具失败只进入 `tool_results` 或上下文错误说明，不阻断圆桌发言。
- 写操作失败时在 `action_results` 中标记失败，不声称已经执行。

## Testing

后端测试覆盖：

- 六个场景都能读取对应 protocol。
- 每个场景的 final result 包含自己的关键字段。
- `schedule_coord` 和 `study_energy_decision` 仍是 decision mode。
- 其它四个场景仍是 brainstorm mode。
- `work_brainstorm` 默认不开放 Jarvis 生活工具。
- 文本文档上下文可以进入 `study_energy_decision` 和 `work_brainstorm`。
- 写操作只生成 pending action，不直接改日历。
- SSE 事件保持向后兼容。

建议测试命令：

```bash
cd shadowlink-ai
.venv311/bin/python -m pytest tests/unit/jarvis/test_roundtable_decision.py tests/unit/jarvis/test_schedule_coord_graph.py tests/unit/jarvis/test_study_energy_decision_graph.py tests/unit/jarvis/test_local_lifestyle_graph.py tests/unit/jarvis/test_emotional_care_graph.py tests/unit/jarvis/test_weekend_recharge_graph.py tests/unit/jarvis/test_work_brainstorm_graph.py -q
```

## Documentation Updates

实现时同步更新：

- `docs/解耦接口说明/roundtable-api-contract.md`
- `docs/解耦接口说明/frontend-decoupling-developer-guide.md`
- `docs/ohmori-worklog/2026-05-02-daily-summary.txt`

文档必须说明：

- 六个场景已经使用中度特化协议。
- 对外接口不变。
- 新增 result 字段为可选扩展。
- 圆桌仍不直接写业务数据。

## Open Choice For Later C Upgrade

B 完成后再从以下候选中选两个升级 C：

- `schedule_coord`：最适合升级成完整日程协调状态机。
- `study_energy_decision`：最适合升级成真正的决策状态机。
- `work_brainstorm`：适合升级成完整创意工作坊，但和生活管家主链路耦合较少。

推荐优先级：`schedule_coord` 和 `study_energy_decision`。
