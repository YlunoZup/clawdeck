"""SQLite-backed chat history.

Schema:
    sessions(id INTEGER PRIMARY KEY, title TEXT, created_at TEXT, updated_at TEXT,
             profile TEXT, starred INTEGER)
    messages(id INTEGER PRIMARY KEY, session_id INTEGER REFERENCES sessions(id),
             role TEXT, text TEXT, created_at TEXT, model TEXT,
             tokens_in INTEGER, tokens_out INTEGER)

Why SQLite over JSON files:
- Scales to many messages without loading everything into memory
- Searchable (SQLite FTS is a Phase 3 upgrade)
- Single-file, Python-stdlib only
- Transactional — a crashed write doesn't corrupt older sessions
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..utils.paths import data_dir

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT    NOT NULL,
    created_at   TEXT    NOT NULL,
    updated_at   TEXT    NOT NULL,
    profile      TEXT    NOT NULL DEFAULT 'default',
    starred      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS messages (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role         TEXT    NOT NULL,
    text         TEXT    NOT NULL,
    created_at   TEXT    NOT NULL,
    model        TEXT,
    tokens_in    INTEGER NOT NULL DEFAULT 0,
    tokens_out   INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_profile ON sessions(profile);
"""


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Session:
    id: int
    title: str
    created_at: datetime
    updated_at: datetime
    profile: str
    starred: bool


@dataclass(frozen=True)
class Message:
    id: int
    session_id: int
    role: str
    text: str
    created_at: datetime
    model: str | None
    tokens_in: int
    tokens_out: int


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


class HistoryStore:
    """Thin sync wrapper around a SQLite connection.

    All methods are fast (<10ms); callers can run them from asyncio loops
    without a threadpool for normal sizes. Heavy queries should be pushed to
    ``asyncio.to_thread``.
    """

    def __init__(self, path: Path | None = None):
        self.path: Path = path or (data_dir() / "chats.db")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    # ------------------------------------------------------------------
    # Connection plumbing
    # ------------------------------------------------------------------

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        c = sqlite3.connect(str(self.path))
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys = ON")
        try:
            yield c
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()

    def _init_schema(self) -> None:
        with self._conn() as c:
            c.executescript(SCHEMA)

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    def list_sessions(
        self, profile: str | None = None, limit: int = 100
    ) -> list[Session]:
        with self._conn() as c:
            if profile is not None:
                rows = c.execute(
                    "SELECT * FROM sessions WHERE profile = ? "
                    "ORDER BY updated_at DESC LIMIT ?",
                    (profile, limit),
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [_session_from_row(r) for r in rows]

    def create_session(
        self, title: str = "New chat", profile: str = "default"
    ) -> Session:
        now = datetime.now().isoformat(timespec="seconds")
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO sessions (title, created_at, updated_at, profile) "
                "VALUES (?, ?, ?, ?)",
                (title, now, now, profile),
            )
            sid = cur.lastrowid
            row = c.execute("SELECT * FROM sessions WHERE id = ?", (sid,)).fetchone()
        return _session_from_row(row)

    def rename_session(self, session_id: int, title: str) -> None:
        with self._conn() as c:
            c.execute(
                "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
                (title, datetime.now().isoformat(timespec="seconds"), session_id),
            )

    def star_session(self, session_id: int, starred: bool) -> None:
        with self._conn() as c:
            c.execute(
                "UPDATE sessions SET starred = ? WHERE id = ?",
                (1 if starred else 0, session_id),
            )

    def delete_session(self, session_id: int) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            c.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    def list_messages(self, session_id: int, limit: int = 500) -> list[Message]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM messages WHERE session_id = ? "
                "ORDER BY id ASC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return [_message_from_row(r) for r in rows]

    def add_message(
        self,
        session_id: int,
        role: str,
        text: str,
        *,
        model: str | None = None,
        tokens_in: int = 0,
        tokens_out: int = 0,
    ) -> Message:
        now = datetime.now().isoformat(timespec="seconds")
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO messages "
                "(session_id, role, text, created_at, model, tokens_in, tokens_out) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (session_id, role, text, now, model, tokens_in, tokens_out),
            )
            mid = cur.lastrowid
            c.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (now, session_id),
            )
            row = c.execute("SELECT * FROM messages WHERE id = ?", (mid,)).fetchone()
        return _message_from_row(row)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def daily_tokens(
        self, days: int = 30, profile: str | None = None
    ) -> list[tuple[str, int, int]]:
        """Return [(YYYY-MM-DD, tokens_in, tokens_out), ...] newest-first."""
        with self._conn() as c:
            if profile is not None:
                rows = c.execute(
                    """
                    SELECT substr(m.created_at, 1, 10) AS day,
                           SUM(m.tokens_in)           AS tin,
                           SUM(m.tokens_out)          AS tout
                    FROM messages m
                    JOIN sessions s ON s.id = m.session_id
                    WHERE s.profile = ?
                    GROUP BY day ORDER BY day DESC LIMIT ?
                    """,
                    (profile, days),
                ).fetchall()
            else:
                rows = c.execute(
                    """
                    SELECT substr(created_at, 1, 10) AS day,
                           SUM(tokens_in)            AS tin,
                           SUM(tokens_out)           AS tout
                    FROM messages
                    GROUP BY day ORDER BY day DESC LIMIT ?
                    """,
                    (days,),
                ).fetchall()
        return [(r["day"], r["tin"] or 0, r["tout"] or 0) for r in rows]


# ---------------------------------------------------------------------------
# Row → dataclass
# ---------------------------------------------------------------------------


def _session_from_row(r: sqlite3.Row) -> Session:
    return Session(
        id=r["id"],
        title=r["title"],
        created_at=datetime.fromisoformat(r["created_at"]),
        updated_at=datetime.fromisoformat(r["updated_at"]),
        profile=r["profile"],
        starred=bool(r["starred"]),
    )


def _message_from_row(r: sqlite3.Row) -> Message:
    return Message(
        id=r["id"],
        session_id=r["session_id"],
        role=r["role"],
        text=r["text"],
        created_at=datetime.fromisoformat(r["created_at"]),
        model=r["model"],
        tokens_in=r["tokens_in"],
        tokens_out=r["tokens_out"],
    )
