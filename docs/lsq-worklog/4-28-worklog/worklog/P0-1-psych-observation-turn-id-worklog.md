# P0-1 Psych Observation Turn ID Worklog

Date: 2026-04-28
Scope: psychological observation real `turn_id` linkage.

## Original Design Mapping

- Source instruction: `???????????.md` P0-1.
- Original psychological-care design requires emotion observations to be traceable to the concrete chat turn.
- This is not full psychological module completion; it only completes the P0-1 traceability gap.

## Completed Scope

- `save_chat_turn()` now returns the inserted `agent_chat_turns.id`.
- Jarvis private chat saves the user turn before `persist_mood_care()` when a mood snapshot exists.
- `persist_mood_care()` accepts `turn_id` and writes it to `jarvis_emotion_observations.turn_id`.
- Final chat persistence avoids duplicating the user turn when it was already saved for care observation.
- Historical observations may still have null `turn_id`; new private-chat care observations get the real id.

## Code Files

- `shadowlink-ai/app/jarvis/persistence.py`
  - `_save_chat_turn_sync()` returns `lastrowid`.
  - `save_chat_turn()` returns `int | None`.
- `shadowlink-ai/app/jarvis/mood_care.py`
  - `persist_mood_care(..., turn_id=None)` passes the id into `save_emotion_observation()`.
- `shadowlink-ai/app/api/v1/jarvis_router.py`
  - Private chat saves user turn before care persistence and passes `turn_id`.
- `shadowlink-ai/tests/unit/jarvis/test_mood_care_observations.py`
  - Added coverage for real chat turn id linkage.

## Tables / Interfaces

- Table: `agent_chat_turns`.
- Table: `jarvis_emotion_observations.turn_id`.
- No public API shape changed; only persistence return value and internal call order changed.

## Frontend Impact

- No UI change.
- New data makes future day-detail / observation-detail UI able to open the exact source chat turn.

## Tests

- `pytest tests/unit/jarvis/test_mood_care_observations.py -q` -> `7 passed`.

## Completion Delta

- Psychological observation traceability: `MVP -> P0 traceable`.
- Psychological module as a whole is not marked full complete.

## Remaining Gaps

- LLM structured emotion fallback and full emotion taxonomy are still later psychological tasks.
- Existing historical rows are not backfilled and may keep `turn_id = NULL`.
