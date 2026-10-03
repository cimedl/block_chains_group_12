import os
import sqlite3
from contextlib import closing
from typing import Optional


class ServiceDatabase:
    # record consumed_requests, ensure that the service can still defend against replay attacks after restarting.
    def __init__(self, db_path: str = "data/service_state.db"):
        self.db_path = db_path
        parent_dir = os.path.dirname(self.db_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with closing(self._get_connection()) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS consumed_requests (
                    request_id TEXT PRIMARY KEY,
                    requester TEXT NOT NULL,
                    record_id INTEGER NOT NULL,
                    consumed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def is_consumed(self, request_id: str) -> bool:
        with closing(self._get_connection()) as conn:
            cursor = conn.execute(
                "SELECT 1 FROM consumed_requests WHERE request_id = ?",
                (str(request_id),)
            )
            return cursor.fetchone() is not None

    def mark_consumed(self, request_id: str, requester: str, record_id: int):
        with closing(self._get_connection()) as conn:
            conn.execute(
                "INSERT INTO consumed_requests (request_id, requester, record_id) VALUES (?, ?, ?)",
                (str(request_id), requester.lower(), record_id)
            )
            conn.commit()