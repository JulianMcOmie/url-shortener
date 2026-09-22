# Walkthrough talking points

45 minutes. Anchor on the two README diagrams. Lead with the outcome, then the why.

Live: https://url-shortener-pta8k.ondigitalocean.app/healthz
Repo: https://github.com/JulianMcOmie/url-shortener

---

## 1. Opening (2 min)

- "It's a URL shortener: create a short code, redirect on it, read metadata, delete, optional custom alias and expiry. There's a one-page UI at the root for the demo."
- "It's live on App Platform, running two containers against managed Postgres. 43 tests run in CI on every push, against both SQLite and Postgres."
- "I started from a written spec, deployed a health check first, then built one feature at a time. Every commit is one step in that plan."
- Show `spec.md` for five seconds: the plan existed before the code.

## 2. The request diagram (8 min)

Walk the create path top to bottom, then the redirect path.

- **Routes (`app/main.py`)** hold no logic. Each one is three lines. Two exception handlers give every error the same shape: `{"error": "field: message"}`.
- **Validation (`app/models.py`, `app/codes.py`)** runs before the route is called. URL must be http/https with a host and under 2048 chars. Alias is 3 to 32 chars, restricted charset, case-sensitive, with a reserved list so nobody claims `healthz`.
- **Link logic (`app/links.py`)** is the only layer that decides status codes: 422 self-referencing URL, 409 alias taken, 404 unknown, 410 expired.
- **Storage** is one interface with two implementations. Nothing above it knows which is running.
- Redirect path: one SQL statement checks expiry, increments the count, and returns the row. Atomic, so concurrent clicks never lose a count. Expired links are never counted.

## 3. The decisions and why (10 min)

Say each as "I chose X over Y because Z."

- **307 over 301.** 301 is cached by browsers, so repeat visits never reach us and hit counts would be wrong. 307 costs one round trip per click, which is the price of having metadata.
- **Random base62 codes over an encoded counter.** 62^7 is 3.5 trillion. No shared counter to coordinate across containers, and codes do not reveal volume. Collisions are handled by retrying the insert; the primary key does the detection.
- **Same URL twice gets two codes.** Two customers shortening the same page should not share analytics. Custom aliases already break one-to-one anyway.
- **410 for expired, 404 for unknown.** A client following an expired link learns it existed and is gone, which is actionable.
- **Errors name the field.** "long_url: must start with http:// or https://" is something a person can fix. A bare 422 is not.
- **Never fetch the target URL to validate it.** Slow, and it lets callers make our server request arbitrary addresses (SSRF).
- **Settings read at startup, not import.** That one choice is why every test can get its own database and why the same code runs locally on SQLite and in production on Postgres.
- **Health check reports the backend.** Cheap, and it is how we confirmed the Postgres cutover from outside.
- **The UI is just another client of the API.** One HTML file served at `/`, calling `POST /v1/links` like curl would. No special routes. That is what an API-first design is for. Open it live: paste a link, shorten it, copy it.

## 4. The story of the day (5 min)

This is the strongest five minutes. It is real and it shows the README was honest before it was tested.

1. First deploy was SQLite. README said: ephemeral disk, one file per container, will not work for more than one container.
2. The console-created app ran two containers. Probe: about half of all redirects returned 404. Exactly the predicted failure.
3. Dropped to one container to stabilise, then added the Postgres backend behind the same interface. Only the storage layer changed. Tests unchanged. CI gained a job that runs them all against a real Postgres.
4. Hit a DigitalOcean gotcha: the dev database's permission grant runs during the deployment that attaches it, and a push superseded that deployment. Documented cause and fix in the README so nobody hits it twice.
5. Same probe, two containers, Postgres: 12 of 12 redirects, all reads agree, data survives redeploys.

"The platform's rollback caught every failed deploy. Users never saw an outage."

## 5. What I skipped and would do next (5 min)

In README order. Say why each is next, not just that it is.

1. **Custom domain.** Short links are `BASE_URL` plus code. Today the base is the long App Platform hostname. One setting fixes it.
2. **Auth on create and delete.** Anyone can delete any link. Smallest fix: return a per-link secret at creation, require it on delete. Then accounts and API keys.
3. **Rate limiting on create.** The only unauthenticated write.
4. **Metrics.** Request counts and latency histograms for alerting. Logs are there; metrics are the next layer.
5. **Async hit counting** at real scale. The synchronous row update becomes the write bottleneck. Emit an event, aggregate elsewhere.

## 6. Scaling, if asked (3 min)

- Reads: redirect is one indexed lookup by primary key. Add containers; the pool handles it. Then a cache in front of the lookup, since links rarely change.
- Writes: creates are rare. Hits are the write load. Move counting off the request path (queue, then batch update or a counter store).
- Database: dev tier to production cluster is a `DATABASE_URL` change. Backups, standby, more connections come with it.
- Codes: 7 chars is 3.5 trillion. Bump to 8 long before it matters; nothing else changes.

## 7. Testing, if asked (3 min)

- 43 tests through FastAPI's TestClient against the real routes. Each test gets an empty database.
- They cover every endpoint's success path and every validation rule. Alias and URL rejections are parametrized, one case per rule.
- Same suite runs on Postgres in CI via a service container, so both backends are proven.
- Not covered, in the order I'd add them: concurrent writes, load, the Dockerfile beyond building.
- The expiry test advances the clock by monkeypatching one function instead of sleeping.

## 8. Observability, if asked (2 min)

- One JSON line per request: method, path, status, latency, UTC time. Health checks at DEBUG so they don't drown traffic.
- Redirect path carries the code, so per-link traffic is derivable from logs alone.
- Unhandled exceptions are logged with traceback as 500 before re-raising.
- Show Runtime Logs in the console if there is time.

## 9. Questions to expect

- **Why Python?** Team preference in the brief, Pydantic gives validation for free, and I had a tested spec pattern for FastAPI.
- **Why not an ORM?** Five SQL statements. An ORM would be more code than the storage layer it replaced.
- **What if two people create the same alias at once?** Both insert; the primary key rejects the second; that one gets 409. No check-then-insert race.
- **Why is delete not idempotent?** Second delete returns 404 because the resource is gone. Defensible either way; I chose to report the truth.
- **Case sensitivity on aliases?** Case-sensitive, stored as given. Simpler, and `Docs` cannot hijack `/docs`. There is a test for that.
- **Where would auth go?** A dependency on the two management routes. Redirect stays public by nature.
- **How did AI tools factor in?** Used for generation against a spec I wrote first; I reviewed every commit against the requirement docs and verified each step live. The spec, the checkpoints, and the rollback story are the evidence.

## Numbers, if useful

| | |
|---|---|
| Endpoints | 5, plus the UI page |
| Tests | 46, on 2 backends |
| Commits | 18, one step each |
| Code size | 8 app files plus one HTML page, about 500 lines of Python |
| Deploys today | ~15, 3 failed, 0 outages |
