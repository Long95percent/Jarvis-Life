# 日程模块重构设计：秘书式冲突协调与智能重排

> 日期：2026-05-01  
> 模块：Jarvis / Maxwell 日程、长期计划、冲突协调  
> 状态：设计已确认，等待拆分实施计划  
> 用户选择：冲突时“先给建议”，由秘书生成 2-3 个可选方案，用户选择后执行。

## 1. 背景问题

当前日程模块已经能创建计划、写入日历、展示冲突、延期和批量操作，但实际使用效果很差，核心原因不是单个按钮问题，而是调度模型不成立：

1. 冲突重排可能把任务改到过去日期。
2. 冲突可以被“忽略”，导致系统承认冲突存在但允许用户绕过，破坏日程可信度。
3. 延期只是简单修改日期，没有结合已有日程、空闲时间、截止日期和用户偏好重排。
4. 秘书 Agent 没有真正承担“日程协调”职责，只是生成或移动记录。
5. 前端承担了过多调度动作，例如直接 `+1 day`，业务规则散落且容易出错。

这说明当前模块更像“日历 CRUD + 计划列表”，还不是“秘书式日程协调系统”。

## 2. 设计目标

重构目标不是继续堆功能，而是让用户真实可用：

- 用户只表达意图，例如“延期”“冲突了帮我安排”“这 30 天备考雅思”。
- 系统先做确定性校验，保证不会生成过去日期、重复任务、硬冲突。
- 秘书 Agent 在需要协调时生成 2-3 个可执行方案。
- 用户选择方案后，系统再执行写库。
- 前端不再直接决定调度结果，只负责呈现意图、方案和执行结果。
- 所有写入前都经过最终校验，避免确认期间数据变化导致二次冲突。

## 3. 核心产品原则

### 3.1 冲突不能忽略

正式用户流里不提供“忽略冲突”。冲突只能有四类结果：

1. 解决：移动某个可移动事项。
2. 替换：取消/覆盖低优先级事项。
3. 保留原样：不写入新的冲突事项。
4. 人工编辑：用户打开详情自行修改。

“忽略冲突”只能作为开发调试能力存在，不能作为正常 UI 操作。

### 3.2 延期不是日期加一天

延期是一个重新规划请求，不是机械日期偏移。

错误逻辑：

```text
原日期 + 1 天 = 新日期
```

正确逻辑：

```text
用户请求延期
→ 后端收集当前事项、计划目标、截止日期、已有日程、空闲窗口
→ 确定性校验器排除不可用窗口
→ 秘书生成 2-3 个重排方案
→ 用户选择
→ 执行器写入
→ 最终校验
```

### 3.3 LLM 只做秘书判断，代码负责硬约束

LLM 适合做：

- 理解用户为什么要延期。
- 在多个可用窗口中做偏好排序。
- 解释方案差异。
- 生成“保守 / 均衡 / 激进”三类方案。

LLM 不负责：

- 判断日期是否在过去。
- 判断具体时间是否重叠。
- 判断数据库是否已有重复事项。
- 直接写库。

这些必须由确定性代码负责。

## 4. 新架构分层

### 4.1 Deterministic Planner Guard（确定性调度守卫）

职责：所有写入和方案生成前后的硬规则校验。

输入：

- 待安排事项。
- 当前日程事件。
- 计划日。
- 任务日。
- 用户本地日期和时区。
- 时间窗口范围。

输出：

- 冲突列表。
- 可用空闲窗口。
- 重复候选。
- 过去日期违规。
- 每日负载评估。
- 是否允许直接写入。

硬规则：

- 不允许安排到今天之前。
- 不允许开始时间晚于结束时间。
- 不允许与不可移动事项重叠。
- 不允许重复安排同一事项。
- 不允许超过计划截止日期，除非方案明确标记为“需要用户接受延期目标”。

### 4.2 Schedule Coordinator（秘书协调器）

