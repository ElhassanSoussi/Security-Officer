import os
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    PROJECT_NAME: str = "NYC Compliance Architect"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "local" # local, development, staging, production

    # Frontend URL (for backend-generated links: email confirmations, Stripe redirects, etc.)
    FRONTEND_URL: str = "http://localhost:3001"

    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_SECRET_KEY: str = ""
    SUPABASE_JWT_SECRET: str = ""
    BILLING_ENABLED: bool = False
    
    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    # Price IDs for plan names (FREE/PRO/ENTERPRISE)
    STRIPE_PRICE_FREE: str = ""
    STRIPE_PRICE_PRO: str = ""
    STRIPE_PRICE_ENTERPRISE: str = ""
    # Plans page: Price IDs for Starter/Growth/Elite plan names
    STRIPE_PRICE_STARTER: str = ""
    STRIPE_PRICE_GROWTH: str = ""
    STRIPE_PRICE_ELITE: str = ""
    # Trial period in days for new PRO subscriptions
    STRIPE_TRIAL_DAYS: int = 14
    
    # OpenAI
    OPENAI_API_KEY: str = ""
    embedding_model: str = "text-embedding-3-small"
    
    # Phase 3: Retrieval Engine Configuration
    RETRIEVAL_SIMILARITY_THRESHOLD: float = 0.55  # Minimum cosine similarity to accept a chunk
    RETRIEVAL_TOP_K: int = 5                       # Max chunks to retrieve per query
    RETRIEVAL_DEBUG: bool = False                   # When True, return top-K chunks with scores in API response
    STRICT_MODE: bool = False                       # When True, model MUST quote from source — no synthesis
    LLM_MODEL: str = "gpt-4-turbo"                 # Model for answer generation
    LLM_TIMEOUT_SECONDS: int = 60                   # Timeout for LLM API calls

    # Phase 4: Multi-Run Intelligence Configuration
    REUSE_EXACT_THRESHOLD: float = 0.90            # ≥0.90 = reuse directly (answer_origin="reused")
    REUSE_SUGGEST_THRESHOLD: float = 0.75          # 0.75-0.90 = show as suggestion
    REUSE_SEARCH_LIMIT: int = 5                    # Max similar Q&A pairs to retrieve
    EMBEDDING_CACHE_SIZE: int = 1000               # LRU cache size for question embeddings
    REUSE_ENABLED: bool = True                     # Master switch for Phase 4 reuse logic

    # Phase 20: Production deployment settings
    # -- Sentry error monitoring --
    SENTRY_DSN: str = ""
    # -- Upload limits --
    MAX_UPLOAD_SIZE_MB: int = 50
    # -- OpenAI resilience --
    OPENAI_TIMEOUT_SECONDS: int = 120
    VECTOR_SEARCH_RETRIES: int = 3
    # -- Environment-aware rate limits (production is stricter) --
    RATE_LIMIT_ANALYSIS: int = 5       # per 60s window
    RATE_LIMIT_EXPORT: int = 10        # per 60s window
    RATE_LIMIT_LOGIN: int = 10         # per 300s window

    # Phase 23: Production hardening rate limits
    RATE_LIMIT_CONTACT: int = 5        # per 300s window (public contact form)
    RATE_LIMIT_AUTH: int = 20          # per 300s window (auth endpoints)

    # Phase 21: SOC2 Readiness
    DATA_RETENTION_DAYS: int = 365              # Configurable retention period
    AUTH_MIN_PASSWORD_LENGTH: int = 10          # Minimum password length for SOC2
    AUTH_REQUIRE_EMAIL_VERIFICATION: bool = True # Block unverified email users

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def is_staging(self) -> bool:
        return self.ENVIRONMENT.lower() == "staging"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT.lower() in ("local", "development")

    @property
    def docs_enabled(self) -> bool:
        """Swagger/ReDoc enabled in development and staging only."""
        return not self.is_production

    @property
    def debug_logging(self) -> bool:
        """Verbose logging in development and staging."""
        return not self.is_production
    
    # Resolve backend/.env regardless of cwd (works for uvicorn run from repo root or backend/)
    _ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

    model_config = {
        "env_file": str(_ENV_FILE) if _ENV_FILE.exists() else None,
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore"  # Allow extra env vars from docker without crashing
    }

