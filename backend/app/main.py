import os
import asyncio
from fastapi import FastAPI, HTTPException, Request as FastAPIRequest
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse
from app.core.config import get_settings

settings = get_settings()

# Python 3.11+ behavior: ensure a default event loop exists for synchronous
# code that calls asyncio.get_event_loop().run_until_complete(...) in tests.
try:
    asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

# Sentry error monitoring (opt-in via SENTRY_DSN)
_sentry_initialized = False
if settings.SENTRY_DSN:
    try:
        import sentry_sdk  # type: ignore[import-untyped]
        from sentry_sdk.integrations.fastapi import FastApiIntegration  # type: ignore[import-untyped]
        from sentry_sdk.integrations.starlette import StarletteIntegration  # type: ignore[import-untyped]
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENVIRONMENT,
            traces_sample_rate=0.1 if settings.is_production else 1.0,
            integrations=[StarletteIntegration(), FastApiIntegration()],
            send_default_pii=False,
        )
        _sentry_initialized = True
    except ImportError:
        pass  # sentry-sdk not installed — silently skip

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json" if settings.docs_enabled else None,
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
)

# Security headers middleware for API responses
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: FastAPIRequest, call_next) -> StarletteResponse:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        if not settings.is_development:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# Max upload file size enforcement middleware
class MaxUploadSizeMiddleware(BaseHTTPMiddleware):
    MAX_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    async def dispatch(self, request: FastAPIRequest, call_next) -> StarletteResponse:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.MAX_BYTES:
            return JSONResponse(
                status_code=413,
                content={
                    "error": "payload_too_large",
                    "message": f"Upload exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit",
                    "detail": f"Max upload size is {settings.MAX_UPLOAD_SIZE_MB}MB",
                },
            )
        return await call_next(request)

app.add_middleware(MaxUploadSizeMiddleware)

# Register structured error handlers
from app.core.error_handler import register_error_handlers
register_error_handlers(app)

# Register request logging middleware (observability)
from app.core.request_logging import RequestLoggingMiddleware
app.add_middleware(RequestLoggingMiddleware)

# CORS Lockdown - production hardening and strictness
allowed_origins = []
if settings.is_production:
    # Production: ONLY explicit origins from env — no defaults, no wildcard
    extra_origins = os.getenv("ALLOWED_ORIGINS", "").split(",")
    allowed_origins = [o.strip() for o in extra_origins if o.strip() and o.strip() != "*"]
    # Always include the canonical production domain if ALLOWED_ORIGINS is set
    _canonical = [
        "https://nyccompliancearchitect.com",
        "https://www.nyccompliancearchitect.com",
    ]
    for origin in _canonical:
        if origin not in allowed_origins:
            allowed_origins.append(origin)
else:
    # Development / staging: allow localhost + env overrides
    allowed_origins = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ]
    extra_origins = os.getenv("ALLOWED_ORIGINS", "").split(",")
    allowed_origins.extend([o.strip() for o in extra_origins if o.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-Id"],
)

@app.get("/")
def root():
    return {"message": "NYC Compliance Architect API is running"}

# Lightweight liveness probe — always 200, no dependencies.
# Render / load-balancer health checks should point here.
@app.get("/health/ping")
def health_ping():
    return {"status": "ok"}

@app.get("/health")
def health_check():
    from datetime import datetime, timezone
    db_ok = False
    try:
        from app.core.database import get_supabase_admin
        sb = get_supabase_admin()
        sb.table("organizations").select("id").limit(1).execute()
        db_ok = True
    except Exception:
        pass

    return {
        "status": "ok" if db_ok else "degraded",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            "database": db_ok,
            "stripe": bool(os.getenv("STRIPE_SECRET_KEY")),
        },
    }