职责：在出现冲突、延期、长期计划重排等复杂情况时，生成可选方案。

输入来自 Deterministic Planner Guard，而不是直接读散落数据。

输出结构化方案：

```json
{
  "proposal_id": "...",
  "strategy": "balanced",
  "title": "均衡方案：移动低优先级事项并保持雅思计划连续",
  "summary": "移动 2 个低优先级事项，雅思计划保持每天执行",
  "changes": [
    {
      "item_type": "plan_day",
      "item_id": "...",
      "from": { "date": "2026-05-03", "start": "19:00", "end": "20:30" },
      "to": { "date": "2026-05-04", "start": "20:00", "end": "21:30" },
      "reason": "原时间与已有会议冲突，次日晚上有完整空闲窗口"
    }
  ],
  "risk_level": "low",
  "requires_goal_shift": false,
  "estimated_delay_days": 1
}
```

### 4.3 Proposal Store（方案暂存）

职责：保存待用户选择的方案，避免前端拿到方案后自行拼执行请求。

建议字段：

- `proposal_id`
- `created_at`
- `expires_at`
- `source_user_request`
- `context_hash`
- `status`: `pending` / `applied` / `expired` / `superseded`
- `proposals`: 结构化方案数组

用途：

- 用户刷新页面后仍能看到待处理方案。
- 执行时可以确认上下文是否变化。
- 便于后续审计和演示 Agent 决策链路。

### 4.4 Proposal Executor（方案执行器）

职责：只执行用户选择过的方案。

执行流程：

1. 根据 `proposal_id` 读取方案。
2. 重新跑 Deterministic Planner Guard。
3. 如果上下文变化且仍可执行，则写入。
4. 如果上下文变化导致新冲突，则拒绝执行并要求重新生成方案。
5. 写入计划日、日历项、变更事件。
6. 返回执行结果和影响范围。

## 5. 用户体验设计

### 5.1 冲突卡片

旧设计：

- 展示冲突。
- 提供“移动到空闲窗口”。
- 提供“忽略本次冲突”。

新设计：

- 展示冲突原因。
- 展示受影响事项。
- 按钮改为：`让秘书生成解决方案`。
- 不再提供“忽略冲突”。

生成后展示：

- 方案 A：保守，不动重要事项，可能推迟低优先级任务。
- 方案 B：均衡，尽量保持长期计划连续。
- 方案 C：激进，压缩部分任务或移动多个事项。

每个方案展示：

- 会移动哪些事项。
- 影响哪些日期。
- 是否改变长期目标日期。
- 风险等级。
- 预计延后天数。

### 5.2 延期按钮

旧设计：

- 单个计划日延期 = 日期 + 1。
- 批量延期 = 多个日期 + 1。

新设计：

- 单个按钮文案：`让秘书重排`。
- 批量按钮文案：`批量请求重排`。
- 点击后生成方案，而不是直接写库。

### 5.3 长期计划重排

旧设计：

- 整体顺延一天。

新设计：

- 用户选择重排原因：临时变忙 / 进度落后 / 考试提前 / 想降低强度 / 自定义。
- 系统生成 2-3 个长期计划调整方案：
  - 保持目标日期，增加每日强度。
  - 保持每日强度，延后目标日期。
  - 平衡方案，局部增加周末学习时间。

## 6. API 设计草案

### 6.1 生成重排方案

```http
POST /api/v1/jarvis/planner/reschedule-proposals
```

请求：

```json
{
  "intent": "postpone_plan_day",
  "item_refs": [
    { "item_type": "plan_day", "item_id": "..." }
  ],
  "reason": "今晚临时有事，帮我重新安排",
  "mode": "suggest_first",
  "timezone": "Asia/Shanghai"
}
```

响应：

```json
{
  "proposal_set_id": "...",
  "conflicts": [],
  "duplicates": [],
  "proposals": []
}
```

