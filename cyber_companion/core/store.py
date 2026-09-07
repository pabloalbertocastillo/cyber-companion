"""One SQLite writer, durable transitions and bounded history; no raw sample log."""
from __future__ import annotations
import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from uuid import uuid4


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.is_symlink():
            raise ValueError("database must not be a symlink")
        self.lock = threading.Lock()
        self.db = sqlite3.connect(path, timeout=1, check_same_thread=False)
        os.chmod(path, 0o600)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1):
            self.db.close()
            raise ValueError("unsupported database version")
        with self.db:
            self.db.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            self.db.execute("CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, time REAL, kind TEXT, payload TEXT)")
            self.db.execute("CREATE TABLE IF NOT EXISTS outbox (id INTEGER PRIMARY KEY, payload TEXT NOT NULL, delivered INTEGER DEFAULT 0)")
            self.db.execute("INSERT OR IGNORE INTO meta VALUES ('store_id', ?)", (uuid4().hex,))
            self.db.execute("PRAGMA user_version=1")
        self.store_id = self.db.execute("SELECT value FROM meta WHERE key='store_id'").fetchone()[0]

    def load(self) -> dict:
        with self.lock:
            row = self.db.execute("SELECT value FROM meta WHERE key='state'").fetchone()
            return json.loads(row[0]) if row else {}

    def reserve(self) -> int:
        with self.lock, self.db:
            row = self.db.execute("SELECT value FROM meta WHERE key='sequence'").fetchone()
            value = int(row[0]) if row else 0
            self.db.execute("INSERT OR REPLACE INTO meta VALUES ('sequence', ?)", (str(value + 1024),))
            return value + 1

    def save(self, state: dict, events: list[dict], audit: dict | None = None) -> None:
        with self.lock, self.db:
            self.db.execute("INSERT OR REPLACE INTO meta VALUES ('state', ?)", (json.dumps(state, allow_nan=False),))
            for event in events:
                payload = json.dumps(event, allow_nan=False)
                self.db.execute("INSERT INTO audit(time, kind, payload) VALUES (?, 'insight', ?)", (time.time(), payload))
                self.db.execute("INSERT INTO outbox(payload) VALUES (?)", (payload,))
            if audit:
                self.db.execute("INSERT INTO audit(time, kind, payload) VALUES (?, 'preference', ?)", (time.time(), json.dumps(audit)))
            self.db.execute("DELETE FROM audit WHERE id NOT IN (SELECT id FROM audit ORDER BY id DESC LIMIT 2000)")
            self.db.execute("DELETE FROM outbox WHERE delivered=1")
            self.db.execute("DELETE FROM outbox WHERE id NOT IN (SELECT id FROM outbox ORDER BY id DESC LIMIT 256)")

    def pending(self) -> list[tuple[int, dict]]:
        with self.lock:
            return [(row[0], json.loads(row[1])) for row in self.db.execute("SELECT id,payload FROM outbox WHERE delivered=0 ORDER BY id LIMIT 16")]

    def delivered(self, ident: int) -> None:
        with self.lock, self.db:
            self.db.execute("UPDATE outbox SET delivered=1 WHERE id=?", (ident,))

    def close(self):
        with self.lock:
            self.db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            self.db.close()
