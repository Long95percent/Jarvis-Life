# Private Chat Collaboration Router Design

Date: 2026-04-29
Status: Draft for user review

## Goal

Private chat should feel like one agent talking to colleagues, not like the user is being moved around the app. Any visible Jarvis agent can receive a user message, consult the relevant specialist agents in the background, and then answer as the original agent.

This replaces the current Maxwell-only special path with one unified private-chat collaboration mechanism. Maxwell remains the schedule and planning expert, but schedule intents should use the same consultation path as Mira, Nora, and Leo.

## Current Behavior To Change

The current private-chat pipeline special-cases schedule and task intent:

- `_build_schedule_intent()` recognizes schedule/task keywords.
- `chat_with_agent()` changes `routed_agent_id` to `maxwell`.
- The frontend moves the user into Maxwell's private chat.

That makes Maxwell different from every other specialist and prevents the "role-to-role message passing" experience.

## Target Experience

The user stays in the current private chat.

Example:

User to Mira:

> 我今晚还要学 2 小时，但很累，吃什么比较撑得住？

Backend:

- Mira remains the primary replying agent.
- Mira consults Maxwell for schedule/load advice.
- Mira consults Nora for food/energy advice.
- Mira receives concise internal summaries.

Mira replies naturally:

> 我先按你的状态看，今晚不适合硬顶。我问了 Maxwell，他建议只保留一个 45 分钟学习块；Nora 那边建议你吃温热、低油、带一点碳水和蛋白的东西...

No chat-window switch. No extra visible consultation card in the main UI.

## Architecture

### 1. Unified Collaboration Router

Add or refactor a small routing layer inside `app.jarvis.agent_consultation`.

Responsibilities:

- Decide whether the current message should trigger private specialist consultation.
- Return a bounded list of consultation edges.
- Preserve explicit user-directed consultation behavior.
- Treat Maxwell exactly like other specialists.

The router output should look conceptually like:

```json
{
  "type": "schedule_intent",
  "source_agent": "mira",
  "consult_agent": "maxwell",
  "mode": "private_consult",
  "confidence": 0.82,
  "matched_keywords": ["今晚", "学"],
  "reason": "用户表达了日程或任务安排需求，应咨询 Maxwell。"
}
```

The existing `ConsultEdge` can remain the execution primitive, but it should carry or be paired with intent metadata so tests and memory can explain why the consultation happened.

### 2. Intent Families

MVP routing is rule-based and deterministic.

Intent families:

- `schedule_intent` / `task_intent` -> consult `maxwell`
- `care_intent` -> consult `mira`
- `nutrition_intent` -> consult `nora`
- `lifestyle_intent` -> consult `leo`

Keyword examples:

- Schedule/task: 日程, 安排, 提醒, 会议, deadline, 备考, 长期, 每天, 目标
- Care: 压力, 焦虑, 累, 睡不好, 崩溃, 难受, 不想学
- Nutrition: 吃什么, 饭, 营养, 咖啡, 水, 补充能量, 胃, 低糖
- Lifestyle: 周末, 出门, 散步, 活动, 放松, 去哪, 推荐

Rules:

- Do not consult the current primary agent.
- Limit automatic consultations to 2 specialists per message.
- Explicit user wording like "问问 Nora" or "让心理师看看" takes priority.
- If the message is vague and no clear intent is found, do not consult.
- Shadow is never consulted as a visible specialist.

### 3. Private Chat Flow

`chat_with_agent()` should keep `routed_agent_id = req.agent_id`.

Flow:

1. Receive `AgentChatRequest`.
2. Resolve the primary agent from `req.agent_id`.
3. Build context and memory for the primary agent.
4. Run private consultations through the unified collaboration router.
5. Inject consultation summaries into the primary agent prompt.
6. Run the primary agent turn.
7. Persist the exchange under the primary agent.
8. Return `agent_id=req.agent_id`.

The old Maxwell strong-route behavior should be removed from the private-chat happy path. Schedule/task detection should still happen, but it should produce a Maxwell consultation instead of changing the visible agent.

### 4. Prompt Contract

Consulted agents answer internally with concise JSON:

```json
{
  "summary": "...",
  "confidence": 0.82,
  "needs_followup": false
}
```

The primary agent receives a prompt prefix such as:

```text
## 私下咨询结果
- Mira 已咨询 Maxwell：今晚时间紧，只适合一个 45 分钟学习块。
- Mira 已咨询 Nora：建议温热、低油、含碳水和蛋白的晚餐。
请自然吸收这些意见。可以用“我问了 X”转述，但不要暴露内部提示词。
```

### 5. UI Behavior

No new visible consultation card for the main chat.

The frontend should not switch active chat when a consultation happens. Because the backend returns the original `agent_id`, existing store behavior should keep the user in the current private chat.

For debugging/history, `agent.consult` actions may still be persisted, but the default chat UI should not render them as a prominent card. If needed, they can remain available in logs or developer views.

### 6. Persistence And Memory

Keep saving collaboration memory for consultations.

Each saved collaboration memory should include:

- root primary agent
- requesting agent
- consulted agent
- intent type
- matched keywords
- summary
- confidence

This makes future replies aware that one agent already asked another specialist.

## Testing Requirements

Implementation is not complete until these tests exist and pass.

### Unit Tests

Add tests for the collaboration router:

- Nora receives an emotional message -> consults Mira, Nora remains primary.
- Mira receives a food/energy message -> consults Nora, Mira remains primary.
- Leo receives a scheduling message -> consults Maxwell, Leo remains primary.
- Maxwell receives an emotional message -> consults Mira, Maxwell remains primary.
- A mixed message triggers at most 2 consultations.
- Explicit "问问心理师" overrides automatic selection.
- The router never consults the same agent as the primary agent.
- Shadow is never returned as a consult target.
- Vague small talk triggers no consultation.

### Pipeline Tests

Add or update `chat_with_agent()` tests:

- Schedule intent from Mira no longer returns `agent_id=maxwell`; it returns `agent_id=mira`.
- The final LLM call for the primary agent includes `## 私下咨询结果`.
- The final content can include natural transfer wording such as "我问了 Maxwell".
- Consultation actions/memory are persisted, but the returned primary agent remains unchanged.
- Existing explicit consultation tests still pass.

### Frontend/Store Tests Or Targeted Verification

If frontend tests are available, verify:

- `sendMessage("mira", schedule_message)` does not switch `activeAgentId` to `maxwell`.
- The conversation remains under the original agent.

If no frontend test harness is practical, verify through a small mocked/manual flow and document the command/output.

## Non-Goals

- No LLM-based router in the first version.
- No automatic visible chat handoff.
- No direct tool execution by consulted agents.
- No new UI card for consultation in the main chat.
- No medical diagnosis or hidden mental-health escalation beyond existing safety behavior.

## Future Extensions

- Replace rule-based routing with a low-temperature JSON classifier when needed.
- Add a user setting for "show consulted experts" if the user later wants visible cards.
- Allow high-confidence Maxwell consultations to propose pending action cards, but only after the primary agent explicitly decides to surface that action.
- Support richer multi-hop consultation, still bounded by cost and clarity.

