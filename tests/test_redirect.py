LONG = "https://example.com/some/path?q=1"


def create(client, **extra):
    r = client.post("/v1/links", json={"long_url": LONG, **extra})
    assert r.status_code == 201
    return r.json()["code"]


def test_redirect_to_long_url(client):
    code = create(client)
    r = client.get(f"/{code}", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == LONG


def test_metadata_counts_hits(client):
    code = create(client)
    client.get(f"/{code}", follow_redirects=False)
    client.get(f"/{code}", follow_redirects=False)
    r = client.get(f"/v1/links/{code}")
    assert r.status_code == 200
    body = r.json()
    assert body["hit_count"] == 2
    assert body["code"] == code
    assert body["long_url"] == LONG


def test_metadata_does_not_count_as_hit(client):
    code = create(client)
    client.get(f"/v1/links/{code}")
    assert client.get(f"/v1/links/{code}").json()["hit_count"] == 0


def test_unknown_code_404_on_both(client):
    for path in ("/nope123", "/v1/links/nope123"):
        r = client.get(path, follow_redirects=False)
        assert r.status_code == 404
        assert r.json() == {"error": "link not found"}


def test_redirect_does_not_shadow_healthz(client):
    assert client.get("/healthz").json() == {"status": "ok"}
