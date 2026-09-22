LONG = "https://example.com/some/path"


def create(client, **extra):
    r = client.post("/v1/links", json={"long_url": LONG, **extra})
    assert r.status_code == 201
    return r.json()["code"]


def test_delete_removes_link(client):
    code = create(client)
    r = client.delete(f"/v1/links/{code}")
    assert r.status_code == 204
    assert r.content == b""
    assert client.get(f"/{code}", follow_redirects=False).status_code == 404
    assert client.get(f"/v1/links/{code}").status_code == 404


def test_delete_unknown_is_404(client):
    r = client.delete("/v1/links/nope123")
    assert r.status_code == 404
    assert r.json() == {"error": "link not found"}


def test_delete_is_not_idempotent_on_second_call(client):
    code = create(client)
    assert client.delete(f"/v1/links/{code}").status_code == 204
    assert client.delete(f"/v1/links/{code}").status_code == 404


def test_deleted_alias_can_be_reused(client):
    create(client, alias="reuse-me")
    client.delete("/v1/links/reuse-me")
    r = client.post("/v1/links", json={"long_url": "https://other.example", "alias": "reuse-me"})
    assert r.status_code == 201
    assert client.get("/reuse-me", follow_redirects=False).headers["location"] == "https://other.example"
