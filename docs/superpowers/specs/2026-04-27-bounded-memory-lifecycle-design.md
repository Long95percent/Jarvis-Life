# Bounded Memory Lifecycle Design

## Goal

Upgrade Jarvis long-term memory from a global top-N recall pool into bounded sharing with lifecycle tiers: recent raw memory, older condensed memory, and stable profile/preference memory.

## Scope

Backend only. No new frontend surface. Existing `MemoryPanel` keeps reading active `jarvis_memories`.

## Memory Tiers

- `raw`: recent detailed memory extracted from a chat turn.
- `condensed`: older memory compressed into a shorter durable summary.
- `profile`: stable user preference/profile memory. Existing `agent_preference_profiles` remains the main preference profile store.

## Visibility

- `global`: safe shared facts, constraints, long-term goals, stable preferences.
- `agent_scoped`: primarily visible to the owner/source agent and explicitly allowed agents.
- `sensitive_summary`: sensitive content that may cross roles only as a short summary.
- `private_raw`: raw sensitive content visible only to the owner/source agent.

## Recall

`build_bounded_memory_recall_prefix(agent_id, user_message, limit=6)` replaces raw `build_memory_recall_prefix()` in private chat. It scores candidate memories using:

- importance
- recency
- agent relevance
- memory kind relevance to agent role
- keyword overlap with current user message
- tier and visibility boosts/penalties

The recall output is capped by item count and never grows linearly with stored memories.

## Compression

`compact_old_raw_memories(cutoff_days=7)` finds active raw memories older than the cutoff, groups them by owner/source agent, creates condensed summaries, and archives the original raw rows. The first version uses deterministic summarization from stored memory content so it is fast and testable; an LLM compressor can replace it later.

## Data Model

Extend `jarvis_memories` with:

- `memory_tier`
- `visibility`
- `owner_agent_id`
- `allowed_agent_ids`
- `compressed_from_ids`
- `expires_at`
- `decay_score`
- `last_accessed_at`
- `access_count`

Existing rows are migrated with conservative defaults.

## Acceptance Criteria

- Nora can use global diet/goal memory and relevant sensitive summaries, but not Mira private raw memory.
- Maxwell receives schedule/goal/reminder memory and not unrelated nutrition detail.
- Recent raw memory can be visible to the owner agent.
- Old raw memory can be compacted into condensed rows and archived.
- Private chat prompt uses bounded memory recall.
