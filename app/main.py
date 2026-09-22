"""HTTP routes. No business logic lives here."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.config import load_settings

settings = load_settings()

app = FastAPI(title="URL Shortener", version="0.1.0")


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    """Collapse Pydantic's error list into one message that names the field."""
    first = exc.errors()[0]
    field = ".".join(str(p) for p in first["loc"] if p != "body") or "body"
    return JSONResponse(status_code=422, content={"error": f"{field}: {first['msg']}"})


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}
