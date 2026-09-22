"""Short code generation and custom alias rules."""

import re
import secrets
import string

ALPHABET = string.ascii_letters + string.digits  # base62
CODE_LENGTH = 7

ALIAS_MIN = 3
ALIAS_MAX = 32
ALIAS_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")

# Paths the service itself owns. An alias here would be unreachable or confusing.
RESERVED = frozenset({"healthz", "v1", "docs", "redoc", "openapi.json"})


def generate_code() -> str:
    """A random base62 code. 62^7 possibilities, so collisions are rare but handled by the caller."""
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))


def validate_alias(alias: str) -> str:
    """Return the alias if acceptable, else raise ValueError with a message naming the problem."""
    if not ALIAS_MIN <= len(alias) <= ALIAS_MAX:
        raise ValueError(f"must be {ALIAS_MIN} to {ALIAS_MAX} characters")
    if not ALIAS_PATTERN.match(alias):
        raise ValueError("may only contain letters, digits, hyphen and underscore")
    if alias in RESERVED:
        raise ValueError("is reserved")
    return alias
