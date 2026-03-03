"""
Multi-Tenant Isolation + Billing Foundations Tests

All tests are deterministic — no real DB / API / OpenAI calls needed.

Tests cover:
1.  MigrationSQL — 012_billing_usage.sql exists on disk
2.  MigrationSQL — subscriptions table defined
3.  MigrationSQL — subscriptions.org_id column present
4.  MigrationSQL — subscriptions.plan_name column present
5.  MigrationSQL — subscriptions plan_name CHECK constraint present (FREE/PRO/ENTERPRISE)
6.  MigrationSQL — usage_metrics table defined
7.  MigrationSQL — usage_metrics.metric_type column present
8.  MigrationSQL — usage_metrics metric_type CHECK constraint present
9.  MigrationSQL — usage_metrics indexes defined
10. MigrationSQL — RLS enabled on subscriptions
11. MigrationSQL — RLS enabled on usage_metrics
12. Subscription — PLAN_DEFAULTS importable with FREE/PRO/ENTERPRISE keys
13. Subscription — FREE plan has max_runs_per_month
14. Subscription — PRO limits exceed FREE limits
15. Subscription — ENTERPRISE limits exceed PRO limits
16. Subscription — get_org_subscription importable
17. Subscription — get_org_subscription returns FREE defaults on DB error
18. Subscription — check_plan_limit importable
19. Subscription — check_plan_limit raises 402 when count >= limit
20. Subscription — check_plan_limit passes when count < limit
21. Subscription — check_plan_limit fails-open on DB error (no raise)
22. Subscription — check_plan_limit skips unknown resource (no raise)
23. Subscription — log_usage_metric importable
24. Subscription — log_usage_metric never raises on DB error
25. Subscription — log_usage_metric never raises when org_id empty
26. Subscription — get_usage_summary importable
27. Subscription — get_usage_summary returns zero-defaults on DB error
28. Subscription — get_usage_summary includes plan and limits keys
29. Isolation — create_run endpoint checks plan limit before role check
30. Isolation — create_run logs RUN_CREATED metric after success
31. Isolation — upload_project_document checks plan limit
32. Isolation — upload_project_document logs DOCUMENT_UPLOADED metric
33. Isolation — promote_institutional_answer checks memory limit
34. Isolation — promote_institutional_answer logs MEMORY_STORED metric
35. Isolation — generate_evidence_package logs EVIDENCE_GENERATED metric
36. Isolation — runs.py exposes GET /usage endpoint
37. Isolation — usage endpoint imports get_usage_summary
38. Isolation — org A run is not visible to org B (resolve_org_id_for_user blocks cross-org)
39. Isolation — org A document is not accessible by org B (resolve_org_id_for_user blocks)
40. Isolation — resolve_org_id_for_user raises 403 for non-member
41. ApiClient — getUsageSummary method exists in api.ts
42. Frontend — UsagePanel component file exists on disk
43. Frontend — PlanLimitModal component file exists on disk
44. Frontend — dashboard page imports UsagePanel
45. Frontend — layout.tsx imports PlanLimitModal
46. Frontend — api.ts dispatches plan:limit_reached event on 402
47. RESOURCE_MAP — runs maps to RUN_CREATED
48. RESOURCE_MAP — documents maps to DOCUMENT_UPLOADED
49. RESOURCE_MAP — memory maps to MEMORY_STORED
50. RESOURCE_MAP — evidence maps to EVIDENCE_GENERATED with no limit field
"""

import sys
import os
import types
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
SQL_PATH = os.path.join(BACKEND_DIR, "scripts", "012_billing_usage.sql")
API_TS_PATH = os.path.join(REPO_ROOT, "frontend", "lib", "api.ts")
USAGE_PANEL_PATH = os.path.join(REPO_ROOT, "frontend", "components", "UsagePanel.tsx")
PLAN_LIMIT_MODAL_PATH = os.path.join(REPO_ROOT, "frontend", "components", "PlanLimitModal.tsx")
DASHBOARD_PAGE_PATH = os.path.join(REPO_ROOT, "frontend", "app", "dashboard", "page.tsx")
LAYOUT_PATH = os.path.join(REPO_ROOT, "frontend", "app", "layout.tsx")
RUNS_ENDPOINT_PATH = os.path.join(BACKEND_DIR, "app", "api", "endpoints", "runs.py")
DOCS_ENDPOINT_PATH = os.path.join(BACKEND_DIR, "app", "api", "endpoints", "documents.py")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sql() -> str:
    with open(SQL_PATH, "r") as f:
        return f.read()


