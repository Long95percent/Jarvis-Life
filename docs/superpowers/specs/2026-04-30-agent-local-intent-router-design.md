# Agent-Local Intent Router Design

Date: 2026-04-30
Status: Approved for implementation

## Goal

Improve single-agent private chat tool use by adding a lightweight intent recognition and slot extraction layer for each visible Jarvis role. The router should make tool dispatch more deterministic without turning private chat into a slow two-model pipeline.

The user stays in the current private chat. This router is not for cross-agent collaboration; it is for deciding what the current agent itself should do with its own tools.

## Current Problem

Private chat currently relies on the LLM to infer tool use from the role prompt and the generated toolkit prompt:

1. The current agent receives the user message.
2. The system appends the agent's allowed tools.
3. The LLM may output `<jarvis-tool>{...}</jarvis-tool>`.
4. The backend validates the tool against the current agent whitelist and executes it.

This is useful but underspecified. There is no explicit layer for:

- user intent classification
- required slot extraction
- missing-slot detection
- confidence
- deterministic tests per agent

## Target Architecture

Add `app.jarvis.intent_router`, a small deterministic router that runs before `run_agent_turn()`.

Flow:

```text
chat_with_agent()
→ plan_agent_intent(agent_id, message, local_now)
→ if chat_only: normal LLM path
→ if missing_slots: inject ask-for-missing-slots guidance into primary agent prompt
→ if call_tool/pending_confirmation: execute the planned tool call before the final reply
→ run current agent response with tool results and intent context
```

The router only plans tools from the current agent's whitelist. It never routes to another agent and never bypasses confirmation for write tools.

## Intent Decision Shape

The router returns an `AgentIntentDecision`:

```json
{
  "agent_id": "nora",
  "intent": "meal_plan",
  "tool_name": "jarvis_meal_plan",
  "confidence": 0.86,
  "slots": {
    "meals": ["dinner"],
    "goal": "stress_recovery"
  },
  "missing_slots": [],
  "next_action": "call_tool",
  "reason": "用户在询问今晚吃什么以恢复精力。"
}
```

Allowed `next_action` values:

- `chat_only`
- `ask_missing_slots`
- `call_tool`
- `pending_confirmation`

## MVP Scope

First version is rule-first and deterministic. LLM fallback is a future extension. This keeps latency low and tests stable.

The router should cover these current agents:

### Maxwell

Supported intents:

- `calendar_create` -> `jarvis_calendar_add`
- `task_decompose` -> `jarvis_task_plan_decompose`
- `free_slot` -> `jarvis_calendar_find_free_slot`

Slot behavior:

- `calendar_create` requires `title`, `start`, and `end`.
- If explicit date/time is missing, return `ask_missing_slots`.
- If slots are complete, return `pending_confirmation`.
- `task_decompose` uses `user_request` as the main slot and returns `call_tool`.
- `free_slot` extracts `duration_minutes` when possible; otherwise asks a concise missing-slot question.

### Nora

Supported intents:

- `meal_plan` -> `jarvis_meal_plan`
- `nutrition_lookup` -> `jarvis_nutrition_lookup`
- `hydration_plan` -> `jarvis_hydration_plan`
- `caffeine_guard` -> `jarvis_caffeine_cutoff_guard`

Slot behavior:

- `meal_plan` maps today/tonight/dinner/lunch/breakfast to `meals`.
- Energy, stress, tired, sleep cues map to `goal`.
- `nutrition_lookup` requires `food_name`.
- `caffeine_guard` defaults `beverage_name` to coffee when the message mentions coffee/caffeine.
- `hydration_plan` defaults `activity_level` to medium unless strong activity cues appear.

### Mira

Supported intents:

- `breathing_protocol` -> `jarvis_breathing_protocol`
- `checkin_schedule` -> `jarvis_checkin_schedule`
- `mood_journal` -> `jarvis_mood_journal`
- `burnout_assess` -> `jarvis_burnout_risk_assess`

Slot behavior:

- Panic/anxiety/overload can trigger `breathing_protocol`.
- "晚点问我/明天回访/提醒我状态" triggers `checkin_schedule`.
- "记一下/记录心情" triggers `mood_journal`; missing mood should be asked.
- Burnout/stress/exhaustion triggers `burnout_assess`.

### Leo

Supported intents:

- `local_activities` -> `jarvis_local_activities`
- `activity_rank` -> `jarvis_activity_rank_by_energy`
- `route_estimate` -> `jarvis_route_estimate`
- `plan_activity_slot` -> `jarvis_plan_activity_slot`

Slot behavior:

- Recommendation/activity/outdoor/weekend cues trigger activities.
- "路线/多久/怎么去" with an activity name triggers route estimate.
- "安排进日程/放到明天" triggers `plan_activity_slot` if activity and time are present; otherwise asks missing slots.

## Pipeline Integration

In `chat_with_agent()`:

1. Compute `intent_decision` after local time is available.
2. If `next_action` is `call_tool` or `pending_confirmation`, execute the planned tool through existing `execute_tool_calls(routed_agent_id, calls)`.
3. Add resulting tool output to the final prompt so the current agent can answer naturally.
4. Convert tool results through existing `to_action_results()` so pending confirmation cards still work.
5. If `ask_missing_slots`, inject a short instruction telling the current agent exactly what to ask.
6. If the LLM also emits a tool call later, keep existing tool execution path; whitelist enforcement remains the final guard.

The router improves first-pass dispatch but does not remove LLM tool use.

## Safety And Boundaries

- The router must only return tools in the current agent's whitelist.
- Write tools still require confirmation via existing tool runtime.
- Low confidence or vague messages return `chat_only`.
- The router should not invent precise dates when the user has not provided enough information.
- The router should avoid medical diagnosis; Mira intents stay in support, journaling, check-in, breathing, and burnout-risk framing.

## Testing Requirements

Implementation is not complete until these pass:

- Maxwell creates a complete calendar intent from "明天下午 3 点提醒我复习英语 1 小时".
- Maxwell asks for missing time from "帮我安排复习英语".
- Maxwell detects long-term study planning as `task_decompose`.
- Nora maps "今晚很累吃什么" to `meal_plan` with dinner and stress/energy recovery goal.
- Nora maps "咖啡现在还能喝吗" to `caffeine_guard`.
- Nora asks for `food_name` when a nutrition lookup request omits the food.
- Mira maps anxiety/panic to `breathing_protocol`.
- Mira maps "明天回访一下我的状态" to `checkin_schedule`.
- Leo maps weekend/activity recommendation to `local_activities`.
- Leo asks missing slots before `plan_activity_slot` when activity time is unclear.
- A tool planned for one agent is never returned for another agent if it is outside the whitelist.
- Private chat pipeline executes a planned Nora meal-plan tool before final response.
- Private chat pipeline keeps pending confirmation behavior for Maxwell calendar creation.
- Ordinary small talk returns `chat_only` and does not execute tools.

## Non-Goals

- No LLM classifier in the first implementation.
- No global cross-agent routing.
- No UI redesign.
- No direct writes without confirmation.
- No full natural-language date parser beyond lightweight common cases.

## Future Extensions

- Add a low-temperature structured LLM fallback for ambiguous cases.
- Add richer date/time parsing.
- Add per-agent intent telemetry for false positives/false negatives.
- Let the router generate user-facing missing-slot questions directly when product copy stabilizes.

