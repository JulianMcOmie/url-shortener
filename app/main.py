"""HTTP routes. No business logic lives here."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app import links
from app.config import load_settings
from app.models import CreateLinkRequest, LinkResponse
from app.storage import Storage


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    app.state.settings = settings
    app.state.storage = Storage(settings.database_path)
    yield
    app.state.storage.close()


app = FastAPI(title="URL Shortener", version="0.1.0", lifespan=lifespan)


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


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.post("/v1/links", status_code=201, response_model=LinkResponse)
def create_link(body: CreateLinkRequest, request: Request) -> LinkResponse:
    state = request.app.state
    link = links.create_link(state.storage, state.settings.base_url, body.long_url)
    return links.to_response(link, state.settings.base_url)
