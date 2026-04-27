# Agent Preference Profiles Design

## Goal

Make Jarvis assistants quietly learn stable user preferences over time and inject those preferences back into each assistant's private-chat prompt.

## Scope

This feature is backend-only. It does not add a frontend settings or inspection surface.

## Behavior

- Shadow preference learning persists preferences to SQLite instead of keeping them only in memory.
- Preferences can be global or specific to one assistant.
- Repeated evidence for the same preference increases `evidence_count` and confidence.
- `/jarvis/chat` injects a preference profile prefix for the active or routed agent.
- The existing long-term memory system remains separate.

## Storage

Add `agent_preference_profiles`:

- `agent_id`: visible agent id or `global`
- `preference_key`
- `preference_value`
- `confidence`
- `evidence_count`
- `source_agent`
- `source_excerpt`
- timestamps

Unique key: `(agent_id, preference_key)`.

## Learning

`PreferenceLearner.observe()` continues to observe in the background. Every extraction cycle, it asks Shadow for structured preferences and writes them to the preference profile table. The API remains silent to the user.

## Prompt Injection

`/jarvis/chat` includes:

```text
## 偏好学习画像
- [全局] ...
- [Nora] ...
```

The prefix is intentionally short and only includes high-confidence, active profile rows.
