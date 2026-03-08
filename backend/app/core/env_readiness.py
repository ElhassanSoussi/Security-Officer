"""app.core.env_readiness

Production-focused environment validation and readiness checks.

Constraints:
- No business-logic changes
- No new product features
- No secret values returned

Usage:
- Backend startup validation: call validate_startup_env(settings)
- Readiness endpoint: call build_readiness_report(settings, app)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
import logging
import os

from fastapi import FastAPI

logger = logging.getLogger("app.env")


@dataclass(frozen=True)
class CheckResult:
    key: str
    status: str  # ok | warning | error
    message: str


def _is_set(value: str | None) -> bool:
    v = (value or "").strip()
    if not v:
        return False
    if "your-" in v.lower():
        return False
    return True


def _is_probably_url(value: str | None) -> bool:
    v = (value or "").strip().lower()
    return v.startswith("http://") or v.startswith("https://")


def _csv_has_values(value: str | None) -> bool:
    parts = [p.strip() for p in (value or "").split(",")]
    return any(parts)


def validate_startup_env(settings: Any) -> list[CheckResult]:
    """Validate required env vars.

    Behavior policy:
    - Production: raise ValueError if critical checks fail
    - Non-production: log warnings and continue

    Return: list of CheckResult for inclusion in readiness reports.
    """

    env = str(getattr(settings, "ENVIRONMENT", os.getenv("ENVIRONMENT", "local")) or "local")
    env_lower = env.lower()
    is_production = env_lower == "production"

    checks: list[CheckResult] = []

    # Core connectivity
    supabase_url = getattr(settings, "SUPABASE_URL", os.getenv("SUPABASE_URL"))
    supabase_key = getattr(settings, "SUPABASE_KEY", os.getenv("SUPABASE_KEY"))
    frontend_url = getattr(settings, "FRONTEND_URL", os.getenv("FRONTEND_URL"))

    # Config values expected in production hardening work
    allowed_origins = os.getenv("ALLOWED_ORIGINS", "")

    # Release metadata
    app_version = getattr(settings, "APP_VERSION", os.getenv("APP_VERSION"))

    # Feature flags
    billing_enabled = bool(getattr(settings, "BILLING_ENABLED", False) or str(os.getenv("BILLING_ENABLED", "")).lower() == "true")
    assistant_enabled = str(os.getenv("ASSISTANT_ENABLED", "")).lower() in ("1", "true", "yes")

    # Billing
    stripe_secret = getattr(settings, "STRIPE_SECRET_KEY", os.getenv("STRIPE_SECRET_KEY"))
    stripe_webhook = getattr(settings, "STRIPE_WEBHOOK_SECRET", os.getenv("STRIPE_WEBHOOK_SECRET"))

    # AI
    openai_key = getattr(settings, "OPENAI_API_KEY", os.getenv("OPENAI_API_KEY"))

    problems: list[str] = []

    def require_ok(key: str, ok: bool, msg_ok: str, msg_bad: str) -> None:
        nonlocal problems
        if ok:
            checks.append(CheckResult(key=key, status="ok", message=msg_ok))
        else:
            checks.append(CheckResult(key=key, status="error", message=msg_bad))
            problems.append(key)

    def warn_if(key: str, ok: bool, msg_ok: str, msg_bad: str) -> None:
        if ok:
            checks.append(CheckResult(key=key, status="ok", message=msg_ok))
        else:
            checks.append(CheckResult(key=key, status="warning", message=msg_bad))

    # Required always
    require_ok(
        "SUPABASE_URL",
        _is_set(supabase_url) and _is_probably_url(supabase_url),
        "SUPABASE_URL set",
        "Missing/invalid SUPABASE_URL",
    )
    require_ok(
        "SUPABASE_KEY",
        _is_set(supabase_key),
        "SUPABASE_KEY set",
        "Missing SUPABASE_KEY",
    )
    require_ok(
        "FRONTEND_URL",
        _is_set(frontend_url) and _is_probably_url(frontend_url),
        "FRONTEND_URL set",
        "Missing/invalid FRONTEND_URL",
    )

    # Required in production, warning elsewhere
    if is_production:
        require_ok(
            "ALLOWED_ORIGINS",
            _csv_has_values(allowed_origins) and allowed_origins.strip() != "*",
            "ALLOWED_ORIGINS configured",
            "Missing/invalid ALLOWED_ORIGINS (must be explicit, not '*')",
        )
        require_ok(
            "APP_VERSION",
            _is_set(app_version),
            "APP_VERSION set",
            "Missing APP_VERSION",
        )
    else:
        warn_if(
            "ALLOWED_ORIGINS",
            _csv_has_values(allowed_origins),
            "ALLOWED_ORIGINS configured",
            "ALLOWED_ORIGINS not set (ok for local dev, required for production)",
        )
        warn_if(
            "APP_VERSION",
            _is_set(app_version),
            "APP_VERSION set",
            "APP_VERSION not set (set for traceability)",
        )

    # Feature-dependent checks
    if assistant_enabled:
        require_ok(
            "OPENAI_API_KEY",
            _is_set(openai_key),
            "OPENAI_API_KEY set",
            "Missing OPENAI_API_KEY but assistant/AI features enabled",
        )
    else:
        warn_if(
            "OPENAI_API_KEY",
            _is_set(openai_key),
            "OPENAI_API_KEY set",
            "OPENAI_API_KEY not set (ok if assistant is disabled)",
        )

    if billing_enabled:
        require_ok(
            "STRIPE_SECRET_KEY",
            _is_set(stripe_secret),
            "STRIPE_SECRET_KEY set",
            "Missing STRIPE_SECRET_KEY but billing is enabled",
        )
        require_ok(
            "STRIPE_WEBHOOK_SECRET",
            _is_set(stripe_webhook),
            "STRIPE_WEBHOOK_SECRET set",
            "Missing STRIPE_WEBHOOK_SECRET but billing is enabled",
        )
    else:
        warn_if(
            "STRIPE_SECRET_KEY",
            _is_set(stripe_secret),
            "STRIPE_SECRET_KEY set",
            "STRIPE_SECRET_KEY not set (ok if billing disabled)",
        )
        warn_if(
            "STRIPE_WEBHOOK_SECRET",
            _is_set(stripe_webhook),
            "STRIPE_WEBHOOK_SECRET set",
            "STRIPE_WEBHOOK_SECRET not set (ok if billing disabled)",
        )

    if problems:
        msg = f"Startup environment validation failed: {', '.join(problems)}"
        if is_production:
            raise ValueError(msg)
        logger.warning(msg)

    return checks


def build_readiness_report(settings: Any, app: FastAPI) -> dict[str, Any]:
    env = str(getattr(settings, "ENVIRONMENT", os.getenv("ENVIRONMENT", "local")) or "local")
    version = str(getattr(settings, "APP_VERSION", os.getenv("APP_VERSION", "")) or "")

    checks = validate_startup_env(settings)

    # Static checks about wiring / middleware
    middleware_names = {m.cls.__name__ for m in getattr(app, "user_middleware", [])}

    def add(key: str, status: str, message: str) -> None:
        checks.append(CheckResult(key=key, status=status, message=message))

    # CORS configured (we assume CORSMiddleware is present)
    if "CORSMiddleware" in middleware_names:
        add("cors", "ok", "CORS middleware enabled")
    else:
        add("cors", "error", "CORS middleware missing")

    if "SecurityHeadersMiddleware" in middleware_names:
        add("security_headers", "ok", "Security headers middleware enabled")
    else:
        add("security_headers", "warning", "Security headers middleware not detected")

    if "EndpointRateLimitMiddleware" in middleware_names:
        add("rate_limiter", "ok", "Critical endpoint rate limiting enabled")
    else:
        add("rate_limiter", "warning", "Rate limiter middleware not detected")

    # Health endpoint route exists
    paths = {getattr(r, "path", None) for r in getattr(app, "routes", [])}
    if "/health" in paths:
        add("health_endpoint", "ok", "GET /health registered")
    else:
        add("health_endpoint", "error", "GET /health route missing")

    # APP_VERSION fallback / placeholder detection (production only)
    # Catches cases where the env var is set to a well-known default instead of a real release tag.
    _FALLBACK_VERSIONS = {"1.0.0", "0.0.0", "0.1.0", "unknown", "dev", "local"}
    if env.lower() == "production" and version.lower() in _FALLBACK_VERSIONS:
        add(
            "app_version_value",
            "warning",
            f"APP_VERSION='{version}' looks like a placeholder — set a real release tag",
        )
    elif version and version.lower() not in _FALLBACK_VERSIONS:
        add("app_version_value", "ok", f"APP_VERSION='{version}'")

    # Summarize
    statuses = [c.status for c in checks]
    if "error" in statuses:
        overall = "error"
    elif "warning" in statuses:
        overall = "warning"
    else:
        overall = "ok"

    return {
        "status": overall,
        "environment": env,
        "version": version or "unknown",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": [
            {"key": c.key, "status": c.status, "message": c.message}
            for c in checks
        ],
    }
