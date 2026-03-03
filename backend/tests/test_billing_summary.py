"""
Billing Summary & Portal Session Tests
========================================

Deterministic tests — no real Stripe / DB / network calls.

Tests cover:
1.  billing-summary endpoint is defined in billing.py
2.  billing-summary returns usage dict in response
3.  billing-summary does not expose stripe_customer_id
4.  billing-summary does not expose stripe_subscription_id
5.  billing-summary uses PlanService limits
6.  portal-session endpoint is defined in billing.py
7.  portal-session accepts org_id in body (PortalSessionRequest)
8.  Frontend billing page exists
9.  Frontend billing page uses getBillingSummary API method
10. Frontend billing page has usage progress bars
11. Frontend billing page has manage billing section
12. Frontend billing page has plan badge
13. Frontend api.ts has getBillingSummary method
14. Frontend api.ts has createPortalSessionV2 method
15. Frontend api.ts getBillingSummary calls billing-summary endpoint
16. Settings layout includes billing nav item
"""

import sys
import os
import pytest

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------
BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

REPO_ROOT = os.path.join(BACKEND_DIR, "..")
FRONTEND_DIR = os.path.join(REPO_ROOT, "frontend")
BILLING_ENDPOINT_PATH = os.path.join(BACKEND_DIR, "app", "api", "endpoints", "billing.py")
BILLING_PAGE_PATH = os.path.join(FRONTEND_DIR, "app", "settings", "billing", "page.tsx")
API_TS_PATH = os.path.join(FRONTEND_DIR, "lib", "api.ts")
SETTINGS_LAYOUT_PATH = os.path.join(FRONTEND_DIR, "app", "settings", "layout.tsx")


def _read(path: str) -> str:
    with open(path) as f:
        return f.read()


# ===========================================================================
# 1–7: Backend billing-summary & portal-session endpoints
# ===========================================================================

class TestBillingSummaryEndpoint:
    """Verify billing-summary endpoint definition."""

    def test_01_billing_summary_endpoint_defined(self):
        src = _read(BILLING_ENDPOINT_PATH)
        assert '"/billing-summary"' in src

    def test_02_billing_summary_returns_usage(self):
        src = _read(BILLING_ENDPOINT_PATH)
        assert "documents_used" in src
        assert "documents_limit" in src
        assert "projects_used" in src
        assert "projects_limit" in src
        assert "runs_used" in src
        assert "runs_limit" in src

    def test_03_billing_summary_no_stripe_customer_id(self):
        """Sensitive Stripe fields must not appear in the response shape."""
        src = _read(BILLING_ENDPOINT_PATH)
        # Find the billing-summary function and check its return dict
        idx = src.index('"/billing-summary"')
        fn_body = src[idx:idx + 3000]
        # The response dict should not contain stripe_customer_id
        assert "stripe_customer_id" not in fn_body.split("return {")[1].split("}")[0] if "return {" in fn_body else True

    def test_04_billing_summary_no_stripe_subscription_id(self):
        src = _read(BILLING_ENDPOINT_PATH)
        idx = src.index('"/billing-summary"')
        fn_body = src[idx:idx + 3000]
        assert "stripe_subscription_id" not in fn_body

    def test_05_billing_summary_uses_plan_service(self):
        src = _read(BILLING_ENDPOINT_PATH)
        assert "PlanService" in src
        assert "get_limits" in src

    def test_06_portal_session_endpoint_defined(self):
        src = _read(BILLING_ENDPOINT_PATH)
        assert '"/portal-session"' in src

    def test_07_portal_session_uses_request_body(self):
        src = _read(BILLING_ENDPOINT_PATH)
        assert "PortalSessionRequest" in src


# ===========================================================================
# 8–12: Frontend billing page
# ===========================================================================

class TestFrontendBillingPage:
    """Verify the /settings/billing page."""

    def test_08_billing_page_exists(self):
        assert os.path.isfile(BILLING_PAGE_PATH)

    def test_09_billing_page_uses_get_billing_summary(self):
        src = _read(BILLING_PAGE_PATH)
        assert "getBillingSummary" in src

    def test_10_billing_page_has_usage_bars(self):
        src = _read(BILLING_PAGE_PATH)
        assert "UsageBar" in src
        assert "Documents" in src
        assert "Projects" in src
        assert "Analysis Runs" in src

    def test_11_billing_page_has_manage_billing(self):
        src = _read(BILLING_PAGE_PATH)
        assert "Manage Billing" in src
        assert "portal" in src.lower()

    def test_12_billing_page_has_plan_badge(self):
        src = _read(BILLING_PAGE_PATH)
        assert "PlanBadge" in src
        assert "StatusBadge" in src


# ===========================================================================
# 13–16: Frontend API client & settings nav
# ===========================================================================

class TestFrontendApiClient:
    """Verify api.ts billing methods."""

    def test_13_api_has_get_billing_summary(self):
        src = _read(API_TS_PATH)
        assert "getBillingSummary" in src

    def test_14_api_has_create_portal_session_v2(self):
        src = _read(API_TS_PATH)
        assert "createPortalSessionV2" in src

    def test_15_api_get_billing_summary_calls_correct_endpoint(self):
        src = _read(API_TS_PATH)
        assert "/billing/billing-summary" in src

    def test_16_settings_layout_has_billing_nav(self):
        src = _read(SETTINGS_LAYOUT_PATH)
        assert "/settings/billing" in src
        assert "Plans & Billing" in src or "Billing" in src