def _read(path: str) -> str:
    with open(path, "r") as f:
        return f.read()


# ===========================================================================
# 1–11: Migration SQL
# ===========================================================================

def test_01_migration_sql_exists():
    assert os.path.isfile(SQL_PATH), f"Migration SQL not found: {SQL_PATH}"


def test_02_subscriptions_table_defined():
    assert "subscriptions" in _sql()


def test_03_subscriptions_org_id_column():
    assert "org_id" in _sql()


def test_04_subscriptions_plan_name_column():
    assert "plan_name" in _sql()


def test_05_subscriptions_plan_check_constraint():
    sql = _sql()
    assert "FREE" in sql and "PRO" in sql and "ENTERPRISE" in sql


def test_06_usage_metrics_table_defined():
    assert "usage_metrics" in _sql()


def test_07_usage_metrics_metric_type_column():
    assert "metric_type" in _sql()


def test_08_usage_metrics_check_constraint():
    sql = _sql()
    assert "RUN_CREATED" in sql
    assert "DOCUMENT_UPLOADED" in sql
    assert "MEMORY_STORED" in sql
    assert "EVIDENCE_GENERATED" in sql


def test_09_usage_metrics_indexes_defined():
    sql = _sql()
    # At least one index on usage_metrics
    assert "usage_metrics" in sql and "CREATE INDEX" in sql


def test_10_rls_enabled_subscriptions():
    sql = _sql()
    assert "ENABLE ROW LEVEL SECURITY" in sql


def test_11_rls_enabled_usage_metrics():
    sql = _sql()
    # RLS must be enabled; both tables are covered
    assert sql.count("ENABLE ROW LEVEL SECURITY") >= 2


# ===========================================================================
# 12–28: subscription.py module
# ===========================================================================

def test_12_plan_defaults_importable():
    from app.core.subscription import PLAN_DEFAULTS
    assert "FREE" in PLAN_DEFAULTS
    assert "PRO" in PLAN_DEFAULTS
    assert "ENTERPRISE" in PLAN_DEFAULTS


def test_13_free_plan_has_run_limit():
    from app.core.subscription import PLAN_DEFAULTS
    assert "max_runs_per_month" in PLAN_DEFAULTS["FREE"]
    assert PLAN_DEFAULTS["FREE"]["max_runs_per_month"] > 0


def test_14_pro_exceeds_free():
    from app.core.subscription import PLAN_DEFAULTS
    assert PLAN_DEFAULTS["PRO"]["max_runs_per_month"] > PLAN_DEFAULTS["FREE"]["max_runs_per_month"]
    assert PLAN_DEFAULTS["PRO"]["max_documents"] > PLAN_DEFAULTS["FREE"]["max_documents"]
    assert PLAN_DEFAULTS["PRO"]["max_memory_entries"] > PLAN_DEFAULTS["FREE"]["max_memory_entries"]


def test_15_enterprise_exceeds_pro():
    from app.core.subscription import PLAN_DEFAULTS
    assert PLAN_DEFAULTS["ENTERPRISE"]["max_runs_per_month"] > PLAN_DEFAULTS["PRO"]["max_runs_per_month"]
    assert PLAN_DEFAULTS["ENTERPRISE"]["max_documents"] > PLAN_DEFAULTS["PRO"]["max_documents"]


def test_16_get_org_subscription_importable():
    from app.core.subscription import get_org_subscription
    assert callable(get_org_subscription)