### 6.2 执行选择的方案

```http
POST /api/v1/jarvis/planner/reschedule-proposals/{proposal_set_id}/apply
```

请求：

```json
{
  "proposal_id": "..."
}
```

响应：

```json
{
  "applied": true,
  "changed_count": 3,
  "events": [],
  "plan_days": []
}
```

## 7. 实施阶段

### 阶段 1：止血规则

目标：先消除最不合理行为。

- 后端所有计划日/日历写入入口禁止过去日期。
- 移除正式 UI 的“忽略冲突”。
- 前端延期按钮不再直接计算最终日期。
- 现有机械延期入口改为“生成重排方案”入口，未接入前先禁用直接写入。

验收：

- 任何 API 都不能把计划日改到今天之前。
- UI 上看不到“忽略冲突”。
- 点击延期不会直接写库。

### 阶段 2：统一 Proposal 模型

目标：把冲突处理、延期、长期计划重排统一成一个方案流。

- 新增 proposal 数据结构。
- 新增生成方案 API。
- 新增执行方案 API。
- 执行前后都跑确定性校验。

验收：

- 冲突处理和延期走同一个 proposal flow。
- 方案执行时如果出现新冲突，会拒绝并提示重新生成。

### 阶段 3：秘书 Agent 接入

目标：让 Maxwell 真正承担秘书协调。

- Maxwell 读取 Deterministic Planner Guard 输出。
- 生成 2-3 个方案。
- 方案必须是结构化 JSON。
- 代码校验 LLM 输出，不合格则重试或返回错误。

验收：

- 用户能看到方案解释。
- 每个方案都有影响范围和风险等级。
- LLM 不能绕过硬约束。

### 阶段 4：前端方案体验

目标：让用户真实可用。

- 冲突卡片展示方案列表。
- 延期按钮展示方案列表。
- 长期计划重排展示方案列表。
- 用户选择后执行。

验收：

- 用户可以理解每个方案改了什么。
- 用户不用处理底层计划日 ID。
- 用户能取消、不执行、重新生成。

### 阶段 5：评测指标

目标：证明系统不是“看起来能跑”，而是真正更可靠。

指标：

- 过去日期违规率：目标 0%。
- 写入后硬冲突率：目标 0%。
- 重复事项写入率：目标接近 0%。
- proposal 可执行率：目标 > 95%。
- 用户确认次数：一般延期/冲突 ≤ 2 次点击。
- LLM 调用占比：只有复杂协调调用，普通 CRUD 不调用。
- 平均方案生成耗时：记录 P50 / P95。

## 8. 优先修复清单

1. P0：后端禁止过去日期写入。
2. P0：移除正式 UI 的“忽略冲突”。
3. P0：延期不再直接写入 `+1 day`。
4. P1：新增确定性 Guard，统一冲突、重复、空闲窗口、过去日期校验。
5. P1：新增 proposal 生成和执行 API。
6. P1：前端冲突/延期统一改为 proposal flow。
7. P2：接入 Maxwell 生成 2-3 个结构化方案。
8. P2：补全评测指标和 demo 链路。

## 9. 设计边界

本轮重构不做：

- 不重做整个聊天系统。
- 不重做所有 Agent 路由。
- 不引入新的日历第三方服务。
- 不让 LLM 直接写数据库。
- 不把复杂调度规则放到前端。

本轮重构必须做：

- 统一调度入口。
- 统一硬约束校验。
- 统一用户确认方案。
- 统一执行前最终校验。

## 10. 下一步

如果该设计通过，下一步进入 implementation plan：

1. 先做 P0 止血：过去日期禁止、移除忽略冲突、禁用机械延期写库。
2. 再抽 Deterministic Planner Guard。
3. 再实现 proposal 生成/执行 API。
4. 最后接 Maxwell 方案生成和前端方案展示。

## 11. 秘书 Skill 与智能体交互设计

用户补充要求：

