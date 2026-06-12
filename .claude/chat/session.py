"""Session store for persistent WhatsApp chat conversations (SQLite)."""

from __future__ import annotations

import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))


@dataclass
class Session:
    """Chat session tied to a platform channel."""

    session_id: str  # Composite: {platform}:{channel_id}:{thread_id}
    agent_session_id: str  # SDK session ID for resume
    platform: str
    channel_id: str
    thread_id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    total_cost_usd: float = 0.0
    status: str = "active"


class SQLiteSessionStore:
    """Persistent session storage backed by SQLite."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL UNIQUE,
                    agent_session_id TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    thread_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    message_count INTEGER DEFAULT 0,
                    total_cost_usd REAL DEFAULT 0.0,
                    status TEXT DEFAULT 'active'
                );
                CREATE INDEX IF NOT EXISTS idx_platform_thread
                    ON chat_sessions(platform, channel_id, thread_id);
            """)

    def _row_to_session(self, row: sqlite3.Row) -> Session:
        return Session(
            session_id=row["session_id"],
            agent_session_id=row["agent_session_id"],
            platform=row["platform"],
            channel_id=row["channel_id"],
            thread_id=row["thread_id"],
            user_id=row["user_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            message_count=row["message_count"],
            total_cost_usd=row["total_cost_usd"],
            status=row["status"],
        )

    def get(self, platform: str, channel_id: str, thread_id: str) -> Session | None:
        session_id = f"{platform}:{channel_id}:{thread_id}"
        with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM chat_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if row is None:
                return None
            return self._row_to_session(row)

    def create(self, session: Session) -> None:
        with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
            conn.execute(
                """INSERT INTO chat_sessions
                   (session_id, agent_session_id, platform, channel_id, thread_id,
                    user_id, created_at, updated_at, message_count, total_cost_usd, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    session.session_id,
                    session.agent_session_id,
                    session.platform,
                    session.channel_id,
                    session.thread_id,
                    session.user_id,
                    session.created_at.isoformat(),
                    session.updated_at.isoformat(),
                    session.message_count,
                    session.total_cost_usd,
                    session.status,
                ),
            )

    def update(self, session: Session) -> None:
        with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
            conn.execute(
                """UPDATE chat_sessions
                   SET agent_session_id = ?, updated_at = ?, message_count = ?,
                       total_cost_usd = ?, status = ?
                   WHERE session_id = ?""",
                (
                    session.agent_session_id,
                    datetime.now().isoformat(),
                    session.message_count,
                    session.total_cost_usd,
                    session.status,
                    session.session_id,
                ),
            )

    def list_active(self, platform: str | None = None) -> list[Session]:
        with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
            conn.row_factory = sqlite3.Row
            if platform:
                rows = conn.execute(
                    "SELECT * FROM chat_sessions WHERE status = 'active' AND platform = ? "
                    "ORDER BY updated_at DESC",
                    (platform,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM chat_sessions WHERE status = 'active' ORDER BY updated_at DESC"
                ).fetchall()
            return [self._row_to_session(row) for row in rows]


def get_session_store(chat_db_path: Path | None = None) -> SQLiteSessionStore:
    if chat_db_path is None:
        from config import CHAT_DB_PATH

        chat_db_path = CHAT_DB_PATH
    return SQLiteSessionStore(chat_db_path)
