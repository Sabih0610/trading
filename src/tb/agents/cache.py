"""Local content-addressed response cache with explicit TTLs."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path


def cache_key(*parts: object) -> str:
    """Hash canonicalized request identity without relying on filesystem-safe text."""

    payload = json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


class ResponseCache:
    """A small SQLite cache separate from the immutable evidence ledger."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """CREATE TABLE IF NOT EXISTS responses (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    expires_at_utc TEXT NOT NULL
                )"""
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def get(self, key: str, *, now: datetime | None = None) -> str | None:
        """Return unexpired content; expired entries are treated as misses."""

        instant = datetime.now(UTC) if now is None else now.astimezone(UTC)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value, expires_at_utc FROM responses WHERE key = ?", (key,)
            ).fetchone()
        if row is None or datetime.fromisoformat(str(row[1])).astimezone(UTC) <= instant:
            return None
        return str(row[0])

    def put(self, key: str, value: str, *, ttl_seconds: int, now: datetime | None = None) -> None:
        """Insert or refresh one operational cache entry."""

        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        instant = datetime.now(UTC) if now is None else now.astimezone(UTC)
        expires = instant + timedelta(seconds=ttl_seconds)
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO responses(key, value, created_at_utc, expires_at_utc)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    created_at_utc = excluded.created_at_utc,
                    expires_at_utc = excluded.expires_at_utc""",
                (key, value, instant.isoformat(), expires.isoformat()),
            )
