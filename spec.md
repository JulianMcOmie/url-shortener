# URL Shortener Service

A REST service that accepts a long URL, returns a short code for it, redirects
anyone who visits the short code to the long URL, and reports metadata about
each link.

Python 3.11, FastAPI, pytest. Deployed to DigitalOcean App Platform from the Dockerfile.

## A link

    {
      "code": "k3Xp9Qa",                          // 7 chars, generated or user-chosen
      "long_url": "https://example.com/some/path",
      "short_url": "https://<host>/k3Xp9Qa",      // built from config, not stored
      "custom": false,                            // true if the user chose the code
      "hit_count": 4,
      "created_at": "2026-09-22T14:03:00Z"
    }

## Endpoints

| Method | Path              | Purpose                                  | Success | Errors |
|--------|-------------------|------------------------------------------|---------|--------|
| GET    | /healthz          | Platform health check                    | 200     |        |
| POST   | /v1/links         | Create a link; optional custom alias     | 201     | 422 invalid, 409 alias taken |
| GET    | /v1/links/{code}  | Metadata for one link                    | 200     | 404 unknown code |
| GET    | /{code}           | Redirect to the long URL, count the hit  | 307     | 404 unknown code |

Request body for POST: `{"long_url": "...", "alias": "optional"}`.

The API lives under `/v1` and redirects live at the root, so the two never collide.
The redirect route is registered last so it cannot swallow `/healthz` or `/v1/...`.

Later, if time: DELETE /v1/links/{code}, `expires_at` on create, list links.

## Validation rules

- `long_url`: required, string, at most 2048 chars. Must parse with scheme `http`
  or `https` and a non-empty host. Reject anything else with 422. Do not fetch
  the URL to check it exists: slow, and lets callers make the server hit
  arbitrary addresses.
- `long_url` whose host is this service's own host: 422. Prevents redirect loops.
- `alias` (optional): 3 to 32 chars, only `[A-Za-z0-9_-]`, case-sensitive,
  stored as given. Otherwise 422.
- `alias` on the reserved list (`healthz`, `v1`, `docs`, `redoc`, `openapi.json`): 422.
- `alias` already in use: 409. A clean conflict, not a validation failure.
- Same `long_url` submitted twice with no alias: mint a new code each time. Two
  callers shortening the same URL should not share a hit count.

Every error response is JSON: `{"error": "<plain message>"}`.

## Code generation

Random, 7 characters from base62 (`[A-Za-z0-9]`), using `secrets.choice`.
On insert conflict, generate again, up to 5 tries, then 500. 62^7 is about
3.5 trillion, so collisions are effectively never hit but the retry is cheap.

Why random over an encoded counter: simpler, no shared counter to coordinate
across instances, and codes do not reveal how many links exist.

## Redirect

307, not 301. A 301 is cached by browsers, so repeat visits never reach the
service and the hit count would be wrong, and the target could never be changed.
307 costs one extra round trip per visit, which is the price of having metadata.

Hit count is `UPDATE links SET hit_count = hit_count + 1` inside the redirect
handler. At scale that row update is the bottleneck; the production answer is
to emit an event and count asynchronously. Stated in README.

## Storage

SQLite from the start, using Python's built-in `sqlite3`, behind a small `Storage`
class in `app/storage.py`. One table, `links`, with `code` as primary key, which
makes alias uniqueness and collision detection fall out of the constraint.
Nothing outside that file knows how data is stored. Database path comes from config.

Why: persistence is real locally and across process restarts. Trade-off: App
Platform's disk is ephemeral, so the file does not survive a redeploy, and two
containers would not share it. Production answer is managed Postgres, which is
a swap inside storage.py. Stated in README.

## Config

Environment variables with defaults, read once in `app/config.py`:

    DATABASE_PATH   default ./links.db
    BASE_URL        default http://localhost:8080, used to build short_url
    PORT            default 8080

## Testing

pytest with FastAPI's `TestClient`, so tests call the real routes without a server.
Each test gets a fresh temporary database so tests never depend on each other.

Tests, in the order they get written:

1. `/healthz` returns 200.
2. Create with a valid URL returns 201, a 7-char code, and `custom: false`.
3. Redirect: create, then GET `/{code}` returns 307 with `Location` set to the long URL.
4. Metadata: after two redirects, GET `/v1/links/{code}` shows `hit_count: 2`.
5. Rejections, each asserting the status code and that the message names the field:
   missing `long_url`, `ftp://` scheme, no host, URL too long.
6. Custom alias: create with `alias` returns 201 with that code and `custom: true`.
7. Alias rejections: too short, bad characters, reserved word (all 422);
   already taken (409).
8. Unknown code returns 404 on both the redirect and the metadata endpoint.
9. Two creates of the same long URL get different codes.

What these prove: every endpoint's success path and every validation rule in this spec.
What they don't cover: concurrent writes, behaviour under load, the real deployed
database, or the Dockerfile. Those would be the next tests to add, in that order.

Tests run locally with `pytest -q` and in GitHub Actions on every push.

## File layout

    app/main.py        routes only, no logic
    app/models.py      Pydantic schemas and validators
    app/codes.py       code generation, alias rules, reserved list
    app/storage.py     Storage class (SQLite via sqlite3)
    app/config.py      settings from environment variables with defaults
    tests/             pytest, using FastAPI's TestClient
    .github/workflows/ci.yml
    .do/app.yaml       App Platform spec, so deploy is one doctl command
    Dockerfile, requirements.txt, README.md

## Architecture diagram

Mermaid in the README. Drawn first as a sketch of this spec, then corrected at
step 7 so it matches what was built. It shows two request flows, create and
redirect, through routes, validation, storage, and one delivery flow: push to
GitHub, Actions runs tests, App Platform rebuilds from the Dockerfile.

## Order of work

1. Sketch the diagram in README. Ten minutes, no more.
2. Skeleton: layout above, /healthz, Dockerfile, ci.yml, app.yaml. Run locally, push, deploy, green.
3. POST /v1/links with generated codes only, stored in SQLite.
4. GET /{code} redirect and GET /v1/links/{code} metadata, with hit counting.
5. Custom aliases: validation, reserved list, 409 on conflict.
6. Tests as listed in the Testing section.
7. README and final diagram.
8. Then, in order: request logging, DELETE, expires_at.

## Rules for the AI

- One step at a time. Stop after each step so I can read and run it.
- Do not add auth, an ORM, background workers, or anything not listed.
- Small dependencies only: fastapi, uvicorn, pydantic, pytest, httpx.
- README and diagram are deliverables, not extras. They come before step 8.
