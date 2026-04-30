# Local Life Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a shared, cached local-life search capability available to Jarvis private chat, roundtable context, and proactive routines.

**Architecture:** Add a small `LocalLifeSearchService` that normalizes web/local activity results and persists them through Jarvis SQLite helpers. Expose it as `jarvis_local_life_search` via the existing tool registry and read cached results in prompt preparation rather than live-searching during roundtable/proactive flows.

**Tech Stack:** Python 3.11, FastAPI, stdlib SQLite persistence, existing `ShadowLinkTool` and Jarvis tool runtime, pytest.

---

### Task 1: Cache Persistence

**Files:**
- Modify: `shadowlink-ai/app/jarvis/persistence.py`
- Test: `shadowlink-ai/tests/unit/jarvis/test_local_life_search.py`

- [ ] Write failing tests for local-life item upsert, future filtering, and source URL dedupe.
- [ ] Run `cd shadowlink-ai && .venv311/bin/python -m pytest tests/unit/jarvis/test_local_life_search.py -q` and confirm the persistence helpers are missing.
- [ ] Add `local_life_items` schema, indexes, row mapping, `upsert_local_life_items`, and `list_local_life_items`.
- [ ] Re-run the same test file and confirm persistence behavior passes.

### Task 2: Search Service

**Files:**
- Create: `shadowlink-ai/app/jarvis/local_life_search.py`
- Modify: `shadowlink-ai/tests/unit/jarvis/test_local_life_search.py`

- [ ] Write failing tests for `LocalLifeSearchService.search`, filtering out expired items and preferring cached results before web fallback.
- [ ] Run the focused test and confirm service symbols are missing or behavior fails.
- [ ] Implement `LocalLifeSearchService`, `LocalLifeSearchQuery`, `LocalLifeSearchItem`, date parsing helpers, ranking, and cache coordination.
- [ ] Re-run the focused test and confirm service behavior passes.

### Task 3: Jarvis Tool And Role Whitelist

**Files:**
- Modify: `shadowlink-ai/app/tools/jarvis_tools.py`
- Modify: `shadowlink-ai/app/core/lifespan.py`
- Modify: `shadowlink-ai/app/jarvis/agents.py`
- Test: `shadowlink-ai/tests/unit/jarvis/test_local_life_search.py`

- [ ] Write failing tests that `jarvis_local_life_search` is registered and allowed for Maxwell, Nora, Mira, and Leo.
- [ ] Run the focused test and confirm the new tool is missing.
- [ ] Add `JarvisLocalLifeSearchTool`, register it in lifespan, and add it to role whitelists.
- [ ] Re-run the focused test.

### Task 4: Scenario Integration

**Files:**
- Modify: `shadowlink-ai/app/jarvis/intent_router.py`
- Modify: `shadowlink-ai/app/api/v1/jarvis_router.py`
- Modify: `shadowlink-ai/app/jarvis/proactive_routines.py`
- Test: `shadowlink-ai/tests/unit/jarvis/test_local_life_search.py`

- [ ] Write failing tests for role-local intent routing, cached roundtable prefix, and proactive cached opportunity text.
- [ ] Run the focused test and confirm behavior fails before implementation.
- [ ] Add local-life intent decisions for all visible private-chat agents.
- [ ] Add cached local-life prefix builder and include it in private chat and roundtable context.
- [ ] Add a proactive helper that reads cached opportunities without live search.
- [ ] Re-run the focused test.

### Task 5: Regression Verification

**Files:**
- No new files expected.

- [ ] Run focused local-life tests.
- [ ] Run Jarvis intent/tool/context regressions.
- [ ] Run frontend build only if frontend files changed.
- [ ] Review `git diff` for scope and architecture fit.
