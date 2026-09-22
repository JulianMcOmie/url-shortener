from datetime import datetime, timedelta, timezone

from app import links, storage

LONG = "https://example.com/some/path"


def in_hours(n):
    return (datetime.now(timezone.utc) + timedelta(hours=n)).isoformat()


def test_create_with_expiry_returns_it(client):
    r = client.post("/v1/links", json={"long_url": LONG, "expires_at": "2030-01-01T00:00:00Z"})
    assert r.status_code == 201
    assert r.json()["expires_at"] == "2030-01-01T00:00:00Z"


def test_no_expiry_is_null(client):
    assert client.post("/v1/links", json={"long_url": LONG}).json()["expires_at"] is None


def test_offset_is_normalised_to_utc(client):
    r = client.post("/v1/links", json={"long_url": LONG, "expires_at": "2030-01-01T05:00:00+05:00"})
    assert r.json()["expires_at"] == "2030-01-01T00:00:00Z"


def test_past_expiry_rejected(client):
    r = client.post("/v1/links", json={"long_url": LONG, "expires_at": "2020-01-01T00:00:00Z"})
    assert r.status_code == 422
    assert r.json()["error"].startswith("expires_at")


def test_garbage_expiry_rejected(client):
    r = client.post("/v1/links", json={"long_url": LONG, "expires_at": "tomorrow"})
    assert r.status_code == 422
    assert r.json()["error"].startswith("expires_at")


def test_unexpired_link_redirects(client):
    code = client.post("/v1/links", json={"long_url": LONG, "expires_at": in_hours(1)}).json()["code"]
    assert client.get(f"/{code}", follow_redirects=False).status_code == 307


def test_expired_link_is_410_and_not_counted(client, monkeypatch):
    code = client.post("/v1/links", json={"long_url": LONG, "expires_at": in_hours(1)}).json()["code"]
    later = storage.format_utc(datetime.now(timezone.utc) + timedelta(hours=2))
    monkeypatch.setattr(links, "utc_now", lambda: later)

    r = client.get(f"/{code}", follow_redirects=False)
    assert r.status_code == 410
    assert r.json() == {"error": "link expired"}

    meta = client.get(f"/v1/links/{code}")
    assert meta.status_code == 200
    assert meta.json()["hit_count"] == 0


def test_old_database_file_gets_expires_at_column(tmp_path):
    import sqlite3

    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE links (code TEXT PRIMARY KEY, long_url TEXT NOT NULL, custom INTEGER NOT NULL DEFAULT 0,"
        " hit_count INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL)"
    )
    conn.execute("INSERT INTO links VALUES ('old1234', 'https://example.com', 0, 3, '2026-01-01T00:00:00Z')")
    conn.commit()
    conn.close()

    s = storage.Storage(str(path))
    link = s.get("old1234")
    assert link.hit_count == 3
    assert link.expires_at is None
