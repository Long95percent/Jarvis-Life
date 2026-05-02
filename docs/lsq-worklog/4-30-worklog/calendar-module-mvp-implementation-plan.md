# 日程模块 MVP 实施计划：智能体自动规划闭环

> 日期：2026-05-01  
> 状态：MVP 版，替代此前偏重架构治理的完整 proposal 计划  
> 目标：先打通“短期计划 / 长期计划 / 智能重排”的真实可用闭环，不做过度设计。  
> 原则：靠 Maxwell / 秘书智能体生成结构化计划，代码负责校验和写库，前端只展示和触发。

## 1. 为什么改成 MVP

此前计划覆盖了完整 Calendar Facade、proposal store、namespace 迁移、多方案选择和审计体系，适合后续工程化，但对当前目标过重。

当前最重要目标是：

1. 用户能说自然语言。
2. Maxwell 能生成短期或长期计划。
3. 后端能校验并写入计划/计划日/日历。
4. 前端能正确展示任务、今日安排和日历投影。
5. 用户没完成时，Maxwell 能基于当前日程重新生成后续安排。

因此本计划只做 MVP 必要闭环。

## 2. MVP 范围

### 必须做

1. 保留并继续使用 `planner_guard.py`。
   - 禁止过去日期。
   - 禁止无效时间范围。
   - 后续补充基础冲突和重复校验。

2. 新增秘书结构化解析层。
   - `secretary_schedule.v1`：短期 / 单日计划。
   - `secretary_long_plan.v1`：长期计划 + 每日计划。
   - `secretary_reschedule.v1`：重排后的后续计划。

3. 新增统一秘书规划服务。
   - 输入：用户请求、intent、当前上下文。
   - 调用 Maxwell / LLM。
   - 解析 JSON。
   - 调用 Guard。
   - 写入 DB。

4. 前端调用统一规划入口。
   - 短期安排。
   - 长期计划。
   - 让秘书重排。

5. 前端展示保持清晰。
   - 所有任务：只显示短期任务 / 长期计划主项。
   - 长期计划详情：显示每日计划。
   - 今日视图 / 日历：显示具体计划日。

### 暂不做

1. 不做完整 `/api/v1/jarvis/calendar/*` namespace 迁移。
2. 不做完整 proposal set 生命周期。
3. 不做三方案 A/B/C 选择 UI。
4. 不做复杂审计系统。
5. 不做完整 Calendar Facade 包拆分。
6. 不彻底删除所有旧接口，只阻止旧接口继续产生错误。

## 3. MVP 端到端链路

### 3.1 短期计划

用户输入：

```text
明天晚上帮我安排一次雅思听力复习
```

链路：

```text
前端发送用户请求
→ 后端判断 intent = short_schedule
→ 构建当天/明天已有日程上下文
→ Maxwell 返回 secretary_schedule.v1
→ 后端校验日期、时间、冲突、重复
→ 写入短期 plan + plan_day
→ 必要时投影 calendar event
→ 前端刷新任务/今日/日历
```

### 3.2 长期计划

用户输入：

```text
我要考雅思，未来 30 天帮我安排学习计划
```

链路：

```text
前端发送用户请求
→ 后端判断 intent = long_plan
→ Maxwell 返回 secretary_long_plan.v1
→ 后端校验所有每日计划
→ 写入 jarvis_plans
→ 写入 jarvis_plan_days
→ 可选投影到 calendar events
→ 前端所有任务只显示长期计划本身
→ 详情页显示每日计划
```

### 3.3 智能重排

用户操作：

```text
点击“让秘书重排”或输入“今天没完成，帮我重新安排”
```

链路：

```text
前端发送 plan_id / plan_day_ids / reason
→ 后端读取长期计划、剩余计划日、已有日程、空闲窗口
→ Maxwell 返回 secretary_reschedule.v1
→ 后端校验不能过去、不能冲突、不能重复
→ 更新剩余 plan_days
→ 同步已有 calendar projection
→ 前端刷新详情/今日/日历
```

MVP 阶段只生成一个推荐重排方案，不做多方案选择。