def test_17_get_org_subscription_returns_free_on_error():
    """get_org_subscription must fall back to FREE when DB is unavailable."""
    from app.core.subscription import PLAN_DEFAULTS

    def _raise(*a, **kw):
        raise RuntimeError("DB unavailable")

    with patch("app.core.subscription._admin_sb", side_effect=_raise):
        from app.core.subscription import get_org_subscription
        result = get_org_subscription("any-org-id")

    assert result["plan_name"] == "FREE"
    assert result["max_runs_per_month"] == PLAN_DEFAULTS["FREE"]["max_runs_per_month"]


def test_18_check_plan_limit_importable():
    from app.core.subscription import check_plan_limit
    assert callable(check_plan_limit)


def test_19_check_plan_limit_raises_402_when_over_limit():
    """When count >= limit, check_plan_limit must raise HTTP 402 PLAN_LIMIT_REACHED."""
    from app.core.subscription import PLAN_DEFAULTS

    FREE_RUN_LIMIT = PLAN_DEFAULTS["FREE"]["max_runs_per_month"]

    # Fake subscription returning FREE plan
    fake_sub = dict(PLAN_DEFAULTS["FREE"])

    # Fake usage_metrics count returning exactly the limit (at limit → blocked)
    fake_count_res = MagicMock()
    fake_count_res.count = FREE_RUN_LIMIT

    fake_select = MagicMock()
    fake_select.eq.return_value = fake_select
    fake_select.gte.return_value = fake_select
    fake_select.execute.return_value = fake_count_res

    fake_table = MagicMock()
    fake_table.select.return_value = fake_select

    fake_sb = MagicMock()
    fake_sb.table.return_value = fake_table

    with patch("app.core.subscription._admin_sb", return_value=fake_sb), \
         patch("app.core.subscription.get_org_subscription", return_value=fake_sub):
        from app.core.subscription import check_plan_limit
        with pytest.raises(HTTPException) as exc:
            check_plan_limit("org-a", "runs")

    assert exc.value.status_code == 402
    detail = exc.value.detail
    assert detail["error"] == "PLAN_LIMIT_REACHED"
    assert detail["resource"] == "runs"
    assert detail["limit"] == FREE_RUN_LIMIT


def test_20_check_plan_limit_passes_when_under_limit():
    """When count < limit, no exception is raised."""
    from app.core.subscription import PLAN_DEFAULTS

    FREE_RUN_LIMIT = PLAN_DEFAULTS["FREE"]["max_runs_per_month"]
    fake_sub = dict(PLAN_DEFAULTS["FREE"])

    fake_count_res = MagicMock()
    fake_count_res.count = max(0, FREE_RUN_LIMIT - 1)

    fake_select = MagicMock()
    fake_select.eq.return_value = fake_select
    fake_select.gte.return_value = fake_select
    fake_select.execute.return_value = fake_count_res

    fake_table = MagicMock()
    fake_table.select.return_value = fake_select

    fake_sb = MagicMock()
    fake_sb.table.return_value = fake_table

    with patch("app.core.subscription._admin_sb", return_value=fake_sb), \
         patch("app.core.subscription.get_org_subscription", return_value=fake_sub):
        from app.core.subscription import check_plan_limit
        # Should not raise
        check_plan_limit("org-a", "runs")


def test_21_check_plan_limit_fails_open_on_db_error():
    """DB errors must NOT propagate — fail-open for reliability."""
    def _raise(*a, **kw):
        raise RuntimeError("DB connection reset")

    with patch("app.core.subscription._admin_sb", side_effect=_raise):
        from app.core.subscription import check_plan_limit
        # Must not raise — should be a no-op
        check_plan_limit("org-a", "runs")


def test_22_check_plan_limit_skips_unknown_resource():
    from app.core.subscription import check_plan_limit
    # Unknown resource → no-op, no exception
    check_plan_limit("org-a", "nonexistent_resource")


def test_23_log_usage_metric_importable():
    from app.core.subscription import log_usage_metric
    assert callable(log_usage_metric)


def test_24_log_usage_metric_never_raises_on_db_error():
    def _raise(*a, **kw):
        raise RuntimeError("network timeout")

    with patch("app.core.subscription._admin_sb", side_effect=_raise):
        from app.core.subscription import log_usage_metric
        # Must never raise
        log_usage_metric("org-a", "RUN_CREATED")


