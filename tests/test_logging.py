import json
import logging

from app.observability import JsonFormatter


def test_request_is_logged_with_fields(client, caplog):
    with caplog.at_level(logging.INFO, logger="app.request"):
        client.post("/v1/links", json={"long_url": "https://example.com"})
    records = [r for r in caplog.records if r.name == "app.request"]
    assert len(records) == 1
    fields = records[0].fields
    assert fields["method"] == "POST"
    assert fields["path"] == "/v1/links"
    assert fields["status"] == 201
    assert fields["duration_ms"] >= 0


def test_healthz_is_logged_at_debug_only(client, caplog):
    with caplog.at_level(logging.INFO, logger="app.request"):
        client.get("/healthz")
    assert not [r for r in caplog.records if r.name == "app.request"]


def test_formatter_emits_one_json_line(client, caplog):
    with caplog.at_level(logging.INFO, logger="app.request"):
        client.get("/v1/links/missing")
    record = [r for r in caplog.records if r.name == "app.request"][0]
    line = JsonFormatter().format(record)
    parsed = json.loads(line)
    assert parsed["status"] == 404
    assert parsed["path"] == "/v1/links/missing"
    assert "\n" not in line


def test_log_time_is_utc(client, caplog):
    with caplog.at_level(logging.INFO, logger="app.request"):
        client.get("/v1/links/missing")
    record = [r for r in caplog.records if r.name == "app.request"][0]
    assert json.loads(JsonFormatter().format(record))["time"].endswith("Z")
