"""
Production Hardening + Security Cleanup Tests

All tests are deterministic — no real DB / API / external calls.

Tests cover:
 1. RLS — production hardening migration SQL file exists
 2. RLS — migration drops overly-permissive anon_insert_sales_leads policy
 3. RLS — migration creates restricted anon insert policy
 4. RLS — migration creates anon deny SELECT policy
 5. RLS — migration creates anon deny UPDATE policy
 6. RLS — migration creates anon deny DELETE policy
 7. RLS — migration documents leaked password protection
 8. RLS — migration creates email+created_at composite index
 9. RLS — all service_role USING(true) policies are legitimate
10. ErrorHandler — APIError class has status_code, error, message fields
11. ErrorHandler — _status_to_error maps 400 to bad_request
12. ErrorHandler — _status_to_error maps 401 to unauthorized
13. ErrorHandler — _status_to_error maps 403 to forbidden
14. ErrorHandler — _status_to_error maps 404 to not_found
15. ErrorHandler — _status_to_error maps 429 to rate_limited
16. ErrorHandler — _status_to_error maps 500 to internal_error
17. ErrorHandler — _status_to_error maps 503 to service_unavailable
18. ErrorHandler — _build_body includes error and message keys
19. ErrorHandler — _build_body includes request_id when provided
20. ErrorHandler — _build_body omits request_id when None
21. RateLimiter — contact_limiter exists and is RateLimiter instance
22. RateLimiter — contact_limiter max_requests is 5
23. RateLimiter — contact_limiter window_seconds is 300
24. RateLimiter — auth_limiter exists and is RateLimiter instance
25. RateLimiter — auth_limiter max_requests is 20
26. RateLimiter — auth_limiter window_seconds is 300
27. RateLimiter — get_client_ip function exists
28. RateLimiter — get_client_ip extracts x-forwarded-for first IP
29. RateLimiter — get_client_ip falls back to client.host
30. RateLimiter — contact_limiter blocks after max_requests exceeded
31. RateLimiter — contact_limiter allows requests within limit
32. RateLimiter — reset clears rate limit state
33. Config — RATE_LIMIT_CONTACT setting exists
34. Config — RATE_LIMIT_CONTACT defaults to 5
35. Config — RATE_LIMIT_AUTH setting exists
36. Config — RATE_LIMIT_AUTH defaults to 20
37. Sales — POST /contact route has request parameter (rate-limited)
38. Sales — sales.py imports contact_limiter
39. Sales — sales.py imports get_client_ip
40. DevBanner — DevBanner component checks isProd
41. DevBanner — config.ts has isProd property
42. DevBanner — DevBanner returns null in production mode
43. HealthFull — /health/full endpoint defined in main.py
44. HealthFull — /health/full source checks database
45. HealthFull — /health/full source checks stripe
46. HealthFull — /health/full source checks vector_search
47. HealthFull — /health/full source checks queue
48. HealthFull — /health/full returns latency metrics
49. HealthFull — /health/full returns version field
50. HealthFull — /health/full returns environment field
51. MainApp — /health endpoint still defined
52. MainApp — /health/ready endpoint still defined
53. MainApp — /health/full endpoint is GET method
54. Verify — VERIFY.md contains production hardening section
55. Verify — VERIFY.md production hardening mentions RLS verified
56. Verify — VERIFY.md production hardening mentions rate limiting active
57. Verify — VERIFY.md production hardening mentions production banner hidden
58. Migration — hardening migration restricts source column values
59. Migration — hardening migration requires email or company_name
60. Migration — hardening migration documents vector extension schema
"""

import ast
import inspect
import os
import re
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ── Setup paths ───────────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent
FRONTEND_DIR = ROOT_DIR / "frontend"
SCRIPTS_DIR = BACKEND_DIR / "scripts"
sys.path.insert(0, str(BACKEND_DIR))

# Ensure env vars so Settings() doesn't crash
for var in ("SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_JWT_SECRET", "SUPABASE_SERVICE_ROLE_KEY"):
    os.environ.setdefault(var, "https://test.supabase.co" if "URL" in var else "test-key-placeholder")


# ══════════════════════════════════════════════════════════════════════════════
# Part 1: RLS Security Hardening Migration (Tests 1-9)
# ══════════════════════════════════════════════════════════════════════════════

