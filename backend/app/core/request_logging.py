"""
Phase 12 Part 6 + Phase 20: Request-level observability middleware.

Generates a unique request_id per request, attaches it to the response headers,
and logs request metadata in structured JSON format.

Phase 20 enhancements:
  • Full JSON log entries per request (Datadog / Logtail / CloudWatch compatible)
  • Structured fields: request_id, timestamp, method, path, user_id, org_id,
    status_code, duration_ms, environment
  • Debug-level logging disabled in production
  • JSONLogFormatter applied globally for production/staging environments
"""
import uuid
import time
import logging
import json
import os
from datetime import datetime, timezone
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("api.requests")

_ENVIRONMENT = os.getenv("ENVIRONMENT", "local").lower()
_IS_JSON_LOG = _ENVIRONMENT in ("production", "staging")


# ─── Phase 20: JSON structured formatter ──────────────────────────────────────

class JSONLogFormatter(logging.Formatter):
    """
    Produces one JSON object per log line — compatible with:
      • Datadog Log Pipeline
      • Logtail / Better Stack
      • AWS CloudWatch Logs Insights
      • GCP Cloud Logging
    """
    def format(self, record: logging.LogRecord) -> str:
        entry: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "environment": _ENVIRONMENT,
        }
        # Merge structured fields from extra dict
        for key in ("request_id", "user_id", "org_id", "method", "path",
                     "status_code", "duration_ms", "error"):
            val = getattr(record, key, None)
            if val is not None:
                entry[key] = val
        return json.dumps(entry, default=str)


# ─── Configure root logger at module load ─────────────────────────────────────

if _IS_JSON_LOG:
    _handler = logging.StreamHandler()
    _handler.setFormatter(JSONLogFormatter())
    logging.root.handlers.clear()
    logging.root.addHandler(_handler)
    logging.root.setLevel(logging.INFO)
else:
    logging.basicConfig(
        level=logging.DEBUG if _ENVIRONMENT == "development" else logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that:
    1. Generates a UUID request_id
    2. Sets X-Request-Id response header
    3. Logs structured request metadata with timing (JSON in prod/staging)
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        start = time.perf_counter()

        # Store on request state so endpoints can access it
        request.state.request_id = request_id

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            user_id = getattr(request.state, "user_id", None)
            org_id = getattr(request.state, "org_id", None)

            if _IS_JSON_LOG:
                logger.error(
                    "request failed",
                    extra={
                        "request_id": request_id,
                        "user_id": user_id,
                        "org_id": org_id,
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": 500,
                        "duration_ms": duration_ms,
                        "error": str(exc)[:200],
                    },
                )
            else:
                logger.error(
                    "request_id=%s user_id=%s org_id=%s method=%s path=%s status=500 duration_ms=%d error=%s",
                    request_id, user_id, org_id,
                    request.method, request.url.path,
                    duration_ms, str(exc)[:200],
                )
            raise

        duration_ms = int((time.perf_counter() - start) * 1000)

        # Attach request_id to response
        response.headers["X-Request-Id"] = request_id

        # Log at appropriate level
        level = logging.WARNING if response.status_code >= 400 else logging.INFO
        user_id = getattr(request.state, "user_id", None)
        org_id = getattr(request.state, "org_id", None)

        if _IS_JSON_LOG:
            logger.log(
                level,
                "request completed",
                extra={
                    "request_id": request_id,
                    "user_id": user_id,
                    "org_id": org_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
        else:
            logger.log(
                level,
                "request_id=%s user_id=%s org_id=%s method=%s path=%s status=%d duration_ms=%d",
                request_id, user_id, org_id,
                request.method, request.url.path,
                response.status_code, duration_ms,
            )

        return response
