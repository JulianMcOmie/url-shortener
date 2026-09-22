import os

import pytest
from fastapi.testclient import TestClient

from app.main import app

# Set TEST_DATABASE_URL to run the same tests against Postgres. CI does this.
POSTGRES_URL = os.environ.get("TEST_DATABASE_URL", "")


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A test client with an empty database for every test.

    Settings are read when the app starts, so setting the environment before
    starting it gives each test its own SQLite file, or an emptied Postgres
    table when TEST_DATABASE_URL is set.
    """
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("DATABASE_URL", POSTGRES_URL)
    monkeypatch.setenv("BASE_URL", "http://short.test")
    with TestClient(app) as c:
        if POSTGRES_URL:
            with app.state.storage._pool.connection() as conn:
                conn.execute("TRUNCATE links")
        yield c