## 4. 结构化 JSON 协议

### 4.1 `secretary_schedule.v1`

用于短期 / 单日计划。

```json
{
  "schema_version": "secretary_schedule.v1",
  "intent": "short_schedule",
  "summary": "明晚安排一次 90 分钟雅思听力复习。",
  "items": [
    {
      "client_item_id": "item-1",
      "date": "2026-05-02",
      "start_time": "19:30",
      "end_time": "21:00",
      "title": "雅思听力复习",
      "description": "完成 Section 1-2 并整理错题。",
      "estimated_minutes": 90,
      "priority": "high",
      "reason": "用户指定明晚，且晚上有完整学习窗口。"
    }
  ]
}
```

### 4.2 `secretary_long_plan.v1`

用于长期计划。

```json
{
  "schema_version": "secretary_long_plan.v1",
  "intent": "long_plan",
  "plan": {
    "title": "雅思 30 天备考计划",
    "goal": "30 天内完成听力、阅读、写作、口语基础训练",
    "plan_type": "long_term",
    "start_date": "2026-05-01",
    "target_date": "2026-05-30"
  },
  "days": [
    {
      "day_index": 1,
      "date": "2026-05-01",
      "start_time": "19:30",
      "end_time": "21:00",
      "title": "雅思听力诊断与基础训练",
      "description": "完成一套听力诊断并整理薄弱题型。",
      "estimated_minutes": 90,
      "reason": "第一天先建立基线。"
    }
  ]
}
```

### 4.3 `secretary_reschedule.v1`

用于重排。

```json
{
  "schema_version": "secretary_reschedule.v1",
  "intent": "reschedule_plan",
  "summary": "已将未完成内容从明天开始重新安排，保持目标日期不变。",
  "plan_id": "plan-ielts-30d",
  "days": [
    {
      "id": "existing-plan-day-id",
      "date": "2026-05-02",
      "start_time": "19:30",
      "end_time": "21:00",
      "title": "雅思听力训练",
      "description": "延期后继续完成听力训练。",
      "estimated_minutes": 90,
      "reason": "用户今日未完成，次日晚上有完整窗口。"
    }
  ]
}
```

## 5. 后端文件计划

### 5.1 已有并保留

- `shadowlink-ai/app/jarvis/planner_guard.py`
  - 已完成初版。
  - 后续扩展冲突和重复校验。

### 5.2 新增

- `shadowlink-ai/app/jarvis/secretary_scheduler.py`
  - 解析 Maxwell 返回的三种 JSON。
  - 构建 prompt。
  - 不写库。

- `shadowlink-ai/app/jarvis/secretary_planning_service.py`
  - 统一执行短期计划、长期计划、重排。
  - 调用 LLM。
  - 调用 parser。
  - 调用 Guard。
  - 写库。

### 5.3 修改

- `shadowlink-ai/app/api/v1/jarvis_router.py`
  - 新增 MVP 入口：

```http
POST /api/v1/jarvis/planner/secretary-plan
```

- `shadowlink-web/src/services/jarvisApi.ts`
  - 新增 `createSecretaryPlan()`。

- `shadowlink-web/src/components/jarvis/CalendarPanel.tsx`
  - “让秘书重排”调用新入口。
  - 后续可把手动延期直接写库改为秘书入口。

## 6. MVP API

### 6.1 统一秘书规划入口

```http
POST /api/v1/jarvis/planner/secretary-plan
```

Request:

```json
{
  "intent": "short_schedule | long_plan | reschedule_plan",
  "message": "我要考雅思，未来 30 天帮我安排学习计划",
  "plan_id": null,
  "plan_day_ids": [],
  "target_date": null,
  "timezone": "Asia/Shanghai",
  "auto_project_calendar": true
}
```

Response:

```json
{
  "intent": "long_plan",
  "summary": "已创建雅思 30 天备考计划。",
  "plan": {},
  "plan_days": [],
  "calendar_events": [],
  "warnings": []
}
```

## 7. 实施任务

### Task 1：保留 P0 Guard

状态：已完成。

已完成：

