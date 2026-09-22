"""Short code generation."""

import secrets
import string

ALPHABET = string.ascii_letters + string.digits  # base62
CODE_LENGTH = 7


def generate_code() -> str:
    """A random base62 code. 62^7 possibilities, so collisions are rare but handled by the caller."""
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))
