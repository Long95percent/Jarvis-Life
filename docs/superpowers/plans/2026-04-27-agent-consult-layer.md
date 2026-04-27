# Agent Consult Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a bounded private consultation layer so one Jarvis role can ask another role for input before replying in private chat.

**Architecture:** Add a focused `agent_consultation.py` module that parses explicit consult requests, executes at most two internal LLM calls, persists consult summaries, and returns prompt/action payloads to `/jarvis/chat`. Keep frontend changes minimal by rendering an `agent.consult` action card.

**Tech Stack:** FastAPI, Python asyncio, SQLite persistence, React/TypeScript Zustand store.

---

### Task 1: Backend Consult Module

**Files:**
- Create: `shadowlink-ai/app/jarvis/agent_consultation.py`
- Test: `shadowlink-ai/tests/unit/jarvis/test_agent_consultation.py`

- [x] Write failing tests for alias parsing, two-hop chain execution, and persistence.
- [x] Implement alias parsing, depth cap, consultation execution, prompt formatting, and action formatting.
- [x] Run focused backend tests.

### Task 2: Chat Pipeline Integration

**Files:**
- Modify: `shadowlink-ai/app/api/v1/jarvis_router.py`
- Test: `shadowlink-ai/tests/unit/jarvis/test_agent_consultation.py`

- [x] Write failing test proving `/chat` injects consult context into the final active agent prompt.
- [x] Call the consult layer before `run_agent_turn`.
- [x] Include `agent.consult` actions in the API response and persisted chat turn.
- [x] Run focused backend tests.

### Task 3: Frontend Display

**Files:**
- Modify: `shadowlink-web/src/components/jarvis/AgentChatPanel.tsx`

- [x] Render `agent.consult` actions as a compact internal-consult card.
- [x] Run frontend type-check.

### Task 4: Worklog And Verification

**Files:**
- Modify: `docs/ohmori-worklog/2026-04-27-daily-summary.txt`

- [x] Update worklog with changed files, behavior, tests, and remaining boundaries.
- [x] Run backend tests, frontend type-check, Python compile, and diff check.
