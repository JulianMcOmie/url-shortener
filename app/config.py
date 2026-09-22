"""Settings, read once from environment variables with local defaults."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_path: str
    base_url: str
    log_level: str


def load_settings() -> Settings:
    return Settings(
        database_path=os.environ.get("DATABASE_PATH", "./links.db"),
        base_url=os.environ.get("BASE_URL", "http://localhost:8080").rstrip("/"),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )
