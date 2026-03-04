"""
Stripe Billing Integration Tests

All tests are deterministic — no real Stripe / DB / network calls.

Tests cover:
1.  MigrationSQL — 013_stripe_billing.sql exists on disk
2.  MigrationSQL — stripe_customer_id column added to subscriptions
3.  MigrationSQL — stripe_subscription_id column added to subscriptions
4.  MigrationSQL — stripe_status column with CHECK constraint
5.  MigrationSQL — current_period_end column added
6.  MigrationSQL — subscriptions_stripe_customer_idx index defined
7.  MigrationSQL — subscriptions_stripe_sub_idx index defined
8.  MigrationSQL — billing_events table created
9.  MigrationSQL — billing_events has stripe_event_id UNIQUE column
10. MigrationSQL — billing_events RLS enabled
11. MigrationSQL — billing_events org_idx index defined
12. StripeBilling — stripe_billing module importable
13. StripeBilling — _price_map returns FREE/PRO/ENTERPRISE keys
14. StripeBilling — _price_to_plan reverses _price_map
15. StripeBilling — create_checkout_session importable and callable
16. StripeBilling — create_checkout_session raises RuntimeError when no Stripe key
17. StripeBilling — create_checkout_session raises ValueError for unknown plan
18. StripeBilling — handle_webhook_event importable and callable
19. StripeBilling — handle_webhook_event raises HTTP 503 when no webhook secret
20. StripeBilling — get_subscription_status importable and callable
21. StripeBilling — get_subscription_status returns is_active=True on DB error (fail-open)
22. StripeBilling — get_subscription_status returns org_id in result
23. StripeBilling — check_subscription_active importable and callable
24. StripeBilling — check_subscription_active does not raise when no DB row (new org)
25. StripeBilling — check_subscription_active raises HTTP 402 SUBSCRIPTION_INACTIVE for past_due
26. StripeBilling — check_subscription_active raises HTTP 402 for canceled status
27. StripeBilling — check_subscription_active does NOT raise for active status
28. StripeBilling — check_subscription_active does NOT raise for trialing status
29. StripeBilling — check_subscription_active fails-open on DB error (no raise)
30. StripeBilling — start_pro_trial importable and callable
31. StripeBilling — start_pro_trial returns dict with plan_name=PRO
32. StripeBilling — start_pro_trial returns stripe_status=trialing
33. StripeBilling — start_pro_trial never raises even on DB error
34. StripeBilling — ACTIVE_STATUSES contains active, trialing, and empty string
35. Config — STRIPE_PRICE_FREE setting exists in config
36. Config — STRIPE_PRICE_PRO setting exists in config
37. Config — STRIPE_PRICE_ENTERPRISE setting exists in config
38. Config — STRIPE_TRIAL_DAYS setting exists and defaults to 14
39. Enforcement — routes.py wires check_subscription_active to /ingest
40. Enforcement — routes.py wires check_subscription_active to /analyze-excel
41. Enforcement — runs.py wires check_subscription_active in generate_evidence_package
42. BillingEndpoint — /billing/checkout endpoint defined in billing.py
43. BillingEndpoint — /billing/webhook19 endpoint defined in billing.py
44. BillingEndpoint — /billing/status endpoint defined in billing.py
45. BillingEndpoint — /billing/trial endpoint defined in billing.py
46. ApiClient — createStripeCheckout method exists in api.ts
47. ApiClient — getSubscriptionStatus method exists in api.ts
48. ApiClient — startProTrial method exists in api.ts
49. ApiClient — subscription:inactive CustomEvent dispatched on 402 SUBSCRIPTION_INACTIVE
50. Frontend — SubscriptionInactiveModal component file exists on disk
51. Frontend — BillingPastDueBanner component file exists on disk
52. Frontend — settings/billing page file exists on disk
53. Frontend — layout.tsx imports SubscriptionInactiveModal
54. Frontend — AppShell.tsx imports BillingPastDueBanner
"""

import sys
import os
import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------
BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

REPO_ROOT = os.path.join(BACKEND_DIR, "..")

