# Background Task Days MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make confirmed long-term task days visible and actionable in the frontend, and add backend MVP support for pushing today's task days to Maxwell's workbench plus marking overdue days.

**Architecture:** Keep the existing `background_tasks` and `background_task_days` model. Add focused persistence helpers for Maxwell workbench items and overdue status transitions, expose them through Jarvis APIs, then have `CalendarPanel` consume `background_task_days` as a lightweight calendar/task projection.

**Tech Stack:** Python 3.11 / FastAPI / SQLite / pytest-asyncio / React / TypeScript / Zustand.

---

## Scope

- Show `background_task_days` in the task detail pane.
- Show `background_task_days` in day/week/month calendar views as long-term task projections.
- Let users complete a daily task from the task detail pane.
- Add backend APIs to push a date's pending daily tasks to Maxwell workbench and mark overdue daily tasks as missed.
- Do not add LLM-based rescheduling in this slice.
- Do not replace `background_tasks` with a new planner schema in this slice.

## Tasks

- [ ] Add backend tests for workbench push idempotency and overdue marking.
- [ ] Implement persistence helpers for workbench items and missed-day marking.
- [ ] Add Jarvis API endpoints for workbench push, workbench list, and overdue processing.
- [ ] Update frontend API types/methods.
- [ ] Update `CalendarPanel` to load, display, and complete daily task days.
- [ ] Update `docs/worklog/2026-04-27-daily-summary.txt`.
- [ ] Verify backend tests, frontend type-check, Python compile, and diff check.
