"""Durable sqlite-backed state store for research runs."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class StateStore:
    """SQLite-backed state persistence for API control-plane and worker runtime."""

    def __init__(self, db_path: str = "research_history.db") -> None:
        self.db_path = db_path
        self._ensure_parent_dir()
        self._init_schema()

    def _ensure_parent_dir(self) -> None:
        parent = Path(self.db_path).resolve().parent
        parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _ensure_columns(self, conn: sqlite3.Connection, table_name: str, columns: list[tuple[str, str]]) -> None:
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}
        for column_name, column_def in columns:
            if column_name not in existing:
                conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    task_id TEXT PRIMARY KEY,
                    topic TEXT NOT NULL,
                    status TEXT NOT NULL,
                    max_turns INTEGER NOT NULL DEFAULT 8,
                    current_turn INTEGER NOT NULL DEFAULT 0,
                    summary TEXT NOT NULL DEFAULT '',
                    error TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    final_answer TEXT
                )
                """
            )
            self._ensure_columns(
                conn,
                "sessions",
                [
                    ("max_turns", "INTEGER NOT NULL DEFAULT 8"),
                    ("current_turn", "INTEGER NOT NULL DEFAULT 0"),
                    ("summary", "TEXT NOT NULL DEFAULT ''"),
                    ("error", "TEXT"),
                ],
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS history_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    turn INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES sessions(task_id) ON DELETE CASCADE
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS run_checkpoints (
                    task_id TEXT PRIMARY KEY,
                    last_completed_turn INTEGER NOT NULL DEFAULT 0,
                    summary_snapshot TEXT NOT NULL DEFAULT '',
                    worker_state_json TEXT,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES sessions(task_id) ON DELETE CASCADE
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS run_processes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    pid INTEGER NOT NULL,
                    started_at TEXT NOT NULL,
                    heartbeat_at TEXT NOT NULL,
                    exit_code INTEGER,
                    failure_reason TEXT,
                    restart_count INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(task_id) REFERENCES sessions(task_id) ON DELETE CASCADE
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS run_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES sessions(task_id) ON DELETE CASCADE
                )
                """
            )

    def create_session(self, topic: str, max_turns: int) -> str:
        task_id = str(uuid.uuid4())
        now = _utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (task_id, topic, status, max_turns, current_turn, summary, created_at)
                VALUES (?, ?, ?, ?, 0, '', ?)
                """,
                (task_id, topic, "queued", max_turns, now),
            )
            conn.execute(
                """
                INSERT INTO run_checkpoints (task_id, last_completed_turn, summary_snapshot, worker_state_json, updated_at)
                VALUES (?, 0, '', ?, ?)
                """,
                (task_id, json.dumps({}), now),
            )
        return task_id

    def get_session(self, task_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE task_id = ?", (task_id,)).fetchone()
        return dict(row) if row else None

    def get_history(self, task_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT turn, action, content, timestamp
                FROM history_entries
                WHERE task_id = ?
                ORDER BY turn ASC, id ASC
                """,
                (task_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_sessions(self, query: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM sessions"
        args: tuple[Any, ...] = ()
        if query:
            sql += " WHERE topic LIKE ?"
            args = (f"%{query}%",)
        sql += " ORDER BY created_at DESC"
        with self._connect() as conn:
            rows = conn.execute(sql, args).fetchall()
        return [dict(row) for row in rows]

    def delete_session(self, task_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM sessions WHERE task_id = ?", (task_id,))

    def get_checkpoint(self, task_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM run_checkpoints WHERE task_id = ?", (task_id,)).fetchone()
        return dict(row) if row else None

    def update_session_status(self, task_id: str, status: str) -> None:
        with self._connect() as conn:
            now = _utc_now_iso()
            started_at = now if status == "running" else None
            completed_at = now if status in {"completed", "failed", "canceled"} else None
            conn.execute(
                """
                UPDATE sessions
                SET status = ?,
                    started_at = COALESCE(?, started_at),
                    completed_at = CASE WHEN ? IS NOT NULL THEN ? ELSE completed_at END
                WHERE task_id = ?
                """,
                (status, started_at, completed_at, completed_at, task_id),
            )

    def insert_process(self, task_id: str, pid: int) -> None:
        now = _utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO run_processes (task_id, pid, started_at, heartbeat_at)
                VALUES (?, ?, ?, ?)
                """,
                (task_id, pid, now, now),
            )

    def commit_turn(
        self,
        task_id: str,
        turn: int,
        action: str,
        content: str,
        summary_snapshot: str,
        status: str = "running",
        worker_state: dict[str, Any] | None = None,
        event_type: str = "turn.committed",
        event_payload: dict[str, Any] | None = None,
    ) -> None:
        now = _utc_now_iso()
        worker_state_json = json.dumps(worker_state if worker_state is not None else {})
        payload_json = json.dumps(event_payload if event_payload is not None else {})
        with self._connect() as conn:
            conn.execute("BEGIN")
            conn.execute(
                """
                INSERT INTO history_entries (task_id, turn, action, content, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                (task_id, turn, action, content, now),
            )
            conn.execute(
                """
                UPDATE sessions
                SET current_turn = ?, summary = ?, status = ?
                WHERE task_id = ?
                """,
                (turn, summary_snapshot, status, task_id),
            )
            conn.execute(
                """
                INSERT INTO run_checkpoints (task_id, last_completed_turn, summary_snapshot, worker_state_json, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    last_completed_turn = excluded.last_completed_turn,
                    summary_snapshot = excluded.summary_snapshot,
                    worker_state_json = excluded.worker_state_json,
                    updated_at = excluded.updated_at
                """,
                (task_id, turn, summary_snapshot, worker_state_json, now),
            )
            conn.execute(
                """
                INSERT INTO run_events (task_id, event_type, payload_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (task_id, event_type, payload_json, now),
            )
            conn.commit()

    def complete_session(self, task_id: str, final_answer: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE sessions
                SET status = 'completed', final_answer = ?, completed_at = ?
                WHERE task_id = ?
                """,
                (final_answer, _utc_now_iso(), task_id),
            )

    def fail_session(self, task_id: str, error: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE sessions
                SET status = 'failed', error = ?, completed_at = ?
                WHERE task_id = ?
                """,
                (error, _utc_now_iso(), task_id),
            )

    def increment_restart_count(self, task_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE run_processes
                SET restart_count = restart_count + 1
                WHERE id = (
                    SELECT id
                    FROM run_processes
                    WHERE task_id = ?
                    ORDER BY id DESC
                    LIMIT 1
                )
                """,
                (task_id,),
            )

    def update_heartbeat(self, task_id: str, pid: int) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE run_processes
                SET heartbeat_at = ?
                WHERE id = (
                    SELECT id
                    FROM run_processes
                    WHERE task_id = ? AND pid = ?
                    ORDER BY id DESC
                    LIMIT 1
                )
                """,
                (_utc_now_iso(), task_id, pid),
            )