SQL_PATH = os.path.join(BACKEND_DIR, "scripts", "013_stripe_billing.sql")
API_TS_PATH = os.path.join(REPO_ROOT, "frontend", "lib", "api.ts")
LAYOUT_PATH = os.path.join(REPO_ROOT, "frontend", "app", "layout.tsx")
APPSHELL_PATH = os.path.join(REPO_ROOT, "frontend", "components", "layout", "AppShell.tsx")
BILLING_ENDPOINT_PATH = os.path.join(BACKEND_DIR, "app", "api", "endpoints", "billing.py")
ROUTES_PATH = os.path.join(BACKEND_DIR, "app", "api", "routes.py")
RUNS_ENDPOINT_PATH = os.path.join(BACKEND_DIR, "app", "api", "endpoints", "runs.py")
SUB_INACTIVE_MODAL_PATH = os.path.join(REPO_ROOT, "frontend", "components", "SubscriptionInactiveModal.tsx")
PAST_DUE_BANNER_PATH = os.path.join(REPO_ROOT, "frontend", "components", "BillingPastDueBanner.tsx")
BILLING_PAGE_PATH = os.path.join(REPO_ROOT, "frontend", "app", "settings", "billing", "page.tsx")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sql() -> str:
    with open(SQL_PATH) as f:
        return f.read()


def _read(path: str) -> str:
    with open(path) as f:
        return f.read()


# ===========================================================================
# 1–11: Migration SQL
# ===========================================================================

def test_01_migration_sql_exists():
    assert os.path.isfile(SQL_PATH), f"Stripe billing migration SQL not found: {SQL_PATH}"


def test_02_stripe_customer_id_column():
    assert "stripe_customer_id" in _sql()


def test_03_stripe_subscription_id_column():
    assert "stripe_subscription_id" in _sql()


def test_04_stripe_status_with_check_constraint():
    sql = _sql()
    assert "stripe_status" in sql
    # CHECK constraint must include the valid status values
    assert "past_due" in sql
    assert "trialing" in sql
    assert "canceled" in sql


def test_05_current_period_end_column():
    assert "current_period_end" in _sql()


def test_06_stripe_customer_idx_defined():
    assert "subscriptions_stripe_customer_idx" in _sql()


def test_07_stripe_sub_idx_defined():
    assert "subscriptions_stripe_sub_idx" in _sql()


def test_08_billing_events_table_created():
    assert "billing_events" in _sql()
    assert "CREATE TABLE IF NOT EXISTS billing_events" in _sql()


def test_09_billing_events_stripe_event_id_unique():
    sql = _sql()
    assert "stripe_event_id" in sql
    assert "UNIQUE" in sql


def test_10_billing_events_rls_enabled():
    sql = _sql()
    assert "ENABLE ROW LEVEL SECURITY" in sql


def test_11_billing_events_org_idx_defined():
    assert "billing_events_org_idx" in _sql()


# ===========================================================================
# 12–34: stripe_billing.py module
# ===========================================================================

def test_12_stripe_billing_importable():
    import app.core.stripe_billing  # noqa: F401


def test_13_price_map_has_three_plans():
    from app.core.stripe_billing import _price_map
    pm = _price_map()
    assert "FREE" in pm
    assert "PRO" in pm
    assert "ENTERPRISE" in pm


def test_14_price_to_plan_is_reverse_of_price_map():
    from app.core.stripe_billing import _price_map, _price_to_plan
    # Set env so there's something to reverse
    with patch.dict(os.environ, {"STRIPE_PRICE_PRO": "price_pro_test"}):
        p2p = _price_to_plan()
        assert p2p.get("price_pro_test") == "PRO"


def test_15_create_checkout_session_importable():
    from app.core.stripe_billing import create_checkout_session
    assert callable(create_checkout_session)


def test_16_create_checkout_raises_runtime_when_no_key():
    from app.core.stripe_billing import create_checkout_session
    with patch.dict(os.environ, {"STRIPE_SECRET_KEY": ""}):
        with pytest.raises(RuntimeError, match="Stripe is not configured"):
            create_checkout_session("org-1", "PRO", "https://ok", "https://cancel")


