# URL Shortener

A REST service that accepts a long URL, returns a short code, redirects visitors
of the short code to the long URL, and reports metadata about each link.

Python 3.12, FastAPI, SQLite. Deployed to DigitalOcean App Platform from the Dockerfile.

## Architecture

```mermaid
flowchart LR
    subgraph clients [Clients]
        C[API client]
        V[Visitor]
    end

    subgraph service [FastAPI service]
        R[Routes<br/>app/main.py]
        M[Validation<br/>app/models.py]
        G[Code generation<br/>app/codes.py]
        S[Storage<br/>app/storage.py]
    end

    DB[(SQLite<br/>links table)]

    C -- "POST /v1/links" --> R
    C -- "GET /v1/links/{code}" --> R
    V -- "GET /{code}" --> R
    R --> M --> G --> S --> DB
    R -- "307 Location: long_url" --> V
```

```mermaid
flowchart LR
    Dev[git push] --> GH[GitHub]
    GH --> CI[GitHub Actions<br/>pytest + docker build]
    GH --> AP[App Platform<br/>builds Dockerfile, deploys]
    AP -- "/healthz" --> Live[Live service]
```

## Run locally

    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    uvicorn app.main:app --reload --port 8080

## Test

    pytest -q

## Deploy

    doctl apps create --spec .do/app.yaml
