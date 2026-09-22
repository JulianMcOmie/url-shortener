import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A test client backed by a fresh database file for every test."""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("BASE_URL", "http://short.test")
    from app import main
    return TestClient(main.app)