def test_17_create_checkout_raises_value_error_unknown_plan():
    from app.core.stripe_billing import create_checkout_session
    with patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_fake"}):
        # No price ID configured for ULTRA
        with pytest.raises(ValueError):
            create_checkout_session("org-1", "ULTRA", "https://ok", "https://cancel")


def test_18_handle_webhook_event_importable():
    from app.core.stripe_billing import handle_webhook_event
    assert callable(handle_webhook_event)


def test_19_handle_webhook_raises_503_when_no_secret():
    from app.core.stripe_billing import handle_webhook_event
    with patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": ""}):
        with pytest.raises(HTTPException) as exc:
            handle_webhook_event(b"payload", "sig_header")
    assert exc.value.status_code == 503


def test_20_get_subscription_status_importable():
    from app.core.stripe_billing import get_subscription_status
    assert callable(get_subscription_status)


def test_21_get_subscription_status_fail_open_on_db_error():
    from app.core.stripe_billing import get_subscription_status

    def _raise(*a, **kw):
        raise RuntimeError("DB offline")

    with patch("app.core.stripe_billing._admin_sb", side_effect=_raise):
        result = get_subscription_status("org-fail")

    assert result["is_active"] is True  # fail-open


def test_22_get_subscription_status_returns_org_id():
    from app.core.stripe_billing import get_subscription_status

    def _raise(*a, **kw):
        raise RuntimeError("DB offline")

    with patch("app.core.stripe_billing._admin_sb", side_effect=_raise):
        result = get_subscription_status("org-abc")

    assert result["org_id"] == "org-abc"


def test_23_check_subscription_active_importable():
    from app.core.stripe_billing import check_subscription_active
    assert callable(check_subscription_active)


def test_24_check_subscription_active_passes_when_no_row():
    """New org with no subscription row → treated as active (fail-open)."""
    from app.core.stripe_billing import check_subscription_active

    fake_res = MagicMock()
    fake_res.data = None

    fake_q = MagicMock()
    fake_q.eq.return_value = fake_q
    fake_q.single.return_value = fake_q
    fake_q.execute.return_value = fake_res

    fake_tbl = MagicMock()
    fake_tbl.select.return_value = fake_q

    fake_sb = MagicMock()
    fake_sb.table.return_value = fake_tbl

    with patch("app.core.stripe_billing._admin_sb", return_value=fake_sb):
        check_subscription_active("org-new")  # must not raise


def test_25_check_subscription_active_raises_402_for_past_due():
    from app.core.stripe_billing import check_subscription_active

    fake_res = MagicMock()
    fake_res.data = {"stripe_status": "past_due"}

    fake_q = MagicMock()
    fake_q.eq.return_value = fake_q
    fake_q.single.return_value = fake_q
    fake_q.execute.return_value = fake_res

    fake_tbl = MagicMock()
    fake_tbl.select.return_value = fake_q

    fake_sb = MagicMock()
    fake_sb.table.return_value = fake_tbl

    with patch("app.core.stripe_billing._admin_sb", return_value=fake_sb):
        with pytest.raises(HTTPException) as exc:
            check_subscription_active("org-x")

    assert exc.value.status_code == 402
    assert exc.value.detail["error"] == "SUBSCRIPTION_INACTIVE"
    assert exc.value.detail["stripe_status"] == "past_due"


def test_26_check_subscription_active_raises_402_for_canceled():
    from app.core.stripe_billing import check_subscription_active

    fake_res = MagicMock()
    fake_res.data = {"stripe_status": "canceled"}

    fake_q = MagicMock()
    fake_q.eq.return_value = fake_q
    fake_q.single.return_value = fake_q
    fake_q.execute.return_value = fake_res

    fake_tbl = MagicMock()
    fake_tbl.select.return_value = fake_q

    fake_sb = MagicMock()
    fake_sb.table.return_value = fake_tbl

    with patch("app.core.stripe_billing._admin_sb", return_value=fake_sb):
        with pytest.raises(HTTPException) as exc:
            check_subscription_active("org-y")

    assert exc.value.status_code == 402