@lru_cache()
def get_settings():
    settings = Settings()

    # ── Normalise service-role key aliases ──────────────────────────────────
    # Accept ANY of: SUPABASE_SERVICE_ROLE_KEY, SUPABASE_SECRET_KEY.
    # Whichever is set, copy it into SUPABASE_SERVICE_ROLE_KEY so every
    # downstream module can just read that single field.
    _svc = (
        settings.SUPABASE_SERVICE_ROLE_KEY
        or settings.SUPABASE_SECRET_KEY
    ).strip()
    if _svc:
        settings.SUPABASE_SERVICE_ROLE_KEY = _svc

    # ── Normalise anon key ──────────────────────────────────────────────────
    # SUPABASE_KEY (anon/public key) is used for RLS-scoped clients.
    # If the user only provided the service-role key, fall back to it so the
    # app can at least start (admin endpoints still work fine).
    if not (settings.SUPABASE_KEY or "").strip() and _svc:
        settings.SUPABASE_KEY = _svc

    # ── Fail-fast: required env vars ────────────────────────────────────────
    required = {
        "SUPABASE_URL": settings.SUPABASE_URL,
        "SUPABASE_SERVICE_ROLE_KEY": settings.SUPABASE_SERVICE_ROLE_KEY,
        "SUPABASE_JWT_SECRET": settings.SUPABASE_JWT_SECRET,
    }
    missing = [k for k, v in required.items() if not (v or "").strip() or "your-" in v]
    if missing:
        hint = (
            "Set these in your Render dashboard (Environment → Environment Variables) "
            "or in backend/.env for local development."
        )
        raise ValueError(
            f"CRITICAL: missing required env var(s): {', '.join(missing)}. {hint}"
        )

    # Stripe: only mandatory when billing is enabled.
    if settings.BILLING_ENABLED:
        if not settings.STRIPE_SECRET_KEY or "your-" in settings.STRIPE_SECRET_KEY:
            raise ValueError("CRITICAL ERROR: STRIPE_SECRET_KEY required when BILLING_ENABLED=true")
        if not settings.STRIPE_WEBHOOK_SECRET or "your-" in settings.STRIPE_WEBHOOK_SECRET:
            if settings.is_production:
                raise ValueError("CRITICAL ERROR: STRIPE_WEBHOOK_SECRET required when BILLING_ENABLED=true in production")
            else:
                import logging as _log
                _log.getLogger("app.config").warning(
                    "STRIPE_WEBHOOK_SECRET not set — webhook endpoint will return 503. "
                    "Run `stripe listen --forward-to http://localhost:8000/api/v1/billing/webhook19` to get one."
                )
    
    # Phase 20: Production-specific validations
    if settings.is_production:
        allowed = os.getenv("ALLOWED_ORIGINS", "")
        if not allowed or allowed.strip() == "*":
            import logging
            logging.getLogger("app.config").warning(
                "PRODUCTION WARNING: ALLOWED_ORIGINS is empty or wildcard — set explicit origins"
            )

    # Phase 12 Part 9: Use logging, not print — never log secret values
    import logging
    _logger = logging.getLogger("app.config")
    _logger.info(
        "Configuration loaded: env=%s billing=%s docs=%s sentry=%s",
        settings.ENVIRONMENT.upper(),
        settings.BILLING_ENABLED,
        settings.docs_enabled,
        bool(settings.SENTRY_DSN),
    )

    # ── Export Stripe settings to os.environ ────────────────────────────────
    # pydantic-settings reads .env files but does NOT inject into os.environ.
    # Many billing modules use os.getenv("STRIPE_*") — sync them here so
    # everything works consistently in local dev AND production.
    _stripe_exports = {
        "STRIPE_SECRET_KEY": settings.STRIPE_SECRET_KEY,
        "STRIPE_WEBHOOK_SECRET": settings.STRIPE_WEBHOOK_SECRET,
        "STRIPE_PRICE_FREE": settings.STRIPE_PRICE_FREE,
        "STRIPE_PRICE_PRO": settings.STRIPE_PRICE_PRO,
        "STRIPE_PRICE_ENTERPRISE": settings.STRIPE_PRICE_ENTERPRISE,
        "STRIPE_PRICE_STARTER": settings.STRIPE_PRICE_STARTER,
        "STRIPE_PRICE_GROWTH": settings.STRIPE_PRICE_GROWTH,
        "STRIPE_PRICE_ELITE": settings.STRIPE_PRICE_ELITE,
        "BILLING_ENABLED": str(settings.BILLING_ENABLED).lower(),
    }
    for _k, _v in _stripe_exports.items():
        if _v and not os.getenv(_k):
            os.environ[_k] = _v

    return settings
