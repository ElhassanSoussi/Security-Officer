"""app.core.rate_limit_middleware

Very small global rate limiting middleware for select endpoints.

Constraints:
- In-memory only (no external deps)
- Non-breaking: only applies to a small set of critical endpoints
- Uses existing RateLimiter implementation and structured HTTPException 429

Keying:
- Prefer authenticated user_id when present in request.state.
- Fall back to client IP.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

from fastapi import HTTPException

from app.core.rate_limit import RateLimiter, get_client_ip


class EndpointRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        limiter: RateLimiter,
        paths: set[str],
    ):
        super().__init__(app)
        self._limiter = limiter
        self._paths = paths

    def _key(self, request: Request) -> str:
        user_id = getattr(getattr(request, "state", None), "user_id", None)
        if user_id:
            return f"user:{user_id}"
        return f"ip:{get_client_ip(request)}"

    async def dispatch(self, request: Request, call_next) -> Response:
        # Match exact paths only to avoid surprising throttling.
        if request.url.path in self._paths:
            try:
                self._limiter.check(self._key(request))
            except HTTPException as exc:
                rid = getattr(getattr(request, "state", None), "request_id", None)
                headers = dict(exc.headers or {})
                if rid:
                    headers.setdefault("X-Request-Id", rid)

                return JSONResponse(
                    status_code=exc.status_code,
                    content=exc.detail if isinstance(exc.detail, dict) else {"error": "rate_limited", "message": str(exc.detail)},
                    headers=headers,
                )
        return await call_next(request)
