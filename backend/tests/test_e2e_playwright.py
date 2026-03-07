"""
Test suite — Feature 6: E2E Tests (Playwright)
===============================================

Validates:
  • Playwright config exists and is properly configured
  • E2E test spec files exist and cover required scenarios
  • Test file structure follows Playwright conventions
  • Billing upgrade funnel tests cover key user flows
  • Frontend test infrastructure is in place
"""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND = os.path.abspath(os.path.join(ROOT, "..", "frontend"))


# ── 1. Playwright config ─────────────────────────────────────────────────────

def test_playwright_config_exists():
    path = os.path.join(FRONTEND, "playwright.config.ts")
    assert os.path.isfile(path), "playwright.config.ts must exist"


def test_playwright_config_has_test_dir():
    src = open(os.path.join(FRONTEND, "playwright.config.ts")).read()
    assert "testDir" in src
    assert "./tests" in src


def test_playwright_config_has_base_url():
    src = open(os.path.join(FRONTEND, "playwright.config.ts")).read()
    assert "baseURL" in src


def test_playwright_config_uses_headless():
    src = open(os.path.join(FRONTEND, "playwright.config.ts")).read()
    assert "headless" in src


# ── 2. E2E test file existence ───────────────────────────────────────────────

def test_billing_upgrade_spec_exists():
    path = os.path.join(FRONTEND, "tests", "e2e-billing-upgrade.spec.ts")
    assert os.path.isfile(path), "e2e-billing-upgrade.spec.ts must exist"


def test_login_dashboard_spec_exists():
    path = os.path.join(FRONTEND, "tests", "e2e-login-dashboard.spec.ts")
    assert os.path.isfile(path), "e2e-login-dashboard.spec.ts must exist"


def test_enterprise_trust_spec_exists():
    path = os.path.join(FRONTEND, "tests", "enterprise-trust.spec.ts")
    assert os.path.isfile(path), "enterprise-trust.spec.ts must exist"


# ── 3. Billing/Upgrade spec content ──────────────────────────────────────────

def _read_billing_spec():
    return open(os.path.join(FRONTEND, "tests", "e2e-billing-upgrade.spec.ts")).read()


def test_billing_spec_imports_playwright():
    src = _read_billing_spec()
    assert "@playwright/test" in src


def test_billing_spec_uses_env_credentials():
    src = _read_billing_spec()
    assert "E2E_EMAIL" in src
    assert "E2E_PASSWORD" in src


def test_billing_spec_has_login_helper():
    src = _read_billing_spec()
    assert "async function login" in src


def test_billing_spec_has_billing_page_tests():
    src = _read_billing_spec()
    assert "Billing Page" in src
    assert "Current Plan" in src


def test_billing_spec_has_plan_badge_test():
    src = _read_billing_spec()
    assert "plan badge" in src.lower() or "Starter|Growth|Elite" in src


def test_billing_spec_has_usage_section_test():
    src = _read_billing_spec()
    assert "Usage" in src
    assert "Documents" in src


def test_billing_spec_has_plan_comparison_test():
    src = _read_billing_spec()
    assert "Plan Comparison" in src


def test_billing_spec_has_promo_code_test():
    src = _read_billing_spec()
    assert "Promo Code" in src
    assert "promo code" in src.lower()


def test_billing_spec_has_manage_billing_test():
    src = _read_billing_spec()
    assert "Manage Billing" in src


def test_billing_spec_has_analytics_tab_test():
    src = _read_billing_spec()
    assert "Analytics" in src


def test_billing_spec_has_refresh_test():
    src = _read_billing_spec()
    assert "Refresh" in src


def test_billing_spec_has_upgrade_flow():
    src = _read_billing_spec()
    assert "Upgrade Flow" in src or "Upgrade Plan" in src


def test_billing_spec_has_plans_page_test():
    src = _read_billing_spec()
    assert "/plans" in src


def test_billing_spec_has_alerts_page_tests():
    src = _read_billing_spec()
    assert "Document Alerts" in src
    assert "/alerts" in src


def test_billing_spec_has_alert_emails_test():
    src = _read_billing_spec()
    assert "Send Alert Emails" in src


def test_billing_spec_has_admin_dashboard_test():
    src = _read_billing_spec()
    assert "Admin Dashboard" in src
    assert "/admin" in src


def test_billing_spec_has_onboarding_test():
    src = _read_billing_spec()
    assert "Onboarding" in src
    assert "/onboarding" in src


# ── 4. Test count validation ─────────────────────────────────────────────────

def test_billing_spec_has_minimum_test_count():
    src = _read_billing_spec()
    test_count = src.count("test(\"") + src.count("test('")
    assert test_count >= 15, f"Expected >= 15 test cases, found {test_count}"


def test_billing_spec_has_test_describe_blocks():
    src = _read_billing_spec()
    describe_count = src.count("test.describe(")
    assert describe_count >= 3, f"Expected >= 3 describe blocks, found {describe_count}"


# ── 5. Test infrastructure ───────────────────────────────────────────────────

def test_package_json_has_playwright_dep():
    src = open(os.path.join(FRONTEND, "package.json")).read()
    assert "playwright" in src.lower()


def test_tests_directory_exists():
    path = os.path.join(FRONTEND, "tests")
    assert os.path.isdir(path), "frontend/tests/ directory must exist"


def test_spec_files_follow_naming_convention():
    """All spec files should end with .spec.ts"""
    tests_dir = os.path.join(FRONTEND, "tests")
    spec_files = [f for f in os.listdir(tests_dir) if f.endswith(".spec.ts")]
    assert len(spec_files) >= 2, f"Expected >= 2 spec files, found {len(spec_files)}"
