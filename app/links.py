"""Link creation and lookup. Routes call this; this calls storage."""

from urllib.parse import urlparse

from fastapi import HTTPException

from app.codes import RESERVED, generate_code
from app.models import LinkResponse
from app.storage import CodeTaken, Link, Storage, utc_now

GENERATE_ATTEMPTS = 5


def to_response(link: Link, base_url: str) -> LinkResponse:
    return LinkResponse(
        code=link.code,
        long_url=link.long_url,
        short_url=f"{base_url}/{link.code}",
        custom=link.custom,
        hit_count=link.hit_count,
        created_at=link.created_at,
        expires_at=link.expires_at,
    )


def create_link(
    storage: Storage, base_url: str, long_url: str, alias: str | None = None, expires_at: str | None = None
) -> Link:
    if urlparse(long_url).netloc == urlparse(base_url).netloc:
        raise HTTPException(422, "long_url: must not point at this service")

    if alias is not None:
        try:
            return storage.insert(alias, long_url, custom=True, expires_at=expires_at)
        except CodeTaken:
            raise HTTPException(409, "alias: already taken")

    for _ in range(GENERATE_ATTEMPTS):
        code = generate_code()
        if code in RESERVED:
            continue
        try:
            return storage.insert(code, long_url, custom=False, expires_at=expires_at)
        except CodeTaken:
            continue
    raise HTTPException(500, "could not generate a unique code, try again")


def get_link(storage: Storage, code: str) -> Link:
    link = storage.get(code)
    if link is None:
        raise HTTPException(404, "link not found")
    return link


def follow_link(storage: Storage, code: str) -> Link:
    """Record a hit and return the link to redirect to.

    410 for a link that exists but has expired: the client learns it is gone for
    good, which a 404 would not say.
    """
    link = storage.record_hit(code, now=utc_now())
    if link is not None:
        return link
    if storage.get(code) is not None:
        raise HTTPException(410, "link expired")
    raise HTTPException(404, "link not found")


def delete_link(storage: Storage, code: str) -> None:
    if not storage.delete(code):
        raise HTTPException(404, "link not found")
