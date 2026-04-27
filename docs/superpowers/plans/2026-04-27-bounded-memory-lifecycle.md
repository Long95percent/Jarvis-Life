# Bounded Memory Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace global top-N long-term memory recall with bounded, role-aware sharing and add raw-to-condensed lifecycle compression.

**Architecture:** Extend `jarvis_memories` metadata, add `memory_recall.py` for fast SQLite-backed scoring and visibility filtering, add `memory_compactor.py` for deterministic old raw memory compression, and switch `/jarvis/chat` to the bounded recall prefix.

**Tech Stack:** Python asyncio, SQLite, FastAPI, pytest.

---

### Task 1: Memory Metadata Persistence

**Files:**
- Modify: `shadowlink-ai/app/jarvis/persistence.py`
- Test: `shadowlink-ai/tests/unit/jarvis/test_memory_lifecycle.py`

- [x] Write failing tests for saving/listing memory lifecycle metadata.
- [x] Add schema columns and migration defaults.
- [x] Extend `save_jarvis_memory` and row decoding.
- [x] Run focused tests.

### Task 2: Bounded Recall

**Files:**
- Create: `shadowlink-ai/app/jarvis/memory_recall.py`
- Test: `shadowlink-ai/tests/unit/jarvis/test_memory_lifecycle.py`
- Modify: `shadowlink-ai/app/api/v1/jarvis_router.py`

- [x] Write failing tests proving private raw does not cross roles and relevant summaries/global memories do.
- [x] Implement role relevance, visibility filtering, scoring, and capped prefix rendering.
- [x] Switch private chat to `build_bounded_memory_recall_prefix`.
- [x] Run focused tests.

### Task 3: Memory Compaction

**Files:**
- Create: `shadowlink-ai/app/jarvis/memory_compactor.py`
- Modify: `shadowlink-ai/app/jarvis/persistence.py`
- Test: `shadowlink-ai/tests/unit/jarvis/test_memory_lifecycle.py`

- [x] Write failing test for archiving old raw rows and creating condensed rows.
- [x] Implement deterministic compaction and archive helper.
- [x] Run focused tests.

### Task 4: Verification And Worklog

**Files:**
- Modify: `docs/ohmori-worklog/2026-04-27-daily-summary.txt`

- [x] Update worklog.
- [x] Run Jarvis tests, py_compile, frontend type-check, and diff check.
