"""SQLite persistence for Jarvis (sessions + context snapshots).

Uses stdlib sqlite3 wrapped in asyncio.to_thread so callers can await.
DB path: data/jarvis.db (relative to CWD; matches existing data/ convention).
Schema is created on first use; no migrations (demo-scale).
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import structlog

from app.config import settings as app_settings

logger = structlog.get_logger("jarvis.persistence")

_DB_PATH = Path(app_settings.data_dir) / "jarvis.db"


SCHEMA = """
CREATE TABLE IF NOT EXISTS roundtable_sessions (
    session_id   TEXT PRIMARY KEY,
    scenario_id  TEXT NOT NULL,
    scenario_name TEXT NOT NULL,
    participants TEXT NOT NULL,        -- JSON list of agent IDs
    agent_roster TEXT NOT NULL,        -- 'jarvis' | 'brainstorm'
    round_count  INTEGER NOT NULL DEFAULT 0,
    title        TEXT NOT NULL DEFAULT '',
    user_prompt  TEXT NOT NULL DEFAULT '',
    created_at   REAL NOT NULL,
    updated_at   REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS roundtable_turns (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT NOT NULL,
    role         TEXT NOT NULL,        -- 'user' or agent_id
    speaker_name TEXT NOT NULL,
    content      TEXT NOT NULL,
    timestamp    REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES roundtable_sessions(session_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_turns_session ON roundtable_turns(session_id);

CREATE TABLE IF NOT EXISTS roundtable_results (
    id                 TEXT PRIMARY KEY,
    session_id         TEXT NOT NULL,
    mode               TEXT NOT NULL DEFAULT 'decision',
    status             TEXT NOT NULL DEFAULT 'draft',
    summary            TEXT NOT NULL,
    options_json       TEXT NOT NULL DEFAULT '[]',
    recommended_option TEXT NOT NULL DEFAULT '',
    tradeoffs_json     TEXT NOT NULL DEFAULT '[]',
    actions_json       TEXT NOT NULL DEFAULT '[]',
    handoff_target     TEXT NOT NULL DEFAULT 'maxwell',
    context_json       TEXT NOT NULL DEFAULT '{}',
    result_json        TEXT NOT NULL DEFAULT '{}',
    user_choice        TEXT,
    handoff_status     TEXT NOT NULL DEFAULT 'none',
    source_session_id  TEXT,
    source_agent_id    TEXT,
    pending_action_id  TEXT,
    created_at         REAL NOT NULL,
    updated_at         REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES roundtable_sessions(session_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_roundtable_results_session ON roundtable_results(session_id, created_at DESC);

CREATE TABLE IF NOT EXISTS life_context_snapshots (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    captured_at      REAL NOT NULL,
    stress_level     REAL NOT NULL,
    schedule_density REAL NOT NULL,
    sleep_quality    REAL NOT NULL,
    mood_trend       TEXT NOT NULL,
    source_agent     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ctx_time ON life_context_snapshots(captured_at DESC);

CREATE TABLE IF NOT EXISTS jarvis_emotion_observations (
    id                   TEXT PRIMARY KEY,
    session_id           TEXT,
    turn_id              INTEGER,
    agent_id             TEXT NOT NULL,
    primary_emotion      TEXT NOT NULL,
    secondary_emotions   TEXT NOT NULL DEFAULT '[]',
    valence              REAL NOT NULL,
    arousal              REAL NOT NULL,
    stress_score         REAL NOT NULL,
    fatigue_score        REAL NOT NULL,
    risk_level           TEXT NOT NULL,
    confidence           REAL NOT NULL DEFAULT 0.6,
    evidence_summary     TEXT NOT NULL,
    signals_json         TEXT NOT NULL DEFAULT '[]',
    source               TEXT NOT NULL DEFAULT 'chat_rule_mvp',
    created_at           REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_emotion_observations_created ON jarvis_emotion_observations(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_emotion_observations_session ON jarvis_emotion_observations(session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_emotion_observations_risk ON jarvis_emotion_observations(risk_level, created_at DESC);

CREATE TABLE IF NOT EXISTS jarvis_mood_snapshots (
    date                    TEXT PRIMARY KEY,
    mood_score              REAL NOT NULL,
    stress_score            REAL NOT NULL,
    energy_score            REAL NOT NULL,
    sleep_risk_score        REAL NOT NULL,
    schedule_pressure_score REAL NOT NULL,
    dominant_emotions       TEXT NOT NULL DEFAULT '[]',
    positive_events         TEXT NOT NULL DEFAULT '[]',
    negative_events         TEXT NOT NULL DEFAULT '[]',
    risk_flags              TEXT NOT NULL DEFAULT '[]',
    summary                 TEXT NOT NULL,
    confidence              REAL NOT NULL DEFAULT 0.0,
    created_at              REAL NOT NULL,
    updated_at              REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_mood_snapshots_updated ON jarvis_mood_snapshots(updated_at DESC);

CREATE TABLE IF NOT EXISTS jarvis_behavior_observations (
    id                       TEXT PRIMARY KEY,
    date                     TEXT NOT NULL,
    session_id               TEXT,
    agent_id                 TEXT NOT NULL,
    observation_type         TEXT NOT NULL,
    expected_bedtime         TEXT,
    expected_wake            TEXT,
    actual_first_active_at   REAL,
    actual_last_active_at    REAL,
    deviation_minutes        INTEGER,
    duration_minutes         INTEGER,
    source                   TEXT NOT NULL DEFAULT 'chat_activity_mvp',
    created_at               REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_behavior_observations_date ON jarvis_behavior_observations(date, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_behavior_observations_session ON jarvis_behavior_observations(session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_behavior_observations_type ON jarvis_behavior_observations(observation_type, created_at DESC);

CREATE TABLE IF NOT EXISTS jarvis_stress_signals (
    id           TEXT PRIMARY KEY,
    date         TEXT NOT NULL,
    signal_type  TEXT NOT NULL,
    severity     TEXT NOT NULL,
    score        REAL NOT NULL,
    reason       TEXT NOT NULL,
    source_refs  TEXT NOT NULL DEFAULT '[]',
    source       TEXT NOT NULL DEFAULT 'schedule_pressure_mvp',
    created_at   REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_stress_signals_date ON jarvis_stress_signals(date, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_stress_signals_type ON jarvis_stress_signals(signal_type, created_at DESC);

CREATE TABLE IF NOT EXISTS agent_chat_turns (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,                   -- private chat session this turn belongs to
    agent_id   TEXT NOT NULL,          -- which agent this 1:1 chat belongs to
    role       TEXT NOT NULL,          -- 'user' or 'agent'
    content    TEXT NOT NULL,
    actions    TEXT NOT NULL DEFAULT '[]',
    timestamp  REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chat_agent ON agent_chat_turns(agent_id, timestamp);

CREATE TABLE IF NOT EXISTS jarvis_memories (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_kind     TEXT NOT NULL,
    content         TEXT NOT NULL,
    source_agent    TEXT NOT NULL,
    session_id      TEXT,
    source_text     TEXT,
    structured_payload TEXT NOT NULL,
    sensitivity     TEXT NOT NULL DEFAULT 'normal',
    confidence      REAL NOT NULL DEFAULT 0.6,
    importance      REAL NOT NULL DEFAULT 0.5,
    memory_tier     TEXT NOT NULL DEFAULT 'raw',
    visibility      TEXT NOT NULL DEFAULT 'global',
    owner_agent_id  TEXT,
    allowed_agent_ids TEXT NOT NULL DEFAULT '[]',
    compressed_from_ids TEXT NOT NULL DEFAULT '[]',
    expires_at      REAL,
    decay_score     REAL NOT NULL DEFAULT 0.0,
    last_accessed_at REAL,
    access_count    INTEGER NOT NULL DEFAULT 0,
    created_at      REAL NOT NULL,
    updated_at      REAL NOT NULL,
    last_used_at    REAL,
    status          TEXT NOT NULL DEFAULT 'active'
);

CREATE INDEX IF NOT EXISTS idx_jarvis_memories_active ON jarvis_memories(status, importance DESC, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_jarvis_memories_kind ON jarvis_memories(memory_kind, updated_at DESC);

CREATE TABLE IF NOT EXISTS agent_preference_profiles (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id         TEXT NOT NULL, -- visible agent id or 'global'
    preference_key   TEXT NOT NULL,
    preference_value TEXT NOT NULL,
    confidence       REAL NOT NULL DEFAULT 0.6,
    evidence_count   INTEGER NOT NULL DEFAULT 1,
    source_agent     TEXT NOT NULL,
    source_excerpt   TEXT,
    created_at       REAL NOT NULL,
    updated_at       REAL NOT NULL,
    last_seen_at     REAL NOT NULL,
    status           TEXT NOT NULL DEFAULT 'active',
    UNIQUE(agent_id, preference_key)
);

CREATE INDEX IF NOT EXISTS idx_agent_preference_profiles_agent ON agent_preference_profiles(status, agent_id, confidence DESC, updated_at DESC);

CREATE TABLE IF NOT EXISTS conversation_history (
    id                 TEXT PRIMARY KEY,
    conversation_type  TEXT NOT NULL, -- private_chat | roundtable | brainstorm
    title              TEXT NOT NULL,
    agent_id           TEXT,
    scenario_id        TEXT,
    session_id         TEXT NOT NULL,
    route_payload      TEXT NOT NULL,
    status             TEXT NOT NULL DEFAULT 'active',
    created_at         REAL NOT NULL,
    updated_at         REAL NOT NULL,
    last_opened_at     REAL
);

CREATE TABLE IF NOT EXISTS collaboration_memories (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id         TEXT,
    source_agent       TEXT NOT NULL,
    participant_agents TEXT NOT NULL,  -- JSON list of agent IDs; empty list = global
    memory_kind        TEXT NOT NULL,  -- discussion | user_request | user_constraint | tool_action | coordination_summary
    content            TEXT NOT NULL,
    structured_payload TEXT NOT NULL,  -- JSON object
    importance         REAL NOT NULL DEFAULT 1.0,
    created_at         REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_collab_created ON collaboration_memories(created_at DESC);

CREATE TABLE IF NOT EXISTS pending_actions (
    id             TEXT PRIMARY KEY,
    action_type    TEXT NOT NULL,
    tool_name      TEXT NOT NULL,
    agent_id       TEXT NOT NULL,
    session_id     TEXT,
    title          TEXT NOT NULL,
    arguments      TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'pending',
    created_at     REAL NOT NULL,
    updated_at     REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pending_status ON pending_actions(status, created_at DESC);

CREATE TABLE IF NOT EXISTS proactive_messages (
    id           TEXT PRIMARY KEY,
    agent_id     TEXT NOT NULL,
    agent_name   TEXT NOT NULL,
    content      TEXT NOT NULL,
    trigger      TEXT NOT NULL,
    priority     TEXT NOT NULL DEFAULT 'normal',
    status       TEXT NOT NULL DEFAULT 'pending',
    created_at   REAL NOT NULL,
    delivered_at REAL,
    read_at      REAL,
    dismissed_at REAL,
    snoozed_until REAL
);

CREATE INDEX IF NOT EXISTS idx_proactive_messages_status ON proactive_messages(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_proactive_messages_agent ON proactive_messages(agent_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS jarvis_care_triggers (
    id                TEXT PRIMARY KEY,
    trigger_type      TEXT NOT NULL,
    severity          TEXT NOT NULL,
    reason            TEXT NOT NULL,
    evidence_ids_json TEXT NOT NULL DEFAULT '[]',
    status            TEXT NOT NULL DEFAULT 'active',
    cooldown_until    REAL,
    message_id        TEXT,
    created_at        REAL NOT NULL,
    resolved_at       REAL
);

CREATE INDEX IF NOT EXISTS idx_care_triggers_type ON jarvis_care_triggers(trigger_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_care_triggers_status ON jarvis_care_triggers(status, created_at DESC);

CREATE TABLE IF NOT EXISTS jarvis_care_interventions (
    id                    TEXT PRIMARY KEY,
    trigger_id            TEXT,
    message_id            TEXT,
    agent_id              TEXT NOT NULL DEFAULT 'mira',
    intervention_type     TEXT NOT NULL,
    content               TEXT NOT NULL,
    suggested_action_json TEXT NOT NULL DEFAULT '{}',
    status                TEXT NOT NULL DEFAULT 'pending',
    user_feedback         TEXT,
    shown_at              REAL,
    acted_at              REAL,
    snoozed_until         REAL,
    created_at            REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_care_interventions_status ON jarvis_care_interventions(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_care_interventions_message ON jarvis_care_interventions(message_id);

CREATE TABLE IF NOT EXISTS proactive_routine_runs (
    id         TEXT PRIMARY KEY,
    routine_id TEXT NOT NULL,
    run_date   TEXT NOT NULL,
    message_id TEXT,
    fired_at   REAL NOT NULL,
    UNIQUE(routine_id, run_date)
);

CREATE INDEX IF NOT EXISTS idx_proactive_routine_runs_date ON proactive_routine_runs(run_date, routine_id);

CREATE TABLE IF NOT EXISTS local_life_items (
    id              TEXT PRIMARY KEY,
    source_url      TEXT NOT NULL UNIQUE,
    title           TEXT NOT NULL,
    item_type       TEXT NOT NULL DEFAULT 'event',
    category        TEXT NOT NULL DEFAULT 'general',
    venue           TEXT,
    address         TEXT,
    lat             REAL,
    lng             REAL,
    distance_m      INTEGER,
    starts_at       TEXT,
    ends_at         TEXT,
    expires_at      TEXT,
    summary         TEXT NOT NULL DEFAULT '',
    fit_tags_json   TEXT NOT NULL DEFAULT '[]',
    confidence      REAL NOT NULL DEFAULT 0.5,
    date_confidence TEXT NOT NULL DEFAULT 'low',
    location_label  TEXT NOT NULL DEFAULT '',
    query           TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'active',
    last_seen_at    REAL NOT NULL,
    created_at      REAL NOT NULL,
    updated_at      REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_local_life_items_expires ON local_life_items(status, expires_at, confidence DESC);
CREATE INDEX IF NOT EXISTS idx_local_life_items_category ON local_life_items(status, category, updated_at DESC);

CREATE TABLE IF NOT EXISTS background_tasks (
    id                    TEXT PRIMARY KEY,
    title                 TEXT NOT NULL,
    task_type             TEXT NOT NULL,
    status                TEXT NOT NULL DEFAULT 'active',
    source_agent          TEXT,
    original_user_request TEXT NOT NULL,
    goal                  TEXT,
    time_horizon          TEXT NOT NULL,
    milestones            TEXT NOT NULL,
    subtasks              TEXT NOT NULL,
    calendar_candidates   TEXT NOT NULL,
    notes                 TEXT,
    created_at            REAL NOT NULL,
    updated_at            REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_background_tasks_status ON background_tasks(status, updated_at DESC);

CREATE TABLE IF NOT EXISTS background_task_days (
    id                TEXT PRIMARY KEY,
    task_id           TEXT NOT NULL,
    plan_date         TEXT NOT NULL,
    title             TEXT NOT NULL,
    description       TEXT,
    start_time        TEXT,
    end_time          TEXT,
    estimated_minutes INTEGER,
    status            TEXT NOT NULL DEFAULT 'pending',
    calendar_event_id TEXT,
    workbench_item_id TEXT,
    sort_order        INTEGER NOT NULL DEFAULT 0,
    llm_payload       TEXT NOT NULL,
    created_at        REAL NOT NULL,
    updated_at        REAL NOT NULL,
    FOREIGN KEY (task_id) REFERENCES background_tasks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_background_task_days_task ON background_task_days(task_id, plan_date ASC, sort_order ASC);
CREATE INDEX IF NOT EXISTS idx_background_task_days_status ON background_task_days(status, plan_date ASC);

CREATE TABLE IF NOT EXISTS jarvis_plans (
    id                    TEXT PRIMARY KEY,
    title                 TEXT NOT NULL,
    plan_type             TEXT NOT NULL,
    status                TEXT NOT NULL DEFAULT 'active',
    source_agent          TEXT,
    source_pending_id     TEXT,
    source_background_task_id TEXT,
    original_user_request TEXT NOT NULL DEFAULT '',
    goal                  TEXT,
    time_horizon_json     TEXT NOT NULL DEFAULT '{}',
    raw_payload_json      TEXT NOT NULL DEFAULT '{}',
    created_at            REAL NOT NULL,
    updated_at            REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jarvis_plans_status ON jarvis_plans(status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_jarvis_plans_source_background ON jarvis_plans(source_background_task_id);

CREATE TABLE IF NOT EXISTS jarvis_plan_days (
    id                TEXT PRIMARY KEY,
    plan_id           TEXT NOT NULL,
    plan_date         TEXT NOT NULL,
    title             TEXT NOT NULL,
    description       TEXT,
    start_time        TEXT,
    end_time          TEXT,
    estimated_minutes INTEGER,
    status            TEXT NOT NULL DEFAULT 'pending',
    calendar_event_id TEXT,
    workbench_item_id TEXT,
    source_task_day_id TEXT,
    sort_order        INTEGER NOT NULL DEFAULT 0,
    raw_payload_json  TEXT NOT NULL DEFAULT '{}',
    reschedule_reason TEXT,
    created_at        REAL NOT NULL,
    updated_at        REAL NOT NULL,
    FOREIGN KEY (plan_id) REFERENCES jarvis_plans(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_jarvis_plan_days_plan ON jarvis_plan_days(plan_id, plan_date ASC, sort_order ASC);
CREATE INDEX IF NOT EXISTS idx_jarvis_plan_days_status ON jarvis_plan_days(status, plan_date ASC);
CREATE INDEX IF NOT EXISTS idx_jarvis_plan_days_date ON jarvis_plan_days(plan_date ASC, status);

CREATE TABLE IF NOT EXISTS jarvis_agent_events (
    id          TEXT PRIMARY KEY,
    event_type  TEXT NOT NULL,
    agent_id    TEXT,
    plan_id     TEXT,
    plan_day_id TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at  REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jarvis_agent_events_type ON jarvis_agent_events(event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jarvis_agent_events_plan ON jarvis_agent_events(plan_id, created_at DESC);


CREATE TABLE IF NOT EXISTS jarvis_calendar_events (
    id             TEXT PRIMARY KEY,
    title          TEXT NOT NULL,
    start          TEXT NOT NULL,
    end            TEXT NOT NULL,
    stress_weight  REAL NOT NULL DEFAULT 1.0,
    location       TEXT,
    notes          TEXT,
    source         TEXT NOT NULL DEFAULT 'user_ui',
    source_agent   TEXT,
    created_reason TEXT,
    status         TEXT NOT NULL DEFAULT 'confirmed',
    route_required INTEGER NOT NULL DEFAULT 0,
    created_at     REAL NOT NULL,
    updated_at     REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jarvis_calendar_events_time ON jarvis_calendar_events(start, end);
CREATE INDEX IF NOT EXISTS idx_jarvis_calendar_events_status ON jarvis_calendar_events(status, start);

CREATE TABLE IF NOT EXISTS maxwell_workbench_items (
    id          TEXT PRIMARY KEY,
    task_day_id TEXT,
    plan_day_id TEXT,
    agent_id    TEXT NOT NULL DEFAULT 'maxwell',
    title       TEXT NOT NULL,
    description TEXT,
    due_at      TEXT,
    status      TEXT NOT NULL DEFAULT 'todo',
    pushed_at   REAL,
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL,
    FOREIGN KEY (task_day_id) REFERENCES background_task_days(id) ON DELETE SET NULL,
    FOREIGN KEY (plan_day_id) REFERENCES jarvis_plan_days(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_maxwell_workbench_status ON maxwell_workbench_items(status, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_maxwell_workbench_task_day ON maxwell_workbench_items(task_day_id) WHERE task_day_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS demo_runs (
    id                 TEXT PRIMARY KEY,
    seed_name          TEXT NOT NULL,
    profile_seed       TEXT NOT NULL,
    status             TEXT NOT NULL DEFAULT 'active',
    created_at         REAL NOT NULL,
    updated_at         REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_demo_runs_updated ON demo_runs(updated_at DESC);

CREATE TABLE IF NOT EXISTS demo_trace_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    demo_run_id     TEXT NOT NULL,
    demo_step_id    TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    agent_id        TEXT,
    user_input      TEXT,
    agent_reply     TEXT,
    tool_calls      TEXT NOT NULL,
    memory_events   TEXT NOT NULL,
    confirmation    TEXT NOT NULL,
    payload         TEXT NOT NULL,
    created_at      REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_demo_trace_run ON demo_trace_events(demo_run_id, created_at ASC);

CREATE TABLE IF NOT EXISTS demo_memory_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    demo_run_id     TEXT NOT NULL,
    demo_step_id    TEXT NOT NULL,
    memory_kind     TEXT NOT NULL,
    content         TEXT NOT NULL,
    source_text     TEXT,
    sensitivity     TEXT NOT NULL DEFAULT 'normal',
    confidence      REAL NOT NULL DEFAULT 0.6,
    importance      REAL NOT NULL DEFAULT 0.5,
    created_at      REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_demo_memory_run ON demo_memory_items(demo_run_id, created_at DESC);
"""


_initialized = False


def _ensure_initialized() -> None:
    global _initialized
    if _initialized:
        return
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(_DB_PATH) as con:
        con.executescript(SCHEMA)
        columns = {row[1] for row in con.execute("PRAGMA table_info(agent_chat_turns)").fetchall()}
        if "session_id" not in columns:
            con.execute("ALTER TABLE agent_chat_turns ADD COLUMN session_id TEXT")
        if "actions" not in columns:
            con.execute("ALTER TABLE agent_chat_turns ADD COLUMN actions TEXT NOT NULL DEFAULT '[]'")
        con.execute("CREATE INDEX IF NOT EXISTS idx_chat_session_agent ON agent_chat_turns(session_id, agent_id, timestamp)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_jarvis_plans_status ON jarvis_plans(status, updated_at DESC)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_jarvis_plans_source_background ON jarvis_plans(source_background_task_id)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_jarvis_plan_days_plan ON jarvis_plan_days(plan_id, plan_date ASC, sort_order ASC)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_jarvis_plan_days_status ON jarvis_plan_days(status, plan_date ASC)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_jarvis_plan_days_date ON jarvis_plan_days(plan_date ASC, status)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_jarvis_agent_events_type ON jarvis_agent_events(event_type, created_at DESC)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_jarvis_agent_events_plan ON jarvis_agent_events(plan_id, created_at DESC)")
        roundtable_columns = {row[1] for row in con.execute("PRAGMA table_info(roundtable_sessions)").fetchall()}
        roundtable_defaults = {
            "mode": "TEXT NOT NULL DEFAULT 'brainstorm'",
            "source_session_id": "TEXT",
            "source_agent_id": "TEXT",
            "status": "TEXT NOT NULL DEFAULT 'active'",
            "title": "TEXT NOT NULL DEFAULT ''",
            "user_prompt": "TEXT NOT NULL DEFAULT ''",
        }
        for column_name, column_def in roundtable_defaults.items():
            if roundtable_columns and column_name not in roundtable_columns:
                con.execute(f"ALTER TABLE roundtable_sessions ADD COLUMN {column_name} {column_def}")
        roundtable_result_columns = {row[1] for row in con.execute("PRAGMA table_info(roundtable_results)").fetchall()}
        roundtable_result_defaults = {
            "result_json": "TEXT NOT NULL DEFAULT '{}'",
            "user_choice": "TEXT",
            "handoff_status": "TEXT NOT NULL DEFAULT 'none'",
        }
        for column_name, column_def in roundtable_result_defaults.items():
            if roundtable_result_columns and column_name not in roundtable_result_columns:
                con.execute(f"ALTER TABLE roundtable_results ADD COLUMN {column_name} {column_def}")
        con.execute("CREATE INDEX IF NOT EXISTS idx_roundtable_results_session ON roundtable_results(session_id, created_at DESC)")
        conversation_columns = {row[1] for row in con.execute("PRAGMA table_info(conversation_history)").fetchall()}
        conversation_defaults = {
            "session_id": "TEXT NOT NULL DEFAULT ''",
            "route_payload": "TEXT NOT NULL DEFAULT '{}'",
            "last_opened_at": "REAL",
        }
        for column_name, column_def in conversation_defaults.items():
            if conversation_columns and column_name not in conversation_columns:
                con.execute(f"ALTER TABLE conversation_history ADD COLUMN {column_name} {column_def}")
        con.execute("CREATE INDEX IF NOT EXISTS idx_conversation_history_active ON conversation_history(status, updated_at DESC)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_conversation_history_unopened ON conversation_history(status, last_opened_at, created_at)")
        collaboration_columns = {row[1] for row in con.execute("PRAGMA table_info(collaboration_memories)").fetchall()}
        if collaboration_columns and "session_id" not in collaboration_columns:
            con.execute("ALTER TABLE collaboration_memories ADD COLUMN session_id TEXT")
        proactive_columns = {row[1] for row in con.execute("PRAGMA table_info(proactive_messages)").fetchall()}
        proactive_defaults = {
            "priority": "TEXT NOT NULL DEFAULT 'normal'",
            "status": "TEXT NOT NULL DEFAULT 'pending'",
            "delivered_at": "REAL",
            "read_at": "REAL",
            "dismissed_at": "REAL",
            "snoozed_until": "REAL",
        }
        for column_name, column_def in proactive_defaults.items():
            if proactive_columns and column_name not in proactive_columns:
                con.execute(f"ALTER TABLE proactive_messages ADD COLUMN {column_name} {column_def}")
        con.execute("CREATE INDEX IF NOT EXISTS idx_proactive_messages_status ON proactive_messages(status, created_at DESC)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_proactive_messages_agent ON proactive_messages(agent_id, status, created_at DESC)")
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS local_life_items (
                id              TEXT PRIMARY KEY,
                source_url      TEXT NOT NULL UNIQUE,
                title           TEXT NOT NULL,
                item_type       TEXT NOT NULL DEFAULT 'event',
                category        TEXT NOT NULL DEFAULT 'general',
                venue           TEXT,
                address         TEXT,
                lat             REAL,
                lng             REAL,
                distance_m      INTEGER,
                starts_at       TEXT,
                ends_at         TEXT,
                expires_at      TEXT,
                summary         TEXT NOT NULL DEFAULT '',
                fit_tags_json   TEXT NOT NULL DEFAULT '[]',
                confidence      REAL NOT NULL DEFAULT 0.5,
                date_confidence TEXT NOT NULL DEFAULT 'low',
                location_label  TEXT NOT NULL DEFAULT '',
                query           TEXT NOT NULL DEFAULT '',
                status          TEXT NOT NULL DEFAULT 'active',
                last_seen_at    REAL NOT NULL,
                created_at      REAL NOT NULL,
                updated_at      REAL NOT NULL
            )
            """
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_local_life_items_expires ON local_life_items(status, expires_at, confidence DESC)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_local_life_items_category ON local_life_items(status, category, updated_at DESC)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_care_triggers_type ON jarvis_care_triggers(trigger_type, created_at DESC)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_care_triggers_status ON jarvis_care_triggers(status, created_at DESC)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_care_interventions_status ON jarvis_care_interventions(status, created_at DESC)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_care_interventions_message ON jarvis_care_interventions(message_id)")
        emotion_columns = {row[1] for row in con.execute("PRAGMA table_info(jarvis_emotion_observations)").fetchall()}
        emotion_defaults = {
            "secondary_emotions": "TEXT NOT NULL DEFAULT '[]'",
            "signals_json": "TEXT NOT NULL DEFAULT '[]'",
            "source": "TEXT NOT NULL DEFAULT 'chat_rule_mvp'",
        }
        for column_name, column_def in emotion_defaults.items():
            if emotion_columns and column_name not in emotion_columns:
                con.execute(f"ALTER TABLE jarvis_emotion_observations ADD COLUMN {column_name} {column_def}")
        con.execute("CREATE INDEX IF NOT EXISTS idx_emotion_observations_created ON jarvis_emotion_observations(created_at DESC)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_emotion_observations_session ON jarvis_emotion_observations(session_id, created_at DESC)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_emotion_observations_risk ON jarvis_emotion_observations(risk_level, created_at DESC)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_mood_snapshots_updated ON jarvis_mood_snapshots(updated_at DESC)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_behavior_observations_date ON jarvis_behavior_observations(date, created_at DESC)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_behavior_observations_session ON jarvis_behavior_observations(session_id, created_at DESC)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_behavior_observations_type ON jarvis_behavior_observations(observation_type, created_at DESC)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_stress_signals_date ON jarvis_stress_signals(date, created_at DESC)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_stress_signals_type ON jarvis_stress_signals(signal_type, created_at DESC)")
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS proactive_routine_runs (
                id         TEXT PRIMARY KEY,
                routine_id TEXT NOT NULL,
                run_date   TEXT NOT NULL,
                message_id TEXT,
                fired_at   REAL NOT NULL,
                UNIQUE(routine_id, run_date)
            )
            """
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_proactive_routine_runs_date ON proactive_routine_runs(run_date, routine_id)")
        memory_columns = {row[1] for row in con.execute("PRAGMA table_info(jarvis_memories)").fetchall()}
        memory_defaults = {
            "memory_tier": "TEXT NOT NULL DEFAULT 'raw'",
            "visibility": "TEXT NOT NULL DEFAULT 'global'",
            "owner_agent_id": "TEXT",
            "allowed_agent_ids": "TEXT NOT NULL DEFAULT '[]'",
            "compressed_from_ids": "TEXT NOT NULL DEFAULT '[]'",
            "expires_at": "REAL",
            "decay_score": "REAL NOT NULL DEFAULT 0.0",
            "last_accessed_at": "REAL",
            "access_count": "INTEGER NOT NULL DEFAULT 0",
        }
        for column_name, column_def in memory_defaults.items():
            if column_name not in memory_columns:
                con.execute(f"ALTER TABLE jarvis_memories ADD COLUMN {column_name} {column_def}")
        con.execute("CREATE INDEX IF NOT EXISTS idx_jarvis_memories_lifecycle ON jarvis_memories(status, memory_tier, visibility, updated_at DESC)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_jarvis_calendar_events_time ON jarvis_calendar_events(start, end)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_jarvis_calendar_events_status ON jarvis_calendar_events(status, start)")
        workbench_columns = {row[1] for row in con.execute("PRAGMA table_info(maxwell_workbench_items)").fetchall()}
        if workbench_columns and "plan_day_id" not in workbench_columns:
            con.execute("ALTER TABLE maxwell_workbench_items ADD COLUMN plan_day_id TEXT")
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_maxwell_workbench_plan_day ON maxwell_workbench_items(plan_day_id) WHERE plan_day_id IS NOT NULL")
        con.commit()
    _initialized = True


@contextmanager
def _conn():
    _ensure_initialized()
    con = sqlite3.connect(_DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
    finally:
        con.close()


# -- Session persistence -------------------------------------------


def _save_session_sync(
    session_id: str,
    scenario_id: str,
    scenario_name: str,
    participants: list[str],
    agent_roster: str,
    round_count: int,
    title: str | None = None,
    user_prompt: str | None = None,
    mode: str | None = None,
    source_session_id: str | None = None,
    source_agent_id: str | None = None,
    status: str = "active",
) -> None:
    now = time.time()
    with _conn() as con:
        existing = con.execute(
            "SELECT mode, source_session_id, source_agent_id, status, title, user_prompt FROM roundtable_sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        effective_mode = mode or (existing["mode"] if existing else "brainstorm")
        effective_source_session_id = source_session_id if source_session_id is not None else (existing["source_session_id"] if existing else None)
        effective_source_agent_id = source_agent_id if source_agent_id is not None else (existing["source_agent_id"] if existing else None)
        effective_status = status or (existing["status"] if existing else "active")
        effective_title = title if title is not None else (existing["title"] if existing else scenario_name)
        effective_user_prompt = user_prompt if user_prompt is not None else (existing["user_prompt"] if existing else "")
        con.execute(
            """
            INSERT INTO roundtable_sessions
              (session_id, scenario_id, scenario_name, participants,
               agent_roster, round_count, title, user_prompt, created_at, updated_at,
               mode, source_session_id, source_agent_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
              round_count = excluded.round_count,
              title = excluded.title,
              user_prompt = excluded.user_prompt,
              mode = excluded.mode,
              source_session_id = excluded.source_session_id,
              source_agent_id = excluded.source_agent_id,
              status = excluded.status,
              updated_at  = excluded.updated_at
            """,
            (session_id, scenario_id, scenario_name, json.dumps(participants),
             agent_roster, round_count, effective_title, effective_user_prompt, now, now, effective_mode, effective_source_session_id, effective_source_agent_id, effective_status),
        )
        con.commit()


async def save_session(
    *,
    session_id: str,
    scenario_id: str,
    scenario_name: str,
    participants: list[str],
    agent_roster: str,
    round_count: int,
    title: str | None = None,
    user_prompt: str | None = None,
    mode: str | None = None,
    source_session_id: str | None = None,
    source_agent_id: str | None = None,
    status: str = "active",
) -> None:
    try:
        await asyncio.to_thread(
            _save_session_sync,
            session_id, scenario_id, scenario_name,
            participants, agent_roster, round_count,
            title, user_prompt,
            mode, source_session_id, source_agent_id, status,
        )
    except Exception as exc:
        logger.warning("persistence.save_session_failed", session_id=session_id, error=str(exc))


def _append_turn_sync(
    session_id: str, role: str, speaker_name: str, content: str, timestamp: float
) -> None:
    with _conn() as con:
        con.execute(
            """
            INSERT INTO roundtable_turns (session_id, role, speaker_name, content, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, role, speaker_name, content, timestamp),
        )
        con.execute(
            "UPDATE roundtable_sessions SET updated_at = ? WHERE session_id = ?",
            (timestamp, session_id),
        )
        con.commit()


async def append_turn(
    *, session_id: str, role: str, speaker_name: str, content: str, timestamp: float
) -> None:
    try:
        await asyncio.to_thread(
            _append_turn_sync, session_id, role, speaker_name, content, timestamp
        )
    except Exception as exc:
        logger.warning("persistence.append_turn_failed", session_id=session_id, error=str(exc))


def _list_sessions_sync(limit: int) -> list[dict[str, Any]]:
    with _conn() as con:
        rows = con.execute(
            """
            SELECT session_id, scenario_id, scenario_name, participants,
                   agent_roster, round_count, mode, source_session_id,
                   source_agent_id, status, title, user_prompt, created_at, updated_at
            FROM roundtable_sessions
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        try:
            d["participants"] = json.loads(d["participants"])
        except Exception:
            d["participants"] = []
        results.append(d)
    return results


async def list_sessions(limit: int = 20) -> list[dict[str, Any]]:
    try:
        return await asyncio.to_thread(_list_sessions_sync, limit)
    except Exception as exc:
        logger.warning("persistence.list_sessions_failed", error=str(exc))
        return []


def _get_roundtable_session_sync(session_id: str) -> dict[str, Any] | None:
    with _conn() as con:
        row = con.execute(
            """
            SELECT session_id, scenario_id, scenario_name, participants,
                   agent_roster, round_count, mode, source_session_id,
                   source_agent_id, status, title, user_prompt, created_at, updated_at
            FROM roundtable_sessions
            WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()
    if row is None:
        return None
    item = dict(row)
    try:
        item["participants"] = json.loads(item["participants"])
    except Exception:
        item["participants"] = []
    return item


async def get_roundtable_session(session_id: str) -> dict[str, Any] | None:
    try:
        return await asyncio.to_thread(_get_roundtable_session_sync, session_id)
    except Exception as exc:
        logger.warning("persistence.get_roundtable_session_failed", session_id=session_id, error=str(exc))
        return None


def _get_session_turns_sync(session_id: str) -> list[dict[str, Any]]:
    with _conn() as con:
        rows = con.execute(
            """
            SELECT role, speaker_name, content, timestamp
            FROM roundtable_turns
            WHERE session_id = ?
            ORDER BY id ASC
            """,
            (session_id,),
        ).fetchall()
    return [dict(r) for r in rows]


async def get_session_turns(session_id: str) -> list[dict[str, Any]]:
    try:
        return await asyncio.to_thread(_get_session_turns_sync, session_id)
    except Exception as exc:
        logger.warning("persistence.get_session_turns_failed", error=str(exc))
        return []


# -- Context snapshot persistence ----------------------------------


def _snapshot_context_sync(
    stress_level: float, schedule_density: float, sleep_quality: float,
    mood_trend: str, source_agent: str,
) -> None:
    with _conn() as con:
        con.execute(
            """
            INSERT INTO life_context_snapshots
              (captured_at, stress_level, schedule_density, sleep_quality, mood_trend, source_agent)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (time.time(), stress_level, schedule_density, sleep_quality, mood_trend, source_agent),
        )
        con.commit()


async def snapshot_context(
    *, stress_level: float, schedule_density: float, sleep_quality: float,
    mood_trend: str, source_agent: str = "system",
) -> None:
    try:
        await asyncio.to_thread(
            _snapshot_context_sync,
            stress_level, schedule_density, sleep_quality, mood_trend, source_agent,
        )
    except Exception as exc:
        logger.warning("persistence.snapshot_failed", error=str(exc))


def _latest_context_sync() -> dict[str, Any] | None:
    with _conn() as con:
        row = con.execute(
            """
            SELECT captured_at, stress_level, schedule_density, sleep_quality,
                   mood_trend, source_agent
            FROM life_context_snapshots
            ORDER BY captured_at DESC
            LIMIT 1
            """,
        ).fetchone()
    return dict(row) if row else None


async def latest_context() -> dict[str, Any] | None:
    try:
        return await asyncio.to_thread(_latest_context_sync)
    except Exception as exc:
        logger.warning("persistence.latest_context_failed", error=str(exc))
        return None


def _context_history_sync(limit: int) -> list[dict[str, Any]]:
    with _conn() as con:
        rows = con.execute(
            """
            SELECT captured_at, stress_level, schedule_density, sleep_quality,
                   mood_trend, source_agent
            FROM life_context_snapshots
            ORDER BY captured_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


async def context_history(limit: int = 100) -> list[dict[str, Any]]:
    try:
        return await asyncio.to_thread(_context_history_sync, limit)
    except Exception as exc:
        logger.warning("persistence.context_history_failed", error=str(exc))
        return []


# -- Emotion observations ------------------------------------------


def _row_to_emotion_observation(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    for key in ("secondary_emotions", "signals_json"):
        try:
            item[key] = json.loads(item.get(key) or "[]")
        except Exception:
            item[key] = []
    return item


def _save_emotion_observation_sync(
    *,
    session_id: str | None,
    turn_id: int | None,
    agent_id: str,
    primary_emotion: str,
    secondary_emotions: list[str] | None = None,
    valence: float,
    arousal: float,
    stress_score: float,
    fatigue_score: float,
    risk_level: str,
    confidence: float,
    evidence_summary: str,
    signals: list[str] | None = None,
    source: str = "chat_rule_mvp",
    created_at: float | None = None,
) -> dict[str, Any]:
    observation_id = f"emo-{uuid4().hex}"
    created_at = created_at if created_at is not None else time.time()
    with _conn() as con:
        con.execute(
            """
            INSERT INTO jarvis_emotion_observations
              (id, session_id, turn_id, agent_id, primary_emotion, secondary_emotions,
               valence, arousal, stress_score, fatigue_score, risk_level, confidence,
               evidence_summary, signals_json, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                observation_id,
                session_id,
                turn_id,
                agent_id,
                primary_emotion,
                json.dumps(secondary_emotions or [], ensure_ascii=False),
                valence,
                arousal,
                stress_score,
                fatigue_score,
                risk_level,
                confidence,
                evidence_summary,
                json.dumps(signals or [], ensure_ascii=False),
                source,
                created_at,
            ),
        )
        row = con.execute(
            "SELECT * FROM jarvis_emotion_observations WHERE id = ?",
            (observation_id,),
        ).fetchone()
        con.commit()
    return _row_to_emotion_observation(row) if row else {}


async def save_emotion_observation(
    *,
    session_id: str | None,
    turn_id: int | None = None,
    agent_id: str,
    primary_emotion: str,
    secondary_emotions: list[str] | None = None,
    valence: float,
    arousal: float,
    stress_score: float,
    fatigue_score: float,
    risk_level: str,
    confidence: float,
    evidence_summary: str,
    signals: list[str] | None = None,
    source: str = "chat_rule_mvp",
    created_at: float | None = None,
) -> dict[str, Any]:
    return await asyncio.to_thread(
        _save_emotion_observation_sync,
        session_id=session_id,
        turn_id=turn_id,
        agent_id=agent_id,
        primary_emotion=primary_emotion,
        secondary_emotions=secondary_emotions,
        valence=valence,
        arousal=arousal,
        stress_score=stress_score,
        fatigue_score=fatigue_score,
        risk_level=risk_level,
        confidence=confidence,
        evidence_summary=evidence_summary,
        signals=signals,
        source=source,
        created_at=created_at,
    )


def _list_emotion_observations_sync(
    *,
    session_id: str | None = None,
    risk_level: str | None = None,
    created_from: float | None = None,
    created_to: float | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if session_id:
        clauses.append("session_id = ?")
        params.append(session_id)
    if risk_level:
        clauses.append("risk_level = ?")
        params.append(risk_level)
    if created_from is not None:
        clauses.append("created_at >= ?")
        params.append(created_from)
    if created_to is not None:
        clauses.append("created_at < ?")
        params.append(created_to)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with _conn() as con:
        rows = con.execute(
            f"""
            SELECT * FROM jarvis_emotion_observations
            {where}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (*params, limit),
        ).fetchall()
    return [_row_to_emotion_observation(row) for row in rows]


async def list_emotion_observations(
    *,
    session_id: str | None = None,
    risk_level: str | None = None,
    created_from: float | None = None,
    created_to: float | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    return await asyncio.to_thread(
        _list_emotion_observations_sync,
        session_id=session_id,
        risk_level=risk_level,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
    )


def _row_to_mood_snapshot(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    for key in ("dominant_emotions", "positive_events", "negative_events", "risk_flags"):
        try:
            item[key] = json.loads(item.get(key) or "[]")
        except Exception:
            item[key] = []
    return item


def _upsert_mood_snapshot_sync(
    *,
    date: str,
    mood_score: float,
    stress_score: float,
    energy_score: float,
    sleep_risk_score: float,
    schedule_pressure_score: float,
    dominant_emotions: list[str] | None = None,
    positive_events: list[str] | None = None,
    negative_events: list[str] | None = None,
    risk_flags: list[str] | None = None,
    summary: str,
    confidence: float,
) -> dict[str, Any]:
    now = time.time()
    with _conn() as con:
        existing = con.execute("SELECT created_at FROM jarvis_mood_snapshots WHERE date = ?", (date,)).fetchone()
        created_at = float(existing["created_at"]) if existing else now
        con.execute(
            """
            INSERT INTO jarvis_mood_snapshots
              (date, mood_score, stress_score, energy_score, sleep_risk_score,
               schedule_pressure_score, dominant_emotions, positive_events,
               negative_events, risk_flags, summary, confidence, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
              mood_score = excluded.mood_score,
              stress_score = excluded.stress_score,
              energy_score = excluded.energy_score,
              sleep_risk_score = excluded.sleep_risk_score,
              schedule_pressure_score = excluded.schedule_pressure_score,
              dominant_emotions = excluded.dominant_emotions,
              positive_events = excluded.positive_events,
              negative_events = excluded.negative_events,
              risk_flags = excluded.risk_flags,
              summary = excluded.summary,
              confidence = excluded.confidence,
              updated_at = excluded.updated_at
            """,
            (
                date,
                mood_score,
                stress_score,
                energy_score,
                sleep_risk_score,
                schedule_pressure_score,
                json.dumps(dominant_emotions or [], ensure_ascii=False),
                json.dumps(positive_events or [], ensure_ascii=False),
                json.dumps(negative_events or [], ensure_ascii=False),
                json.dumps(risk_flags or [], ensure_ascii=False),
                summary,
                confidence,
                created_at,
                now,
            ),
        )
        row = con.execute("SELECT * FROM jarvis_mood_snapshots WHERE date = ?", (date,)).fetchone()
        con.commit()
    return _row_to_mood_snapshot(row) if row else {}


async def upsert_mood_snapshot(
    *,
    date: str,
    mood_score: float,
    stress_score: float,
    energy_score: float,
    sleep_risk_score: float,
    schedule_pressure_score: float,
    dominant_emotions: list[str] | None = None,
    positive_events: list[str] | None = None,
    negative_events: list[str] | None = None,
    risk_flags: list[str] | None = None,
    summary: str,
    confidence: float,
) -> dict[str, Any]:
    return await asyncio.to_thread(
        _upsert_mood_snapshot_sync,
        date=date,
        mood_score=mood_score,
        stress_score=stress_score,
        energy_score=energy_score,
        sleep_risk_score=sleep_risk_score,
        schedule_pressure_score=schedule_pressure_score,
        dominant_emotions=dominant_emotions,
        positive_events=positive_events,
        negative_events=negative_events,
        risk_flags=risk_flags,
        summary=summary,
        confidence=confidence,
    )


def _list_mood_snapshots_sync(start: str | None = None, end: str | None = None, limit: int = 60) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if start:
        clauses.append("date >= ?")
        params.append(start)
    if end:
        clauses.append("date <= ?")
        params.append(end)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with _conn() as con:
        rows = con.execute(
            f"""
            SELECT * FROM jarvis_mood_snapshots
            {where}
            ORDER BY date DESC
            LIMIT ?
            """,
            (*params, limit),
        ).fetchall()
    return [_row_to_mood_snapshot(row) for row in rows]


async def list_mood_snapshots(start: str | None = None, end: str | None = None, limit: int = 60) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_list_mood_snapshots_sync, start, end, limit)


def _row_to_behavior_observation(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def _save_behavior_observation_sync(
    *,
    date: str,
    session_id: str | None,
    agent_id: str,
    observation_type: str,
    expected_bedtime: str | None,
    expected_wake: str | None,
    actual_first_active_at: float | None = None,
    actual_last_active_at: float | None = None,
    deviation_minutes: int | None = None,
    duration_minutes: int | None = None,
    source: str = "chat_activity_mvp",
    created_at: float | None = None,
) -> dict[str, Any]:
    observation_id = uuid4().hex
    observed_at = created_at if created_at is not None else time.time()
    with _conn() as con:
        con.execute(
            """
            INSERT INTO jarvis_behavior_observations (
                id, date, session_id, agent_id, observation_type,
                expected_bedtime, expected_wake,
                actual_first_active_at, actual_last_active_at,
                deviation_minutes, duration_minutes, source, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                observation_id,
                date,
                session_id,
                agent_id,
                observation_type,
                expected_bedtime,
                expected_wake,
                actual_first_active_at,
                actual_last_active_at,
                deviation_minutes,
                duration_minutes,
                source,
                observed_at,
            ),
        )
        row = con.execute("SELECT * FROM jarvis_behavior_observations WHERE id = ?", (observation_id,)).fetchone()
        con.commit()
    return _row_to_behavior_observation(row) if row else {}


async def save_behavior_observation(
    *,
    date: str,
    session_id: str | None,
    agent_id: str,
    observation_type: str,
    expected_bedtime: str | None,
    expected_wake: str | None,
    actual_first_active_at: float | None = None,
    actual_last_active_at: float | None = None,
    deviation_minutes: int | None = None,
    duration_minutes: int | None = None,
    source: str = "chat_activity_mvp",
    created_at: float | None = None,
) -> dict[str, Any]:
    return await asyncio.to_thread(
        _save_behavior_observation_sync,
        date=date,
        session_id=session_id,
        agent_id=agent_id,
        observation_type=observation_type,
        expected_bedtime=expected_bedtime,
        expected_wake=expected_wake,
        actual_first_active_at=actual_first_active_at,
        actual_last_active_at=actual_last_active_at,
        deviation_minutes=deviation_minutes,
        duration_minutes=duration_minutes,
        source=source,
        created_at=created_at,
    )


def _upsert_behavior_activity_window_sync(
    *,
    date: str,
    session_id: str | None,
    agent_id: str,
    expected_bedtime: str | None,
    expected_wake: str | None,
    started_at: float,
    last_active_at: float,
    deviation_minutes: int | None = None,
    duration_minutes: int | None = None,
    source: str = "frontend_activity_window",
) -> dict[str, Any]:
    observed_at = last_active_at
    session_key = session_id or "__global__"
    with _conn() as con:
        row = con.execute(
            """
            SELECT * FROM jarvis_behavior_observations
            WHERE date = ? AND agent_id = ? AND COALESCE(session_id, '__global__') = ?
              AND observation_type = 'activity_window'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (date, agent_id, session_key),
        ).fetchone()
        if row:
            first_active = float(row["actual_first_active_at"] or started_at)
            last_active = max(float(row["actual_last_active_at"] or first_active), last_active_at)
            effective_duration = duration_minutes
            if effective_duration is None and last_active >= first_active:
                effective_duration = int((last_active - first_active) // 60)
            con.execute(
                """
                UPDATE jarvis_behavior_observations
                SET actual_first_active_at = ?, actual_last_active_at = ?,
                    deviation_minutes = ?, duration_minutes = ?, source = ?, created_at = ?
                WHERE id = ?
                """,
                (first_active, last_active, deviation_minutes, effective_duration, source, observed_at, row["id"]),
            )
            observation_id = row["id"]
        else:
            observation_id = uuid4().hex
            effective_duration = duration_minutes
            if effective_duration is None and last_active_at >= started_at:
                effective_duration = int((last_active_at - started_at) // 60)
            con.execute(
                """
                INSERT INTO jarvis_behavior_observations (
                    id, date, session_id, agent_id, observation_type,
                    expected_bedtime, expected_wake,
                    actual_first_active_at, actual_last_active_at,
                    deviation_minutes, duration_minutes, source, created_at
                )
                VALUES (?, ?, ?, ?, 'activity_window', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    observation_id,
                    date,
                    session_id,
                    agent_id,
                    expected_bedtime,
                    expected_wake,
                    started_at,
                    last_active_at,
                    deviation_minutes,
                    effective_duration,
                    source,
                    observed_at,
                ),
            )
        result = con.execute("SELECT * FROM jarvis_behavior_observations WHERE id = ?", (observation_id,)).fetchone()
        con.commit()
    return _row_to_behavior_observation(result) if result else {}


async def upsert_behavior_activity_window(**kwargs: Any) -> dict[str, Any]:
    return await asyncio.to_thread(_upsert_behavior_activity_window_sync, **kwargs)


def _list_behavior_observations_sync(
    *,
    date: str | None = None,
    session_id: str | None = None,
    observation_type: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if date:
        clauses.append("date = ?")
        params.append(date)
    if session_id:
        clauses.append("session_id = ?")
        params.append(session_id)
    if observation_type:
        clauses.append("observation_type = ?")
        params.append(observation_type)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with _conn() as con:
        rows = con.execute(
            f"""
            SELECT * FROM jarvis_behavior_observations
            {where}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (*params, limit),
        ).fetchall()
    return [_row_to_behavior_observation(row) for row in rows]


async def list_behavior_observations(
    *,
    date: str | None = None,
    session_id: str | None = None,
    observation_type: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    return await asyncio.to_thread(
        _list_behavior_observations_sync,
        date=date,
        session_id=session_id,
        observation_type=observation_type,
        limit=limit,
    )


def _row_to_stress_signal(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    try:
        item["source_refs"] = json.loads(item.get("source_refs") or "[]")
    except Exception:
        item["source_refs"] = []
    return item


def _replace_stress_signals_sync(
    *,
    date: str,
    signals: list[dict[str, Any]],
    source: str = "schedule_pressure_mvp",
) -> list[dict[str, Any]]:
    now = time.time()
    with _conn() as con:
        con.execute("DELETE FROM jarvis_stress_signals WHERE date = ? AND source = ?", (date, source))
        for signal in signals:
            con.execute(
                """
                INSERT INTO jarvis_stress_signals
                  (id, date, signal_type, severity, score, reason, source_refs, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid4().hex,
                    date,
                    str(signal.get("signal_type") or "unknown"),
                    str(signal.get("severity") or "low"),
                    float(signal.get("score") or 0.0),
                    str(signal.get("reason") or "未提供原因"),
                    json.dumps(signal.get("source_refs") or [], ensure_ascii=False, default=str),
                    source,
                    now,
                ),
            )
        rows = con.execute(
            """
            SELECT * FROM jarvis_stress_signals
            WHERE date = ? AND source = ?
            ORDER BY score DESC, created_at DESC
            """,
            (date, source),
        ).fetchall()
        con.commit()
    return [_row_to_stress_signal(row) for row in rows]


async def replace_stress_signals(
    *,
    date: str,
    signals: list[dict[str, Any]],
    source: str = "schedule_pressure_mvp",
) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_replace_stress_signals_sync, date=date, signals=signals, source=source)


def _list_stress_signals_sync(
    *,
    date: str | None = None,
    signal_type: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if date:
        clauses.append("date = ?")
        params.append(date[:10])
    if signal_type:
        clauses.append("signal_type = ?")
        params.append(signal_type)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with _conn() as con:
        rows = con.execute(
            f"""
            SELECT * FROM jarvis_stress_signals
            {where}
            ORDER BY score DESC, created_at DESC
            LIMIT ?
            """,
            (*params, limit),
        ).fetchall()
    return [_row_to_stress_signal(row) for row in rows]


async def list_stress_signals(
    *,
    date: str | None = None,
    signal_type: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_list_stress_signals_sync, date=date, signal_type=signal_type, limit=limit)


def _clear_psychological_care_data_sync() -> dict[str, int]:
    tables = [
        "jarvis_emotion_observations",
        "jarvis_behavior_observations",
        "jarvis_stress_signals",
        "jarvis_mood_snapshots",
    ]
    result: dict[str, int] = {}
    with _conn() as con:
        for table in tables:
            cursor = con.execute(f"DELETE FROM {table}")
            result[table] = cursor.rowcount
        con.commit()
    return result


async def clear_psychological_care_data() -> dict[str, int]:
    return await asyncio.to_thread(_clear_psychological_care_data_sync)


# 鈹€鈹€ Agent chat history (1:1 private chats) 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€


def _save_chat_turn_sync(
    agent_id: str,
    role: str,
    content: str,
    actions: list[dict[str, Any]] | None = None,
    session_id: str | None = None,
) -> int | None:
    actions_json = json.dumps(actions or [], ensure_ascii=False)
    with _conn() as con:
        cur = con.execute(
            """
            INSERT INTO agent_chat_turns (session_id, agent_id, role, content, actions, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (session_id, agent_id, role, content, actions_json, time.time()),
        )
        con.commit()
        return int(cur.lastrowid) if cur.lastrowid is not None else None


async def save_chat_turn(
    *,
    agent_id: str,
    role: str,
    content: str,
    actions: list[dict[str, Any]] | None = None,
    session_id: str | None = None,
) -> int | None:
    try:
        return await asyncio.to_thread(_save_chat_turn_sync, agent_id, role, content, actions, session_id)
    except Exception as exc:
        logger.warning("persistence.save_chat_turn_failed", agent_id=agent_id, error=str(exc))
        return None


def _get_chat_history_sync(agent_id: str, limit: int, session_id: str | None = None) -> list[dict[str, Any]]:
    with _conn() as con:
        if session_id:
            rows = con.execute(
                """
                SELECT role, content, actions, timestamp
                FROM agent_chat_turns
                WHERE agent_id = ? AND session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (agent_id, session_id, limit),
            ).fetchall()
        else:
            rows = con.execute(
                """
                SELECT role, content, actions, timestamp
                FROM agent_chat_turns
                WHERE agent_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (agent_id, limit),
            ).fetchall()
    # Reverse so the oldest is first (chronological order for display)
    turns: list[dict[str, Any]] = []
    for row in reversed(rows):
        item = dict(row)
        try:
            item["actions"] = json.loads(item.get("actions") or "[]")
        except Exception:
            item["actions"] = []
        turns.append(item)
    return turns


async def get_chat_history(agent_id: str, limit: int = 50, session_id: str | None = None) -> list[dict[str, Any]]:
    try:
        return await asyncio.to_thread(_get_chat_history_sync, agent_id, limit, session_id)
    except Exception as exc:
        logger.warning("persistence.get_chat_history_failed", agent_id=agent_id, error=str(exc))
        return []


# -- Unified Jarvis memory -----------------------------------------


def _row_to_jarvis_memory(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    try:
        item["structured_payload"] = json.loads(item["structured_payload"])
    except Exception:
        item["structured_payload"] = {}
    for key in ("allowed_agent_ids", "compressed_from_ids"):
        try:
            parsed = json.loads(item.get(key) or "[]")
            item[key] = parsed if isinstance(parsed, list) else []
        except Exception:
            item[key] = []
    return item


def _find_similar_memory_sync(memory_kind: str, content: str) -> dict[str, Any] | None:
    normalized = " ".join(content.strip().split())
    with _conn() as con:
        row = con.execute(
            """
            SELECT * FROM jarvis_memories
            WHERE status = 'active' AND memory_kind = ? AND content = ?
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (memory_kind, normalized),
        ).fetchone()
    return _row_to_jarvis_memory(row) if row else None


def _save_jarvis_memory_sync(
    *,
    memory_kind: str,
    content: str,
    source_agent: str,
    session_id: str | None,
    source_text: str | None,
    structured_payload: dict[str, Any] | None,
    sensitivity: str,
    confidence: float,
    importance: float,
    memory_tier: str,
    visibility: str,
    owner_agent_id: str | None,
    allowed_agent_ids: list[str] | None,
    compressed_from_ids: list[int] | None,
    expires_at: float | None,
    decay_score: float,
) -> dict[str, Any]:
    normalized = " ".join(content.strip().split())
    existing = _find_similar_memory_sync(memory_kind, normalized)
    now = time.time()
    payload = structured_payload or {}
    owner = owner_agent_id or source_agent
    allowed = allowed_agent_ids if allowed_agent_ids is not None else ([] if visibility == "global" else [owner])
    compressed_from = compressed_from_ids or []
    with _conn() as con:
        if existing:
            new_confidence = max(float(existing.get("confidence") or 0.0), confidence)
            new_importance = max(float(existing.get("importance") or 0.0), importance)
            con.execute(
                """
                UPDATE jarvis_memories
                SET source_agent = ?, session_id = COALESCE(?, session_id), source_text = COALESCE(?, source_text),
                    structured_payload = ?, sensitivity = ?, confidence = ?, importance = ?,
                    memory_tier = ?, visibility = ?, owner_agent_id = ?,
                    allowed_agent_ids = ?, compressed_from_ids = ?, expires_at = ?,
                    decay_score = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    source_agent,
                    session_id,
                    source_text,
                    json.dumps(payload, ensure_ascii=False, default=str),
                    sensitivity,
                    new_confidence,
                    new_importance,
                    memory_tier,
                    visibility,
                    owner,
                    json.dumps(allowed, ensure_ascii=False),
                    json.dumps(compressed_from, ensure_ascii=False),
                    expires_at,
                    decay_score,
                    now,
                    existing["id"],
                ),
            )
            memory_id = existing["id"]
        else:
            cursor = con.execute(
                """
                INSERT INTO jarvis_memories
                  (memory_kind, content, source_agent, session_id, source_text, structured_payload,
                   sensitivity, confidence, importance, memory_tier, visibility, owner_agent_id,
                   allowed_agent_ids, compressed_from_ids, expires_at, decay_score, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory_kind,
                    normalized,
                    source_agent,
                    session_id,
                    source_text,
                    json.dumps(payload, ensure_ascii=False, default=str),
                    sensitivity,
                    confidence,
                    importance,
                    memory_tier,
                    visibility,
                    owner,
                    json.dumps(allowed, ensure_ascii=False),
                    json.dumps(compressed_from, ensure_ascii=False),
                    expires_at,
                    decay_score,
                    now,
                    now,
                ),
            )
            memory_id = cursor.lastrowid
        row = con.execute("SELECT * FROM jarvis_memories WHERE id = ?", (memory_id,)).fetchone()
        con.commit()
    return _row_to_jarvis_memory(row)


async def save_jarvis_memory(
    *,
    memory_kind: str,
    content: str,
    source_agent: str,
    session_id: str | None = None,
    source_text: str | None = None,
    structured_payload: dict[str, Any] | None = None,
    sensitivity: str = "normal",
    confidence: float = 0.6,
    importance: float = 0.5,
    memory_tier: str = "raw",
    visibility: str | None = None,
    owner_agent_id: str | None = None,
    allowed_agent_ids: list[str] | None = None,
    compressed_from_ids: list[int] | None = None,
    expires_at: float | None = None,
    decay_score: float = 0.0,
) -> dict[str, Any]:
    effective_visibility = visibility or ("global" if sensitivity == "normal" else "private_raw")
    return await asyncio.to_thread(
        _save_jarvis_memory_sync,
        memory_kind=memory_kind,
        content=content,
        source_agent=source_agent,
        session_id=session_id,
        source_text=source_text,
        structured_payload=structured_payload,
        sensitivity=sensitivity,
        confidence=confidence,
        importance=importance,
        memory_tier=memory_tier,
        visibility=effective_visibility,
        owner_agent_id=owner_agent_id,
        allowed_agent_ids=allowed_agent_ids,
        compressed_from_ids=compressed_from_ids,
        expires_at=expires_at,
        decay_score=decay_score,
    )


def _list_jarvis_memories_sync(
    *,
    memory_kind: str | None = None,
    status: str = "active",
    limit: int = 50,
) -> list[dict[str, Any]]:
    with _conn() as con:
        if memory_kind:
            rows = con.execute(
                """
                SELECT * FROM jarvis_memories
                WHERE status = ? AND memory_kind = ?
                ORDER BY importance DESC, updated_at DESC
                LIMIT ?
                """,
                (status, memory_kind, limit),
            ).fetchall()
        else:
            rows = con.execute(
                """
                SELECT * FROM jarvis_memories
                WHERE status = ?
                ORDER BY importance DESC, updated_at DESC
                LIMIT ?
                """,
                (status, limit),
            ).fetchall()
    return [_row_to_jarvis_memory(row) for row in rows]


async def list_jarvis_memories(
    *,
    memory_kind: str | None = None,
    status: str = "active",
    limit: int = 50,
) -> list[dict[str, Any]]:
    return await asyncio.to_thread(
        _list_jarvis_memories_sync,
        memory_kind=memory_kind,
        status=status,
        limit=limit,
    )


def _mark_jarvis_memories_used_sync(memory_ids: list[int]) -> None:
    if not memory_ids:
        return
    placeholders = ",".join("?" for _ in memory_ids)
    with _conn() as con:
        con.execute(
            f"UPDATE jarvis_memories SET last_used_at = ?, last_accessed_at = ?, access_count = access_count + 1 WHERE id IN ({placeholders})",
            (time.time(), time.time(), *memory_ids),
        )
        con.commit()


def _archive_jarvis_memories_sync(memory_ids: list[int]) -> int:
    if not memory_ids:
        return 0
    placeholders = ",".join("?" for _ in memory_ids)
    with _conn() as con:
        cursor = con.execute(
            f"UPDATE jarvis_memories SET status = 'archived', updated_at = ? WHERE id IN ({placeholders}) AND status = 'active'",
            (time.time(), *memory_ids),
        )
        con.commit()
    return cursor.rowcount


async def mark_jarvis_memories_used(memory_ids: list[int]) -> None:
    await asyncio.to_thread(_mark_jarvis_memories_used_sync, memory_ids)


async def archive_jarvis_memories(memory_ids: list[int]) -> int:
    return await asyncio.to_thread(_archive_jarvis_memories_sync, memory_ids)


def _delete_jarvis_memory_sync(memory_id: int) -> bool:
    with _conn() as con:
        cursor = con.execute(
            "UPDATE jarvis_memories SET status = 'deleted', updated_at = ? WHERE id = ? AND status != 'deleted'",
            (time.time(), memory_id),
        )
        con.commit()
    return cursor.rowcount > 0


async def delete_jarvis_memory(memory_id: int) -> bool:
    return await asyncio.to_thread(_delete_jarvis_memory_sync, memory_id)


# -- Agent preference profiles -------------------------------------


def _row_to_agent_preference_profile(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def _upsert_agent_preference_profile_sync(
    *,
    agent_id: str,
    preference_key: str,
    preference_value: str,
    confidence: float,
    source_agent: str,
    source_excerpt: str | None,
) -> dict[str, Any]:
    normalized_agent = (agent_id or "global").strip().lower()
    normalized_key = " ".join(preference_key.strip().split())
    normalized_value = " ".join(preference_value.strip().split())
    now = time.time()
    with _conn() as con:
        existing = con.execute(
            """
            SELECT * FROM agent_preference_profiles
            WHERE status = 'active' AND agent_id = ? AND preference_key = ?
            LIMIT 1
            """,
            (normalized_agent, normalized_key),
        ).fetchone()
        if existing:
            con.execute(
                """
                UPDATE agent_preference_profiles
                SET preference_value = ?,
                    confidence = MAX(confidence, ?),
                    evidence_count = evidence_count + 1,
                    source_agent = ?,
                    source_excerpt = COALESCE(?, source_excerpt),
                    updated_at = ?,
                    last_seen_at = ?
                WHERE id = ?
                """,
                (
                    normalized_value,
                    confidence,
                    source_agent,
                    source_excerpt,
                    now,
                    now,
                    existing["id"],
                ),
            )
            profile_id = existing["id"]
        else:
            cursor = con.execute(
                """
                INSERT INTO agent_preference_profiles
                  (agent_id, preference_key, preference_value, confidence,
                   evidence_count, source_agent, source_excerpt,
                   created_at, updated_at, last_seen_at)
                VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?)
                """,
                (
                    normalized_agent,
                    normalized_key,
                    normalized_value,
                    confidence,
                    source_agent,
                    source_excerpt,
                    now,
                    now,
                    now,
                ),
            )
            profile_id = cursor.lastrowid
        row = con.execute("SELECT * FROM agent_preference_profiles WHERE id = ?", (profile_id,)).fetchone()
        con.commit()
    return _row_to_agent_preference_profile(row)


async def upsert_agent_preference_profile(
    *,
    agent_id: str,
    preference_key: str,
    preference_value: str,
    confidence: float = 0.6,
    source_agent: str,
    source_excerpt: str | None = None,
) -> dict[str, Any]:
    return await asyncio.to_thread(
        _upsert_agent_preference_profile_sync,
        agent_id=agent_id,
        preference_key=preference_key,
        preference_value=preference_value,
        confidence=confidence,
        source_agent=source_agent,
        source_excerpt=source_excerpt,
    )


def _list_agent_preference_profiles_sync(
    *,
    agent_id: str | None = None,
    status: str = "active",
    limit: int = 20,
) -> list[dict[str, Any]]:
    with _conn() as con:
        if agent_id:
            rows = con.execute(
                """
                SELECT * FROM agent_preference_profiles
                WHERE status = ? AND agent_id = ?
                ORDER BY confidence DESC, evidence_count DESC, updated_at DESC
                LIMIT ?
                """,
                (status, agent_id.strip().lower(), limit),
            ).fetchall()
        else:
            rows = con.execute(
                """
                SELECT * FROM agent_preference_profiles
                WHERE status = ?
                ORDER BY confidence DESC, evidence_count DESC, updated_at DESC
                LIMIT ?
                """,
                (status, limit),
            ).fetchall()
    return [_row_to_agent_preference_profile(row) for row in rows]


async def list_agent_preference_profiles(
    *,
    agent_id: str | None = None,
    status: str = "active",
    limit: int = 20,
) -> list[dict[str, Any]]:
    return await asyncio.to_thread(
        _list_agent_preference_profiles_sync,
        agent_id=agent_id,
        status=status,
        limit=limit,
    )


# -- Conversation history list -------------------------------------


def _row_to_conversation(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    try:
        item["route_payload"] = json.loads(item["route_payload"])
    except Exception:
        item["route_payload"] = {}
    return item


def _cleanup_expired_conversations_sync(days: int = 7) -> int:
    cutoff = time.time() - days * 24 * 60 * 60
    with _conn() as con:
        cursor = con.execute(
            """
            UPDATE conversation_history
            SET status = 'deleted', updated_at = ?
            WHERE status = 'active' AND COALESCE(last_opened_at, updated_at, created_at) < ?
            """,
            (time.time(), cutoff),
        )
        con.commit()
    return cursor.rowcount


async def cleanup_expired_conversations(days: int = 7) -> int:
    return await asyncio.to_thread(_cleanup_expired_conversations_sync, days)


def _save_conversation_sync(
    *,
    conversation_id: str,
    conversation_type: str,
    title: str,
    agent_id: str | None,
    scenario_id: str | None,
    session_id: str,
    route_payload: dict[str, Any],
) -> dict[str, Any]:
    now = time.time()
    with _conn() as con:
        con.execute(
            """
            INSERT INTO conversation_history
              (id, conversation_type, title, agent_id, scenario_id, session_id, route_payload,
               status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              title = excluded.title,
              agent_id = excluded.agent_id,
              scenario_id = excluded.scenario_id,
              route_payload = excluded.route_payload,
              status = 'active',
              updated_at = excluded.updated_at
            """,
            (
                conversation_id,
                conversation_type,
                title,
                agent_id,
                scenario_id,
                session_id,
                json.dumps(route_payload, ensure_ascii=False, default=str),
                now,
                now,
            ),
        )
        row = con.execute("SELECT * FROM conversation_history WHERE id = ?", (conversation_id,)).fetchone()
        con.commit()
    return _row_to_conversation(row)


async def save_conversation(
    *,
    conversation_id: str,
    conversation_type: str,
    title: str,
    agent_id: str | None = None,
    scenario_id: str | None = None,
    session_id: str,
    route_payload: dict[str, Any],
) -> dict[str, Any]:
    return await asyncio.to_thread(
        _save_conversation_sync,
        conversation_id=conversation_id,
        conversation_type=conversation_type,
        title=title,
        agent_id=agent_id,
        scenario_id=scenario_id,
        session_id=session_id,
        route_payload=route_payload,
    )


def _list_conversations_sync(limit: int = 30) -> list[dict[str, Any]]:
    _cleanup_expired_conversations_sync(days=7)
    with _conn() as con:
        rows = con.execute(
            """
            SELECT * FROM conversation_history
            WHERE status = 'active'
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [_row_to_conversation(row) for row in rows]


async def list_conversations(limit: int = 30) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_list_conversations_sync, limit)


def _mark_conversation_opened_sync(conversation_id: str) -> dict[str, Any] | None:
    now = time.time()
    with _conn() as con:
        con.execute(
            "UPDATE conversation_history SET last_opened_at = ?, updated_at = ? WHERE id = ? AND status = 'active'",
            (now, now, conversation_id),
        )
        row = con.execute("SELECT * FROM conversation_history WHERE id = ? AND status = 'active'", (conversation_id,)).fetchone()
        con.commit()
    return _row_to_conversation(row) if row else None


async def mark_conversation_opened(conversation_id: str) -> dict[str, Any] | None:
    return await asyncio.to_thread(_mark_conversation_opened_sync, conversation_id)


def _delete_conversation_sync(conversation_id: str) -> bool:
    with _conn() as con:
        row = con.execute(
            "SELECT conversation_type, agent_id, session_id FROM conversation_history WHERE id = ? AND status != 'deleted'",
            (conversation_id,),
        ).fetchone()
        cursor = con.execute(
            "UPDATE conversation_history SET status = 'deleted', updated_at = ? WHERE id = ? AND status != 'deleted'",
            (time.time(), conversation_id),
        )
        if row and row["conversation_type"] == "private_chat" and row["agent_id"] and row["session_id"]:
            con.execute(
                "DELETE FROM agent_chat_turns WHERE agent_id = ? AND session_id = ?",
                (row["agent_id"], row["session_id"]),
            )
        con.commit()
    return cursor.rowcount > 0


async def delete_conversation(conversation_id: str) -> bool:
    return await asyncio.to_thread(_delete_conversation_sync, conversation_id)


def _clear_chat_history_sync(agent_id: str, session_id: str | None = None) -> int:
    with _conn() as con:
        if session_id:
            cur = con.execute(
                "DELETE FROM agent_chat_turns WHERE agent_id = ? AND session_id = ?",
                (agent_id, session_id),
            )
        else:
            cur = con.execute("DELETE FROM agent_chat_turns WHERE agent_id = ?", (agent_id,))
        con.commit()
        return cur.rowcount


async def clear_chat_history(agent_id: str, session_id: str | None = None) -> int:
    try:
        return await asyncio.to_thread(_clear_chat_history_sync, agent_id, session_id)
    except Exception as exc:
        logger.warning("persistence.clear_chat_history_failed", agent_id=agent_id, error=str(exc))
        return 0


# 鈹€鈹€ Shared collaboration memories 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€


def _save_collaboration_memory_sync(
    session_id: str | None,
    source_agent: str,
    participant_agents: list[str],
    memory_kind: str,
    content: str,
    structured_payload: dict[str, Any],
    importance: float,
) -> None:
    with _conn() as con:
        con.execute(
            """
            INSERT INTO collaboration_memories
              (session_id, source_agent, participant_agents, memory_kind,
               content, structured_payload, importance, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                source_agent,
                json.dumps(participant_agents, ensure_ascii=False),
                memory_kind,
                content,
                json.dumps(structured_payload, ensure_ascii=False),
                importance,
                time.time(),
            ),
        )
        con.commit()


async def save_collaboration_memory(
    *,
    session_id: str | None = None,
    source_agent: str,
    participant_agents: list[str],
    memory_kind: str,
    content: str,
    structured_payload: dict[str, Any] | None = None,
    importance: float = 1.0,
) -> None:
    try:
        await asyncio.to_thread(
            _save_collaboration_memory_sync,
            session_id,
            source_agent,
            participant_agents,
            memory_kind,
            content,
            structured_payload or {},
            importance,
        )
    except Exception as exc:
        logger.warning(
            "persistence.save_collaboration_memory_failed",
            source_agent=source_agent,
            memory_kind=memory_kind,
            error=str(exc),
        )


def _get_relevant_collaboration_memories_sync(agent_id: str, limit: int) -> list[dict[str, Any]]:
    with _conn() as con:
        rows = con.execute(
            """
            SELECT session_id, source_agent, participant_agents, memory_kind,
                   content, structured_payload, importance, created_at
            FROM collaboration_memories
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (max(limit * 8, 40),),
        ).fetchall()

    results: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        try:
            participants = json.loads(item["participant_agents"])
        except Exception:
            participants = []
        try:
            payload = json.loads(item["structured_payload"])
        except Exception:
            payload = {}

        is_global = not participants
        if not is_global and agent_id not in participants and item["source_agent"] != agent_id:
            continue

        item["participant_agents"] = participants
        item["structured_payload"] = payload
        results.append(item)
        if len(results) >= limit:
            break

    return list(reversed(results))


async def get_relevant_collaboration_memories(agent_id: str, limit: int = 8) -> list[dict[str, Any]]:
    try:
        return await asyncio.to_thread(_get_relevant_collaboration_memories_sync, agent_id, limit)
    except Exception as exc:
        logger.warning(
            "persistence.get_relevant_collaboration_memories_failed",
            agent_id=agent_id,
            error=str(exc),
        )
        return []


def _clear_collaboration_memories_sync() -> int:
    with _conn() as con:
        cur = con.execute("DELETE FROM collaboration_memories")
        con.commit()
        return cur.rowcount


async def clear_collaboration_memories() -> int:
    try:
        return await asyncio.to_thread(_clear_collaboration_memories_sync)
    except Exception as exc:
        logger.warning("persistence.clear_collaboration_memories_failed", error=str(exc))
        return 0


# -- Pending actions ------------------------------------------------


def _save_pending_action_sync(
    *,
    pending_id: str,
    action_type: str,
    tool_name: str,
    agent_id: str,
    session_id: str | None,
    title: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    now = time.time()
    with _conn() as con:
        con.execute(
            """
            INSERT INTO pending_actions
              (id, action_type, tool_name, agent_id, session_id, title,
               arguments, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              action_type = excluded.action_type,
              tool_name = excluded.tool_name,
              agent_id = excluded.agent_id,
              session_id = excluded.session_id,
              title = excluded.title,
              arguments = excluded.arguments,
              updated_at = excluded.updated_at
            """,
            (
                pending_id,
                action_type,
                tool_name,
                agent_id,
                session_id,
                title,
                json.dumps(arguments, ensure_ascii=False, default=str),
                now,
                now,
            ),
        )
        con.commit()
    return _get_pending_action_sync(pending_id) or {}


async def save_pending_action(
    *,
    pending_id: str,
    action_type: str,
    tool_name: str,
    agent_id: str,
    session_id: str | None,
    title: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    return await asyncio.to_thread(
        _save_pending_action_sync,
        pending_id=pending_id,
        action_type=action_type,
        tool_name=tool_name,
        agent_id=agent_id,
        session_id=session_id,
        title=title,
        arguments=arguments,
    )


def _row_to_pending_action(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    try:
        item["arguments"] = json.loads(item["arguments"])
    except Exception:
        item["arguments"] = {}
    return item


def _get_pending_action_sync(pending_id: str) -> dict[str, Any] | None:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM pending_actions WHERE id = ?",
            (pending_id,),
        ).fetchone()
    return _row_to_pending_action(row) if row else None


async def get_pending_action(pending_id: str) -> dict[str, Any] | None:
    return await asyncio.to_thread(_get_pending_action_sync, pending_id)


def _list_pending_actions_sync(status: str | None = "pending") -> list[dict[str, Any]]:
    with _conn() as con:
        if status:
            rows = con.execute(
                "SELECT * FROM pending_actions WHERE status = ? ORDER BY created_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = con.execute("SELECT * FROM pending_actions ORDER BY created_at DESC").fetchall()
    return [_row_to_pending_action(row) for row in rows]


async def list_pending_actions(status: str | None = "pending") -> list[dict[str, Any]]:
    return await asyncio.to_thread(_list_pending_actions_sync, status)


def _update_pending_action_sync(
    pending_id: str,
    *,
    status: str | None = None,
    arguments: dict[str, Any] | None = None,
    title: str | None = None,
) -> dict[str, Any] | None:
    existing = _get_pending_action_sync(pending_id)
    if existing is None:
        return None
    new_status = status or existing["status"]
    new_arguments = arguments if arguments is not None else existing["arguments"]
    new_title = title if title is not None else existing["title"]
    with _conn() as con:
        con.execute(
            """
            UPDATE pending_actions
            SET status = ?, arguments = ?, title = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                new_status,
                json.dumps(new_arguments, ensure_ascii=False, default=str),
                new_title,
                time.time(),
                pending_id,
            ),
        )
        con.commit()
    return _get_pending_action_sync(pending_id)


async def update_pending_action(
    pending_id: str,
    *,
    status: str | None = None,
    arguments: dict[str, Any] | None = None,
    title: str | None = None,
) -> dict[str, Any] | None:
    return await asyncio.to_thread(
        _update_pending_action_sync,
        pending_id,
        status=status,
        arguments=arguments,
        title=title,
    )


# -- Proactive message persistence -----------------------------------


def _ts_to_datetime(value: float | None) -> datetime | None:
    if value is None:
        return None
    return datetime.utcfromtimestamp(value)


def _datetime_to_ts(value: Any, fallback: float | None = None) -> float:
    if isinstance(value, datetime):
        return value.timestamp()
    if isinstance(value, (int, float)):
        return float(value)
    return fallback if fallback is not None else time.time()


def _row_to_proactive_message(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["created_at"] = _ts_to_datetime(item.get("created_at"))
    item["delivered_at"] = _ts_to_datetime(item.get("delivered_at"))
    item["read_at"] = _ts_to_datetime(item.get("read_at"))
    item["dismissed_at"] = _ts_to_datetime(item.get("dismissed_at"))
    item["snoozed_until"] = _ts_to_datetime(item.get("snoozed_until"))
    item["read"] = item.get("status") == "read" or item.get("read_at") is not None
    return item


def _row_to_roundtable_result(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    json_fields = {
        "options_json": "options",
        "tradeoffs_json": "tradeoffs",
        "actions_json": "actions",
        "context_json": "context",
        "result_json": "result_json",
    }
    for raw_key, public_key in json_fields.items():
        try:
            fallback = {} if raw_key in {"context_json", "result_json"} else []
            item[public_key] = json.loads(item.get(raw_key) or json.dumps(fallback))
        except Exception:
            item[public_key] = {} if raw_key in {"context_json", "result_json"} else []
        item.pop(raw_key, None)
    if not isinstance(item.get("result_json"), dict) or not item.get("result_json"):
        item["result_json"] = {
            "summary": item.get("summary") or "",
            "options": item.get("options") or [],
            "recommended_option": item.get("recommended_option") or "",
            "tradeoffs": item.get("tradeoffs") or [],
            "actions": item.get("actions") or [],
            "context": item.get("context") or {},
        }
    return item


def _save_roundtable_result_sync(
    *,
    result_id: str,
    session_id: str,
    mode: str,
    status: str,
    summary: str,
    options: list[dict[str, Any]],
    recommended_option: str,
    tradeoffs: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    handoff_target: str,
    context: dict[str, Any],
    source_session_id: str | None = None,
    source_agent_id: str | None = None,
    pending_action_id: str | None = None,
    result_json: dict[str, Any] | None = None,
    user_choice: str | None = None,
    handoff_status: str | None = None,
) -> dict[str, Any]:
    now = time.time()
    normalized_result_json = result_json or {
        "summary": summary,
        "options": options,
        "recommended_option": recommended_option,
        "tradeoffs": tradeoffs,
        "actions": actions,
        "handoff_target": handoff_target,
        "context": context,
    }
    normalized_handoff_status = handoff_status or ("pending" if pending_action_id else "none")
    with _conn() as con:
        con.execute(
            """
            INSERT INTO roundtable_results
              (id, session_id, mode, status, summary, options_json,
               recommended_option, tradeoffs_json, actions_json, handoff_target,
               context_json, result_json, user_choice, handoff_status,
               source_session_id, source_agent_id, pending_action_id,
               created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              status = excluded.status,
              summary = excluded.summary,
              options_json = excluded.options_json,
              recommended_option = excluded.recommended_option,
              tradeoffs_json = excluded.tradeoffs_json,
              actions_json = excluded.actions_json,
              handoff_target = excluded.handoff_target,
              context_json = excluded.context_json,
              result_json = excluded.result_json,
              user_choice = COALESCE(excluded.user_choice, roundtable_results.user_choice),
              handoff_status = excluded.handoff_status,
              pending_action_id = excluded.pending_action_id,
              updated_at = excluded.updated_at
            """,
            (
                result_id,
                session_id,
                mode,
                status,
                summary,
                json.dumps(options, ensure_ascii=False, default=str),
                recommended_option,
                json.dumps(tradeoffs, ensure_ascii=False, default=str),
                json.dumps(actions, ensure_ascii=False, default=str),
                handoff_target,
                json.dumps(context, ensure_ascii=False, default=str),
                json.dumps(normalized_result_json, ensure_ascii=False, default=str),
                user_choice,
                normalized_handoff_status,
                source_session_id,
                source_agent_id,
                pending_action_id,
                now,
                now,
            ),
        )
        con.commit()
    return _get_roundtable_result_sync(result_id) or {}


async def save_roundtable_result(**kwargs: Any) -> dict[str, Any]:
    return await asyncio.to_thread(_save_roundtable_result_sync, **kwargs)


def _get_roundtable_result_sync(result_id: str) -> dict[str, Any] | None:
    with _conn() as con:
        row = con.execute("SELECT * FROM roundtable_results WHERE id = ?", (result_id,)).fetchone()
    return _row_to_roundtable_result(row) if row else None


async def get_roundtable_result(result_id: str) -> dict[str, Any] | None:
    return await asyncio.to_thread(_get_roundtable_result_sync, result_id)


def _get_latest_roundtable_result_sync(session_id: str, mode: str | None = None) -> dict[str, Any] | None:
    clauses = ["session_id = ?"]
    params: list[Any] = [session_id]
    if mode:
        clauses.append("mode = ?")
        params.append(mode)
    with _conn() as con:
        row = con.execute(
            f"""
            SELECT * FROM roundtable_results
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at DESC
            LIMIT 1
            """,
            tuple(params),
        ).fetchone()
    return _row_to_roundtable_result(row) if row else None


async def get_latest_roundtable_result(session_id: str, mode: str | None = None) -> dict[str, Any] | None:
    return await asyncio.to_thread(_get_latest_roundtable_result_sync, session_id, mode)


def _get_proactive_message_sync(message_id: str) -> dict[str, Any] | None:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM proactive_messages WHERE id = ?",
            (message_id,),
        ).fetchone()
    return _row_to_proactive_message(row) if row else None


def _save_proactive_message_sync(message: Any) -> dict[str, Any]:
    data = message.model_dump() if hasattr(message, "model_dump") else dict(message)
    now = time.time()
    created_at = _datetime_to_ts(data.get("created_at"), fallback=now)
    delivered_at = _datetime_to_ts(data.get("delivered_at")) if data.get("delivered_at") else None
    read_at = _datetime_to_ts(data.get("read_at")) if data.get("read_at") else None
    dismissed_at = _datetime_to_ts(data.get("dismissed_at")) if data.get("dismissed_at") else None
    snoozed_until = _datetime_to_ts(data.get("snoozed_until")) if data.get("snoozed_until") else None
    status = data.get("status") or ("read" if data.get("read") else "pending")
    with _conn() as con:
        con.execute(
            """
            INSERT INTO proactive_messages
              (id, agent_id, agent_name, content, trigger, priority, status,
               created_at, delivered_at, read_at, dismissed_at, snoozed_until)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              agent_id = excluded.agent_id,
              agent_name = excluded.agent_name,
              content = excluded.content,
              trigger = excluded.trigger,
              priority = excluded.priority,
              status = excluded.status,
              delivered_at = excluded.delivered_at,
              read_at = excluded.read_at,
              dismissed_at = excluded.dismissed_at,
              snoozed_until = excluded.snoozed_until
            """,
            (
                data["id"],
                data["agent_id"],
                data["agent_name"],
                data["content"],
                data["trigger"],
                data.get("priority", "normal"),
                status,
                created_at,
                delivered_at,
                read_at,
                dismissed_at,
                snoozed_until,
            ),
        )
        con.commit()
    saved = _get_proactive_message_sync(data["id"])
    return saved or {}


async def save_proactive_message(message: Any) -> dict[str, Any]:
    return await asyncio.to_thread(_save_proactive_message_sync, message)


def _list_proactive_messages_sync(
    *,
    include_read: bool = False,
    limit: int = 50,
    agent_id: str | None = None,
) -> list[dict[str, Any]]:
    clauses = ["status != 'dismissed'", "(snoozed_until IS NULL OR snoozed_until <= ?)"]
    params: list[Any] = [time.time()]
    if not include_read:
        clauses.append("status != 'read'")
    if agent_id:
        clauses.append("agent_id = ?")
        params.append(agent_id)
    params.append(limit)
    with _conn() as con:
        rows = con.execute(
            f"""
            SELECT * FROM proactive_messages
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            tuple(params),
        ).fetchall()
    return [_row_to_proactive_message(row) for row in rows]


async def list_proactive_messages(
    *,
    include_read: bool = False,
    limit: int = 50,
    agent_id: str | None = None,
) -> list[dict[str, Any]]:
    return await asyncio.to_thread(
        _list_proactive_messages_sync,
        include_read=include_read,
        limit=limit,
        agent_id=agent_id,
    )


# -- Local life cache -----------------------------------------------


def _row_to_local_life_item(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    try:
        tags = json.loads(item.get("fit_tags_json") or "[]")
        item["fit_tags"] = tags if isinstance(tags, list) else []
    except Exception:
        item["fit_tags"] = []
    item.pop("fit_tags_json", None)
    return item


def _upsert_local_life_items_sync(items: list[dict[str, Any]], now_ts: float | None = None) -> list[dict[str, Any]]:
    now = now_ts if now_ts is not None else time.time()
    saved_urls: list[str] = []
    with _conn() as con:
        for raw in items:
            source_url = str(raw.get("source_url") or "").strip()
            title = str(raw.get("title") or "").strip()
            if not source_url or not title:
                continue
            fit_tags = raw.get("fit_tags") or raw.get("fit_tags_json") or []
            if not isinstance(fit_tags, list):
                fit_tags = []
            item_id = str(raw.get("id") or f"local_life_{uuid4().hex}")
            con.execute(
                """
                INSERT INTO local_life_items
                  (id, source_url, title, item_type, category, venue, address,
                   lat, lng, distance_m, starts_at, ends_at, expires_at, summary,
                   fit_tags_json, confidence, date_confidence, location_label,
                   query, status, last_seen_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
                ON CONFLICT(source_url) DO UPDATE SET
                  title = excluded.title,
                  item_type = excluded.item_type,
                  category = excluded.category,
                  venue = excluded.venue,
                  address = excluded.address,
                  lat = excluded.lat,
                  lng = excluded.lng,
                  distance_m = excluded.distance_m,
                  starts_at = excluded.starts_at,
                  ends_at = excluded.ends_at,
                  expires_at = excluded.expires_at,
                  summary = excluded.summary,
                  fit_tags_json = excluded.fit_tags_json,
                  confidence = excluded.confidence,
                  date_confidence = excluded.date_confidence,
                  location_label = excluded.location_label,
                  query = excluded.query,
                  status = 'active',
                  last_seen_at = excluded.last_seen_at,
                  updated_at = excluded.updated_at
                """,
                (
                    item_id,
                    source_url,
                    title,
                    str(raw.get("item_type") or "event"),
                    str(raw.get("category") or "general"),
                    raw.get("venue"),
                    raw.get("address"),
                    raw.get("lat"),
                    raw.get("lng"),
                    raw.get("distance_m"),
                    raw.get("starts_at"),
                    raw.get("ends_at"),
                    raw.get("expires_at"),
                    str(raw.get("summary") or ""),
                    json.dumps(fit_tags, ensure_ascii=False, default=str),
                    float(raw.get("confidence") or 0.5),
                    str(raw.get("date_confidence") or "low"),
                    str(raw.get("location_label") or ""),
                    str(raw.get("query") or ""),
                    now,
                    now,
                    now,
                ),
            )
            saved_urls.append(source_url)
        con.commit()
        if not saved_urls:
            return []
        placeholders = ",".join("?" for _ in saved_urls)
        rows = con.execute(
            f"SELECT * FROM local_life_items WHERE source_url IN ({placeholders}) ORDER BY confidence DESC, updated_at DESC",
            tuple(saved_urls),
        ).fetchall()
    return [_row_to_local_life_item(row) for row in rows]


async def upsert_local_life_items(items: list[dict[str, Any]], now_ts: float | None = None) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_upsert_local_life_items_sync, items, now_ts)


def _list_local_life_items_sync(
    *,
    min_expires_at: str | None = None,
    category: str | None = None,
    query: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    clauses = ["status = 'active'"]
    params: list[Any] = []
    if min_expires_at:
        clauses.append("(expires_at IS NOT NULL AND expires_at >= ?)")
        params.append(min_expires_at)
    if category:
        clauses.append("(category = ? OR fit_tags_json LIKE ?)")
        params.extend([category, f"%{category}%"])
    if query:
        clauses.append("(query = ? OR title LIKE ? OR summary LIKE ?)")
        like = f"%{query}%"
        params.extend([query, like, like])
    params.append(max(1, min(limit, 50)))
    with _conn() as con:
        rows = con.execute(
            f"""
            SELECT * FROM local_life_items
            WHERE {' AND '.join(clauses)}
            ORDER BY
              CASE date_confidence WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
              confidence DESC,
              COALESCE(distance_m, 999999) ASC,
              updated_at DESC
            LIMIT ?
            """,
            tuple(params),
        ).fetchall()
    return [_row_to_local_life_item(row) for row in rows]


async def list_local_life_items(
    *,
    min_expires_at: str | None = None,
    category: str | None = None,
    query: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    return await asyncio.to_thread(
        _list_local_life_items_sync,
        min_expires_at=min_expires_at,
        category=category,
        query=query,
        limit=limit,
    )


def _mark_proactive_messages_delivered_sync(message_ids: list[str]) -> int:
    if not message_ids:
        return 0
    placeholders = ",".join("?" for _ in message_ids)
    now = time.time()
    with _conn() as con:
        cur = con.execute(
            f"""
            UPDATE proactive_messages
            SET status = 'delivered', delivered_at = COALESCE(delivered_at, ?)
            WHERE id IN ({placeholders}) AND status = 'pending'
            """,
            (now, *message_ids),
        )
        con.commit()
        return cur.rowcount


async def mark_proactive_messages_delivered(message_ids: list[str]) -> int:
    return await asyncio.to_thread(_mark_proactive_messages_delivered_sync, message_ids)


def _mark_proactive_message_read_sync(message_id: str) -> dict[str, Any] | None:
    now = time.time()
    with _conn() as con:
        con.execute(
            """
            UPDATE proactive_messages
            SET status = 'read',
                delivered_at = COALESCE(delivered_at, ?),
                read_at = COALESCE(read_at, ?)
            WHERE id = ? AND status != 'dismissed'
            """,
            (now, now, message_id),
        )
        con.commit()
    return _get_proactive_message_sync(message_id)


async def mark_proactive_message_read(message_id: str) -> dict[str, Any] | None:
    return await asyncio.to_thread(_mark_proactive_message_read_sync, message_id)


def _dismiss_proactive_message_sync(message_id: str) -> dict[str, Any] | None:
    now = time.time()
    with _conn() as con:
        con.execute(
            """
            UPDATE proactive_messages
            SET status = 'dismissed',
                dismissed_at = COALESCE(dismissed_at, ?)
            WHERE id = ? AND status != 'dismissed'
            """,
            (now, message_id),
        )
        con.commit()
    return _get_proactive_message_sync(message_id)


async def dismiss_proactive_message(message_id: str) -> dict[str, Any] | None:
    return await asyncio.to_thread(_dismiss_proactive_message_sync, message_id)


def _snooze_proactive_message_sync(message_id: str, snoozed_until: float) -> dict[str, Any] | None:
    now = time.time()
    with _conn() as con:
        con.execute(
            """
            UPDATE proactive_messages
            SET status = 'snoozed', snoozed_until = ?, delivered_at = COALESCE(delivered_at, ?)
            WHERE id = ? AND status != 'dismissed'
            """,
            (snoozed_until, now, message_id),
        )
        con.commit()
    return _get_proactive_message_sync(message_id)


async def snooze_proactive_message(message_id: str, snoozed_until: float) -> dict[str, Any] | None:
    return await asyncio.to_thread(_snooze_proactive_message_sync, message_id, snoozed_until)


def _row_to_care_trigger(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    try:
        item["evidence_ids"] = json.loads(item.pop("evidence_ids_json") or "[]")
    except Exception:
        item["evidence_ids"] = []
    item["created_at"] = _ts_to_datetime(item.get("created_at"))
    item["cooldown_until"] = _ts_to_datetime(item.get("cooldown_until"))
    item["resolved_at"] = _ts_to_datetime(item.get("resolved_at"))
    return item


def _row_to_care_intervention(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    try:
        item["suggested_action"] = json.loads(item.pop("suggested_action_json") or "{}")
    except Exception:
        item["suggested_action"] = {}
    item["created_at"] = _ts_to_datetime(item.get("created_at"))
    item["shown_at"] = _ts_to_datetime(item.get("shown_at"))
    item["acted_at"] = _ts_to_datetime(item.get("acted_at"))
    item["snoozed_until"] = _ts_to_datetime(item.get("snoozed_until"))
    return item


def _recent_care_trigger_exists_sync(trigger_type: str, cooldown_after: float) -> bool:
    with _conn() as con:
        row = con.execute(
            """
            SELECT id FROM jarvis_care_triggers
            WHERE trigger_type = ? AND created_at >= ? AND status != 'dismissed'
            LIMIT 1
            """,
            (trigger_type, cooldown_after),
        ).fetchone()
    return row is not None


async def recent_care_trigger_exists(trigger_type: str, cooldown_after: float) -> bool:
    return await asyncio.to_thread(_recent_care_trigger_exists_sync, trigger_type, cooldown_after)


def _count_care_triggers_for_day_sync(day: str) -> int:
    start = datetime.fromisoformat(day[:10]).timestamp()
    end = start + 86400
    with _conn() as con:
        row = con.execute(
            "SELECT COUNT(*) AS count FROM jarvis_care_triggers WHERE created_at >= ? AND created_at < ?",
            (start, end),
        ).fetchone()
    return int(row["count"] if row else 0)


async def count_care_triggers_for_day(day: str) -> int:
    return await asyncio.to_thread(_count_care_triggers_for_day_sync, day)


def _list_care_triggers_for_day_sync(day: str, limit: int = 50) -> list[dict[str, Any]]:
    start = datetime.fromisoformat(day[:10]).timestamp()
    end = start + 86400
    day_key = day[:10]
    with _conn() as con:
        rows = con.execute(
            """
            SELECT * FROM jarvis_care_triggers
            WHERE (created_at >= ? AND created_at < ?)
               OR evidence_ids_json LIKE ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (start, end, f'%"date": "{day_key}"%', limit),
        ).fetchall()
    return [_row_to_care_trigger(row) for row in rows]


async def list_care_triggers_for_day(day: str, limit: int = 50) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_list_care_triggers_for_day_sync, day, limit)


def _save_care_trigger_and_intervention_sync(
    *,
    trigger_type: str,
    severity: str,
    reason: str,
    evidence_ids: list[dict[str, Any]],
    content: str,
    suggested_action: dict[str, Any] | None = None,
    cooldown_until: float | None = None,
) -> dict[str, Any]:
    now = time.time()
    trigger_id = f"care_trigger_{uuid4().hex}"
    intervention_id = f"care_intervention_{uuid4().hex}"
    message_id = f"care-{uuid4().hex}"
    priority = "high" if severity == "high" else "normal"
    with _conn() as con:
        con.execute(
            """
            INSERT INTO jarvis_care_triggers
              (id, trigger_type, severity, reason, evidence_ids_json, status, cooldown_until, message_id, created_at)
            VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?)
            """,
            (trigger_id, trigger_type, severity, reason, json.dumps(evidence_ids, ensure_ascii=False, default=str), cooldown_until, message_id, now),
        )
        con.execute(
            """
            INSERT INTO proactive_messages
              (id, agent_id, agent_name, content, trigger, priority, status, created_at)
            VALUES (?, 'mira', 'Mira', ?, ?, ?, 'pending', ?)
            """,
            (message_id, content, trigger_type, priority, now),
        )
        con.execute(
            """
            INSERT INTO jarvis_care_interventions
              (id, trigger_id, message_id, agent_id, intervention_type, content,
               suggested_action_json, status, created_at)
            VALUES (?, ?, ?, 'mira', ?, ?, ?, 'pending', ?)
            """,
            (intervention_id, trigger_id, message_id, trigger_type, content, json.dumps(suggested_action or {}, ensure_ascii=False, default=str), now),
        )
        trigger_row = con.execute("SELECT * FROM jarvis_care_triggers WHERE id = ?", (trigger_id,)).fetchone()
        intervention_row = con.execute("SELECT * FROM jarvis_care_interventions WHERE id = ?", (intervention_id,)).fetchone()
        message_row = con.execute("SELECT * FROM proactive_messages WHERE id = ?", (message_id,)).fetchone()
        con.commit()
    return {
        "trigger": _row_to_care_trigger(trigger_row),
        "intervention": _row_to_care_intervention(intervention_row),
        "message": _row_to_proactive_message(message_row),
    }


async def save_care_trigger_and_intervention(**kwargs: Any) -> dict[str, Any]:
    return await asyncio.to_thread(_save_care_trigger_and_intervention_sync, **kwargs)


def _update_care_intervention_feedback_sync(
    *,
    message_id: str,
    feedback: str,
    status: str,
    snoozed_until: float | None = None,
) -> dict[str, Any] | None:
    now = time.time()
    with _conn() as con:
        con.execute(
            """
            UPDATE jarvis_care_interventions
            SET user_feedback = ?, status = ?, acted_at = ?, snoozed_until = ?
            WHERE message_id = ?
            """,
            (feedback, status, now, snoozed_until, message_id),
        )
        if status == "snoozed" and snoozed_until is not None:
            con.execute("UPDATE proactive_messages SET status = 'snoozed', snoozed_until = ? WHERE id = ?", (snoozed_until, message_id))
        elif status in {"dismissed", "resolved"}:
            con.execute("UPDATE proactive_messages SET status = ?, dismissed_at = COALESCE(dismissed_at, ?) WHERE id = ?", ("dismissed" if status == "dismissed" else "read", now, message_id))
        row = con.execute("SELECT * FROM jarvis_care_interventions WHERE message_id = ?", (message_id,)).fetchone()
        con.commit()
    return _row_to_care_intervention(row) if row else None


async def update_care_intervention_feedback(
    *,
    message_id: str,
    feedback: str,
    status: str,
    snoozed_until: float | None = None,
) -> dict[str, Any] | None:
    return await asyncio.to_thread(
        _update_care_intervention_feedback_sync,
        message_id=message_id,
        feedback=feedback,
        status=status,
        snoozed_until=snoozed_until,
    )


def _recent_negative_care_feedback_count_sync(since: float) -> int:
    with _conn() as con:
        row = con.execute(
            """
            SELECT COUNT(*) AS count FROM jarvis_care_interventions
            WHERE acted_at >= ? AND user_feedback IN ('too_frequent', 'not_needed')
            """,
            (since,),
        ).fetchone()
    return int(row["count"] if row else 0)


async def recent_negative_care_feedback_count(since: float) -> int:
    return await asyncio.to_thread(_recent_negative_care_feedback_count_sync, since)


def _recent_negative_care_feedback_count_by_type_sync(trigger_type: str, since: float) -> int:
    with _conn() as con:
        row = con.execute(
            """
            SELECT COUNT(*) AS count
            FROM jarvis_care_interventions i
            JOIN jarvis_care_triggers t ON t.id = i.trigger_id
            WHERE t.trigger_type = ?
              AND i.user_feedback IN ('too_frequent', 'not_needed')
              AND i.acted_at >= ?
            """,
            (trigger_type, since),
        ).fetchone()
    return int(row["count"] if row else 0)


async def recent_negative_care_feedback_count_by_type(trigger_type: str, since: float) -> int:
    return await asyncio.to_thread(_recent_negative_care_feedback_count_by_type_sync, trigger_type, since)


# -- Proactive routine run persistence -------------------------------


def _row_to_proactive_routine_run(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["fired_at"] = _ts_to_datetime(item.get("fired_at"))
    return item


def _has_proactive_routine_run_sync(routine_id: str, run_date: str) -> bool:
    with _conn() as con:
        row = con.execute(
            """
            SELECT 1 FROM proactive_routine_runs
            WHERE routine_id = ? AND run_date = ?
            """,
            (routine_id, run_date),
        ).fetchone()
    return row is not None


async def has_proactive_routine_run(routine_id: str, run_date: str) -> bool:
    return await asyncio.to_thread(_has_proactive_routine_run_sync, routine_id, run_date)


def _save_proactive_routine_run_sync(
    *,
    routine_id: str,
    run_date: str,
    message_id: str | None,
) -> dict[str, Any]:
    now = time.time()
    with _conn() as con:
        con.execute(
            """
            INSERT INTO proactive_routine_runs
              (id, routine_id, run_date, message_id, fired_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(routine_id, run_date) DO NOTHING
            """,
            (uuid4().hex, routine_id, run_date, message_id, now),
        )
        row = con.execute(
            """
            SELECT * FROM proactive_routine_runs
            WHERE routine_id = ? AND run_date = ?
            """,
            (routine_id, run_date),
        ).fetchone()
        con.commit()
    return _row_to_proactive_routine_run(row) if row else {}


async def save_proactive_routine_run(
    *,
    routine_id: str,
    run_date: str,
    message_id: str | None,
) -> dict[str, Any]:
    return await asyncio.to_thread(
        _save_proactive_routine_run_sync,
        routine_id=routine_id,
        run_date=run_date,
        message_id=message_id,
    )


# -- Background task planning --------------------------------------


def _row_to_background_task(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    for key in ("time_horizon", "milestones", "subtasks", "calendar_candidates"):
        try:
            item[key] = json.loads(item[key])
        except Exception:
            item[key] = {} if key == "time_horizon" else []
    return item


def _save_background_task_sync(
    *,
    task_id: str,
    title: str,
    task_type: str,
    status: str,
    source_agent: str | None,
    original_user_request: str,
    goal: str | None,
    time_horizon: dict[str, Any] | None,
    milestones: list[dict[str, Any]] | None,
    subtasks: list[dict[str, Any]] | None,
    calendar_candidates: list[dict[str, Any]] | None,
    notes: str | None = None,
) -> dict[str, Any]:
    now = time.time()
    with _conn() as con:
        con.execute(
            """
            INSERT INTO background_tasks
              (id, title, task_type, status, source_agent, original_user_request,
               goal, time_horizon, milestones, subtasks, calendar_candidates,
               notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              title = excluded.title,
              task_type = excluded.task_type,
              status = excluded.status,
              source_agent = excluded.source_agent,
              original_user_request = excluded.original_user_request,
              goal = excluded.goal,
              time_horizon = excluded.time_horizon,
              milestones = excluded.milestones,
              subtasks = excluded.subtasks,
              calendar_candidates = excluded.calendar_candidates,
              notes = excluded.notes,
              updated_at = excluded.updated_at
            """,
            (
                task_id,
                title,
                task_type,
                status,
                source_agent,
                original_user_request,
                goal,
                json.dumps(time_horizon or {}, ensure_ascii=False, default=str),
                json.dumps(milestones or [], ensure_ascii=False, default=str),
                json.dumps(subtasks or [], ensure_ascii=False, default=str),
                json.dumps(calendar_candidates or [], ensure_ascii=False, default=str),
                notes,
                now,
                now,
            ),
        )
        con.commit()
    return _get_background_task_sync(task_id) or {}


async def save_background_task(
    *,
    task_id: str,
    title: str,
    task_type: str,
    status: str = "active",
    source_agent: str | None = None,
    original_user_request: str,
    goal: str | None = None,
    time_horizon: dict[str, Any] | None = None,
    milestones: list[dict[str, Any]] | None = None,
    subtasks: list[dict[str, Any]] | None = None,
    calendar_candidates: list[dict[str, Any]] | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    return await asyncio.to_thread(
        _save_background_task_sync,
        task_id=task_id,
        title=title,
        task_type=task_type,
        status=status,
        source_agent=source_agent,
        original_user_request=original_user_request,
        goal=goal,
        time_horizon=time_horizon,
        milestones=milestones,
        subtasks=subtasks,
        calendar_candidates=calendar_candidates,
        notes=notes,
    )


def _get_background_task_sync(task_id: str) -> dict[str, Any] | None:
    with _conn() as con:
        row = con.execute("SELECT * FROM background_tasks WHERE id = ?", (task_id,)).fetchone()
    return _row_to_background_task(row) if row else None


async def get_background_task(task_id: str) -> dict[str, Any] | None:
    return await asyncio.to_thread(_get_background_task_sync, task_id)


def _list_background_tasks_sync(status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    with _conn() as con:
        if status:
            rows = con.execute(
                "SELECT * FROM background_tasks WHERE status = ? ORDER BY updated_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM background_tasks ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [_row_to_background_task(row) for row in rows]


async def list_background_tasks(status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_list_background_tasks_sync, status, limit)


def _row_to_background_task_day(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    try:
        item["llm_payload"] = json.loads(item.get("llm_payload") or "{}")
    except Exception:
        item["llm_payload"] = {}
    return item


def _normalize_background_task_day(task_id: str, raw: dict[str, Any], index: int) -> dict[str, Any] | None:
    plan_date = str(raw.get("date") or raw.get("plan_date") or "").strip()
    title = str(raw.get("title") or "").strip()
    if not plan_date or not title:
        return None
    estimated = raw.get("estimated_minutes")
    try:
        estimated_minutes = int(estimated) if estimated is not None and str(estimated).strip() else None
    except (TypeError, ValueError):
        estimated_minutes = None
    day_id = str(raw.get("id") or f"taskday_{uuid4().hex}")
    return {
        "id": day_id,
        "task_id": task_id,
        "plan_date": plan_date[:10],
        "title": title,
        "description": str(raw.get("description") or raw.get("notes") or "").strip() or None,
        "start_time": str(raw.get("start_time") or "").strip() or None,
        "end_time": str(raw.get("end_time") or "").strip() or None,
        "estimated_minutes": estimated_minutes,
        "status": str(raw.get("status") or "pending").strip() or "pending",
        "calendar_event_id": raw.get("calendar_event_id") if isinstance(raw.get("calendar_event_id"), str) else None,
        "workbench_item_id": raw.get("workbench_item_id") if isinstance(raw.get("workbench_item_id"), str) else None,
        "sort_order": int(raw.get("sort_order") or index),
        "llm_payload": raw,
    }


def _save_background_task_days_sync(
    *,
    task_id: str,
    daily_plan: list[dict[str, Any]],
    replace_existing: bool = True,
) -> list[dict[str, Any]]:
    now = time.time()
    normalized = [
        day for index, raw in enumerate(daily_plan)
        if isinstance(raw, dict) and (day := _normalize_background_task_day(task_id, raw, index)) is not None
    ]
    with _conn() as con:
        if replace_existing:
            con.execute("DELETE FROM background_task_days WHERE task_id = ?", (task_id,))
        for day in normalized:
            con.execute(
                """
                INSERT INTO background_task_days
                  (id, task_id, plan_date, title, description, start_time, end_time,
                   estimated_minutes, status, calendar_event_id, workbench_item_id,
                   sort_order, llm_payload, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  task_id = excluded.task_id,
                  plan_date = excluded.plan_date,
                  title = excluded.title,
                  description = excluded.description,
                  start_time = excluded.start_time,
                  end_time = excluded.end_time,
                  estimated_minutes = excluded.estimated_minutes,
                  status = excluded.status,
                  calendar_event_id = excluded.calendar_event_id,
                  workbench_item_id = excluded.workbench_item_id,
                  sort_order = excluded.sort_order,
                  llm_payload = excluded.llm_payload,
                  updated_at = excluded.updated_at
                """,
                (
                    day["id"],
                    day["task_id"],
                    day["plan_date"],
                    day["title"],
                    day["description"],
                    day["start_time"],
                    day["end_time"],
                    day["estimated_minutes"],
                    day["status"],
                    day["calendar_event_id"],
                    day["workbench_item_id"],
                    day["sort_order"],
                    json.dumps(day["llm_payload"], ensure_ascii=False, default=str),
                    now,
                    now,
                ),
            )
        con.commit()
    return _list_background_task_days_sync(task_id=task_id, limit=max(len(normalized), 1))


async def save_background_task_days(
    *,
    task_id: str,
    daily_plan: list[dict[str, Any]],
    replace_existing: bool = True,
) -> list[dict[str, Any]]:
    return await asyncio.to_thread(
        _save_background_task_days_sync,
        task_id=task_id,
        daily_plan=daily_plan,
        replace_existing=replace_existing,
    )


def _list_background_task_days_sync(
    *,
    task_id: str | None = None,
    status: str | None = None,
    plan_date: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if task_id:
        clauses.append("task_id = ?")
        params.append(task_id)
    if status:
        clauses.append("status = ?")
        params.append(status)
    if plan_date:
        clauses.append("plan_date = ?")
        params.append(plan_date[:10])
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with _conn() as con:
        rows = con.execute(
            f"""
            SELECT *
            FROM background_task_days
            {where}
            ORDER BY plan_date ASC, sort_order ASC, created_at ASC
            LIMIT ?
            """,
            (*params, limit),
        ).fetchall()
    return [_row_to_background_task_day(row) for row in rows]


async def list_background_task_days(
    *,
    task_id: str | None = None,
    status: str | None = None,
    plan_date: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    return await asyncio.to_thread(
        _list_background_task_days_sync,
        task_id=task_id,
        status=status,
        plan_date=plan_date,
        limit=limit,
    )


def _update_background_task_day_status_sync(day_id: str, status: str) -> dict[str, Any] | None:
    with _conn() as con:
        con.execute(
            "UPDATE background_task_days SET status = ?, updated_at = ? WHERE id = ?",
            (status, time.time(), day_id),
        )
        con.commit()
        row = con.execute("SELECT * FROM background_task_days WHERE id = ?", (day_id,)).fetchone()
    return _row_to_background_task_day(row) if row else None


async def update_background_task_day_status(day_id: str, status: str) -> dict[str, Any] | None:
    return await asyncio.to_thread(_update_background_task_day_status_sync, day_id, status)


def _calendar_dt_to_iso(value: Any) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value).replace(" ", "T")


def _calendar_event_to_row(event: Any) -> dict[str, Any]:
    data = event.model_dump() if hasattr(event, "model_dump") else dict(event)
    return data


def _row_to_calendar_event_dict(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["route_required"] = bool(item.get("route_required"))
    return item


def save_calendar_event_sync(event: Any) -> dict[str, Any]:
    data = _calendar_event_to_row(event)
    now = time.time()
    with _conn() as con:
        con.execute(
            """
            INSERT INTO jarvis_calendar_events
              (id, title, start, end, stress_weight, location, notes, source,
               source_agent, created_reason, status, route_required, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              title = excluded.title,
              start = excluded.start,
              end = excluded.end,
              stress_weight = excluded.stress_weight,
              location = excluded.location,
              notes = excluded.notes,
              source = excluded.source,
              source_agent = excluded.source_agent,
              created_reason = excluded.created_reason,
              status = excluded.status,
              route_required = excluded.route_required,
              updated_at = excluded.updated_at
            """,
            (
                data["id"], data["title"], _calendar_dt_to_iso(data["start"]), _calendar_dt_to_iso(data["end"]), float(data.get("stress_weight") or 1.0),
                data.get("location"), data.get("notes"), data.get("source") or "user_ui", data.get("source_agent"),
                data.get("created_reason"), data.get("status") or "confirmed", 1 if data.get("route_required") else 0, now, now,
            ),
        )
        con.commit()
        row = con.execute("SELECT * FROM jarvis_calendar_events WHERE id = ?", (data["id"],)).fetchone()
    return _row_to_calendar_event_dict(row) if row else {}


def get_calendar_event_sync(event_id: str) -> dict[str, Any] | None:
    with _conn() as con:
        row = con.execute("SELECT * FROM jarvis_calendar_events WHERE id = ?", (event_id,)).fetchone()
    return _row_to_calendar_event_dict(row) if row else None


def list_calendar_events_between_sync(start: str, end: str) -> list[dict[str, Any]]:
    with _conn() as con:
        rows = con.execute(
            """
            SELECT * FROM jarvis_calendar_events
            WHERE start < ? AND end > ? AND status != 'deleted'
            ORDER BY start ASC
            """,
            (end, start),
        ).fetchall()
    return [_row_to_calendar_event_dict(row) for row in rows]


def list_upcoming_calendar_events_sync(now_iso: str, cutoff_iso: str) -> list[dict[str, Any]]:
    with _conn() as con:
        rows = con.execute(
            """
            SELECT * FROM jarvis_calendar_events
            WHERE start >= ? AND start <= ? AND status != 'deleted'
            ORDER BY start ASC
            """,
            (now_iso, cutoff_iso),
        ).fetchall()
    return [_row_to_calendar_event_dict(row) for row in rows]


def update_calendar_event_sync(event_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    allowed = {"title", "start", "end", "stress_weight", "location", "notes", "source", "source_agent", "created_reason", "status", "route_required"}
    updates = {key: value for key, value in patch.items() if key in allowed and value is not None}
    if not updates:
        return get_calendar_event_sync(event_id)
    updates["updated_at"] = time.time()
    if "route_required" in updates:
        updates["route_required"] = 1 if updates["route_required"] else 0
    for key in ("start", "end"):
        if key in updates:
            updates[key] = _calendar_dt_to_iso(updates[key])
    assignments = ", ".join(f"{key} = ?" for key in updates)
    with _conn() as con:
        con.execute(f"UPDATE jarvis_calendar_events SET {assignments} WHERE id = ?", (*updates.values(), event_id))
        con.commit()
        row = con.execute("SELECT * FROM jarvis_calendar_events WHERE id = ?", (event_id,)).fetchone()
    return _row_to_calendar_event_dict(row) if row else None


def delete_calendar_event_sync(event_id: str) -> bool:
    with _conn() as con:
        cur = con.execute("UPDATE jarvis_calendar_events SET status = 'deleted', updated_at = ? WHERE id = ? AND status != 'deleted'", (time.time(), event_id))
        con.commit()
    return cur.rowcount > 0


def _json_load(value: Any, fallback: Any) -> Any:
    try:
        return json.loads(value or "")
    except Exception:
        return fallback


def _row_to_jarvis_plan(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["time_horizon"] = _json_load(item.pop("time_horizon_json", "{}"), {})
    item["raw_payload"] = _json_load(item.pop("raw_payload_json", "{}"), {})
    return item


def _row_to_jarvis_plan_day(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["raw_payload"] = _json_load(item.pop("raw_payload_json", "{}"), {})
    return item


def _record_agent_event_sync(
    *,
    event_type: str,
    agent_id: str | None = None,
    plan_id: str | None = None,
    plan_day_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event_id = f"event_{uuid4().hex}"
    now = time.time()
    with _conn() as con:
        con.execute(
            """
            INSERT INTO jarvis_agent_events
              (id, event_type, agent_id, plan_id, plan_day_id, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (event_id, event_type, agent_id, plan_id, plan_day_id, json.dumps(payload or {}, ensure_ascii=False, default=str), now),
        )
        con.commit()
        row = con.execute("SELECT * FROM jarvis_agent_events WHERE id = ?", (event_id,)).fetchone()
    item = dict(row) if row else {"id": event_id, "event_type": event_type}
    item["payload"] = _json_load(item.pop("payload_json", "{}"), {}) if "payload_json" in item else payload or {}
    return item


async def record_agent_event(**kwargs: Any) -> dict[str, Any]:
    return await asyncio.to_thread(_record_agent_event_sync, **kwargs)


def _normalize_plan_day(plan_id: str, raw: dict[str, Any], index: int) -> dict[str, Any] | None:
    plan_date = str(raw.get("date") or raw.get("plan_date") or "").strip()
    title = str(raw.get("title") or "").strip()
    if not plan_date or not title:
        return None
    estimated = raw.get("estimated_minutes")
    try:
        estimated_minutes = int(estimated) if estimated is not None and str(estimated).strip() else None
    except (TypeError, ValueError):
        estimated_minutes = None
    return {
        "id": str(raw.get("plan_day_id") or raw.get("id") or f"planday_{uuid4().hex}"),
        "plan_id": plan_id,
        "plan_date": plan_date[:10],
        "title": title,
        "description": str(raw.get("description") or raw.get("notes") or "").strip() or None,
        "start_time": str(raw.get("start_time") or raw.get("start") or "").strip() or None,
        "end_time": str(raw.get("end_time") or raw.get("end") or "").strip() or None,
        "estimated_minutes": estimated_minutes,
        "status": str(raw.get("status") or "pending"),
        "calendar_event_id": raw.get("calendar_event_id") if isinstance(raw.get("calendar_event_id"), str) else None,
        "workbench_item_id": raw.get("workbench_item_id") if isinstance(raw.get("workbench_item_id"), str) else None,
        "source_task_day_id": raw.get("source_task_day_id") if isinstance(raw.get("source_task_day_id"), str) else None,
        "sort_order": int(raw.get("sort_order") if raw.get("sort_order") is not None else index),
        "raw_payload": raw,
    }


def _save_jarvis_plan_sync(
    *,
    plan_id: str,
    title: str,
    plan_type: str,
    status: str = "active",
    source_agent: str | None = None,
    source_pending_id: str | None = None,
    source_background_task_id: str | None = None,
    original_user_request: str = "",
    goal: str | None = None,
    time_horizon: dict[str, Any] | None = None,
    raw_payload: dict[str, Any] | None = None,
    days: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    now = time.time()
    normalized_days = [_normalize_plan_day(plan_id, raw, index) for index, raw in enumerate(days or [])]
    normalized_days = [day for day in normalized_days if day is not None]
    with _conn() as con:
        con.execute(
            """
            INSERT INTO jarvis_plans
              (id, title, plan_type, status, source_agent, source_pending_id,
               source_background_task_id, original_user_request, goal,
               time_horizon_json, raw_payload_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              title = excluded.title,
              plan_type = excluded.plan_type,
              status = excluded.status,
              source_agent = excluded.source_agent,
              source_pending_id = excluded.source_pending_id,
              source_background_task_id = excluded.source_background_task_id,
              original_user_request = excluded.original_user_request,
              goal = excluded.goal,
              time_horizon_json = excluded.time_horizon_json,
              raw_payload_json = excluded.raw_payload_json,
              updated_at = excluded.updated_at
            """,
            (
                plan_id,
                title,
                plan_type,
                status,
                source_agent,
                source_pending_id,
                source_background_task_id,
                original_user_request,
                goal,
                json.dumps(time_horizon or {}, ensure_ascii=False, default=str),
                json.dumps(raw_payload or {}, ensure_ascii=False, default=str),
                now,
                now,
            ),
        )
        if days is not None:
            con.execute("DELETE FROM jarvis_plan_days WHERE plan_id = ?", (plan_id,))
        for day in normalized_days:
            con.execute(
                """
                INSERT INTO jarvis_plan_days
                  (id, plan_id, plan_date, title, description, start_time, end_time,
                   estimated_minutes, status, calendar_event_id, workbench_item_id,
                   source_task_day_id, sort_order, raw_payload_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    day["id"], day["plan_id"], day["plan_date"], day["title"], day["description"],
                    day["start_time"], day["end_time"], day["estimated_minutes"], day["status"],
                    day["calendar_event_id"], day["workbench_item_id"], day["source_task_day_id"], day["sort_order"],
                    json.dumps(day["raw_payload"], ensure_ascii=False, default=str), now, now,
                ),
            )
        con.execute(
            """
            INSERT INTO jarvis_agent_events (id, event_type, agent_id, plan_id, payload_json, created_at)
            VALUES (?, 'plan.created', ?, ?, ?, ?)
            """,
            (f"event_{uuid4().hex}", source_agent, plan_id, json.dumps({"day_count": len(normalized_days)}, ensure_ascii=False), now),
        )
        con.commit()
        row = con.execute("SELECT * FROM jarvis_plans WHERE id = ?", (plan_id,)).fetchone()
    return _row_to_jarvis_plan(row)


async def save_jarvis_plan(**kwargs: Any) -> dict[str, Any]:
    return await asyncio.to_thread(_save_jarvis_plan_sync, **kwargs)


def _get_jarvis_plan_sync(plan_id: str) -> dict[str, Any] | None:
    with _conn() as con:
        row = con.execute("SELECT * FROM jarvis_plans WHERE id = ?", (plan_id,)).fetchone()
    return _row_to_jarvis_plan(row) if row else None


async def get_jarvis_plan(plan_id: str) -> dict[str, Any] | None:
    return await asyncio.to_thread(_get_jarvis_plan_sync, plan_id)


def _list_jarvis_plans_sync(status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    with _conn() as con:
        if status:
            rows = con.execute("SELECT * FROM jarvis_plans WHERE status = ? ORDER BY updated_at DESC LIMIT ?", (status, limit)).fetchall()
        else:
            rows = con.execute("SELECT * FROM jarvis_plans ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
    return [_row_to_jarvis_plan(row) for row in rows]


async def list_jarvis_plans(status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_list_jarvis_plans_sync, status, limit)


def _list_jarvis_plan_days_sync(
    *, plan_id: str | None = None, status: str | None = None, start: str | None = None, end: str | None = None, limit: int = 500
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if plan_id:
        clauses.append("plan_id = ?")
        params.append(plan_id)
    if status:
        clauses.append("status = ?")
        params.append(status)
    if start:
        clauses.append("plan_date >= ?")
        params.append(start[:10])
    if end:
        clauses.append("plan_date <= ?")
        params.append(end[:10])
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with _conn() as con:
        rows = con.execute(
            f"SELECT * FROM jarvis_plan_days {where} ORDER BY plan_date ASC, sort_order ASC LIMIT ?",
            (*params, limit),
        ).fetchall()
    return [_row_to_jarvis_plan_day(row) for row in rows]


async def list_jarvis_plan_days(**kwargs: Any) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_list_jarvis_plan_days_sync, **kwargs)


def _update_jarvis_plan_day_sync(day_id: str, patch: dict[str, Any], event_type: str = "plan_day.updated") -> dict[str, Any] | None:
    allowed = {"plan_date", "title", "description", "start_time", "end_time", "estimated_minutes", "status", "calendar_event_id", "workbench_item_id", "reschedule_reason"}
    updates = {key: value for key, value in patch.items() if key in allowed}
    if not updates:
        return None
    updates["updated_at"] = time.time()
    assignments = ", ".join(f"{key} = ?" for key in updates)
    with _conn() as con:
        con.execute(f"UPDATE jarvis_plan_days SET {assignments} WHERE id = ?", (*updates.values(), day_id))
        row = con.execute("SELECT * FROM jarvis_plan_days WHERE id = ?", (day_id,)).fetchone()
        if row:
            item = _row_to_jarvis_plan_day(row)
            con.execute(
                "INSERT INTO jarvis_agent_events (id, event_type, plan_id, plan_day_id, payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (f"event_{uuid4().hex}", event_type, item["plan_id"], day_id, json.dumps({"patch": patch}, ensure_ascii=False, default=str), time.time()),
            )
        con.commit()
    return _row_to_jarvis_plan_day(row) if row else None


async def update_jarvis_plan_day(day_id: str, patch: dict[str, Any], event_type: str = "plan_day.updated") -> dict[str, Any] | None:
    return await asyncio.to_thread(_update_jarvis_plan_day_sync, day_id, patch, event_type)


def _cancel_jarvis_plan_sync(plan_id: str) -> dict[str, Any] | None:
    now = time.time()
    with _conn() as con:
        con.execute("UPDATE jarvis_plans SET status = 'cancelled', updated_at = ? WHERE id = ?", (now, plan_id))
        con.execute("UPDATE jarvis_plan_days SET status = 'cancelled', updated_at = ? WHERE plan_id = ? AND status IN ('pending','pushed','rescheduled')", (now, plan_id))
        con.execute("INSERT INTO jarvis_agent_events (id, event_type, plan_id, payload_json, created_at) VALUES (?, 'plan.cancelled', ?, '{}', ?)", (f"event_{uuid4().hex}", plan_id, now))
        con.commit()
        row = con.execute("SELECT * FROM jarvis_plans WHERE id = ?", (plan_id,)).fetchone()
    return _row_to_jarvis_plan(row) if row else None


async def cancel_jarvis_plan(plan_id: str) -> dict[str, Any] | None:
    return await asyncio.to_thread(_cancel_jarvis_plan_sync, plan_id)


def _row_to_maxwell_workbench_item(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def _list_maxwell_workbench_items_sync(
    *,
    status: str | None = None,
    plan_date: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    join_clause = ""
    if status:
        clauses.append("w.status = ?")
        params.append(status)
    if plan_date:
        join_clause = "LEFT JOIN background_task_days d ON d.id = w.task_day_id LEFT JOIN jarvis_plan_days pd ON pd.id = w.plan_day_id"
        clauses.append("(d.plan_date = ? OR pd.plan_date = ?)")
        params.extend([plan_date[:10], plan_date[:10]])
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with _conn() as con:
        rows = con.execute(
            f"""
            SELECT w.*
            FROM maxwell_workbench_items w
            {join_clause}
            {where}
            ORDER BY COALESCE(w.due_at, '') ASC, w.created_at DESC
            LIMIT ?
            """,
            (*params, limit),
        ).fetchall()
    return [_row_to_maxwell_workbench_item(row) for row in rows]


async def list_maxwell_workbench_items(
    *,
    status: str | None = None,
    plan_date: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    return await asyncio.to_thread(
        _list_maxwell_workbench_items_sync,
        status=status,
        plan_date=plan_date,
        limit=limit,
    )


def _due_at_for_task_day(day: sqlite3.Row | dict[str, Any]) -> str | None:
    plan_date = str(day["plan_date"] or "").strip()
    if not plan_date:
        return None
    start_time = str(day["start_time"] or "").strip()
    if start_time:
        return f"{plan_date}T{start_time[:5]}:00"
    return f"{plan_date}T23:59:00"


def _push_background_task_days_to_workbench_sync(plan_date: str) -> list[dict[str, Any]]:
    date_key = plan_date[:10]
    now = time.time()
    pushed: list[dict[str, Any]] = []
    with _conn() as con:
        rows = con.execute(
            """
            SELECT *
            FROM background_task_days
            WHERE plan_date = ?
              AND status = 'pending'
              AND workbench_item_id IS NULL
            ORDER BY sort_order ASC, created_at ASC
            """,
            (date_key,),
        ).fetchall()
        for day in rows:
            item_id = f"workbench_{uuid4().hex}"
            try:
                con.execute(
                    """
                    INSERT INTO maxwell_workbench_items
                      (id, task_day_id, plan_day_id, agent_id, title, description, due_at,
                       status, pushed_at, created_at, updated_at)
                    VALUES (?, ?, NULL, 'maxwell', ?, ?, ?, 'todo', ?, ?, ?)
                    """,
                    (item_id, day["id"], day["title"], day["description"], _due_at_for_task_day(day), now, now, now),
                )
            except sqlite3.IntegrityError:
                continue
            con.execute(
                """
                UPDATE background_task_days
                SET status = 'pushed', workbench_item_id = ?, updated_at = ?
                WHERE id = ? AND status = 'pending'
                """,
                (item_id, now, day["id"]),
            )
            pushed_row = con.execute("SELECT * FROM maxwell_workbench_items WHERE id = ?", (item_id,)).fetchone()
            if pushed_row is not None:
                pushed.append(_row_to_maxwell_workbench_item(pushed_row))
        con.commit()
    return pushed


async def push_background_task_days_to_workbench(plan_date: str) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_push_background_task_days_to_workbench_sync, plan_date)


def _push_jarvis_plan_days_to_workbench_sync(plan_date: str) -> list[dict[str, Any]]:
    date_key = plan_date[:10]
    now = time.time()
    pushed: list[dict[str, Any]] = []
    with _conn() as con:
        rows = con.execute(
            """
            SELECT *
            FROM jarvis_plan_days
            WHERE plan_date = ?
              AND status IN ('pending', 'scheduled', 'rescheduled')
              AND workbench_item_id IS NULL
            ORDER BY sort_order ASC, created_at ASC
            """,
            (date_key,),
        ).fetchall()
        for day in rows:
            item_id = f"workbench_{uuid4().hex}"
            try:
                con.execute(
                    """
                    INSERT INTO maxwell_workbench_items
                      (id, task_day_id, plan_day_id, agent_id, title, description, due_at,
                       status, pushed_at, created_at, updated_at)
                    VALUES (?, NULL, ?, 'maxwell', ?, ?, ?, 'todo', ?, ?, ?)
                    """,
                    (item_id, day["id"], day["title"], day["description"], _due_at_for_task_day(day), now, now, now),
                )
            except sqlite3.IntegrityError:
                continue
            con.execute(
                """
                UPDATE jarvis_plan_days
                SET status = 'pushed', workbench_item_id = ?, updated_at = ?
                WHERE id = ? AND status IN ('pending', 'scheduled', 'rescheduled')
                """,
                (item_id, now, day["id"]),
            )
            con.execute(
                "INSERT INTO jarvis_agent_events (id, event_type, plan_id, plan_day_id, payload_json, created_at) VALUES (?, 'day.pushed', ?, ?, ?, ?)",
                (f"event_{uuid4().hex}", day["plan_id"], day["id"], json.dumps({"workbench_item_id": item_id}, ensure_ascii=False), now),
            )
            pushed_row = con.execute("SELECT * FROM maxwell_workbench_items WHERE id = ?", (item_id,)).fetchone()
            if pushed_row is not None:
                pushed.append(_row_to_maxwell_workbench_item(pushed_row))
        con.commit()
    return pushed


async def push_jarvis_plan_days_to_workbench(plan_date: str) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_push_jarvis_plan_days_to_workbench_sync, plan_date)


async def push_planner_days_to_workbench(plan_date: str) -> list[dict[str, Any]]:
    legacy = await push_background_task_days_to_workbench(plan_date)
    unified = await push_jarvis_plan_days_to_workbench(plan_date)
    return [*legacy, *unified]


def _mark_overdue_background_task_days_missed_sync(today: str) -> list[dict[str, Any]]:
    today_key = today[:10]
    now = time.time()
    with _conn() as con:
        rows = con.execute(
            """
            SELECT id
            FROM background_task_days
            WHERE plan_date < ?
              AND status IN ('pending', 'pushed')
            ORDER BY plan_date ASC, sort_order ASC, created_at ASC
            """,
            (today_key,),
        ).fetchall()
        ids = [str(row["id"]) for row in rows]
        if ids:
            placeholders = ",".join("?" for _ in ids)
            con.execute(
                f"""
                UPDATE background_task_days
                SET status = 'missed', updated_at = ?
                WHERE id IN ({placeholders})
                """,
                (now, *ids),
            )
            missed_rows = con.execute(
                f"""
                SELECT *
                FROM background_task_days
                WHERE id IN ({placeholders})
                ORDER BY plan_date ASC, sort_order ASC, created_at ASC
                """,
                tuple(ids),
            ).fetchall()
        else:
            missed_rows = []
        con.commit()
    return [_row_to_background_task_day(row) for row in missed_rows]


async def mark_overdue_background_task_days_missed(today: str) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_mark_overdue_background_task_days_missed_sync, today)


def _mark_overdue_jarvis_plan_days_missed_sync(today: str) -> list[dict[str, Any]]:
    today_key = today[:10]
    now = time.time()
    with _conn() as con:
        rows = con.execute(
            """
            SELECT id, plan_id
            FROM jarvis_plan_days
            WHERE plan_date < ?
              AND status IN ('pending', 'scheduled', 'pushed', 'rescheduled')
            ORDER BY plan_date ASC, sort_order ASC, created_at ASC
            """,
            (today_key,),
        ).fetchall()
        ids = [str(row["id"]) for row in rows]
        if ids:
            placeholders = ",".join("?" for _ in ids)
            con.execute(
                f"""
                UPDATE jarvis_plan_days
                SET status = 'missed', updated_at = ?
                WHERE id IN ({placeholders})
                """,
                (now, *ids),
            )
            for row in rows:
                con.execute(
                    "INSERT INTO jarvis_agent_events (id, event_type, plan_id, plan_day_id, payload_json, created_at) VALUES (?, 'day.missed', ?, ?, ?, ?)",
                    (f"event_{uuid4().hex}", row["plan_id"], row["id"], json.dumps({"today": today_key}, ensure_ascii=False), now),
                )
            missed_rows = con.execute(
                f"""
                SELECT *
                FROM jarvis_plan_days
                WHERE id IN ({placeholders})
                ORDER BY plan_date ASC, sort_order ASC
                """,
                (*ids,),
            ).fetchall()
        else:
            missed_rows = []
        con.commit()
    return [_row_to_jarvis_plan_day(row) for row in missed_rows]


async def mark_overdue_jarvis_plan_days_missed(today: str) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_mark_overdue_jarvis_plan_days_missed_sync, today)


async def mark_overdue_planner_days_missed(today: str) -> dict[str, list[dict[str, Any]]]:
    legacy = await mark_overdue_background_task_days_missed(today)
    unified = await mark_overdue_jarvis_plan_days_missed(today)
    return {"background_task_days": legacy, "plan_days": unified}


# -- Demo memory and trace -----------------------------------------


def _reset_demo_data_sync() -> dict[str, Any]:
    with _conn() as con:
        memory_count = con.execute("SELECT COUNT(*) FROM demo_memory_items").fetchone()[0]
        trace_count = con.execute("SELECT COUNT(*) FROM demo_trace_events").fetchone()[0]
        run_count = con.execute("SELECT COUNT(*) FROM demo_runs").fetchone()[0]
        con.execute("DELETE FROM demo_memory_items")
        con.execute("DELETE FROM demo_trace_events")
        con.execute("DELETE FROM demo_runs")
        con.commit()
    return {"demo_runs": run_count, "trace_events": trace_count, "memory_items": memory_count}


async def reset_demo_data() -> dict[str, Any]:
    return await asyncio.to_thread(_reset_demo_data_sync)


def _start_demo_run_sync(*, demo_run_id: str, seed_name: str, profile_seed: dict[str, Any]) -> dict[str, Any]:
    now = time.time()
    with _conn() as con:
        con.execute(
            """
            INSERT INTO demo_runs (id, seed_name, profile_seed, status, created_at, updated_at)
            VALUES (?, ?, ?, 'active', ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              seed_name = excluded.seed_name,
              profile_seed = excluded.profile_seed,
              status = 'active',
              updated_at = excluded.updated_at
            """,
            (demo_run_id, seed_name, json.dumps(profile_seed, ensure_ascii=False, default=str), now, now),
        )
        con.commit()
    return _get_demo_run_sync(demo_run_id) or {}


async def start_demo_run(*, demo_run_id: str, seed_name: str, profile_seed: dict[str, Any]) -> dict[str, Any]:
    return await asyncio.to_thread(
        _start_demo_run_sync,
        demo_run_id=demo_run_id,
        seed_name=seed_name,
        profile_seed=profile_seed,
    )


def _row_to_demo_run(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    try:
        item["profile_seed"] = json.loads(item["profile_seed"])
    except Exception:
        item["profile_seed"] = {}
    return item


def _get_demo_run_sync(demo_run_id: str) -> dict[str, Any] | None:
    with _conn() as con:
        row = con.execute("SELECT * FROM demo_runs WHERE id = ?", (demo_run_id,)).fetchone()
    return _row_to_demo_run(row) if row else None


async def get_demo_run(demo_run_id: str) -> dict[str, Any] | None:
    return await asyncio.to_thread(_get_demo_run_sync, demo_run_id)


def _list_demo_runs_sync(limit: int = 20) -> list[dict[str, Any]]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM demo_runs ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [_row_to_demo_run(row) for row in rows]


async def list_demo_runs(limit: int = 20) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_list_demo_runs_sync, limit)


def _row_to_demo_trace(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    for key, fallback in (("tool_calls", []), ("memory_events", []), ("confirmation", {}), ("payload", {})):
        try:
            item[key] = json.loads(item[key])
        except Exception:
            item[key] = fallback
    return item


def _row_to_demo_memory(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def _append_demo_trace_event_sync(
    *,
    demo_run_id: str,
    demo_step_id: str,
    event_type: str,
    agent_id: str | None,
    user_input: str | None,
    agent_reply: str | None,
    tool_calls: list[dict[str, Any]] | None,
    memory_events: list[dict[str, Any]] | None,
    confirmation: dict[str, Any] | None,
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    now = time.time()
    with _conn() as con:
        cursor = con.execute(
            """
            INSERT INTO demo_trace_events
              (demo_run_id, demo_step_id, event_type, agent_id, user_input, agent_reply,
               tool_calls, memory_events, confirmation, payload, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                demo_run_id,
                demo_step_id,
                event_type,
                agent_id,
                user_input,
                agent_reply,
                json.dumps(tool_calls or [], ensure_ascii=False, default=str),
                json.dumps(memory_events or [], ensure_ascii=False, default=str),
                json.dumps(confirmation or {}, ensure_ascii=False, default=str),
                json.dumps(payload or {}, ensure_ascii=False, default=str),
                now,
            ),
        )
        con.execute("UPDATE demo_runs SET updated_at = ? WHERE id = ?", (now, demo_run_id))
        row = con.execute("SELECT * FROM demo_trace_events WHERE id = ?", (cursor.lastrowid,)).fetchone()
        con.commit()
    return _row_to_demo_trace(row)


async def append_demo_trace_event(
    *,
    demo_run_id: str,
    demo_step_id: str,
    event_type: str,
    agent_id: str | None = None,
    user_input: str | None = None,
    agent_reply: str | None = None,
    tool_calls: list[dict[str, Any]] | None = None,
    memory_events: list[dict[str, Any]] | None = None,
    confirmation: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return await asyncio.to_thread(
        _append_demo_trace_event_sync,
        demo_run_id=demo_run_id,
        demo_step_id=demo_step_id,
        event_type=event_type,
        agent_id=agent_id,
        user_input=user_input,
        agent_reply=agent_reply,
        tool_calls=tool_calls,
        memory_events=memory_events,
        confirmation=confirmation,
        payload=payload,
    )


def _save_demo_memory_item_sync(
    *,
    demo_run_id: str,
    demo_step_id: str,
    memory_kind: str,
    content: str,
    source_text: str | None,
    sensitivity: str,
    confidence: float,
    importance: float,
) -> dict[str, Any]:
    now = time.time()
    with _conn() as con:
        cursor = con.execute(
            """
            INSERT INTO demo_memory_items
              (demo_run_id, demo_step_id, memory_kind, content, source_text,
               sensitivity, confidence, importance, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (demo_run_id, demo_step_id, memory_kind, content, source_text, sensitivity, confidence, importance, now),
        )
        con.execute("UPDATE demo_runs SET updated_at = ? WHERE id = ?", (now, demo_run_id))
        row = con.execute("SELECT * FROM demo_memory_items WHERE id = ?", (cursor.lastrowid,)).fetchone()
        con.commit()
    return _row_to_demo_memory(row)


async def save_demo_memory_item(
    *,
    demo_run_id: str,
    demo_step_id: str,
    memory_kind: str,
    content: str,
    source_text: str | None = None,
    sensitivity: str = "normal",
    confidence: float = 0.6,
    importance: float = 0.5,
) -> dict[str, Any]:
    return await asyncio.to_thread(
        _save_demo_memory_item_sync,
        demo_run_id=demo_run_id,
        demo_step_id=demo_step_id,
        memory_kind=memory_kind,
        content=content,
        source_text=source_text,
        sensitivity=sensitivity,
        confidence=confidence,
        importance=importance,
    )


def _export_demo_trace_sync(demo_run_id: str) -> dict[str, Any] | None:
    run = _get_demo_run_sync(demo_run_id)
    if run is None:
        return None
    with _conn() as con:
        trace_rows = con.execute(
            "SELECT * FROM demo_trace_events WHERE demo_run_id = ? ORDER BY created_at ASC",
            (demo_run_id,),
        ).fetchall()
        memory_rows = con.execute(
            "SELECT * FROM demo_memory_items WHERE demo_run_id = ? ORDER BY created_at ASC",
            (demo_run_id,),
        ).fetchall()
    return {
        "demo_run": run,
        "trace_events": [_row_to_demo_trace(row) for row in trace_rows],
        "memory_items": [_row_to_demo_memory(row) for row in memory_rows],
    }


async def export_demo_trace(demo_run_id: str) -> dict[str, Any] | None:
    return await asyncio.to_thread(_export_demo_trace_sync, demo_run_id)



def _row_to_agent_event(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["payload"] = _json_load(item.pop("payload_json", "{}"), {})
    return item


def _list_agent_events_sync(*, plan_id: str | None = None, event_type: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if plan_id:
        clauses.append("plan_id = ?")
        params.append(plan_id)
    if event_type:
        clauses.append("event_type = ?")
        params.append(event_type)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with _conn() as con:
        rows = con.execute(
            f"SELECT * FROM jarvis_agent_events {where} ORDER BY created_at DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
    return [_row_to_agent_event(row) for row in rows]


async def list_agent_events(*, plan_id: str | None = None, event_type: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_list_agent_events_sync, plan_id=plan_id, event_type=event_type, limit=limit)
