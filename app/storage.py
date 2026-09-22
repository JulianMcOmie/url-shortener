"""SQLite persistence. Nothing outside this file knows how links are stored."""

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
                    created_at TEXT NOT NULL
                )
                """
            )

    def insert(self, code: str, long_url: str, custom: bool) -> Link:
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        with self._lock:
            try:
                with self._conn:
                    self._conn.execute(
                        "INSERT INTO links (code, long_url, custom, hit_count, created_at) VALUES (?, ?, ?, 0, ?)",
                        (code, long_url, int(custom), created_at),
                    )
            except sqlite3.IntegrityError as e:
                raise CodeTaken(code) from e
        return Link(code=code, long_url=long_url, custom=custom, hit_count=0, created_at=created_at)

    def get(self, code: str) -> Link | None:
        row = self._conn.execute("SELECT * FROM links WHERE code = ?", (code,)).fetchone()
        return self._to_link(row) if row else None

    def record_hit(self, code: str) -> Link | None:
        """Increment the hit count and return the link, or None if the code is unknown."""
        with self._lock, self._conn:
            row = self._conn.execute(
                "UPDATE links SET hit_count = hit_count + 1 WHERE code = ? RETURNING *", (code,)
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
        )
