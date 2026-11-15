"""SQLite storage for workspaces and waypoints.

A single file (default ``<data dir>/jezero.sqlite3``, override with
``JEZERO_DB_PATH``) — no database server to run. The schema is created on
startup. WAL mode lets several API workers read while one writes.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS workspaces (
  id            TEXT PRIMARY KEY,
  key_hash      TEXT NOT NULL UNIQUE CHECK (length(key_hash) = 64),
  created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  last_seen_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS waypoints (
  id            TEXT PRIMARY KEY,
  workspace_id  TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  name          TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 120),
  description   TEXT NOT NULL DEFAULT '' CHECK (length(description) <= 4000),
  x             REAL NOT NULL,
  y             REAL NOT NULL,
  lon_e         REAL NOT NULL CHECK (lon_e >= 0 AND lon_e < 360),
  lat           REAL NOT NULL CHECK (lat BETWEEN -90 AND 90),
  crs_id        TEXT NOT NULL,
  crs_version   INTEGER NOT NULL,
  created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  updated_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS waypoints_workspace_idx ON waypoints(workspace_id, created_at);
"""

NOW = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"

_path: Path | None = None


def _dict_row(cur: sqlite3.Cursor, row: tuple) -> dict:
    return {d[0]: v for d, v in zip(cur.description, row, strict=True)}


def _connect(path: Path) -> sqlite3.Connection:
    # isolation_level=None: autocommit; writes use explicit BEGIN IMMEDIATE via transaction()
    conn = sqlite3.connect(path, timeout=10.0, isolation_level=None, check_same_thread=False)
    conn.row_factory = _dict_row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


def init(path: Path) -> None:
    """Create the database file and schema if needed."""
    global _path
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = _connect(path)
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)
    finally:
        conn.close()
    _path = path


def close() -> None:
    global _path
    _path = None


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    if _path is None:
        raise RuntimeError("Database not initialised")
    conn = _connect(_path)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Write transaction: takes the write lock up front, commits or rolls back."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


def ping() -> bool:
    try:
        with connection() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:  # noqa: BLE001
        return False