def test_27_check_subscription_active_passes_for_active():
    from app.core.stripe_billing import check_subscription_active

    fake_res = MagicMock()
    fake_res.data = {"stripe_status": "active"}

    fake_q = MagicMock()
    fake_q.eq.return_value = fake_q
    fake_q.single.return_value = fake_q
    fake_q.execute.return_value = fake_res

    fake_tbl = MagicMock()
    fake_tbl.select.return_value = fake_q

    fake_sb = MagicMock()
    fake_sb.table.return_value = fake_tbl

    with patch("app.core.stripe_billing._admin_sb", return_value=fake_sb):
        check_subscription_active("org-active")  # must not raise


def test_28_check_subscription_active_passes_for_trialing():
    from app.core.stripe_billing import check_subscription_active

    fake_res = MagicMock()
    fake_res.data = {"stripe_status": "trialing"}

    fake_q = MagicMock()
    fake_q.eq.return_value = fake_q
    fake_q.single.return_value = fake_q
    fake_q.execute.return_value = fake_res

    fake_tbl = MagicMock()
    fake_tbl.select.return_value = fake_q

    fake_sb = MagicMock()
    fake_sb.table.return_value = fake_tbl

    with patch("app.core.stripe_billing._admin_sb", return_value=fake_sb):
        check_subscription_active("org-trial")  # must not raise


def test_29_check_subscription_active_fails_open_on_db_error():
    from app.core.stripe_billing import check_subscription_active

    def _raise(*a, **kw):
        raise RuntimeError("connection refused")

    with patch("app.core.stripe_billing._admin_sb", side_effect=_raise):
        check_subscription_active("org-db-down")  # must not raise


def test_30_start_pro_trial_importable():
    from app.core.stripe_billing import start_pro_trial
    assert callable(start_pro_trial)


def test_31_start_pro_trial_returns_pro_plan():
    from app.core.stripe_billing import start_pro_trial

    def _raise(*a, **kw):
        raise RuntimeError("DB offline")  # simulate DB unavailable

    with patch("app.core.stripe_billing._admin_sb", side_effect=_raise):
        result = start_pro_trial("org-trial")

    assert result["plan_name"] == "PRO"


def test_32_start_pro_trial_returns_trialing_status():
    from app.core.stripe_billing import start_pro_trial

    def _raise(*a, **kw):
        raise RuntimeError("DB offline")

    with patch("app.core.stripe_billing._admin_sb", side_effect=_raise):
        result = start_pro_trial("org-trial")

    assert result["stripe_status"] == "trialing"


def test_33_start_pro_trial_never_raises_on_db_error():
    from app.core.stripe_billing import start_pro_trial

    def _raise(*a, **kw):
        raise RuntimeError("network timeout")

    with patch("app.core.stripe_billing._admin_sb", side_effect=_raise):
        try:
            start_pro_trial("org-trial")
        except Exception:
            pytest.fail("start_pro_trial raised an exception on DB error")


def test_34_active_statuses_contains_expected_values():
    from app.core.stripe_billing import ACTIVE_STATUSES
    assert "active" in ACTIVE_STATUSES
    assert "trialing" in ACTIVE_STATUSES
    assert "" in ACTIVE_STATUSES  # empty string = no Stripe yet → treated as active


# ===========================================================================
# 35–38: Config settings
# ===========================================================================

def test_35_config_has_stripe_price_free():
    from app.core.config import Settings
    assert hasattr(Settings, "model_fields")
    s = Settings()
    assert hasattr(s, "STRIPE_PRICE_FREE")


def test_36_config_has_stripe_price_pro():
    from app.core.config import Settings
    s = Settings()
    assert hasattr(s, "STRIPE_PRICE_PRO")


def test_37_config_has_stripe_price_enterprise():
    from app.core.config import Settings
    s = Settings()
    assert hasattr(s, "STRIPE_PRICE_ENTERPRISE")


