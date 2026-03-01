"""
Phase 20 Verification: Production Deployment + CI/CD + Observability

All tests are deterministic — no real DB / API / Docker calls.

Tests cover:
 1. Config — ENVIRONMENT setting exists and defaults to "local"
 2. Config — is_production property returns True for "production"
 3. Config — is_staging property returns True for "staging"
 4. Config — is_development property returns True for "local" and "development"
 5. Config — docs_enabled is False in production
 6. Config — docs_enabled is True in development/staging
 7. Config — debug_logging is False in production
 8. Config — SENTRY_DSN setting exists (default empty)
 9. Config — MAX_UPLOAD_SIZE_MB setting exists (default 50)
10. Config — OPENAI_TIMEOUT_SECONDS setting exists (default 120)
11. Config — VECTOR_SEARCH_RETRIES setting exists (default 3)
12. Config — RATE_LIMIT_ANALYSIS setting exists
13. Config — RATE_LIMIT_EXPORT setting exists
14. Config — RATE_LIMIT_LOGIN setting exists
15. MainApp — Swagger disabled in production mode
16. MainApp — /health endpoint defined
17. MainApp — /health/ready endpoint defined
18. MainApp — SecurityHeadersMiddleware registered
19. MainApp — MaxUploadSizeMiddleware registered
20. MainApp — RequestLoggingMiddleware registered
21. Logging — JSONLogFormatter class exists
22. Logging — JSONLogFormatter outputs valid JSON
23. Logging — JSONLogFormatter includes timestamp field
24. Logging — JSONLogFormatter includes level field
25. Logging — JSONLogFormatter includes environment field
26. Logging — RequestLoggingMiddleware class exists
27. Logging — RequestLoggingMiddleware sets X-Request-Id header
28. ErrorHandler — _build_body includes request_id when provided
29. ErrorHandler — _build_body omits request_id when None
30. ErrorHandler — _get_request_id helper exists
31. ErrorHandler — structured errors always have "error" key
32. ErrorHandler — structured errors always have "message" key
33. Resilience — resilience module importable
34. Resilience — openai_with_timeout callable
35. Resilience — openai_with_timeout raises TimeoutError on timeout
36. Resilience — retry_vector_search callable
37. Resilience — retry_vector_search retries on failure
38. Resilience — retry_vector_search succeeds on second attempt
39. Resilience — structured_error returns correct shape
40. Resilience — structured_error includes request_id when provided
41. Dockerfile — multi-stage build (deps + production)
42. Dockerfile — non-root USER directive present
43. Dockerfile — HEALTHCHECK directive present
44. Dockerfile — ENVIRONMENT=production set
45. CI — .github/workflows/ci.yml exists
46. CI — ci.yml defines backend-tests job
47. CI — ci.yml defines frontend-checks job
48. CI — ci.yml defines docker-build job
49. Frontend — SentryInit component file exists
50. Frontend — sentry.ts lib file exists
51. Frontend — layout.tsx imports SentryInit
52. CORS — production mode does not include localhost origins
"""

import sys
import os
import json
import logging
import pytest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------
BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

REPO_ROOT = os.path.join(BACKEND_DIR, "..")

DOCKERFILE_PATH = os.path.join(BACKEND_DIR, "Dockerfile")
CI_YML_PATH = os.path.join(REPO_ROOT, ".github", "workflows", "ci.yml")
MAIN_PATH = os.path.join(BACKEND_DIR, "app", "main.py")
REQUEST_LOGGING_PATH = os.path.join(BACKEND_DIR, "app", "core", "request_logging.py")
ERROR_HANDLER_PATH = os.path.join(BACKEND_DIR, "app", "core", "error_handler.py")
LAYOUT_PATH = os.path.join(REPO_ROOT, "frontend", "app", "layout.tsx")
SENTRY_INIT_PATH = os.path.join(REPO_ROOT, "frontend", "components", "SentryInit.tsx")
SENTRY_LIB_PATH = os.path.join(REPO_ROOT, "frontend", "lib", "sentry.ts")


def _read(path: str) -> str:
    with open(path) as f:
        return f.read()


# ===========================================================================
# 1–14: Config settings
# ===========================================================================

def test_01_config_environment_exists():
    from app.core.config import Settings
    s = Settings()
    assert hasattr(s, "ENVIRONMENT")
    assert s.ENVIRONMENT in ("local", "development", "staging", "production")


def test_02_is_production():
    from app.core.config import Settings
    s = Settings()
    s.ENVIRONMENT = "production"
    assert s.is_production is True


def test_03_is_staging():
    from app.core.config import Settings
    s = Settings()
    s.ENVIRONMENT = "staging"
    assert s.is_staging is True


def test_04_is_development():
    from app.core.config import Settings
    s = Settings()
    s.ENVIRONMENT = "local"
    assert s.is_development is True
    s.ENVIRONMENT = "development"
    assert s.is_development is True


