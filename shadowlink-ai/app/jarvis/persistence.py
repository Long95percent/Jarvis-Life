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
from pathlib import Path
from typing import Any

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
    agent_id   TEXT NOT NULL,          -- which agent this 1:1 chat belongs to
    role       TEXT NOT NULL,          -- 'user' or 'agent'
    content    TEXT NOT NULL,
    timestamp  REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chat_agent ON agent_chat_turns(agent_id, timestamp);

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
"""


_initialized = False


def _ensure_initialized() -> None:
    global _initialized
    if _initialized:
        return
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(_DB_PATH) as con:
        con.executescript(SCHEMA)
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


def _save_chat_turn_sync(agent_id: str, role: str, content: str) -> None:
    with _conn() as con:
        con.execute(
            """
            INSERT INTO agent_chat_turns (agent_id, role, content, timestamp)
            VALUES (?, ?, ?, ?)
            """,
            (agent_id, role, content, time.time()),
        )
        con.commit()


async def save_chat_turn(*, agent_id: str, role: str, content: str) -> None:
    try:
        await asyncio.to_thread(_save_chat_turn_sync, agent_id, role, content)
    except Exception as exc:
        logger.warning("persistence.save_chat_turn_failed", agent_id=agent_id, error=str(exc))


def _get_chat_history_sync(agent_id: str, limit: int) -> list[dict[str, Any]]:
    with _conn() as con:
        rows = con.execute(
            """
            SELECT role, content, timestamp
            FROM agent_chat_turns
            WHERE agent_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (agent_id, limit),
        ).fetchall()
    # Reverse so the oldest is first (chronological order for display)
    return [dict(r) for r in reversed(rows)]


async def get_chat_history(agent_id: str, limit: int = 50) -> list[dict[str, Any]]:
    try:
        return await asyncio.to_thread(_get_chat_history_sync, agent_id, limit)
    except Exception as exc:
        logger.warning("persistence.get_chat_history_failed", agent_id=agent_id, error=str(exc))
        return []


def _clear_chat_history_sync(agent_id: str) -> int:
    with _conn() as con:
        cur = con.execute("DELETE FROM agent_chat_turns WHERE agent_id = ?", (agent_id,))
        con.commit()
        return cur.rowcount


async def clear_chat_history(agent_id: str) -> int:
    try:
        return await asyncio.to_thread(_clear_chat_history_sync, agent_id)
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