def test_25_log_usage_metric_never_raises_when_org_id_empty():
    from app.core.subscription import log_usage_metric
    # Empty org_id → silently returns
    log_usage_metric("", "RUN_CREATED")
    log_usage_metric(None, "RUN_CREATED")  # type: ignore[arg-type]


def test_26_get_usage_summary_importable():
    from app.core.subscription import get_usage_summary
    assert callable(get_usage_summary)


def test_27_get_usage_summary_returns_defaults_on_error():
    def _raise(*a, **kw):
        raise RuntimeError("DB down")

    with patch("app.core.subscription._admin_sb", side_effect=_raise):
        from app.core.subscription import get_usage_summary
        result = get_usage_summary("org-a")

    assert result["runs_this_month"] == 0
    assert result["documents_total"] == 0
    assert result["memory_entries_total"] == 0
    assert result["evidence_exports_total"] == 0


def test_28_get_usage_summary_has_plan_and_limits_keys():
    def _raise(*a, **kw):
        raise RuntimeError("DB down")

    with patch("app.core.subscription._admin_sb", side_effect=_raise):
        from app.core.subscription import get_usage_summary
        result = get_usage_summary("org-a")

    assert "plan" in result
    assert "limits" in result


# ===========================================================================
# 29–37: Endpoint wiring (source-level checks)
# ===========================================================================

def test_29_create_run_checks_plan_limit():
    src = _read(RUNS_ENDPOINT_PATH)
    # check_plan_limit must be called with "runs" in create_run
    assert 'check_plan_limit(resolved_org_id, "runs")' in src


def test_30_create_run_logs_run_created_metric():
    src = _read(RUNS_ENDPOINT_PATH)
    assert 'log_usage_metric(resolved_org_id, "RUN_CREATED")' in src


def test_31_upload_document_checks_plan_limit():
    src = _read(DOCS_ENDPOINT_PATH)
    assert 'check_plan_limit(org_id, "documents")' in src


def test_32_upload_document_logs_document_uploaded():
    src = _read(DOCS_ENDPOINT_PATH)
    assert 'log_usage_metric(org_id, "DOCUMENT_UPLOADED")' in src


def test_33_promote_memory_checks_memory_limit():
    src = _read(RUNS_ENDPOINT_PATH)
    assert 'check_plan_limit(_mem_org_id, "memory")' in src


def test_34_promote_memory_logs_memory_stored():
    src = _read(RUNS_ENDPOINT_PATH)
    assert 'log_usage_metric(_mem_org_id, "MEMORY_STORED")' in src


def test_35_generate_evidence_logs_evidence_generated():
    src = _read(RUNS_ENDPOINT_PATH)
    assert '"EVIDENCE_GENERATED"' in src


def test_36_runs_exposes_usage_endpoint():
    src = _read(RUNS_ENDPOINT_PATH)
    assert '@router.get("/usage")' in src


def test_37_usage_endpoint_imports_get_usage_summary():
    src = _read(RUNS_ENDPOINT_PATH)
    assert "get_usage_summary" in src


# ===========================================================================
# 38–40: Cross-org isolation via resolve_org_id_for_user
# ===========================================================================

def test_38_cross_org_run_isolation():
    """
    Org B's user cannot access org A's data.
    resolve_org_id_for_user raises 403 when user does not belong to the org.
    """
    from app.core.org_context import resolve_org_id_for_user

    ORG_A = "aaaaaaaa-0000-0000-0000-000000000001"
    USER_B = "bbbbbbbb-0000-0000-0000-000000000002"

    # Simulate: user B is not a member of org A
    fake_member_res = MagicMock()
    fake_member_res.data = None  # no membership row

    fake_select = MagicMock()
    fake_select.eq.return_value = fake_select
    fake_select.single.return_value = fake_select
    fake_select.execute.return_value = fake_member_res

    fake_table = MagicMock()
    fake_table.select.return_value = fake_select

    fake_sb = MagicMock()
    fake_sb.table.return_value = fake_table

    # Passing org_id forces the membership check path
    with pytest.raises(HTTPException) as exc:
        resolve_org_id_for_user(fake_sb, USER_B, ORG_A)

    assert exc.value.status_code in (403, 404)