- 秘书 Skill 需要判断当天日程情况。
- Skill 返回特定格式的日程安排。
- 代码拿到结构化结果后负责写库。
- 重排也通过 LLM 请求，让它基于长期任务整体安排返回延期一天后的特定格式，再由代码写库。

### 11.1 总原则

秘书 Skill 是“日程协调大脑”，但不是数据库执行器。

```text
用户意图
→ Agent 路由判断是否属于秘书日程能力
→ 确定性代码收集上下文并生成可调度输入
→ 秘书 Skill/LLM 返回结构化方案
→ 代码校验方案
→ 用户选择方案
→ 代码执行写库
```

### 11.2 Agent 路由

当用户输入包含以下意图时，路由到 Maxwell/秘书 Skill：

- 新建长期计划：例如“我要准备雅思 30 天”。
- 写入日程：例如“帮我写入日程”。
- 单日安排：例如“今天帮我安排一下”。
- 冲突协调：例如“这个和会议冲突了，帮我调整”。
- 延期/重排：例如“今天没完成，帮我延期一天”。
- 整体计划调整：例如“这周太忙，把计划重新排一下”。

路由输出不直接触发写库，只生成调度意图：

```json
{
  "target_agent": "maxwell",
  "skill": "secretary_schedule_coordination",
  "intent": "reschedule_long_plan",
  "requires_llm_planning": true,
  "requires_user_choice": true
}
```

### 11.3 秘书 Skill 输入格式

代码在调用 Skill 前，先准备一个完整但紧凑的上下文包。

```json
{
  "request_id": "uuid",
  "intent": "plan_today | create_long_plan | resolve_conflict | postpone_items | reschedule_long_plan",
  "today": "2026-05-01",
  "timezone": "Asia/Shanghai",
  "user_request": "今晚临时有事，把雅思计划延期一天并重新安排",
  "user_preferences": {
    "preferred_study_windows": ["19:00-22:00"],
    "weekend_extra_capacity": true,
    "avoid_late_night": true
  },
  "target_plan": {
    "id": "plan-ielts-30d",
    "title": "雅思 30 天备考计划",
    "goal": "30 天后完成雅思阶段备考",
    "start_date": "2026-05-01",
    "target_date": "2026-05-30",
    "status": "active"
  },
  "plan_days": [
    {
      "id": "day-001",
      "plan_date": "2026-05-01",
      "start_time": "19:00",
      "end_time": "20:30",
      "title": "雅思听力训练",
      "status": "pending",
      "estimated_minutes": 90
    }
  ],
  "calendar_items": [
    {
      "item_type": "calendar_event",
      "id": "evt-001",
      "date": "2026-05-01",
      "start_time": "20:00",
      "end_time": "21:00",
      "title": "项目会议",
      "movable": false
    }
  ],
  "free_windows": [
    {
      "date": "2026-05-01",
      "start_time": "18:00",
      "end_time": "19:30",
      "duration_minutes": 90
    }
  ],
  "constraints": {
    "no_past_dates": true,
    "no_overlap_with_fixed_events": true,
    "no_duplicate_titles_in_same_plan": true,
    "preserve_completed_history": true,
    "must_return_strict_json": true
  }
}
```

### 11.4 Skill 输出：当天安排

用于“今天帮我安排一下”“把今天日程推给 Maxwell 工作台”。

Skill 必须返回严格 JSON：

```json
{
  "schema_version": "secretary_schedule.v1",
  "intent": "plan_today",
  "summary": "今天保留会议，安排 2 个学习窗口，晚上不超过 22 点。",
  "schedule_items": [
    {
      "client_item_id": "temp-1",
      "source_type": "plan_day",
      "source_id": "day-001",
      "action": "schedule",
      "date": "2026-05-01",
      "start_time": "18:00",
      "end_time": "19:30",
      "title": "雅思听力训练",
      "description": "完成听力 Section 1-2 并复盘错题",
      "priority": "high",
      "reason": "避开 20:00 会议，利用会议前完整 90 分钟窗口"
    }
  ],
  "unchanged_items": [
    {
      "source_type": "calendar_event",
      "source_id": "evt-001",
      "reason": "固定会议，不移动"
    }
  ],
  "warnings": []
}
```

