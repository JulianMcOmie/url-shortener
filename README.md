# URL Shortener

A REST service that accepts a long URL, returns a short code, redirects visitors
of the short code to the long URL, and reports metadata about each link.

Python 3.12, FastAPI, Postgres in production and SQLite for local runs and tests.
Deployed to DigitalOcean App Platform from the Dockerfile.

Live: https://url-shortener-pta8k.ondigitalocean.app/healthz

## API

| Method | Path              | Purpose                                  | Success | Errors |
|--------|-------------------|------------------------------------------|---------|--------|
| GET    | /                 | One-page UI for creating links           | 200     |        |
| GET    | /healthz          | Health check; reports storage backend    | 200     |        |
| POST   | /v1/links         | Create a link; optional custom alias     | 201     | 422 invalid, 409 alias taken |
| GET    | /v1/links/{code}  | Metadata for one link                    | 200     | 404 unknown code |
| DELETE | /v1/links/{code}  | Retire a link; its code becomes free     | 204     | 404 unknown code |
| GET    | /{code}           | Redirect to the long URL, count the hit  | 307     | 404 unknown code, 410 expired |

The root serves a single-page UI (`app/index.html`) that is a plain client of the API
below. Interactive API docs are served at `/docs`.

Every error is JSON with one message that names the offending field:

    {"error": "long_url: must start with http:// or https://"}

### Create a link

    curl -X POST https://url-shortener-pta8k.ondigitalocean.app/v1/links \
      -H 'content-type: application/json' \
      -d '{"long_url": "https://www.digitalocean.com/products/app-platform"}'

    {
      "code": "mHlophd",
      "long_url": "https://www.digitalocean.com/products/app-platform",
      "short_url": "https://url-shortener-pta8k.ondigitalocean.app/mHlophd",
      "custom": false,
      "hit_count": 0,
      "created_at": "2026-09-22T19:19:59Z",
      "expires_at": null
    }

Optional fields in the body:

- `"alias": "launch"` to choose the code yourself.
- `"expires_at": "2026-12-31T23:59:59Z"` to make the link stop working after that time.
  Any ISO 8601 timestamp; an offset is honoured and a naive value is taken as UTC.

### Follow a link

    curl -i https://url-shortener-pta8k.ondigitalocean.app/mHlophd

    HTTP/1.1 307 Temporary Redirect
    location: https://www.digitalocean.com/products/app-platform

### Delete a link

    curl -X DELETE https://url-shortener-pta8k.ondigitalocean.app/v1/links/mHlophd

Returns 204. The short link stops redirecting immediately and the code can be
claimed again as a custom alias.

### Read metadata

    curl https://url-shortener-pta8k.ondigitalocean.app/v1/links/mHlophd

Same shape as the create response, with `hit_count` reflecting redirects served.

## Validation rules

- `long_url`: required, at most 2048 characters, scheme `http` or `https`, non-empty host.
  Not fetched to check it resolves: that is slow and would let callers make the
  server request arbitrary addresses.
- `long_url` pointing at this service's own host is rejected, to prevent redirect loops.
- `alias`: optional, 3 to 32 characters from `[A-Za-z0-9_-]`, case-sensitive, stored as given.
  Reserved words (`healthz`, `v1`, `docs`, `redoc`, `openapi.json`) are rejected.
- Alias already in use returns 409, a conflict rather than a validation failure.
- `expires_at`: optional, must parse as ISO 8601 and be in the future. An expired
  link answers 410 Gone on redirect and does not count a hit; its metadata stays
  readable so the owner can see when it lapsed.
- The same `long_url` submitted twice without an alias gets two different codes,
  so two callers never share a hit count.

## Architecture

### Request lifecycle

```mermaid
flowchart LR
    subgraph clients [Clients]
        C[API client]
        V[Visitor]
    end

    subgraph service [FastAPI service, each container]
        R["Routes<br/>app/main.py"]
        M["Validation<br/>app/models.py + app/codes.py"]
        L["Link logic<br/>app/links.py"]
        S["Storage<br/>app/storage.py (SQLite)<br/>app/storage_postgres.py"]
    end

    DB[("Managed Postgres<br/>links table<br/>code PRIMARY KEY")]

    C -- "POST /v1/links" --> R
    C -- "GET /v1/links/{code}" --> R
    C -- "DELETE /v1/links/{code}" --> R
    V -- "GET /{code}" --> R
    R -- "422 on bad input" --> M
    M --> L
    L -- "insert / get / record_hit / delete" --> S
    S --> DB
    L -- "409 alias taken<br/>404 unknown<br/>410 expired" --> R
    R -- "307 Location: long_url" --> V
```

Create: the body is validated by Pydantic (shape, URL rules, alias rules). The link
layer refuses self-referencing URLs, then either inserts the custom alias or generates
random codes until one inserts cleanly. The primary key on `code` is what makes both
alias uniqueness and collision detection reliable.

Redirect: one `UPDATE ... RETURNING` both increments the hit count and fetches the
target, so a redirect is a single write. Unknown codes are 404 and expired ones 410,
in the same JSON shape as every other error.

### Delivery

```mermaid
flowchart LR
    Dev[git push main] --> GH[GitHub]
    GH --> CI["GitHub Actions<br/>pytest on SQLite<br/>pytest on Postgres<br/>docker build"]
    GH -- "deploy_on_push" --> AP["App Platform<br/>builds Dockerfile"]
    AP -- "GET /healthz" --> Live[Live containers]
    Live --> PG[(Managed Postgres)]
```

CI and deploy run in parallel from the same push. App Platform only routes traffic to
a new container once `/healthz` answers.

## Design decisions

