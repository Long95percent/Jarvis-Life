import sqlite3
import os
import time
import uuid

class HistoryManager:
    def __init__(self, db_path="chat_history.db"):
        self.db_path = db_path
        self._init_db()
        self.cleanup_old_sessions(30)

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                mode_id TEXT,
                title TEXT,
                updated_at REAL,
                is_protected INTEGER DEFAULT 0,
                is_pinned INTEGER DEFAULT 0
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                role TEXT,
                content TEXT,
                timestamp REAL,
                FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )''')
            conn.commit()

    def cleanup_old_sessions(self, days=30):
        cutoff = time.time() - (days * 86400)
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            # Delete unprotected and unpinned sessions older than cutoff
            c.execute("SELECT id FROM sessions WHERE updated_at < ? AND is_protected = 0 AND is_pinned = 0", (cutoff,))
            rows = c.fetchall()
            for (sid,) in rows:
                c.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
                c.execute("DELETE FROM sessions WHERE id = ?", (sid,))
            conn.commit()

    def create_session(self, mode_id: str, title: str = "New Chat") -> str:
        session_id = str(uuid.uuid4())
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("INSERT INTO sessions (id, mode_id, title, updated_at) VALUES (?, ?, ?, ?)",
                      (session_id, mode_id, title, now))
            conn.commit()
        return session_id

    def get_sessions(self, mode_id: str):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT id, title, updated_at, is_protected, is_pinned FROM sessions WHERE mode_id = ? ORDER BY is_pinned DESC, updated_at DESC", (mode_id,))
            rows = c.fetchall()
            return [{"id": r[0], "title": r[1], "updated_at": r[2], "is_protected": bool(r[3]), "is_pinned": bool(r[4])} for r in rows]

    def get_session_by_id(self, session_id: str):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT id, mode_id, title, updated_at, is_protected, is_pinned FROM sessions WHERE id = ?", (session_id,))
            r = c.fetchone()
            if r:
                return {"id": r[0], "mode_id": r[1], "title": r[2], "updated_at": r[3], "is_protected": bool(r[4]), "is_pinned": bool(r[5])}
            return None

    def rename_session(self, session_id: str, title: str):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("UPDATE sessions SET title = ? WHERE id = ?", (title, session_id))
            conn.commit()

    def toggle_protect(self, session_id: str, is_protected: bool):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("UPDATE sessions SET is_protected = ? WHERE id = ?", (1 if is_protected else 0, session_id))
            conn.commit()

    def toggle_pin(self, session_id: str, is_pinned: bool):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("UPDATE sessions SET is_pinned = ? WHERE id = ?", (1 if is_pinned else 0, session_id))
            conn.commit()

    def delete_session(self, session_id: str):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            c.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()

    def delete_messages_up_to(self, session_id: str, timestamp: float):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM messages WHERE session_id = ? AND timestamp <= ?", (session_id, timestamp))
            conn.commit()

    def add_message(self, session_id: str, role: str, content: str):
        msg_id = str(uuid.uuid4())
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("INSERT INTO messages (id, session_id, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
                      (msg_id, session_id, role, content, now))
            c.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id))
            conn.commit()
        return msg_id

    def get_messages(self, session_id: str):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT role, content, timestamp FROM messages WHERE session_id = ? ORDER BY timestamp ASC", (session_id,))
            rows = c.fetchall()
            return [{"role": r[0], "content": r[1], "timestamp": r[2]} for r in rows]

    def get_all_messages_for_mode(self, mode_id: str):
        # Fetch all messages for a specific mode to build the history index
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("""
                SELECT s.id, m.role, m.content, m.timestamp 
                FROM sessions s JOIN messages m ON s.id = m.session_id 
                WHERE s.mode_id = ? 
                ORDER BY m.timestamp ASC
            """, (mode_id,))
            rows = c.fetchall()
            return [{"session_id": r[0], "role": r[1], "content": r[2], "timestamp": r[3]} for r in rows]
