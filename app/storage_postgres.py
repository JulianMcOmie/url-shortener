"""Postgres storage. Same five methods as the SQLite Storage class.

Used when DATABASE_URL is set. A small pool of connections lets many requests,
and many containers, share one database safely.
"""

from psycopg import errors
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.storage import CodeTaken, Link, utc_now

SCHEMA = """
CREATE TABLE IF NOT EXISTS links (
    code       TEXT PRIMARY KEY,
    long_url   TEXT NOT NULL,
    custom     BOOLEAN NOT NULL DEFAULT FALSE,
    hit_count  INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    expires_at TEXT
);
ALTER TABLE links ADD COLUMN IF NOT EXISTS expires_at TEXT;
"""


class PostgresStorage:
    name = "postgres"

    def __init__(self, url: str) -> None:
        self._pool = ConnectionPool(url, min_size=1, max_size=4, kwargs={"row_factory": dict_row}, open=True)
        with self._pool.connection() as conn:
            conn.execute(SCHEMA)

    def insert(self, code: str, long_url: str, custom: bool, expires_at: str | None = None) -> Link:
        created_at = utc_now()
        try:
            with self._pool.connection() as conn:
                conn.execute(
                    "INSERT INTO links (code, long_url, custom, hit_count, created_at, expires_at)"
                    " VALUES (%s, %s, %s, 0, %s, %s)",
                    (code, long_url, custom, created_at, expires_at),
                )
        except errors.UniqueViolation as e:
            raise CodeTaken(code) from e
        return Link(code=code, long_url=long_url, custom=custom, hit_count=0,
                    created_at=created_at, expires_at=expires_at)

    def get(self, code: str) -> Link | None:
        with self._pool.connection() as conn:
            row = conn.execute("SELECT * FROM links WHERE code = %s", (code,)).fetchone()
        return Link(**row) if row else None

    def record_hit(self, code: str, now: str) -> Link | None:
        with self._pool.connection() as conn:
            row = conn.execute(
                "UPDATE links SET hit_count = hit_count + 1"
                " WHERE code = %s AND (expires_at IS NULL OR expires_at > %s) RETURNING *",
                (code, now),
            ).fetchone()
        return Link(**row) if row else None

    def delete(self, code: str) -> bool:
        with self._pool.connection() as conn:
            cur = conn.execute("DELETE FROM links WHERE code = %s", (code,))
        return cur.rowcount == 1

    def close(self) -> None:
        self._pool.close()
