"""
Phase 12 Part 2: Structured error handling for the API.
All errors return JSON: { "error": "machine_code", "message": "human message", "details": optional }

- No stack traces leak to clients in any environment.
- Stack traces are logged server-side only in development / local.
- ValidationError (Pydantic) is caught and mapped to 422.
"""
import logging
import traceback
import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger("api.errors")

_ENVIRONMENT = os.getenv("ENVIRONMENT", "local").lower()
_IS_PRODUCTION = _ENVIRONMENT in ("production", "staging")


class APIError(Exception):
    """Raise from any endpoint for a structured JSON error."""

    def __init__(self, status_code: int = 500, error: str = "internal_error", message: str = "Internal Server Error", details: str | None = None):
        self.status_code = status_code
        self.error = error
        self.message = message
        self.details = details


def _status_to_error(status_code: int) -> str:
    mapping = {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        405: "method_not_allowed",
        409: "conflict",
        422: "unprocessable_entity",
        429: "rate_limited",
        500: "internal_error",
        503: "service_unavailable",
    }
    return mapping.get(status_code, "error")


def _build_body(error: str, message: str, details: str | None = None, request_id: str | None = None) -> dict:
    body: dict = {"error": error, "message": message}
    if details:
        body["details"] = details
    # Phase 20: Always include request_id for traceability
    if request_id:
        body["request_id"] = request_id
    return body


def _headers_with_request_id(request: Request) -> dict:
    request_id = getattr(getattr(request, "state", None), "request_id", None)
    return {"X-Request-Id": request_id} if request_id else {}


def _get_request_id(request: Request) -> str | None:
    return getattr(getattr(request, "state", None), "request_id", None)


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    logger.warning("APIError %d: %s | %s", exc.status_code, exc.message, exc.details)
    rid = _get_request_id(request)
    return JSONResponse(
        status_code=exc.status_code,
        content=_build_body(exc.error, exc.message, exc.details, request_id=rid),
        headers=_headers_with_request_id(request),
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    message = ""
    details_val = None
    if isinstance(exc.detail, dict):
        message = exc.detail.get("message") or exc.detail.get("detail") or ""
        details_val = exc.detail.get("details")
        error = exc.detail.get("error") or _status_to_error(exc.status_code)
    else:
        message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        error = _status_to_error(exc.status_code)

    logger.warning("HTTPException %d: %s", exc.status_code, message)
    rid = _get_request_id(request)
    return JSONResponse(
        status_code=exc.status_code,
        content=_build_body(error, message or error, details_val, request_id=rid),
        headers=_headers_with_request_id(request),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    tb = traceback.format_exc()
    if _IS_PRODUCTION:
        logger.error("Unhandled %s on %s %s (details suppressed in production)", type(exc).__name__, request.method, request.url.path)
    else:
        logger.error("Unhandled %s on %s %s\n%s", type(exc).__name__, request.method, request.url.path, tb)
    error = _status_to_error(500)
    rid = _get_request_id(request)
    return JSONResponse(
        status_code=500,
        content=_build_body(error, "Internal Server Error", request_id=rid),
        headers=_headers_with_request_id(request),
    )


def register_error_handlers(app: FastAPI) -> None:
    """Call once at startup to install all structured error handlers."""
    from pydantic import ValidationError

    async def type_error_handler(request: Request, exc: TypeError) -> JSONResponse:
        tb = traceback.format_exc()
        if _IS_PRODUCTION:
            logger.error("TypeError on %s %s (details suppressed in production)", request.method, request.url.path)
        else:
            logger.error("TypeError on %s %s\n%s", request.method, request.url.path, tb)
        rid = _get_request_id(request)
        return JSONResponse(
            status_code=500,
            content=_build_body(_status_to_error(500), "Internal Server Error", request_id=rid),
            headers=_headers_with_request_id(request),
        )

    async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
        logger.warning("ValidationError on %s %s: %s", request.method, request.url.path, str(exc)[:300])
        rid = _get_request_id(request)
        return JSONResponse(
            status_code=422,
            content=_build_body("validation_error", "Request validation failed",
                                str(exc.error_count()) + " validation error(s)" if _IS_PRODUCTION else str(exc),
                                request_id=rid),
            headers=_headers_with_request_id(request),
        )

    app.add_exception_handler(APIError, api_error_handler)           # type: ignore[arg-type]
    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(TypeError, type_error_handler)          # type: ignore[arg-type]
    app.add_exception_handler(ValidationError, validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)
