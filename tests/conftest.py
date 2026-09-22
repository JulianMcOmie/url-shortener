import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A test client backed by a fresh database file for every test.

    Settings are read at startup, so setting the env before entering the
    TestClient context gives each test its own database.
    """
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("BASE_URL", "http://short.test")
    with TestClient(app) as c:
        yield c