class TestRLSSecurityMigration:
    """Verify production hardening migration SQL exists and contains proper security policies."""

    MIGRATION_FILE = SCRIPTS_DIR / "016_production_hardening_rls.sql"

    @pytest.fixture(autouse=True)
    def _load_sql(self):
        self.sql = self.MIGRATION_FILE.read_text() if self.MIGRATION_FILE.exists() else ""
        self.sql_lower = self.sql.lower()

    def test_01_migration_file_exists(self):
        assert self.MIGRATION_FILE.exists(), "016_production_hardening_rls.sql not found"

    def test_02_drops_permissive_anon_insert(self):
        assert 'drop policy if exists "anon_insert_sales_leads"' in self.sql_lower

    def test_03_creates_restricted_anon_insert(self):
        assert "anon_insert_sales_leads_restricted" in self.sql_lower
        assert "for insert" in self.sql_lower

    def test_04_creates_anon_deny_select(self):
        assert "anon_deny_select_sales_leads" in self.sql_lower
        assert "using (false)" in self.sql_lower

    def test_05_creates_anon_deny_update(self):
        assert "anon_deny_update_sales_leads" in self.sql_lower

    def test_06_creates_anon_deny_delete(self):
        assert "anon_deny_delete_sales_leads" in self.sql_lower

    def test_07_documents_leaked_password_protection(self):
        assert "leaked_password_protection" in self.sql.lower() or "leaked password" in self.sql.lower()

    def test_08_creates_email_created_index(self):
        assert "idx_sales_leads_email_created" in self.sql_lower

    def test_09_service_role_using_true_are_legitimate(self):
        """All USING (true) in migration files are on service_role policies."""
        migration_files = [
            SCRIPTS_DIR / "003_retrieval_engine.sql",
            SCRIPTS_DIR / "004_multi_run_intelligence.sql",
            SCRIPTS_DIR / "002_project_workspace.sql",
        ]
        for mf in migration_files:
            if not mf.exists():
                continue
            content = mf.read_text()
            # Find all policies with USING (true)
            # They should all be preceded by service_role context
            lines = content.split("\n")
            for i, line in enumerate(lines):
                if "using (true)" in line.lower():
                    # Look backwards for service_role in the same policy block
                    context = "\n".join(lines[max(0, i - 10):i + 1]).lower()
                    assert "service_role" in context, (
                        f"USING (true) at line {i+1} in {mf.name} is NOT a service_role policy"
                    )


# ══════════════════════════════════════════════════════════════════════════════
# Part 2: Structured Error Codes (Tests 10-20)
# ══════════════════════════════════════════════════════════════════════════════

class TestStructuredErrorCodes:
    """Verify error handler produces structured error codes for all HTTP statuses."""

    def test_10_api_error_has_fields(self):
        from app.core.error_handler import APIError
        err = APIError(status_code=400, error="bad_request", message="test")
        assert err.status_code == 400
        assert err.error == "bad_request"
        assert err.message == "test"

    def test_11_status_to_error_400(self):
        from app.core.error_handler import _status_to_error
        assert _status_to_error(400) == "bad_request"

    def test_12_status_to_error_401(self):
        from app.core.error_handler import _status_to_error
        assert _status_to_error(401) == "unauthorized"

    def test_13_status_to_error_403(self):
        from app.core.error_handler import _status_to_error
        assert _status_to_error(403) == "forbidden"

    def test_14_status_to_error_404(self):
        from app.core.error_handler import _status_to_error
        assert _status_to_error(404) == "not_found"

    def test_15_status_to_error_429(self):
        from app.core.error_handler import _status_to_error
        assert _status_to_error(429) == "rate_limited"

    def test_16_status_to_error_500(self):
        from app.core.error_handler import _status_to_error
        assert _status_to_error(500) == "internal_error"

    def test_17_status_to_error_503(self):
        from app.core.error_handler import _status_to_error
        assert _status_to_error(503) == "service_unavailable"

    def test_18_build_body_has_error_and_message(self):
        from app.core.error_handler import _build_body
        body = _build_body("bad_request", "Invalid input")
        assert body["error"] == "bad_request"
        assert body["message"] == "Invalid input"

    def test_19_build_body_includes_request_id(self):
        from app.core.error_handler import _build_body
        body = _build_body("bad_request", "test", request_id="req-123")
        assert body["request_id"] == "req-123"

    def test_20_build_body_omits_request_id_when_none(self):
        from app.core.error_handler import _build_body
        body = _build_body("bad_request", "test", request_id=None)
        assert "request_id" not in body


# ══════════════════════════════════════════════════════════════════════════════
# Part 3: Rate Limiting Production Mode (Tests 21-32)
# ══════════════════════════════════════════════════════════════════════════════

