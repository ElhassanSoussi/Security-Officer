"""app.core.security_headers

Central security headers middleware.

Goals:
- Lightweight (no extra deps)
- Non-breaking: only adds/overrides response headers
- Safe defaults for API + frontend calls

Notes:
- CSP is intentionally conservative and mostly applies to browser contexts.
  For API responses it's harmless; browsers ignore it for XHR unless rendering.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


def _default_csp() -> str:
    # Minimal, sane baseline. Adjust per frontend needs.
    return (
        "default-src 'self'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'; "
        "object-src 'none'; "
        "img-src 'self' data: https:; "
        "style-src 'self' 'unsafe-inline' https:; "
        "script-src 'self' 'unsafe-inline' https:; "
        "connect-src 'self' https:; "
        "font-src 'self' data: https:"
    )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, is_development: bool, csp: str | None = None):
        super().__init__(app)
        self._is_development = is_development
        self._csp = csp or _default_csp()

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Basic hardening
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-XSS-Protection", "1; mode=block")

        # CSP (set if not already set by an upstream reverse proxy)
        response.headers.setdefault("Content-Security-Policy", self._csp)

        # HSTS only when TLS is expected (non-local)
        if not self._is_development:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )

        return response