**307, not 301.** A 301 is cached by browsers, so repeat visits would never reach the
service and the hit count would be wrong. 307 costs one extra round trip per visit,
which is the price of having metadata.

**Random codes, not an encoded counter.** 7 characters of base62 gives about 3.5 trillion
codes. Random needs no shared counter across instances and does not reveal how many
links exist. Collisions are handled by retrying the insert, up to five times.

**Storage behind one interface, two backends.** Nothing outside the two storage
modules knows how links are stored. `DATABASE_URL` unset means SQLite in a local file:
zero setup for development, and each test gets a fresh file. `DATABASE_URL` set means
managed Postgres through a small connection pool, which is what the deployed app uses.
CI runs the full test suite against both.

Why Postgres in production: App Platform's disk is ephemeral and per container. The
first deploy ran two containers on SQLite and about half of all redirects returned 404,
because each container had its own file. A shared database is the fix, and it also
means links survive redeploys. Hit counting is still a synchronous row update; at much
larger scale that becomes the write bottleneck and would move to an event stream with
async aggregation.

**410 for expired, 404 for unknown.** A client following an expired link learns it
existed and is gone for good, which a 404 would not say. The hit-count update and the
expiry check are one SQL statement, so an expired link is never counted.

**Routes hold no logic.** `app/main.py` maps HTTP to calls in `app/links.py`. Validation
is in the schemas, storage is in storage. Each layer can be tested and swapped alone.

## Run locally

    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    uvicorn app.main:app --reload --port 8080

Then open http://localhost:8080/docs.

## Test

    pytest -q

46 tests, run with FastAPI's `TestClient` against the real routes. Each test gets an
empty database, so tests never depend on each other. They cover every endpoint's
success path and every validation rule above.

The same suite runs against Postgres when `TEST_DATABASE_URL` is set. CI does this
with a Postgres service container, so both backends are proven on every push. Locally:

    docker run -d --name pg -e POSTGRES_PASSWORD=test -e POSTGRES_DB=links -p 55432:5432 postgres:16-alpine
    TEST_DATABASE_URL=postgresql://postgres:test@localhost:55432/links pytest -q

Not covered: concurrent writes, behaviour under load, and the Dockerfile beyond CI
checking that it builds. Those would be the next tests to add, in that order.

## Observability

Every request is logged as one JSON line on stdout, which App Platform collects
and shows under Runtime Logs:

    {"time": "2026-09-22T19:40:12Z", "level": "INFO", "logger": "app.request", "message": "request",
     "method": "GET", "path": "/mHlophd", "status": 307, "duration_ms": 1.4}

Health checks are logged at `DEBUG` so they do not drown out real traffic. Unhandled
exceptions are logged with a traceback and status 500. The redirect path carries the
short code, so per-link traffic can be derived from the logs without extra tables.

## Configuration

| Variable        | Default                  | Purpose                                  |
|-----------------|--------------------------|------------------------------------------|
| `DATABASE_URL`  | unset                    | Postgres connection string; unset means SQLite |
| `DATABASE_PATH` | `./links.db`             | SQLite file location, used when `DATABASE_URL` is unset |
| `BASE_URL`      | `http://localhost:8080`  | Used to build `short_url` in responses   |
| `LOG_LEVEL`     | `INFO`                   | `DEBUG` also logs health checks          |

## Deploy

The app spec is in `.do/app.yaml`. It declares the web service and a dev Postgres
database, binds `BASE_URL` to App Platform's `${APP_URL}` and `DATABASE_URL` to the
database's connection string, and sets the health check to `/healthz`.

    doctl apps create --spec .do/app.yaml

After that, every push to `main` redeploys. Without a database attached, the app
falls back to SQLite on the container's ephemeral disk, which is fine for a single
container but not for more.

The attached database is App Platform's dev tier, a cost choice for this exercise.
Moving to a production managed cluster (backups, standby, more connections) is a
change to `DATABASE_URL` only; the code path is the same one CI tests.

One operational note: App Platform grants the dev database user its schema
permissions during the deployment that attaches it. If that deployment is
superseded by a push before it finishes, the grant never happens and the app fails
at startup with `permission denied for schema public`. The fix is to delete and
re-create the database and let that deployment complete uninterrupted.

## Layout

    app/main.py        routes only
    app/index.html     the one-page UI, served at /
    app/models.py      request and response schemas, URL validation
    app/codes.py       code generation, alias rules, reserved list
    app/links.py       create, get, follow, delete; the only caller of storage
    app/storage.py     SQLite backend, shared types, and the backend factory
    app/storage_postgres.py  Postgres backend, same interface, connection pool
    app/config.py      settings from environment variables
    app/observability.py  JSON log formatter and request logging middleware
    tests/             pytest, one file per feature
    .github/workflows/ci.yml
    .do/app.yaml
    Dockerfile, requirements.txt
    documents/         overview.html, a visual walkthrough of the code
    spec.md            the plan this was built from

## Next steps

In the order I would do them:

1. A short custom domain. Every short link is `BASE_URL` plus the code, and today
   `BASE_URL` is the long App Platform hostname. Pointing a domain such as
   `hkg.to` at the app and setting `BASE_URL` to it makes the links short with
   no code change.
2. Auth on create and delete, then a list endpoint. Anyone can delete any link
   today, and a "my links" endpoint cannot exist until there is a "me": without
   ownership it would list everyone's destinations. Smallest fix is a per-link
   secret returned at creation; the real fix is API keys, which then make
   listing safe. The UI's per-browser history is the stand-in until then.
3. Rate limiting on create, since it is the only unauthenticated write.
4. Metrics endpoint (request counts and latency histograms) for alerting.