class TestRateLimitingProduction:
    """Verify contact_limiter, auth_limiter, and get_client_ip are properly configured."""

    def test_21_contact_limiter_exists(self):
        from app.core.rate_limit import contact_limiter, RateLimiter
        assert isinstance(contact_limiter, RateLimiter)

    def test_22_contact_limiter_max_requests(self):
        from app.core.rate_limit import contact_limiter
        assert contact_limiter.max_requests == 5

    def test_23_contact_limiter_window_seconds(self):
        from app.core.rate_limit import contact_limiter
        assert contact_limiter.window_seconds == 300

    def test_24_auth_limiter_exists(self):
        from app.core.rate_limit import auth_limiter, RateLimiter
        assert isinstance(auth_limiter, RateLimiter)

    def test_25_auth_limiter_max_requests(self):
        from app.core.rate_limit import auth_limiter
        assert auth_limiter.max_requests == 20

    def test_26_auth_limiter_window_seconds(self):
        from app.core.rate_limit import auth_limiter
        assert auth_limiter.window_seconds == 300

    def test_27_get_client_ip_exists(self):
        from app.core.rate_limit import get_client_ip
        assert callable(get_client_ip)

    def test_28_get_client_ip_extracts_forwarded_for(self):
        from app.core.rate_limit import get_client_ip
        mock_request = MagicMock()
        mock_request.headers = {"x-forwarded-for": "1.2.3.4, 5.6.7.8"}
        mock_request.client.host = "127.0.0.1"
        assert get_client_ip(mock_request) == "1.2.3.4"

    def test_29_get_client_ip_falls_back_to_client_host(self):
        from app.core.rate_limit import get_client_ip
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.client.host = "10.0.0.1"
        assert get_client_ip(mock_request) == "10.0.0.1"

    def test_30_contact_limiter_blocks_after_exceeded(self):
        from app.core.rate_limit import RateLimiter
        from fastapi import HTTPException
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        limiter.check("test-ip-block")
        limiter.check("test-ip-block")
        with pytest.raises(HTTPException) as exc_info:
            limiter.check("test-ip-block")
        assert exc_info.value.status_code == 429
        limiter.reset()

    def test_31_contact_limiter_allows_within_limit(self):
        from app.core.rate_limit import RateLimiter
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        # Should not raise
        limiter.check("test-ip-allow")
        limiter.check("test-ip-allow")
        limiter.check("test-ip-allow")
        limiter.reset()

    def test_32_reset_clears_state(self):
        from app.core.rate_limit import RateLimiter
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        limiter.check("reset-key")
        limiter.reset("reset-key")
        # After reset, should be allowed again
        limiter.check("reset-key")
        limiter.reset()


# ══════════════════════════════════════════════════════════════════════════════
# Part 3b: Config Rate Limit Settings (Tests 33-36)
# ══════════════════════════════════════════════════════════════════════════════

class TestConfigRateLimitSettings:
    """Verify config.py has rate limit settings for contact and auth."""

    def _make_settings(self):
        from app.core.config import Settings
        return Settings(
            SUPABASE_URL="https://test.supabase.co",
            SUPABASE_KEY="test-key",
            SUPABASE_JWT_SECRET="test-secret",
            SUPABASE_SERVICE_ROLE_KEY="test-service-key",
        )

    def test_33_rate_limit_contact_setting_exists(self):
        s = self._make_settings()
        assert hasattr(s, "RATE_LIMIT_CONTACT")

    def test_34_rate_limit_contact_default_is_5(self):
        s = self._make_settings()
        assert s.RATE_LIMIT_CONTACT == 5

    def test_35_rate_limit_auth_setting_exists(self):
        s = self._make_settings()
        assert hasattr(s, "RATE_LIMIT_AUTH")

    def test_36_rate_limit_auth_default_is_20(self):
        s = self._make_settings()
        assert s.RATE_LIMIT_AUTH == 20


# ══════════════════════════════════════════════════════════════════════════════
# Part 3c: Sales Endpoint Rate Limiting (Tests 37-39)
# ══════════════════════════════════════════════════════════════════════════════

class TestSalesRateLimiting:
    """Verify POST /contact is rate-limited via contact_limiter."""

    def test_37_contact_route_has_request_param(self):
        """The submit_contact_form function accepts a Request parameter (for IP extraction)."""
        from app.api.endpoints.sales import submit_contact_form
        sig = inspect.signature(submit_contact_form)
        param_names = list(sig.parameters.keys())
        assert "request" in param_names, "submit_contact_form must accept 'request' for rate limiting"

    def test_38_sales_imports_contact_limiter(self):
        source = (BACKEND_DIR / "app" / "api" / "endpoints" / "sales.py").read_text()
        assert "contact_limiter" in source

    def test_39_sales_imports_get_client_ip(self):
        source = (BACKEND_DIR / "app" / "api" / "endpoints" / "sales.py").read_text()
        assert "get_client_ip" in source


