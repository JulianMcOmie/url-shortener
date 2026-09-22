"""Request and response schemas, with input validation."""

from datetime import datetime, timezone
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

from app.codes import validate_alias
from app.storage import format_utc

MAX_URL_LENGTH = 2048


class CreateLinkRequest(BaseModel):
    long_url: str = Field(..., max_length=MAX_URL_LENGTH)
    alias: str | None = None
    expires_at: datetime | None = None

    @field_validator("long_url")
    @classmethod
    def must_be_http_url(cls, value: str) -> str:
        value = value.strip()
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("must start with http:// or https://")
        if not parsed.netloc:
            raise ValueError("must include a host")
        return value

    @field_validator("alias")
    @classmethod
    def alias_rules(cls, value: str | None) -> str | None:
        return None if value is None else validate_alias(value)

    @field_validator("expires_at")
    @classmethod
    def must_be_future(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)  # naive timestamps are taken as UTC
        if value <= datetime.now(timezone.utc):
            raise ValueError("must be in the future")
        return value

    def expires_at_utc(self) -> str | None:
        return None if self.expires_at is None else format_utc(self.expires_at)


class LinkResponse(BaseModel):
    code: str
    long_url: str
    short_url: str
    custom: bool
    hit_count: int
    created_at: str
    expires_at: str | None
