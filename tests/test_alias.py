import pytest

LONG = "https://example.com/some/path"


def test_custom_alias_is_used(client):
    r = client.post("/v1/links", json={"long_url": LONG, "alias": "my-Link_1"})
    assert r.status_code == 201
    body = r.json()
    assert body["code"] == "my-Link_1"
    assert body["custom"] is True
    assert body["short_url"] == "http://short.test/my-Link_1"

    r = client.get("/my-Link_1", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == LONG


def test_alias_is_case_sensitive(client):
    assert client.post("/v1/links", json={"long_url": LONG, "alias": "Docs"}).status_code == 201
    assert client.get("/docs", follow_redirects=False).status_code != 307


def test_alias_taken_is_409(client):
    assert client.post("/v1/links", json={"long_url": LONG, "alias": "taken"}).status_code == 201
    r = client.post("/v1/links", json={"long_url": "https://other.example", "alias": "taken"})
    assert r.status_code == 409
    assert r.json()["error"].startswith("alias")


@pytest.mark.parametrize(
    "alias",
    ["ab", "a" * 33, "has space", "has/slash", "émoji", "healthz", "v1", "openapi.json"],
)
def test_alias_rejected(client, alias):
    r = client.post("/v1/links", json={"long_url": LONG, "alias": alias})
    assert r.status_code == 422
    assert r.json()["error"].startswith("alias")


def test_alias_null_means_generated(client):
    r = client.post("/v1/links", json={"long_url": LONG, "alias": None})
    assert r.status_code == 201
    assert r.json()["custom"] is False
