# Local Life Search Design

## Goal

Add a shared local-life discovery capability that agents can use in private chat, roundtable context, and proactive routines without creating a parallel architecture outside the existing Jarvis tool system.

## Scope

The feature adds a lightweight `LocalLifeSearchService`, a role-whitelisted `jarvis_local_life_search` tool, SQLite-backed result caching, and read-only context injection for roundtable/proactive use. It focuses on nearby, recent, actionable local information. Items without a clear date or deadline are allowed as low-confidence background candidates but are not promoted as "recent events" unless their `expires_at` is today or later.

## Architecture

- `app/jarvis/local_life_search.py` owns result normalization, date filtering, distance filtering, dedupe, ranking, web search fallback, and cache read/write coordination.
- `app/jarvis/persistence.py` owns the `local_life_items` table and small async CRUD helpers.
- `app/tools/jarvis_tools.py` exposes `jarvis_local_life_search` through the existing `ShadowLinkTool` pattern.
- `app/jarvis/agents.py` grants the tool to Maxwell, Nora, Mira, and Leo with role-specific usage through prompts and intent routing.
- `app/jarvis/intent_router.py` plans local-life calls for high-signal private chat requests before the LLM turn.
- `app/api/v1/jarvis_router.py` injects a small cached local-life prefix into private chat and roundtable prompts. It must not trigger a live web search on roundtable preparation.
- `app/jarvis/proactive_routines.py` may read cached local-life opportunities when generating routine messages, but should not block on web search.

## Data Model

Each cached item stores:

- `source_url`
- `title`
- `item_type`
- `category`
- `venue`
- `address`
- `lat`
- `lng`
- `distance_m`
- `starts_at`
- `ends_at`
- `expires_at`
- `summary`
- `fit_tags_json`
- `confidence`
- `date_confidence`
- `location_label`
- `query`
- `last_seen_at`
- `created_at`
- `updated_at`

`source_url` is unique. The service updates existing rows when the same URL appears again.

## Behavior

Private chat:

- If the current role receives a nearby/recent activity request, the local intent router calls `jarvis_local_life_search`.
- The current role remains the speaker. Maxwell schedules, Leo recommends, Mira filters for low-stimulation recovery, and Nora filters for food/nutrition-related opportunities.

Roundtable:

- Context preparation reads up to 5 cached local-life items whose `expires_at` is today or later.
- Roundtable preparation does not perform live web search.

Proactive routines:

- Routines may include cached local-life opportunities when they already fit the trigger.
- Search failures must not prevent proactive messages from being created.

## Error Handling

- Web search errors return cached results if available.
- Items missing title or source URL are discarded.
- Items with past `expires_at` are not returned unless a caller explicitly asks for stale data; this implementation does not expose stale results.
- Live search output is best-effort and conservative. Ambiguous dates get `date_confidence="low"` and lower ranking.

## Testing

Unit tests cover:

- Future/past filtering and date confidence behavior.
- Cache upsert/list helpers.
- Tool execution through the existing tool runtime.
- Private-chat intent planning for all relevant roles.
- Roundtable context only reading cache and not live-searching.
- Proactive local-life message generation reading cached opportunities without blocking on search.
