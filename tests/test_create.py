import pytest

LONG = "https://example.com/some/path?q=1"


def test_create_returns_generated_code(client):
    r = client.post("/v1/links", json={"long_url": LONG})
    assert r.status_code == 201
    body = r.json()
    assert len(body["code"]) == 7
    assert body["code"].isalnum()
    assert body["long_url"] == LONG
    assert body["short_url"] == f"http://short.test/{body['code']}"
    assert body["custom"] is False
    assert body["hit_count"] == 0
    assert body["created_at"].endswith("Z")


def test_same_url_twice_gets_different_codes(client):
    a = client.post("/v1/links", json={"long_url": LONG}).json()["code"]
    b = client.post("/v1/links", json={"long_url": LONG}).json()["code"]
    assert a != b


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"long_url": "ftp://example.com/file"},
        {"long_url": "https://"},
        {"long_url": "not a url"},
        {"long_url": "https://example.com/" + "a" * 2048},
        {"long_url": "http://short.test/abc"},
    ],
)
def test_create_rejects_bad_urls(client, payload):
    r = client.post("/v1/links", json=payload)
    assert r.status_code == 422
    assert r.json()["error"].startswith("long_url")
