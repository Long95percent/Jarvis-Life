# Agent Preference Profiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist and inject per-agent preference profiles learned silently by Shadow.

**Architecture:** Add SQLite persistence helpers for agent preference profiles, upgrade `PreferenceLearner` to write structured global/per-agent preferences, and inject a compact profile prefix into `/jarvis/chat`.

**Tech Stack:** Python asyncio, SQLite, FastAPI, pytest.

---

### Task 1: Persistence

**Files:**
- Modify: `shadowlink-ai/app/jarvis/persistence.py`
- Test: `shadowlink-ai/tests/unit/jarvis/test_preference_learner.py`

- [x] Add failing tests for upsert, evidence_count increment, and per-agent listing.
- [x] Add `agent_preference_profiles` schema and persistence helpers.
- [x] Run focused tests.

### Task 2: Learner

**Files:**
- Modify: `shadowlink-ai/app/jarvis/preference_learner.py`
- Test: `shadowlink-ai/tests/unit/jarvis/test_preference_learner.py`

- [x] Add failing test for Shadow extracting global and per-agent preferences.
- [x] Parse structured LLM output and persist rows.
- [x] Keep existing in-memory `get_profile()` compatibility.
- [x] Run focused tests.

### Task 3: Prompt Injection

**Files:**
- Modify: `shadowlink-ai/app/jarvis/preference_learner.py`
- Modify: `shadowlink-ai/app/api/v1/jarvis_router.py`
- Test: `shadowlink-ai/tests/unit/jarvis/test_preference_learner.py`

- [x] Add failing test for `build_preference_profile_prefix(agent_id)`.
- [x] Inject preference prefix into private chat prompt.
- [x] Run backend tests and compile checks.

### Task 4: Worklog

**Files:**
- Modify: `docs/ohmori-worklog/2026-04-27-daily-summary.txt`

- [x] Update worklog with behavior, files, verification, and boundaries.
