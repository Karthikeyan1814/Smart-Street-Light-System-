import sqlite3
from contextlib import contextmanager
from typing import Iterator

from .config import settings


def _safe_add_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    """Add a column to a table only if it doesn't already exist (safe migration)."""
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    except sqlite3.OperationalError:
        pass  # Column already exists — no action needed


def _init_db() -> None:
    """
    Initialize the SQLite database with the required schema if it does not exist.

    This function is idempotent and safe to call on every startup.
    """
    with sqlite3.connect(settings.SQLITE_PATH) as conn:
        # Events table (Phase 3)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tower_id TEXT NOT NULL,
                location TEXT NOT NULL,
                event_type TEXT NOT NULL,
                emotion TEXT NOT NULL,
                confidence REAL NOT NULL,
                risk_level TEXT NOT NULL,
                llm_summary TEXT,
                recommended_action TEXT,
                video_path TEXT,
                created_at TEXT NOT NULL,
                processed_at TEXT,
                gesture_detected TEXT DEFAULT 'NONE',
                activity TEXT DEFAULT 'UNKNOWN',
                threat_tags TEXT DEFAULT '',
                emotion_group TEXT DEFAULT 'Neutral'
            )
            """
        )

        # Users table for JWT auth (Phase 4)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                hashed_password TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin','operator'))
            )
            """
        )

        # Tower heartbeat/status tracking
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tower_status (
                tower_id TEXT PRIMARY KEY,
                last_heartbeat TEXT NOT NULL
            )
            """
        )

        # Model metadata (for auto-update)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS model_metadata (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                version TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        # Performance indexes for scalable queries
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_created_at ON events(created_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_tower_id ON events(tower_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_risk_level ON events(risk_level)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tower_status_tower_id "
            "ON tower_status(tower_id)"
        )

        try:
            from .auth import jwt_handler
            hashed_karthi = jwt_handler.hash_password("karthi8825")
            conn.execute(
                "INSERT OR IGNORE INTO users (username, hashed_password, role) VALUES (?, ?, ?)",
                ("karthi", hashed_karthi, "admin"),
            )
        except Exception as e:
            print(f"User seed failed: {e}")

        # Migration: add new behavioral columns to existing databases without them
        _safe_add_column(conn, "events", "gesture_detected", "TEXT DEFAULT 'NONE'")
        _safe_add_column(conn, "events", "activity", "TEXT DEFAULT 'UNKNOWN'")
        _safe_add_column(conn, "events", "threat_tags", "TEXT DEFAULT ''")
        _safe_add_column(conn, "events", "emotion_group", "TEXT DEFAULT 'Neutral'")

        conn.commit()


@contextmanager
def get_db() -> Iterator[sqlite3.Connection]:
    """
    Context manager yielding a SQLite connection with row_factory set to dict-like rows.

    Usage:
        with get_db() as conn:
            ...
    """
    conn = sqlite3.connect(settings.SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# Initialize database schema on module import
_init_db()