代码处理规则：

- 只接受 `schema_version = secretary_schedule.v1`。
- 只允许写入 `schedule_items`。
- 每条写入前重新校验日期、时间、冲突、重复。
- `unchanged_items` 和 `warnings` 只用于展示，不写库。

### 11.5 Skill 输出：重排方案

用于延期、冲突解决、长期计划整体重排。

Skill 不直接返回一个最终结果，而是返回 2-3 个 proposals：

```json
{
  "schema_version": "secretary_reschedule.v1",
  "intent": "reschedule_long_plan",
  "summary": "基于延期一天，给出 3 个可执行方案。",
  "proposal_set_title": "雅思计划延期一天后的重排方案",
  "proposals": [
    {
      "proposal_id": "balanced",
      "strategy": "balanced",
      "title": "均衡方案：整体顺延一天，周末补一部分",
      "summary": "保持每天学习节奏，目标日期不变，周末增加 30 分钟。",
      "changes": [
        {
          "change_id": "change-001",
          "source_type": "plan_day",
          "source_id": "day-001",
          "action": "move",
          "from": {
            "date": "2026-05-01",
            "start_time": "19:00",
            "end_time": "20:30"
          },
          "to": {
            "date": "2026-05-02",
            "start_time": "19:00",
            "end_time": "20:30"
          },
          "title": "雅思听力训练",
          "description": "延期后保持原训练内容",
          "reason": "用户今晚临时有事，次日晚间有完整空闲窗口"
        }
      ],
      "estimated_delay_days": 1,
      "risk_level": "low",
      "requires_goal_shift": false
    }
  ],
  "rejected_options": [
    {
      "title": "直接塞到今晚 22:30 后",
      "reason": "违反用户避免深夜学习偏好"
    }
  ]
}
```

代码处理规则：

- 保存整组 proposal，不立即写库。
- 前端展示每个 proposal 的影响范围。
- 用户选定 `proposal_id` 后，代码才执行对应 `changes`。
- 执行前再次调用确定性 Guard。
- 如果方案中出现过去日期、冲突、重复、未知 ID，整条方案标记不可执行。

### 11.6 延期一天的特殊规则

用户说“延期一天”时，不是简单 `+1 day`，而是 Skill 的重排意图参数：

```json
{
  "intent": "reschedule_long_plan",
  "reschedule_policy": {
    "requested_shift_days": 1,
    "scope": "remaining_plan_days",
    "preserve_completed_history": true,
    "prefer_same_time_of_day": true,
    "allow_weekend_compensation": true,
    "allow_goal_date_shift": false
  }
}
```

Skill 需要基于整个长期任务返回完整后续安排，而不是只移动一个计划日。

要求：

- 已完成计划日不改。
- 已错过计划日不改历史状态。
- 从今天起的未完成计划日都纳入重排。
- 返回的日期不得早于今天。
- 如果无法保持原目标日期，必须在 proposal 中标记 `requires_goal_shift: true`。

### 11.7 为什么不是所有事情都请求 LLM

不调用 LLM 的场景：

- 用户手动编辑标题/描述。
- 用户完成/删除某个计划日。
- 简单查询今天日程。
- 确定性重复检测。
- 确定性冲突检测。

调用 LLM 的场景：

- 需要在多个空闲窗口里做取舍。
- 需要平衡长期目标和每日负载。
- 需要解释多个方案差异。
- 需要根据用户偏好生成可执行安排。

这样可以保证系统既智能，又不会因为所有操作都请求 LLM 导致慢和不稳定。
