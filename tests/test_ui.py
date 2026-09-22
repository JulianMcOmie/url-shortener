def test_root_serves_the_page(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "Shorten a link" in r.text
    assert 'fetch("/v1/links"' in r.text


def test_root_is_not_treated_as_a_code(client):
    """'/' must serve the page, never fall through to the redirect route."""
    assert client.get("/", follow_redirects=False).status_code == 200


def test_page_is_not_in_api_schema(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "/" not in paths
    assert "/v1/links" in paths


def test_page_can_list_and_delete_its_links(client):
    """The history section uses only existing API calls: metadata GET and DELETE."""
    page = client.get("/").text
    assert "Your links" in page
    assert 'method: "DELETE"' in page