- 新增 `planner_guard.py`。
- 旧写入口接入过去日期 / 时间范围校验。
- 定向测试通过。

### Task 2：秘书 JSON Parser

目标：先让 Maxwell 的输出变成可验证、可落库的结构化数据。

步骤：

1. 新增测试文件：`shadowlink-ai/tests/unit/jarvis/test_secretary_scheduler.py`。
2. 测试 `secretary_schedule.v1` 能解析。
3. 测试 `secretary_long_plan.v1` 能解析。
4. 测试 `secretary_reschedule.v1` 能解析。
5. 测试错误 schema / 非 JSON / 缺字段会被拒绝。
6. 新增 `secretary_scheduler.py` 实现 parser。

验收：

- Parser 不写库。
- Parser 不接受 Markdown 文本。
- Parser 不接受错误 schema。

### Task 3：秘书规划服务

目标：把短期、长期、重排三个能力统一到一个后端服务。

步骤：

1. 新增 `secretary_planning_service.py`。
2. 实现 `run_secretary_plan_request()`。
3. 短期计划：写入 short_term plan + plan_day。
4. 长期计划：写入 long_term plan + plan_days。
5. 重排：更新已有 remaining plan_days。
6. 写库前调用 `planner_guard.py`。
7. 可选投影到 calendar events。

验收：

- LLM 输出不直接落库。
- 写库前必须 Guard。
- 长期计划只生成一个 plan，多天内容写入 plan_days。

### Task 4：API 入口

目标：前端和 Agent 都调用一个 MVP 入口。

步骤：

1. 在 `jarvis_router.py` 新增 `SecretaryPlanRequest`。
2. 新增 `POST /planner/secretary-plan`。
3. API 调用 `run_secretary_plan_request()`。
4. 返回 plan、plan_days、calendar_events、warnings。

验收：

- 短期 / 长期 / 重排都能通过同一个 API。
- 错误返回结构化 message。

### Task 5：前端接入 MVP API

目标：让用户能在前端触发秘书规划。

步骤：

1. `jarvisApi.ts` 新增 `createSecretaryPlan()`。
2. `CalendarPanel.tsx` 中“让秘书重排”调用新 API。
3. 长期计划生成后的刷新逻辑保持：任务列表、计划详情、日历刷新。
4. 先不做复杂 proposal UI。

验收：

- 前端不直接计算最终重排日期。
- 点击“让秘书重排”后由后端返回结果。
- 前端刷新后能看到更新后的计划日。

### Task 6：三个 MVP Demo 验证

目标：确认基本闭环真的能用。

Demo 1：短期计划

```text
明天晚上帮我安排一次雅思听力复习
```

期望：

- 生成 short_term plan。
- 生成一个 plan_day。
- 今日/日历可显示。

Demo 2：长期计划

```text
我要考雅思，未来 30 天帮我安排学习计划
```

期望：

- 所有任务只显示一个长期计划。
- 详情显示 30 天计划日。
- 日历可投影。

Demo 3：智能重排

```text
今天没完成，帮我重新安排后面的计划
```

期望：

- Maxwell 基于剩余计划日返回新安排。
- 不排到过去。
- 不重复写任务。
- 前端刷新后显示新计划。

## 8. 验收标准

MVP 完成必须满足：

1. 短期自然语言计划能写入。
2. 长期自然语言计划能写入。
3. 长期计划不会在所有任务里拆成一堆顶层任务。
4. 每日计划能在详情、今日、日历看到。
5. 重排由 Maxwell 结构化输出驱动，不是前端 `+1 day`。
6. 后端写库前拒绝过去日期。
7. 后端写库前拒绝无效时间范围。
8. LLM 不直接写库。
9. 前端不直接算最终调度日期。
10. `npm.cmd run type-check` 通过。

## 9. 后续非 MVP 增强

MVP 跑通后再考虑：

1. 多方案 proposal A/B/C。
2. 完整 Calendar Facade 包拆分。
3. `/api/v1/jarvis/calendar/*` 全量 namespace 迁移。
4. 更强冲突求解算法。
5. 更完整审计和指标。
6. Agent 路由可视化。
