"""Short code generation and custom alias rules."""

import re
import secrets
import string

ALPHABET = string.ascii_letters + string.digits  # 62 characters
CODE_LENGTH = 7

ALIAS_MIN = 3
ALIAS_MAX = 32
ALIAS_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")

# Paths the service uses itself. An alias with one of these names could never be reached.
RESERVED = frozenset({"healthz", "v1", "docs", "redoc", "openapi.json"})


def generate_code() -> str:
    """A random 7-character code. 62^7 possibilities, so a clash is rare; the caller retries if one happens."""
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))


def validate_alias(alias: str) -> str:
    """Return the alias if it is acceptable. Otherwise raise ValueError saying what is wrong."""
    if not ALIAS_MIN <= len(alias) <= ALIAS_MAX:
        raise ValueError(f"must be {ALIAS_MIN} to {ALIAS_MAX} characters")
    if not ALIAS_PATTERN.match(alias):
        raise ValueError("may only contain letters, digits, hyphen and underscore")
    if alias in RESERVED:
        raise ValueError("is reserved")
    return alias
