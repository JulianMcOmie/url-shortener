"""Unit tests for the pure functions. No app, no database, no HTTP."""

import json
import logging
from datetime import datetime, timedelta, timezone

import pytest

from app.codes import ALIAS_MAX, ALIAS_MIN, ALPHABET, CODE_LENGTH, generate_code, validate_alias
from app.observability import JsonFormatter
from app.storage import format_utc, utc_now


def test_generate_code_shape():
    for _ in range(200):
        code = generate_code()
        assert len(code) == CODE_LENGTH
        assert all(ch in ALPHABET for ch in code)


def test_generate_code_varies():
    assert len({generate_code() for _ in range(50)}) > 45


def test_validate_alias_accepts_boundaries():
    assert validate_alias("a" * ALIAS_MIN) == "a" * ALIAS_MIN
    assert validate_alias("a" * ALIAS_MAX) == "a" * ALIAS_MAX
    assert validate_alias("Mixed_Case-1") == "Mixed_Case-1"


@pytest.mark.parametrize(
    "alias, message",
    [
        ("ab", "must be 3 to 32 characters"),
        ("a" * 33, "must be 3 to 32 characters"),
        ("has space", "may only contain"),
        ("dot.com", "may only contain"),
        ("healthz", "is reserved"),
        ("openapi.json", "may only contain"),  # fails the charset rule before the reserved check
    ],
)
def test_validate_alias_rejects(alias, message):
    with pytest.raises(ValueError, match=message):
        validate_alias(alias)


def test_format_utc_normalises_offsets():
    plus_five = datetime(2030, 1, 1, 5, 0, 0, tzinfo=timezone(timedelta(hours=5)))
    assert format_utc(plus_five) == "2030-01-01T00:00:00Z"


def test_format_utc_drops_microseconds():
    dt = datetime(2030, 1, 1, 0, 0, 0, 123456, tzinfo=timezone.utc)
    assert format_utc(dt) == "2030-01-01T00:00:00Z"


def test_utc_now_is_in_the_stored_format():
    now = utc_now()
    assert len(now) == 20 and now.endswith("Z")
    datetime.strptime(now, "%Y-%m-%dT%H:%M:%SZ")


def test_timestamps_compare_as_text():
    earlier = format_utc(datetime(2030, 1, 1, tzinfo=timezone.utc))
    later = format_utc(datetime(2030, 1, 2, tzinfo=timezone.utc))
    assert earlier < later


def test_json_formatter_puts_fields_at_top_level():
    record = logging.LogRecord("app.request", logging.INFO, __file__, 1, "request", None, None)
    record.fields = {"method": "GET", "path": "/abc", "status": 307, "duration_ms": 1.2}
    line = JsonFormatter().format(record)
    parsed = json.loads(line)
    assert parsed["message"] == "request"
    assert parsed["method"] == "GET"
    assert parsed["status"] == 307
    assert parsed["time"].endswith("Z")
    assert "\n" not in line