def test_38_config_stripe_trial_days_defaults_to_14():
    from app.core.config import Settings
    s = Settings()
    assert hasattr(s, "STRIPE_TRIAL_DAYS")
    assert s.STRIPE_TRIAL_DAYS == 14


# ===========================================================================
# 39–41: Enforcement wiring (source-level checks)
# ===========================================================================

def test_39_routes_wires_check_subscription_active_to_ingest():
    src = _read(ROUTES_PATH)
    assert "check_subscription_active" in src
    # Must appear in the /ingest handler section
    ingest_idx = src.find('"/ingest"')
    if ingest_idx == -1:
        ingest_idx = src.find("'/ingest'")
    assert ingest_idx != -1, "/ingest route not found in routes.py"
    # check_subscription_active must appear after /ingest definition
    assert "check_subscription_active" in src[ingest_idx:]


def test_40_routes_wires_check_subscription_active_to_analyze_excel():
    src = _read(ROUTES_PATH)
    excel_idx = src.find('"/analyze-excel"')
    if excel_idx == -1:
        excel_idx = src.find("'/analyze-excel'")
    assert excel_idx != -1, "/analyze-excel route not found in routes.py"
    assert "check_subscription_active" in src[excel_idx:]


def test_41_runs_wires_check_subscription_active_in_generate_evidence():
    src = _read(RUNS_ENDPOINT_PATH)
    gen_idx = src.find("generate_evidence_package")
    assert gen_idx != -1, "generate_evidence_package not found in runs.py"
    # check_subscription_active must appear somewhere in the function body
    # (after the function definition)
    assert "check_subscription_active" in src[gen_idx:]


# ===========================================================================
# 42–45: Billing endpoint definitions
# ===========================================================================

def test_42_billing_endpoint_has_checkout():
    src = _read(BILLING_ENDPOINT_PATH)
    assert '"/checkout"' in src or "'/checkout'" in src


def test_43_billing_endpoint_has_webhook19():
    src = _read(BILLING_ENDPOINT_PATH)
    assert '"/webhook19"' in src or "'/webhook19'" in src


def test_44_billing_endpoint_has_status():
    src = _read(BILLING_ENDPOINT_PATH)
    # The billing status route
    assert '"/status"' in src or "'/status'" in src


def test_45_billing_endpoint_has_trial():
    src = _read(BILLING_ENDPOINT_PATH)
    assert '"/trial"' in src or "'/trial'" in src


# ===========================================================================
# 46–49: ApiClient (api.ts) source-level checks
# ===========================================================================

def test_46_api_ts_has_create_stripe_checkout():
    assert "createStripeCheckout" in _read(API_TS_PATH)


def test_47_api_ts_has_get_subscription_status():
    assert "getSubscriptionStatus" in _read(API_TS_PATH)


def test_48_api_ts_has_start_pro_trial():
    assert "startProTrial" in _read(API_TS_PATH)


def test_49_api_ts_dispatches_subscription_inactive_event():
    src = _read(API_TS_PATH)
    assert "subscription:inactive" in src
    assert "SUBSCRIPTION_INACTIVE" in src


# ===========================================================================
# 50–54: Frontend file existence checks
# ===========================================================================

def test_50_subscription_inactive_modal_exists():
    assert os.path.isfile(SUB_INACTIVE_MODAL_PATH), (
        f"SubscriptionInactiveModal.tsx not found at {SUB_INACTIVE_MODAL_PATH}"
    )


def test_51_billing_past_due_banner_exists():
    assert os.path.isfile(PAST_DUE_BANNER_PATH), (
        f"BillingPastDueBanner.tsx not found at {PAST_DUE_BANNER_PATH}"
    )


def test_52_billing_settings_page_exists():
    assert os.path.isfile(BILLING_PAGE_PATH), (
        f"settings/billing/page.tsx not found at {BILLING_PAGE_PATH}"
    )


def test_53_layout_imports_subscription_inactive_modal():
    src = _read(LAYOUT_PATH)
    assert "SubscriptionInactiveModal" in src


def test_54_appshell_imports_billing_past_due_banner():
    src = _read(APPSHELL_PATH)
    assert "BillingPastDueBanner" in src