def test_05_docs_disabled_in_production():
    from app.core.config import Settings
    s = Settings()
    s.ENVIRONMENT = "production"
    assert s.docs_enabled is False


def test_06_docs_enabled_in_dev_staging():
    from app.core.config import Settings
    s = Settings()
    s.ENVIRONMENT = "local"
    assert s.docs_enabled is True
    s.ENVIRONMENT = "staging"
    assert s.docs_enabled is True


def test_07_debug_logging_off_in_production():
    from app.core.config import Settings
    s = Settings()
    s.ENVIRONMENT = "production"
    assert s.debug_logging is False


def test_08_sentry_dsn_exists():
    from app.core.config import Settings
    s = Settings()
    assert hasattr(s, "SENTRY_DSN")


def test_09_max_upload_size_mb():
    from app.core.config import Settings
    s = Settings()
    assert s.MAX_UPLOAD_SIZE_MB == 50


def test_10_openai_timeout_seconds():
    from app.core.config import Settings
    s = Settings()
    assert s.OPENAI_TIMEOUT_SECONDS == 120


def test_11_vector_search_retries():
    from app.core.config import Settings
    s = Settings()
    assert s.VECTOR_SEARCH_RETRIES == 3


def test_12_rate_limit_analysis():
    from app.core.config import Settings
    s = Settings()
    assert hasattr(s, "RATE_LIMIT_ANALYSIS")
    assert s.RATE_LIMIT_ANALYSIS > 0


def test_13_rate_limit_export():
    from app.core.config import Settings
    s = Settings()
    assert hasattr(s, "RATE_LIMIT_EXPORT")
    assert s.RATE_LIMIT_EXPORT > 0


def test_14_rate_limit_login():
    from app.core.config import Settings
    s = Settings()
    assert hasattr(s, "RATE_LIMIT_LOGIN")
    assert s.RATE_LIMIT_LOGIN > 0


# ===========================================================================
# 15–20: main.py source checks
# ===========================================================================

def test_15_swagger_disabled_in_production():
    src = _read(MAIN_PATH)
    assert "docs_enabled" in src
    # Should use the settings property, not hardcoded string comparison
    assert 'docs_url="/docs"' in src


def test_16_health_endpoint_defined():
    src = _read(MAIN_PATH)
    assert '@app.get("/health")' in src


def test_17_health_ready_endpoint_defined():
    src = _read(MAIN_PATH)
    assert '@app.get("/health/ready")' in src


def test_18_security_headers_middleware():
    src = _read(MAIN_PATH)
    assert "SecurityHeadersMiddleware" in src


def test_19_max_upload_size_middleware():
    src = _read(MAIN_PATH)
    assert "MaxUploadSizeMiddleware" in src


def test_20_request_logging_middleware():
    src = _read(MAIN_PATH)
    assert "RequestLoggingMiddleware" in src


# ===========================================================================
# 21–27: Structured logging
# ===========================================================================

def test_21_json_log_formatter_exists():
    from app.core.request_logging import JSONLogFormatter
    assert JSONLogFormatter is not None


def test_22_json_log_formatter_outputs_valid_json():
    from app.core.request_logging import JSONLogFormatter
    fmt = JSONLogFormatter()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="hello", args=(), exc_info=None,
    )
    output = fmt.format(record)
    parsed = json.loads(output)
    assert parsed["message"] == "hello"


def test_23_json_log_formatter_has_timestamp():
    from app.core.request_logging import JSONLogFormatter
    fmt = JSONLogFormatter()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="ts test", args=(), exc_info=None,
    )
    parsed = json.loads(fmt.format(record))
    assert "timestamp" in parsed


def test_24_json_log_formatter_has_level():
    from app.core.request_logging import JSONLogFormatter
    fmt = JSONLogFormatter()
    record = logging.LogRecord(
        name="test", level=logging.WARNING, pathname="", lineno=0,
        msg="warn", args=(), exc_info=None,
    )
    parsed = json.loads(fmt.format(record))
    assert parsed["level"] == "WARNING"


def test_25_json_log_formatter_has_environment():
    from app.core.request_logging import JSONLogFormatter
    fmt = JSONLogFormatter()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="env", args=(), exc_info=None,
    )
    parsed = json.loads(fmt.format(record))
    assert "environment" in parsed


def test_26_request_logging_middleware_exists():
    from app.core.request_logging import RequestLoggingMiddleware
    assert RequestLoggingMiddleware is not None


def test_27_request_logging_middleware_sets_request_id():
    """Source check: middleware sets X-Request-Id on response."""
    src = _read(REQUEST_LOGGING_PATH)
    assert "X-Request-Id" in src
    assert "request_id" in src


# ===========================================================================
# 28–32: Error handler
# ===========================================================================

def test_28_build_body_includes_request_id():
    from app.core.error_handler import _build_body
    body = _build_body("test_error", "test msg", request_id="rid-123")
    assert body["request_id"] == "rid-123"


