import os
import sqlite3
import time
from contextlib import closing
from typing import Optional


class ServiceDatabase:
    def __init__(self, db_path: str = "data/service_state.db", namespace: str = ""):
        self.db_path = db_path
        self.namespace= namespace
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
            if conn.execute("SELECT 1 FROM consumed_requests LIMIT 1").fetchone():
                raise RuntimeError("Legacy replay database has unscoped requests; archive it and use a fresh database for a fresh deployment.")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS request_deliveries (
                    namespace TEXT NOT NULL, request_id TEXT NOT NULL,
                    requester TEXT NOT NULL, record_id TEXT NOT NULL,
                    outcome TEXT NOT NULL DEFAULT 'claimed', error_type TEXT,
                    consumed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (namespace, request_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS record_files (
                    registry_namespace TEXT NOT NULL, record_id TEXT NOT NULL,
                    enc_path TEXT NOT NULL, key_path TEXT NOT NULL,
                    PRIMARY KEY (registry_namespace, record_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS delivery_challenges (
                    namespace TEXT NOT NULL, message TEXT NOT NULL,
                    record_id TEXT NOT NULL, request_id TEXT NOT NULL,
                    requester TEXT NOT NULL, tx_hash TEXT NOT NULL,
                    expires_at INTEGER NOT NULL, used INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (namespace, message)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS delivery_attempts (
                    id INTEGER PRIMARY KEY, namespace TEXT NOT NULL,
                    request_id TEXT NOT NULL, requester TEXT NOT NULL,
                    record_id TEXT NOT NULL, tx_hash TEXT NOT NULL,
                    outcome TEXT NOT NULL, error_type TEXT,
                    attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def is_consumed(self, request_id: str) -> bool:
        with closing(self._get_connection()) as conn:
            cursor = conn.execute(
                "SELECT 1 FROM request_deliveries WHERE namespace = ? AND request_id = ?",
                (self.namespace, str(int(request_id)))
            )
            return cursor.fetchone() is not None

    def mark_consumed(self, request_id: str, requester: str, record_id: int, challenge: str):
        # claim once, even with concurrent requests
        with closing(self._get_connection()) as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                updated = conn.execute(
                    "UPDATE delivery_challenges SET used = 1 WHERE namespace = ? AND message = ? AND used = 0 AND expires_at > ?",
                    (self.namespace, challenge, int(time.time()))
                )
                if updated.rowcount != 1:
                    raise PermissionError("Wallet challenge is expired or already used.")
                conn.execute(
                    "INSERT INTO request_deliveries (namespace, request_id, requester, record_id) VALUES (?, ?, ?, ?)",
                    (self.namespace, str(int(request_id)), requester.lower(), str(int(record_id))))
                conn.commit()
            except sqlite3.IntegrityError as failure:
                conn.rollback()
                raise PermissionError("Request ID has already been consumed.") from failure
            except Exception:
                conn.rollback()
                raise

    def set_record_file(self, registry_namespace, record_id, enc_path, key_path):
        with closing(self._get_connection()) as conn:
            conn.execute("INSERT INTO record_files VALUES (?, ?, ?, ?) ON CONFLICT(registry_namespace, record_id) DO UPDATE SET enc_path = excluded.enc_path, key_path = excluded.key_path",
                (registry_namespace, str(int(record_id)), enc_path, key_path))
            conn.commit()

    def get_record_file(self, registry_namespace, record_id):
        with closing(self._get_connection()) as conn:
            return conn.execute("SELECT enc_path, key_path FROM record_files WHERE registry_namespace = ? AND record_id = ?",
                (registry_namespace, str(int(record_id)))).fetchone()

    def add_challenge(self, message, record_id, request_id, requester, tx_hash, expires_at):
        with closing(self._get_connection()) as conn:
            conn.execute("INSERT INTO delivery_challenges (namespace, message, record_id, request_id, requester, tx_hash, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (self.namespace, message, str(int(record_id)), str(int(request_id)), requester.lower(), tx_hash.lower(), expires_at))
            conn.commit()

    def check_challenge(self, message, record_id, request_id, requester, tx_hash):
        with closing(self._get_connection()) as conn:
            row = conn.execute("SELECT record_id, request_id, requester, tx_hash, expires_at, used FROM delivery_challenges WHERE namespace = ? AND message = ?",
                (self.namespace, message)).fetchone()
        expected = (str(int(record_id)), str(int(request_id)), requester.lower(), tx_hash.lower())
        if row is None or tuple(row[:4]) != expected or row[5] or row[4] <= int(time.time()):
            raise PermissionError("Wallet challenge is unknown, mismatched, expired or already used.")

    def finish_delivery(self, request_id, outcome, error_type=None):
        with closing(self._get_connection()) as conn:
            conn.execute("UPDATE request_deliveries SET outcome = ?, error_type = ? WHERE namespace = ? AND request_id = ?",
                (outcome, error_type, self.namespace, str(int(request_id))))
            conn.commit()

    def record_attempt(self, request_id, requester, record_id, tx_hash, outcome, error_type=None):
        with closing(self._get_connection()) as conn:
            conn.execute("INSERT INTO delivery_attempts (namespace, request_id, requester, record_id, tx_hash, outcome, error_type) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (self.namespace, str(request_id), str(requester).lower(), str(record_id), str(tx_hash).lower(), outcome, error_type))
            conn.commit()
