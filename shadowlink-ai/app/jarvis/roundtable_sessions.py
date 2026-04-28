"""Roundtable session state — in-memory transcript for multi-turn discussions.

Each session tracks the scenario, participating agents, and the full transcript
so far (user turns + agent turns interleaved). When the user interjects via
/roundtable/continue, the agents see the full history in their prompt.

For a competition demo this is in-memory only. For production, swap _sessions
with a persistent store (SQLite / Redis).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal


TurnRole = Literal["user", "system"] | str  # "system" or agent_id


@dataclass
class Turn:
    role: TurnRole
    speaker_name: str  # "You" / agent display name
    content: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class RoundtableSession:
    session_id: str
    scenario_id: str
    scenario_name: str
    participants: list[str]  # agent IDs in speaking order
    agent_roster: Literal["jarvis", "brainstorm"]
    transcript: list[Turn] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    round_count: int = 0

    def add_turn(self, role: TurnRole, speaker_name: str, content: str) -> None:
        self.transcript.append(Turn(role=role, speaker_name=speaker_name, content=content))

    def format_for_prompt(self, max_chars: int = 3500) -> str:
        """Format the transcript for inclusion in an agent's prompt.

        Truncates from the oldest turns if total length exceeds max_chars.
        Returns a multi-line string like:
            用户: <msg>
            Maxwell（秘书）: <msg>
            Nora（营养师）: <msg>
        """
        if not self.transcript:
            return "(尚无发言)"

        lines: list[str] = []
        total = 0
        for turn in reversed(self.transcript):
            prefix = "用户" if turn.role == "user" else turn.speaker_name
            line = f"{prefix}: {turn.content}"
            if total + len(line) > max_chars:
                lines.insert(0, "(...较早的讨论已省略...)")
                break
            lines.insert(0, line)
            total += len(line)

        return "\n\n".join(lines)


# In-memory store; cleared on process restart
_sessions: dict[str, RoundtableSession] = {}

# Simple LRU-ish bound: if we exceed this, evict the oldest session
_MAX_SESSIONS = 128


def create_session(
    session_id: str,
    scenario_id: str,
    scenario_name: str,
    participants: list[str],
    agent_roster: Literal["jarvis", "brainstorm"] = "jarvis",
) -> RoundtableSession:
    if len(_sessions) >= _MAX_SESSIONS:
        # Evict the oldest
        oldest_id = min(_sessions, key=lambda sid: _sessions[sid].created_at)
        _sessions.pop(oldest_id, None)

    session = RoundtableSession(
        session_id=session_id,
        scenario_id=scenario_id,
        scenario_name=scenario_name,
        participants=participants,
        agent_roster=agent_roster,
    )
    _sessions[session_id] = session
    return session


def get_session(session_id: str) -> RoundtableSession | None:
    return _sessions.get(session_id)


def end_session(session_id: str) -> None:
    _sessions.pop(session_id, None)


# --- Persistence-aware async variants -------------------------------


async def create_session_async(
    session_id: str,
    scenario_id: str,
    scenario_name: str,
    participants: list[str],
    agent_roster: Literal["jarvis", "brainstorm"] = "jarvis",
    mode: str = "brainstorm",
    source_session_id: str | None = None,
    source_agent_id: str | None = None,
    title: str | None = None,
    user_prompt: str | None = None,
    status: str = "active",
) -> RoundtableSession:
    """Async variant that creates the in-memory session AND writes a
    roundtable_sessions row to SQLite so it survives a restart."""
    session = create_session(
        session_id=session_id,
        scenario_id=scenario_id,
        scenario_name=scenario_name,
        participants=participants,
        agent_roster=agent_roster,
    )
    from app.jarvis.persistence import save_session

    await save_session(
        session_id=session.session_id,
        scenario_id=session.scenario_id,
        scenario_name=session.scenario_name,
        participants=session.participants,
        agent_roster=session.agent_roster,
        round_count=session.round_count,
        title=title or scenario_name,
        user_prompt=user_prompt or "",
        mode=mode,
        source_session_id=source_session_id,
        source_agent_id=source_agent_id,
        status=status,
    )
    return session


async def add_turn_async(
    session: RoundtableSession,
    role: TurnRole,
    speaker_name: str,
    content: str,
) -> Turn:
    """Append a turn in-memory AND persist it to SQLite.

    Returns the Turn we appended (so callers can inspect the timestamp).
    """
    session.add_turn(role, speaker_name, content)
    turn = session.transcript[-1]
    from app.jarvis.persistence import append_turn, save_session

    # Make sure the parent session row exists AND its round_count is fresh.
    await save_session(
        session_id=session.session_id,
        scenario_id=session.scenario_id,
        scenario_name=session.scenario_name,
        participants=session.participants,
        agent_roster=session.agent_roster,
        round_count=session.round_count,
    )
    await append_turn(
        session_id=session.session_id,
        role=str(role),
        speaker_name=speaker_name,
        content=content,
        timestamp=turn.timestamp,
    )
    from app.jarvis.collaboration_memory import remember_roundtable_turn

    await remember_roundtable_turn(
        session_id=session.session_id,
        source_agent="user" if role == "user" else str(role),
        participant_agents=session.participants,
        memory_kind="user_request" if role == "user" else "discussion",
        content=content,
        payload={
            "speaker_name": speaker_name,
            "scenario_id": session.scenario_id,
            "round_count": session.round_count,
        },
        importance=1.3 if role == "user" else 1.0,
    )
    return turn


async def rehydrate_from_disk(limit: int = 20) -> int:
    """Load recent sessions + their turns into the in-memory store.

    Called on startup so that /roundtable/continue works for session IDs
    that predate the restart.
    """
    from app.jarvis.persistence import get_session_turns, list_sessions

    records = await list_sessions(limit=limit)
    count = 0
    for rec in records:
        session = RoundtableSession(
            session_id=rec["session_id"],
            scenario_id=rec["scenario_id"],
            scenario_name=rec["scenario_name"],
            participants=rec["participants"],
            agent_roster=rec["agent_roster"],
            round_count=rec["round_count"],
            created_at=rec["created_at"],
        )
        turns = await get_session_turns(rec["session_id"])
        for t in turns:
            session.transcript.append(
                Turn(
                    role=t["role"],
                    speaker_name=t["speaker_name"],
                    content=t["content"],
                    timestamp=t["timestamp"],
                )
            )
        _sessions[session.session_id] = session
        count += 1
    return count
