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
CREATE INDEX IF NOT EXISTS idx_jarvis_memories_lifecycle ON jarvis_memories(status, memory_tier, visibility, updated_at DESC);

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
    dismissed_at REAL
);

CREATE INDEX IF NOT EXISTS idx_proactive_messages_status ON proactive_messages(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_proactive_messages_agent ON proactive_messages(agent_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS proactive_routine_runs (
    id         TEXT PRIMARY KEY,
    routine_id TEXT NOT NULL,
    run_date   TEXT NOT NULL,
    message_id TEXT,
    fired_at   REAL NOT NULL,
    UNIQUE(routine_id, run_date)
);

CREATE INDEX IF NOT EXISTS idx_proactive_routine_runs_date ON proactive_routine_runs(run_date, routine_id);

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

CREATE TABLE IF NOT EXISTS maxwell_workbench_items (
    id          TEXT PRIMARY KEY,
    task_day_id TEXT,
    agent_id    TEXT NOT NULL DEFAULT 'maxwell',
    title       TEXT NOT NULL,
    description TEXT,
    due_at      TEXT,
    status      TEXT NOT NULL DEFAULT 'todo',
    pushed_at   REAL,
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL,
    FOREIGN KEY (task_day_id) REFERENCES background_task_days(id) ON DELETE SET NULL
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
        }
        for column_name, column_def in proactive_defaults.items():
            if proactive_columns and column_name not in proactive_columns:
                con.execute(f"ALTER TABLE proactive_messages ADD COLUMN {column_name} {column_def}")
        con.execute("CREATE INDEX IF NOT EXISTS idx_proactive_messages_status ON proactive_messages(status, created_at DESC)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_proactive_messages_agent ON proactive_messages(agent_id, status, created_at DESC)")
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
) -> None:
    now = time.time()
    with _conn() as con:
        con.execute(
            """
            INSERT INTO roundtable_sessions
              (session_id, scenario_id, scenario_name, participants,
               agent_roster, round_count, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
              round_count = excluded.round_count,
              updated_at  = excluded.updated_at
            """,
            (session_id, scenario_id, scenario_name, json.dumps(participants),
             agent_roster, round_count, now, now),
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
) -> None:
    try:
        await asyncio.to_thread(
            _save_session_sync,
            session_id, scenario_id, scenario_name,
            participants, agent_roster, round_count,
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
                   agent_roster, round_count, created_at, updated_at
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


# ── Agent chat history (1:1 private chats) ────────────────────────


def _save_chat_turn_sync(
    agent_id: str,
    role: str,
    content: str,
    actions: list[dict[str, Any]] | None = None,
    session_id: str | None = None,
) -> None:
    actions_json = json.dumps(actions or [], ensure_ascii=False)
    with _conn() as con:
        con.execute(
            """
            INSERT INTO agent_chat_turns (session_id, agent_id, role, content, actions, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (session_id, agent_id, role, content, actions_json, time.time()),
        )
        con.commit()


async def save_chat_turn(
    *,
    agent_id: str,
    role: str,
    content: str,
    actions: list[dict[str, Any]] | None = None,
    session_id: str | None = None,
) -> None:
    try:
        await asyncio.to_thread(_save_chat_turn_sync, agent_id, role, content, actions, session_id)
    except Exception as exc:
        logger.warning("persistence.save_chat_turn_failed", agent_id=agent_id, error=str(exc))


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
            WHERE status = 'active' AND last_opened_at IS NULL AND created_at < ?
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
        cursor = con.execute(
            "UPDATE conversation_history SET status = 'deleted', updated_at = ? WHERE id = ? AND status != 'deleted'",
            (time.time(), conversation_id),
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


# ── Shared collaboration memories ─────────────────────────────────


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
    item["read"] = item.get("status") == "read" or item.get("read_at") is not None
    return item


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
    status = data.get("status") or ("read" if data.get("read") else "pending")
    with _conn() as con:
        con.execute(
            """
            INSERT INTO proactive_messages
              (id, agent_id, agent_name, content, trigger, priority, status,
               created_at, delivered_at, read_at, dismissed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              agent_id = excluded.agent_id,
              agent_name = excluded.agent_name,
              content = excluded.content,
              trigger = excluded.trigger,
              priority = excluded.priority,
              status = excluded.status,
              delivered_at = excluded.delivered_at,
              read_at = excluded.read_at,
              dismissed_at = excluded.dismissed_at
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
    clauses = ["status != 'dismissed'"]
    params: list[Any] = []
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
        join_clause = "LEFT JOIN background_task_days d ON d.id = w.task_day_id"
        clauses.append("d.plan_date = ?")
        params.append(plan_date[:10])
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


def _due_at_for_task_day(day: sqlite3.Row) -> str | None:
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
                      (id, task_day_id, agent_id, title, description, due_at,
                       status, pushed_at, created_at, updated_at)
                    VALUES (?, ?, 'maxwell', ?, ?, ?, 'todo', ?, ?, ?)
                    """,
                    (
                        item_id,
                        day["id"],
                        day["title"],
                        day["description"],
                        _due_at_for_task_day(day),
                        now,
                        now,
                        now,
                    ),
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
            pushed_row = con.execute(
                "SELECT * FROM maxwell_workbench_items WHERE id = ?",
                (item_id,),
            ).fetchone()
            if pushed_row is not None:
                pushed.append(_row_to_maxwell_workbench_item(pushed_row))
        con.commit()
    return pushed


async def push_background_task_days_to_workbench(plan_date: str) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_push_background_task_days_to_workbench_sync, plan_date)


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
