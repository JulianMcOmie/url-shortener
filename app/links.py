"""Link creation and lookup. Routes call this; this calls storage."""

from urllib.parse import urlparse

from fastapi import HTTPException

from app.codes import generate_code
from app.models import LinkResponse
from app.storage import CodeTaken, Link, Storage

GENERATE_ATTEMPTS = 5


def to_response(link: Link, base_url: str) -> LinkResponse:
    return LinkResponse(
        code=link.code,
        long_url=link.long_url,
        short_url=f"{base_url}/{link.code}",
        custom=link.custom,
        hit_count=link.hit_count,
        created_at=link.created_at,
    )


def create_link(storage: Storage, base_url: str, long_url: str) -> Link:
    if urlparse(long_url).netloc == urlparse(base_url).netloc:
        raise HTTPException(422, "long_url: must not point at this service")

    for _ in range(GENERATE_ATTEMPTS):
        try:
            return storage.insert(generate_code(), long_url, custom=False)
        except CodeTaken:
            continue
    raise HTTPException(500, "could not generate a unique code, try again")
