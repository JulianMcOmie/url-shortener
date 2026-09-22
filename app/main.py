"""HTTP routes. No business logic lives here."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.exceptions import HTTPException

from app import links
from app.config import load_settings
from app.models import CreateLinkRequest, LinkResponse
from app.observability import configure_logging, log_requests
from app.storage import open_storage


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    configure_logging(settings.log_level)
    app.state.settings = settings
    app.state.storage = open_storage(settings.database_url, settings.database_path)
    yield
    app.state.storage.close()


app = FastAPI(title="URL Shortener", version="0.1.0", lifespan=lifespan)

INDEX_HTML = (Path(__file__).parent / "index.html").read_text()
app.middleware("http")(log_requests)


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    """Collapse Pydantic's error list into one message that names the field."""
    first = exc.errors()[0]
    field = ".".join(str(p) for p in first["loc"] if p != "body") or "body"
    msg = first["msg"].removeprefix("Value error, ")
    return JSONResponse(status_code=422, content={"error": f"{field}: {msg}"})


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index() -> HTMLResponse:
    """The one-page UI. It is a plain client of the API below; no special routes."""
    return HTMLResponse(INDEX_HTML)


@app.get("/healthz")
def healthz(request: Request) -> dict:
    """Liveness plus which storage backend this container is using."""
    return {"status": "ok", "storage": request.app.state.storage.name}


@app.post("/v1/links", status_code=201, response_model=LinkResponse)
def create_link(body: CreateLinkRequest, request: Request) -> LinkResponse:
    state = request.app.state
    link = links.create_link(
        state.storage, state.settings.base_url, body.long_url, body.alias, body.expires_at_utc()
    )
    return links.to_response(link, state.settings.base_url)


@app.get("/v1/links/{code}", response_model=LinkResponse)
def get_link(code: str, request: Request) -> LinkResponse:
    state = request.app.state
    return links.to_response(links.get_link(state.storage, code), state.settings.base_url)


@app.delete("/v1/links/{code}", status_code=204)
def delete_link(code: str, request: Request) -> Response:
    links.delete_link(request.app.state.storage, code)
    return Response(status_code=204)


# Registered last so it never shadows /healthz or /v1/... paths.
@app.get("/{code}", status_code=307, response_class=RedirectResponse)
def redirect(code: str, request: Request) -> RedirectResponse:
    link = links.follow_link(request.app.state.storage, code)
    return RedirectResponse(link.long_url, status_code=307)
