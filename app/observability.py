"""Request logging. One JSON line per request on stdout."""

import json
import logging
import sys
import time

from fastapi import Request

log = logging.getLogger("app.request")


class JsonFormatter(logging.Formatter):
    converter = time.gmtime  # UTC, same as created_at

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(getattr(record, "fields", {}))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(level: str) -> None:
    """Send every log record to stdout as one JSON line. App Platform collects stdout."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())


async def log_requests(request: Request, call_next):
    """Log method, path, status and time taken for every request.

    Health checks go to DEBUG so they do not drown out real traffic.
    """
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        log.exception("request failed", extra={"fields": _fields(request, 500, start)})
        raise
    level = logging.DEBUG if request.url.path == "/healthz" else logging.INFO
    log.log(level, "request", extra={"fields": _fields(request, response.status_code, start)})
    return response


def _fields(request: Request, status: int, start: float) -> dict:
    return {
        "method": request.method,
        "path": request.url.path,
        "status": status,
        "duration_ms": round((time.perf_counter() - start) * 1000, 1),
    }
