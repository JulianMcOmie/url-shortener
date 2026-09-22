def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["storage"] in ("sqlite", "postgres")


def test_unknown_path_is_json_error(client):
    r = client.get("/v1/nope")
    assert r.status_code == 404
    assert r.json() == {"error": "Not Found"}
