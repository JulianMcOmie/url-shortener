"""Request and response schemas, with input validation."""

from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

MAX_URL_LENGTH = 2048


class CreateLinkRequest(BaseModel):
    long_url: str = Field(..., max_length=MAX_URL_LENGTH)

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


class LinkResponse(BaseModel):
    code: str
    long_url: str
    short_url: str
    custom: bool
    hit_count: int
    created_at: str
