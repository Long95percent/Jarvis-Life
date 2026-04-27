# Agent Consult Design

## Goal

Allow a Jarvis role in private chat to privately consult another role before answering the user, without entering roundtable mode.

## Scope

This slice implements explicit user-directed consultation, such as "Nora, ask Mira about my mental state before deciding what I should eat." It also supports a bounded two-hop chain, such as "let Nora ask Mira, then Mira ask Maxwell." It does not implement unlimited autonomous agent networking.

## Behavior

- Any visible agent except Shadow may consult any other visible agent except itself.
- Shadow remains non-conversational and cannot be consulted.
- Consult chains are capped at two edges.
- Consultations are internal. The final user-facing response comes from the active agent.
- Each consultation is saved to `collaboration_memories` with `memory_kind="agent_consultation"`.
- The final agent prompt receives a `## 私下咨询结果` section so the agent knows what happened.
- The API response includes a non-pending `agent.consult` action for optional UI display.

## Parsing

The first version detects explicit agent aliases in user text. Supported aliases include English names and Chinese role names:

- Alfred / 总管家 / 管家
- Maxwell / 秘书 / 日程 / 日程管家
- Nora / 营养师 / 营养
- Mira / 心理师 / 心理
- Leo / 生活顾问 / 生活

If a message asks the current agent to "问/咨询/听听" another role, the current agent becomes the source. If the message says "A 问 B", A becomes the source for that edge.

## Data Flow

1. `/jarvis/chat` prepares normal private-chat context.
2. The consult layer parses explicit consult edges from the user message.
3. The consult layer executes downstream edges first, so `B -> C` can be included when `A -> B` runs.
4. Each target agent receives a private-consult prompt and returns a concise answer.
5. Results are persisted to collaboration memory.
6. The final active agent receives consult results and answers the user.

## Testing

Backend unit tests cover:

- Explicit role aliases produce a `Nora -> Mira` consult.
- A two-hop chain executes in dependency order and injects downstream context.
- Consultation results are saved to collaboration memory.
- `/chat` injects consult results into the final agent turn and returns `agent.consult` actions.
