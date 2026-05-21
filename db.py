"""SQLite schema and connection for gh-notify."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "notifications.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY,
    reason TEXT NOT NULL,
    repo TEXT NOT NULL,
    subject_type TEXT,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    seen_at TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'unread'
);
CREATE INDEX IF NOT EXISTS idx_state_updated ON notifications(state, updated_at DESC);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(SCHEMA)
    return conn