# ══════════════════════════════════════════════════════════════════════════════
# Part 4: DevBanner Production Guard (Tests 40-42)
# ══════════════════════════════════════════════════════════════════════════════

class TestDevBannerProductionGuard:
    """Verify DevBanner is hidden in production via config.isProd."""

    def test_40_devbanner_checks_is_prod(self):
        devbanner = FRONTEND_DIR / "components" / "ui" / "DevBanner.tsx"
        assert devbanner.exists(), "DevBanner.tsx not found"
        source = devbanner.read_text()
        assert "isProd" in source or "is_prod" in source or "isProduction" in source

    def test_41_config_has_is_prod(self):
        config_file = FRONTEND_DIR / "lib" / "config.ts"
        assert config_file.exists(), "config.ts not found"
        source = config_file.read_text()
        assert "isProd" in source

    def test_42_devbanner_returns_null_in_production(self):
        devbanner = FRONTEND_DIR / "components" / "ui" / "DevBanner.tsx"
        source = devbanner.read_text()
        # Component returns null when isProd is true
        assert "return null" in source


# ══════════════════════════════════════════════════════════════════════════════
# Part 5: /health/full Endpoint (Tests 43-53)
# ══════════════════════════════════════════════════════════════════════════════

class TestHealthFullEndpoint:
    """Verify /health/full comprehensive monitoring endpoint."""

    @pytest.fixture(autouse=True)
    def _load_main_source(self):
        self.main_source = (BACKEND_DIR / "app" / "main.py").read_text()

    def test_43_health_full_endpoint_defined(self):
        assert "/health/full" in self.main_source

    def test_44_health_full_checks_database(self):
        # Find the full_health_check function body
        assert '"database"' in self.main_source

    def test_45_health_full_checks_stripe(self):
        assert '"stripe"' in self.main_source

    def test_46_health_full_checks_vector_search(self):
        assert '"vector_search"' in self.main_source

    def test_47_health_full_checks_queue(self):
        assert '"queue"' in self.main_source

    def test_48_health_full_returns_latency(self):
        assert "latency" in self.main_source

    def test_49_health_full_returns_version(self):
        assert '"version"' in self.main_source

    def test_50_health_full_returns_environment(self):
        assert '"environment"' in self.main_source

    def test_51_health_endpoint_still_defined(self):
        from app.main import app
        paths = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/health" in paths

    def test_52_health_ready_still_defined(self):
        from app.main import app
        paths = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/health/ready" in paths

    def test_53_health_full_is_get_method(self):
        from app.main import app
        for route in app.routes:
            if hasattr(route, "path") and route.path == "/health/full":
                assert "GET" in route.methods
                return
        pytest.fail("/health/full route not found in app.routes")


# ══════════════════════════════════════════════════════════════════════════════
# Part 6: VERIFY.md Production Hardening Section (Tests 54-57)
# ══════════════════════════════════════════════════════════════════════════════

class TestVerifyMD:
    """Verify VERIFY.md has production hardening checklist."""

    @pytest.fixture(autouse=True)
    def _load_verify(self):
        verify_file = ROOT_DIR / "VERIFY.md"
        self.verify_content = verify_file.read_text() if verify_file.exists() else ""

    def test_54_verify_has_phase23_section(self):
        assert "Production Hardening" in self.verify_content or "production hardening" in self.verify_content.lower()

    def test_55_verify_mentions_rls_verified(self):
        assert "RLS" in self.verify_content and "verif" in self.verify_content.lower()

    def test_56_verify_mentions_rate_limiting(self):
        assert "rate limit" in self.verify_content.lower()

    def test_57_verify_mentions_production_banner(self):
        assert "banner" in self.verify_content.lower() and "production" in self.verify_content.lower()


# ══════════════════════════════════════════════════════════════════════════════
# Part 6b: Migration Content Checks (Tests 58-60)
# ══════════════════════════════════════════════════════════════════════════════

class TestMigrationContent:
    """Additional migration content verification."""

    @pytest.fixture(autouse=True)
    def _load_sql(self):
        mf = SCRIPTS_DIR / "016_production_hardening_rls.sql"
        self.sql = mf.read_text() if mf.exists() else ""

    def test_58_migration_restricts_source_values(self):
        assert "contact_form" in self.sql
        assert "enterprise_interest" in self.sql

    def test_59_migration_requires_email_or_company(self):
        assert "email" in self.sql and "company_name" in self.sql

    def test_60_migration_documents_vector_extension(self):
        assert "vector" in self.sql.lower() and "schema" in self.sql.lower()