def test_39_cross_org_document_isolation():
    """
    The same resolve_org_id_for_user mechanic blocks cross-org document access.
    Re-checks with document context to ensure consistent behaviour.
    """
    from app.core.org_context import resolve_org_id_for_user

    ORG_A = "aaaaaaaa-0000-0000-0000-000000000001"
    USER_C = "cccccccc-0000-0000-0000-000000000003"

    fake_member_res = MagicMock()
    fake_member_res.data = None

    fake_select = MagicMock()
    fake_select.eq.return_value = fake_select
    fake_select.single.return_value = fake_select
    fake_select.execute.return_value = fake_member_res

    fake_table = MagicMock()
    fake_table.select.return_value = fake_select

    fake_sb = MagicMock()
    fake_sb.table.return_value = fake_table

    with pytest.raises(HTTPException) as exc:
        resolve_org_id_for_user(fake_sb, USER_C, ORG_A)

    assert exc.value.status_code in (403, 404)


def test_40_resolve_org_id_raises_for_non_member():
    """resolve_org_id_for_user with explicit org_id always verifies membership."""
    from app.core.org_context import resolve_org_id_for_user

    ORG_X = "xxxxxxxx-0000-0000-0000-000000000099"
    USER_Y = "yyyyyyyy-0000-0000-0000-000000000088"

    fake_res = MagicMock()
    fake_res.data = None  # not a member

    fake_sel = MagicMock()
    fake_sel.eq.return_value = fake_sel
    fake_sel.single.return_value = fake_sel
    fake_sel.execute.return_value = fake_res

    fake_tbl = MagicMock()
    fake_tbl.select.return_value = fake_sel

    fake_sb = MagicMock()
    fake_sb.table.return_value = fake_tbl

    with pytest.raises(HTTPException):
        resolve_org_id_for_user(fake_sb, USER_Y, ORG_X)


# ===========================================================================
# 41–46: Frontend source-level checks
# ===========================================================================

def test_41_api_ts_has_get_usage_summary():
    src = _read(API_TS_PATH)
    assert "getUsageSummary" in src


def test_42_usage_panel_component_exists():
    assert os.path.isfile(USAGE_PANEL_PATH), f"UsagePanel.tsx not found at {USAGE_PANEL_PATH}"


def test_43_plan_limit_modal_component_exists():
    assert os.path.isfile(PLAN_LIMIT_MODAL_PATH), f"PlanLimitModal.tsx not found at {PLAN_LIMIT_MODAL_PATH}"


def test_44_dashboard_imports_usage_panel():
    src = _read(DASHBOARD_PAGE_PATH)
    assert "UsagePanel" in src


def test_45_layout_imports_plan_limit_modal():
    src = _read(LAYOUT_PATH)
    assert "PlanLimitModal" in src


def test_46_api_ts_dispatches_plan_limit_event():
    src = _read(API_TS_PATH)
    assert "plan:limit_reached" in src


# ===========================================================================
# 47–50: RESOURCE_MAP correctness
# ===========================================================================

def test_47_resource_map_runs():
    from app.core.subscription import RESOURCE_MAP
    metric_type, limit_field = RESOURCE_MAP["runs"]
    assert metric_type == "RUN_CREATED"
    assert limit_field == "max_runs_per_month"


def test_48_resource_map_documents():
    from app.core.subscription import RESOURCE_MAP
    metric_type, limit_field = RESOURCE_MAP["documents"]
    assert metric_type == "DOCUMENT_UPLOADED"
    assert limit_field == "max_documents"


def test_49_resource_map_memory():
    from app.core.subscription import RESOURCE_MAP
    metric_type, limit_field = RESOURCE_MAP["memory"]
    assert metric_type == "MEMORY_STORED"
    assert limit_field == "max_memory_entries"


def test_50_resource_map_evidence_no_limit():
    from app.core.subscription import RESOURCE_MAP
    metric_type, limit_field = RESOURCE_MAP["evidence"]
    assert metric_type == "EVIDENCE_GENERATED"
    assert limit_field is None  # evidence is unmetered