def test_29_build_body_omits_request_id_when_none():
    from app.core.error_handler import _build_body
    body = _build_body("test_error", "test msg")
    assert "request_id" not in body


def test_30_get_request_id_helper_exists():
    from app.core.error_handler import _get_request_id
    assert callable(_get_request_id)


def test_31_structured_errors_have_error_key():
    from app.core.error_handler import _build_body
    body = _build_body("some_error", "some message")
    assert "error" in body


def test_32_structured_errors_have_message_key():
    from app.core.error_handler import _build_body
    body = _build_body("some_error", "some message")
    assert "message" in body


# ===========================================================================
# 33–40: Resilience module
# ===========================================================================

def test_33_resilience_importable():
    import app.core.resilience  # noqa: F401


def test_34_openai_with_timeout_callable():
    from app.core.resilience import openai_with_timeout
    assert callable(openai_with_timeout)


def test_35_openai_with_timeout_raises_on_timeout():
    import time
    from app.core.resilience import openai_with_timeout

    def slow_func():
        time.sleep(5)
        return "done"

    with pytest.raises(TimeoutError):
        openai_with_timeout(slow_func, timeout_seconds=1)


def test_36_retry_vector_search_callable():
    from app.core.resilience import retry_vector_search
    assert callable(retry_vector_search)


def test_37_retry_vector_search_retries_on_failure():
    from app.core.resilience import retry_vector_search
    call_count = {"n": 0}

    def always_fail():
        call_count["n"] += 1
        raise RuntimeError("transient")

    with pytest.raises(RuntimeError):
        retry_vector_search(always_fail, max_retries=3, backoff_base=0.01)

    assert call_count["n"] == 3


def test_38_retry_vector_search_succeeds_on_second():
    from app.core.resilience import retry_vector_search
    call_count = {"n": 0}

    def fail_then_ok():
        call_count["n"] += 1
        if call_count["n"] < 2:
            raise RuntimeError("first fail")
        return "ok"

    result = retry_vector_search(fail_then_ok, max_retries=3, backoff_base=0.01)
    assert result == "ok"
    assert call_count["n"] == 2


def test_39_structured_error_shape():
    from app.core.resilience import structured_error
    body = structured_error("test_code", "test detail")
    assert body == {"code": "test_code", "detail": "test detail"}


def test_40_structured_error_with_request_id():
    from app.core.resilience import structured_error
    body = structured_error("err", "detail", request_id="rid-abc")
    assert body["request_id"] == "rid-abc"


# ===========================================================================
# 41–44: Dockerfile
# ===========================================================================

def test_41_dockerfile_multi_stage():
    src = _read(DOCKERFILE_PATH)
    # Must have at least two FROM directives (multi-stage)
    assert src.count("FROM ") >= 2


def test_42_dockerfile_non_root_user():
    src = _read(DOCKERFILE_PATH)
    assert "USER app" in src


def test_43_dockerfile_healthcheck():
    src = _read(DOCKERFILE_PATH)
    assert "HEALTHCHECK" in src


def test_44_dockerfile_production_env():
    src = _read(DOCKERFILE_PATH)
    assert "ENVIRONMENT=production" in src


# ===========================================================================
# 45–48: CI/CD pipeline
# ===========================================================================

def test_45_ci_yml_exists():
    assert os.path.isfile(CI_YML_PATH), f"ci.yml not found at {CI_YML_PATH}"


def test_46_ci_yml_has_backend_tests_job():
    src = _read(CI_YML_PATH)
    assert "backend-tests" in src


def test_47_ci_yml_has_frontend_checks_job():
    src = _read(CI_YML_PATH)
    assert "frontend-checks" in src


def test_48_ci_yml_has_docker_build_job():
    src = _read(CI_YML_PATH)
    assert "docker-build" in src


# ===========================================================================
# 49–52: Frontend files
# ===========================================================================

def test_49_sentry_init_component_exists():
    assert os.path.isfile(SENTRY_INIT_PATH), f"SentryInit.tsx not found at {SENTRY_INIT_PATH}"


def test_50_sentry_lib_exists():
    assert os.path.isfile(SENTRY_LIB_PATH), f"sentry.ts not found at {SENTRY_LIB_PATH}"


def test_51_layout_imports_sentry_init():
    src = _read(LAYOUT_PATH)
    assert "SentryInit" in src


def test_52_cors_production_no_localhost():
    """In production mode, allowed_origins must NOT include localhost defaults."""
    src = _read(MAIN_PATH)
    # The production branch should not add localhost origins
    assert "is_production" in src or "is_development" in src
    # Check that localhost origins are only in the else (non-production) branch
    prod_idx = src.find("if settings.is_production:")
    assert prod_idx != -1, "Production CORS branch not found"
    # Between production branch and else, localhost should not appear
    else_idx = src.find("else:", prod_idx)
    assert else_idx > prod_idx
    prod_section = src[prod_idx:else_idx]
    assert "localhost" not in prod_section