@app.get("/health/ready")
def readiness_check():
    """
    Readiness probe.
    Verifies DB connection, Stripe key presence, and OpenAI key presence.
    Returns 200 if all checks pass, 503 otherwise.
    Suitable for Kubernetes readinessProbe / ALB health checks.
    """
    from datetime import datetime, timezone

    checks = {
        "database": False,
        "stripe_configured": False,
        "openai_configured": False,
    }
    errors = {}

    # DB connectivity
    try:
        from app.core.database import get_supabase_admin
        sb = get_supabase_admin()
        sb.table("organizations").select("id").limit(1).execute()
        checks["database"] = True
    except Exception as e:
        errors["database"] = str(e)[:200]

    # Stripe key presence (not live test — just env check)
    stripe_key = (os.getenv("STRIPE_SECRET_KEY") or "").strip()
    checks["stripe_configured"] = bool(stripe_key)
    if not stripe_key:
        errors["stripe_configured"] = "STRIPE_SECRET_KEY not set"

    # OpenAI key presence
    openai_key = (settings.OPENAI_API_KEY or "").strip()
    checks["openai_configured"] = bool(openai_key)
    if not openai_key:
        errors["openai_configured"] = "OPENAI_API_KEY not set"

    all_ok = all(checks.values())
    payload = {
        "status": "ready" if all_ok else "not_ready",
        "environment": settings.ENVIRONMENT,
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if errors:
        payload["errors"] = errors

    if not all_ok:
        return JSONResponse(status_code=503, content=payload)
    return payload

@app.get(f"{settings.API_V1_STR}/health/deep")
def deep_health_check():
    """
    Deep readiness: verifies Supabase DB, storage, billing tables, and service-role access.
    Fails with 503 if any required check is false.
    """
    from datetime import datetime, timezone
    from app.core.database import get_supabase_admin

    billing_enabled = bool(getattr(settings, "BILLING_ENABLED", False))
    billing_configured = bool((settings.STRIPE_SECRET_KEY or "").strip())
    env_required = {
        "SUPABASE_URL": bool((settings.SUPABASE_URL or "").strip()),
        "SUPABASE_KEY": bool((settings.SUPABASE_KEY or "").strip()),
        "SUPABASE_JWT_SECRET": bool((settings.SUPABASE_JWT_SECRET or "").strip()),
        "SUPABASE_SERVICE_ROLE_KEY": bool((settings.SUPABASE_SERVICE_ROLE_KEY or "").strip()),
    }
    missing_env = [k for k, ok in env_required.items() if not ok]
    checks = {"database": False, "storage": False, "billing": not billing_enabled, "rls": False}
    errors = {}

    admin_sb = None
    try:
        admin_sb = get_supabase_admin()
        admin_sb.table("organizations").select("id").limit(1).execute()
        checks["database"] = True
        checks["rls"] = True  # service-role read succeeded
    except Exception as e:
        errors["database"] = str(e)

    if admin_sb:
        try:
            # Storage bucket list requires service-level access; any response means connectivity works.
            admin_sb.storage.list_buckets()
            checks["storage"] = True
        except Exception as e:
            errors["storage"] = str(e)

        if billing_enabled:
            try:
                admin_sb.table("billing_events").select("stripe_event_id").limit(1).execute()
                checks["billing"] = True
            except Exception as e:
                errors["billing"] = str(e)

    status = "ok" if all(checks.values()) else "fail"
    payload = {
        "status": status,
        "checks": checks,
        "env": {
            "required": env_required,
            "missing": missing_env,
            "billing_enabled": billing_enabled,
            "billing_configured": billing_configured,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if errors:
        payload["errors"] = errors

    if status != "ok":
        code = 503 if billing_enabled else 503
        return JSONResponse(status_code=code, content=payload)
    return payload


@app.get("/health/full")
def full_health_check():
    """
    Comprehensive health endpoint.
    Returns DB connectivity, Stripe status, vector search status, queue health.
    Suitable for production monitoring dashboards.
    """
    from datetime import datetime, timezone
    import logging as _logging

    _health_logger = _logging.getLogger("health.full")

    checks = {
        "database": False,
        "stripe": False,
        "vector_search": False,
        "queue": True,  # In-memory queue is always healthy in single-process mode
    }
    errors = {}
    latency = {}

    # 1. Database connectivity
    import time as _time
    db_start = _time.monotonic()
    try:
        from app.core.database import get_supabase_admin
        sb = get_supabase_admin()
        sb.table("organizations").select("id").limit(1).execute()
        checks["database"] = True
    except Exception as e:
        errors["database"] = str(e)[:200]
    latency["database_ms"] = round((_time.monotonic() - db_start) * 1000, 1)

    # 2. Stripe configuration status
    stripe_key = (os.getenv("STRIPE_SECRET_KEY") or "").strip()
    billing_on = bool(getattr(settings, "BILLING_ENABLED", False))
    if not billing_on:
        # Billing disabled — Stripe check is N/A but not a failure
        checks["stripe"] = True
    elif stripe_key:
        checks["stripe"] = True
    else:
        errors["stripe"] = "STRIPE_SECRET_KEY not set but BILLING_ENABLED=true"

    # 3. Vector search (pgvector / embeddings) readiness
    vec_start = _time.monotonic()
    try:
        from app.core.database import get_supabase_admin
        sb = get_supabase_admin()
        # Verify the chunks table and vector extension are accessible
        sb.table("chunks").select("id").limit(1).execute()
        checks["vector_search"] = True
    except Exception as e:
        errors["vector_search"] = str(e)[:200]
    latency["vector_search_ms"] = round((_time.monotonic() - vec_start) * 1000, 1)

    # 4. Queue health — in-memory, always healthy for single-process
    # Future: check Redis / Celery connectivity when distributed queue is added
    checks["queue"] = True

    all_ok = all(checks.values())
    status = "healthy" if all_ok else "degraded"

    payload = {
        "status": status,
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "checks": checks,
        "latency": latency,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if errors:
        payload["errors"] = errors

    if not all_ok:
        _health_logger.warning("Health check degraded: %s", errors)
        return JSONResponse(status_code=503, content=payload)
    return payload


from app.api.routes import router as main_router
from app.api.endpoints import runs, billing, orgs, projects, settings as settings_ep, audit, documents
from app.api.endpoints import admin as admin_ep
from app.api.endpoints import sales as sales_ep
from app.api.endpoints import onboarding as onboarding_ep
from app.api.endpoints import account as account_ep
from app.api.endpoints import assistant as assistant_ep

app.include_router(main_router, prefix=settings.API_V1_STR)
app.include_router(projects.router, prefix=f"{settings.API_V1_STR}/projects", tags=["Projects"])
app.include_router(documents.router, prefix=f"{settings.API_V1_STR}/projects", tags=["Project Documents"])
app.include_router(runs.router, prefix=f"{settings.API_V1_STR}/runs", tags=["Runs"])
app.include_router(billing.router, prefix=f"{settings.API_V1_STR}/billing", tags=["Billing"])
app.include_router(orgs.router, prefix=f"{settings.API_V1_STR}/orgs", tags=["Organizations"])
app.include_router(settings_ep.router, prefix=f"{settings.API_V1_STR}/settings", tags=["Settings"])
app.include_router(audit.router, prefix=f"{settings.API_V1_STR}/audit", tags=["Audit"])
# Onboarding guide endpoints
app.include_router(onboarding_ep.router, prefix=settings.API_V1_STR, tags=["Onboarding"])
# Admin + SOC2 compliance endpoints
app.include_router(admin_ep.router, prefix=settings.API_V1_STR, tags=["Admin", "SOC2"])
# Sales engine + lead capture + demo reset
app.include_router(sales_ep.router, prefix=settings.API_V1_STR, tags=["Sales", "Demo"])
# Account profile + appearance
app.include_router(account_ep.router, prefix=settings.API_V1_STR, tags=["Account"])
app.include_router(assistant_ep.router, prefix=f"{settings.API_V1_STR}/assistant", tags=["Assistant"])
