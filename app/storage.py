"""SQLite persistence, plus the factory that picks a backend.

Nothing outside the storage modules knows how links are stored.
"""

import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class Link:
    code: str
    long_url: str
    custom: bool
    hit_count: int
    created_at: str
    expires_at: str | None = None


def utc_now() -> str:
    """Current time in the one format every timestamp in the table uses."""
    return format_utc(datetime.now(timezone.utc))


def format_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class CodeTaken(Exception):
    """The code already exists in the table."""


class Storage:
    def __init__(self, path: str) -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._conn:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS links (
                    code       TEXT PRIMARY KEY,
                    long_url   TEXT NOT NULL,
                    custom     INTEGER NOT NULL DEFAULT 0,
                    hit_count  INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    expires_at TEXT
                )
                """
            )
            self._migrate()

    def _migrate(self) -> None:
        """Bring an older database file up to the current schema."""
        columns = {row["name"] for row in self._conn.execute("PRAGMA table_info(links)")}
        if "expires_at" not in columns:
            self._conn.execute("ALTER TABLE links ADD COLUMN expires_at TEXT")

    def insert(self, code: str, long_url: str, custom: bool, expires_at: str | None = None) -> Link:
        created_at = utc_now()
        with self._lock:
            try:
                with self._conn:
                    self._conn.execute(
                        "INSERT INTO links (code, long_url, custom, hit_count, created_at, expires_at)"
                        " VALUES (?, ?, ?, 0, ?, ?)",
                        (code, long_url, int(custom), created_at, expires_at),
                    )
            except sqlite3.IntegrityError as e:
                raise CodeTaken(code) from e
        return Link(code=code, long_url=long_url, custom=custom, hit_count=0,
                    created_at=created_at, expires_at=expires_at)

    def get(self, code: str) -> Link | None:
        row = self._conn.execute("SELECT * FROM links WHERE code = ?", (code,)).fetchone()
        return self._to_link(row) if row else None

    def record_hit(self, code: str, now: str) -> Link | None:
        """Increment the hit count and return the link.

        Returns None if the code is unknown or the link expired before `now`, so an
        expired link never counts a hit. Timestamps compare as strings because they
        are all stored in the same UTC format.
        """
        with self._lock, self._conn:
            row = self._conn.execute(
                "UPDATE links SET hit_count = hit_count + 1"
                " WHERE code = ? AND (expires_at IS NULL OR expires_at > ?) RETURNING *",
                (code, now),
            ).fetchone()
        return self._to_link(row) if row else None

    def delete(self, code: str) -> bool:
        """Remove a link. Returns False if the code was unknown."""
        with self._lock, self._conn:
            cur = self._conn.execute("DELETE FROM links WHERE code = ?", (code,))
        return cur.rowcount == 1

    def close(self) -> None:
        self._conn.close()

    @staticmethod
    def _to_link(row: sqlite3.Row) -> Link:
        return Link(
            code=row["code"],
            long_url=row["long_url"],
            custom=bool(row["custom"]),
            hit_count=row["hit_count"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
        )


def open_storage(database_url: str, database_path: str):
    """Postgres when DATABASE_URL is set, SQLite otherwise."""
    if database_url:
        from app.storage_postgres import PostgresStorage  # optional backend, imported on demand
        return PostgresStorage(database_url)
    return Storage(database_path)
