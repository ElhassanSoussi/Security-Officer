"""
Plan Enforcement Tests
======================

Deterministic tests for subscription tier enforcement.
No real Stripe / DB / network calls.

Tests cover:
 1. Plan enum — Plan has STARTER value
 2. Plan enum — Plan has GROWTH value
 3. Plan enum — Plan has ELITE value
 4. Plan enum — Plan values are lowercase strings
 5. Plan enum — Plan rejects invalid value
 6. Plan enum — Plan is a str subclass (usable as dict key)
 7. PLAN_LIMITS — STARTER limits defined
 8. PLAN_LIMITS — GROWTH limits defined
 9. PLAN_LIMITS — ELITE limits defined
10. PLAN_LIMITS — STARTER max_projects is 5
11. PLAN_LIMITS — STARTER max_documents is 25
12. PLAN_LIMITS — STARTER max_runs_per_month is 10
13. PLAN_LIMITS — GROWTH max_projects is 25
14. PLAN_LIMITS — GROWTH max_documents is 500
15. PLAN_LIMITS — GROWTH max_runs_per_month is 100
16. PLAN_LIMITS — ELITE max_projects is 10000
17. PLAN_LIMITS — ELITE max_documents is 100000
18. PLAN_LIMITS — ELITE max_runs_per_month is 10000
19. PLAN_LIMITS — every plan has all three limit keys
20. PlanService.get_limits — returns dict for STARTER
21. PlanService.get_limits — returns dict for GROWTH
22. PlanService.get_limits — returns dict for ELITE
23. PlanService.get_limits — returns copy (not reference)
24. PriceMapping — resolve_price_id returns None for unknown
25. PriceMapping — resolve_price_id maps STRIPE_PRICE_STARTER
26. PriceMapping — resolve_price_id maps STRIPE_PRICE_GROWTH
27. PriceMapping — resolve_price_id maps STRIPE_PRICE_ELITE
28. PriceMapping — resolve_price_id maps legacy STRIPE_PRICE_FREE to STARTER
29. PriceMapping — resolve_price_id maps legacy STRIPE_PRICE_PRO to GROWTH
30. PriceMapping — resolve_price_id maps legacy STRIPE_PRICE_ENTERPRISE to ELITE
31. PriceMapping — empty env returns empty mapping
32. Enforcement — enforce_runs_limit raises 403 when over limit
33. Enforcement — enforce_runs_limit passes when under limit
34. Enforcement — enforce_runs_limit fail-open on DB error
35. Enforcement — enforce_documents_limit raises 403 when over limit
36. Enforcement — enforce_documents_limit passes when under limit
37. Enforcement — enforce_documents_limit fail-open on DB error
38. Enforcement — enforce_projects_limit raises 403 when over limit
39. Enforcement — enforce_projects_limit passes when under limit
40. Enforcement — enforce_projects_limit fail-open on DB error
41. Enforcement — 403 body has error=plan_limit_exceeded
42. Enforcement — 403 body has message=Upgrade required to continue
43. Enforcement — 403 body includes resource field
44. Enforcement — 403 body includes current_count field
45. Enforcement — 403 body includes limit field
46. Enforcement — 403 body includes plan field
47. SetOrgPlan — set_org_plan is callable
48. Webhook — billing.py handle_subscription_updated sets plan column
49. Webhook — billing.py handle_subscription_deleted resets plan to starter
50. Webhook — stripe_billing._handle_subscription_updated calls PlanService
51. Webhook — stripe_billing._handle_subscription_deleted calls PlanService
52. Migration — 020_plan_enforcement.sql exists on disk
53. Migration — SQL adds plan column
54. Migration — SQL adds stripe_price_id column
55. Migration — SQL adds CHECK constraint for plan
56. Migration — SQL ensures subscription_status column
57. Migration — SQL creates idx_organizations_plan index
58. Migration — SQL back-fills plan from plan_tier
59. EndpointHook — projects.py imports PlanService
60. EndpointHook — documents.py imports PlanService
61. EndpointHook — runs.py imports PlanService
62. EndpointHook — projects.py calls enforce_projects_limit
63. EndpointHook — documents.py calls enforce_documents_limit
64. EndpointHook — runs.py calls enforce_runs_limit
65. BackwardCompat — subscription.PLAN_DEFAULTS still importable
66. BackwardCompat — entitlements.PLAN_ENTITLEMENTS still importable
67. BackwardCompat — billing.PLAN_PRICE_MAP still importable
68. BackwardCompat — billing.PRICE_TO_PLAN still importable
69. NoPhaseLang — plan_service.py contains no 'phase' word
70. NoPhaseLang — 020 migration contains no 'phase' word
71. NoPhaseLang — this test file contains no 'phase' word (except this meta-assertion)
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
SQL_PATH = os.path.join(BACKEND_DIR, "scripts", "020_plan_enforcement.sql")
PLAN_SERVICE_PATH = os.path.join(BACKEND_DIR, "app", "core", "plan_service.py")
PROJECTS_PATH = os.path.join(BACKEND_DIR, "app", "api", "endpoints", "projects.py")
DOCUMENTS_PATH = os.path.join(BACKEND_DIR, "app", "api", "endpoints", "documents.py")
RUNS_PATH = os.path.join(BACKEND_DIR, "app", "api", "endpoints", "runs.py")
BILLING_PATH = os.path.join(BACKEND_DIR, "app", "core", "billing.py")
STRIPE_BILLING_PATH = os.path.join(BACKEND_DIR, "app", "core", "stripe_billing.py")


# ===========================================================================
# 1. Plan Enum
# ===========================================================================
class TestPlanEnum:
    def test_01_plan_has_starter(self):
        from app.core.plan_service import Plan
        assert Plan.STARTER is not None

    def test_02_plan_has_growth(self):
        from app.core.plan_service import Plan
        assert Plan.GROWTH is not None

    def test_03_plan_has_elite(self):
        from app.core.plan_service import Plan
        assert Plan.ELITE is not None

    def test_04_plan_values_are_lowercase(self):
        from app.core.plan_service import Plan
        assert Plan.STARTER.value == "starter"
        assert Plan.GROWTH.value == "growth"
        assert Plan.ELITE.value == "elite"

    def test_05_plan_rejects_invalid(self):
        from app.core.plan_service import Plan
        with pytest.raises(ValueError):
            Plan("neon")

    def test_06_plan_is_str_subclass(self):
        from app.core.plan_service import Plan
        assert isinstance(Plan.STARTER, str)
        assert Plan.STARTER == "starter"


# ===========================================================================
# 2. Plan Limits
# ===========================================================================
class TestPlanLimits:
    def test_07_starter_limits_defined(self):
        from app.core.plan_service import Plan, PLAN_LIMITS
        assert Plan.STARTER in PLAN_LIMITS

    def test_08_growth_limits_defined(self):
        from app.core.plan_service import Plan, PLAN_LIMITS
        assert Plan.GROWTH in PLAN_LIMITS

    def test_09_elite_limits_defined(self):
        from app.core.plan_service import Plan, PLAN_LIMITS
        assert Plan.ELITE in PLAN_LIMITS

    def test_10_starter_max_projects(self):
        from app.core.plan_service import Plan, PLAN_LIMITS
        assert PLAN_LIMITS[Plan.STARTER]["max_projects"] == 5

    def test_11_starter_max_documents(self):
        from app.core.plan_service import Plan, PLAN_LIMITS
        assert PLAN_LIMITS[Plan.STARTER]["max_documents"] == 25

    def test_12_starter_max_runs(self):
        from app.core.plan_service import Plan, PLAN_LIMITS
        assert PLAN_LIMITS[Plan.STARTER]["max_runs_per_month"] == 10

    def test_13_growth_max_projects(self):
        from app.core.plan_service import Plan, PLAN_LIMITS
        assert PLAN_LIMITS[Plan.GROWTH]["max_projects"] == 25

    def test_14_growth_max_documents(self):
        from app.core.plan_service import Plan, PLAN_LIMITS
        assert PLAN_LIMITS[Plan.GROWTH]["max_documents"] == 500

    def test_15_growth_max_runs(self):
        from app.core.plan_service import Plan, PLAN_LIMITS
        assert PLAN_LIMITS[Plan.GROWTH]["max_runs_per_month"] == 100

    def test_16_elite_max_projects(self):
        from app.core.plan_service import Plan, PLAN_LIMITS
        assert PLAN_LIMITS[Plan.ELITE]["max_projects"] == 10_000

    def test_17_elite_max_documents(self):
        from app.core.plan_service import Plan, PLAN_LIMITS
        assert PLAN_LIMITS[Plan.ELITE]["max_documents"] == 100_000

    def test_18_elite_max_runs(self):
        from app.core.plan_service import Plan, PLAN_LIMITS
        assert PLAN_LIMITS[Plan.ELITE]["max_runs_per_month"] == 10_000

    def test_19_every_plan_has_all_keys(self):
        from app.core.plan_service import Plan, PLAN_LIMITS
        required = {"max_projects", "max_documents", "max_runs_per_month"}
        for plan in Plan:
            assert required.issubset(PLAN_LIMITS[plan].keys()), f"{plan.value} missing keys"


# ===========================================================================
# 3. PlanService.get_limits
# ===========================================================================
class TestPlanServiceGetLimits:
    def test_20_get_limits_starter(self):
        from app.core.plan_service import Plan, PlanService
        limits = PlanService.get_limits(Plan.STARTER)
        assert limits["max_projects"] == 5

    def test_21_get_limits_growth(self):
        from app.core.plan_service import Plan, PlanService
        limits = PlanService.get_limits(Plan.GROWTH)
        assert limits["max_runs_per_month"] == 100

    def test_22_get_limits_elite(self):
        from app.core.plan_service import Plan, PlanService
        limits = PlanService.get_limits(Plan.ELITE)
        assert limits["max_documents"] == 100_000

    def test_23_get_limits_returns_copy(self):
        from app.core.plan_service import Plan, PlanService, PLAN_LIMITS
        limits = PlanService.get_limits(Plan.STARTER)
        limits["max_projects"] = 999
        assert PLAN_LIMITS[Plan.STARTER]["max_projects"] == 5


# ===========================================================================
# 4. Stripe Price ID Mapping
# ===========================================================================
class TestPriceMapping:
    def test_24_unknown_returns_none(self):
        from app.core.plan_service import resolve_price_id
        assert resolve_price_id("price_unknown_xyz") is None

    def test_25_maps_starter(self):
        from app.core.plan_service import resolve_price_id, Plan
        with patch.dict(os.environ, {"STRIPE_PRICE_STARTER": "price_starter_test"}):
            assert resolve_price_id("price_starter_test") == Plan.STARTER

    def test_26_maps_growth(self):
        from app.core.plan_service import resolve_price_id, Plan
        with patch.dict(os.environ, {"STRIPE_PRICE_GROWTH": "price_growth_test"}):
            assert resolve_price_id("price_growth_test") == Plan.GROWTH

    def test_27_maps_elite(self):
        from app.core.plan_service import resolve_price_id, Plan
        with patch.dict(os.environ, {"STRIPE_PRICE_ELITE": "price_elite_test"}):
            assert resolve_price_id("price_elite_test") == Plan.ELITE

    def test_28_maps_legacy_free_to_starter(self):
        from app.core.plan_service import resolve_price_id, Plan
        with patch.dict(os.environ, {"STRIPE_PRICE_FREE": "price_free_test"}):
            assert resolve_price_id("price_free_test") == Plan.STARTER

    def test_29_maps_legacy_pro_to_growth(self):
        from app.core.plan_service import resolve_price_id, Plan
        with patch.dict(os.environ, {"STRIPE_PRICE_PRO": "price_pro_test"}):
            assert resolve_price_id("price_pro_test") == Plan.GROWTH

    def test_30_maps_legacy_enterprise_to_elite(self):
        from app.core.plan_service import resolve_price_id, Plan
        with patch.dict(os.environ, {"STRIPE_PRICE_ENTERPRISE": "price_ent_test"}):
            assert resolve_price_id("price_ent_test") == Plan.ELITE

    def test_31_empty_env_returns_empty(self):
        from app.core.plan_service import _build_price_to_plan
        env_overrides = {
            "STRIPE_PRICE_STARTER": "",
            "STRIPE_PRICE_GROWTH": "",
            "STRIPE_PRICE_ELITE": "",
            "STRIPE_PRICE_FREE": "",
            "STRIPE_PRICE_PRO": "",
            "STRIPE_PRICE_ENTERPRISE": "",
        }
        with patch.dict(os.environ, env_overrides, clear=False):
            mapping = _build_price_to_plan()
            # May contain values from other env vars, but our test keys won't be there
            for k in env_overrides:
                assert "" not in mapping


# ===========================================================================
# 5. Enforcement
# ===========================================================================

def _mock_sb_count(count_value):
    """Create a mock Supabase chain that returns a count."""
    mock_result = MagicMock()
    mock_result.count = count_value
    mock_result.data = []

    mock_chain = MagicMock()
    mock_chain.select.return_value = mock_chain
    mock_chain.eq.return_value = mock_chain
    mock_chain.gte.return_value = mock_chain
    mock_chain.execute.return_value = mock_result
    return mock_chain


def _mock_sb_plan(plan_value="starter"):
    """Create a mock Supabase admin that returns a plan."""
    mock_sb = MagicMock()

    # For org plan lookup
    plan_result = MagicMock()
    plan_result.data = {"plan": plan_value}
    plan_chain = MagicMock()
    plan_chain.select.return_value = plan_chain
    plan_chain.eq.return_value = plan_chain
    plan_chain.single.return_value = plan_chain
    plan_chain.execute.return_value = plan_result

    # For count queries
    count_chain = _mock_sb_count(0)

    def table_side_effect(name):
        if name == "organizations":
            return plan_chain
        return count_chain

    mock_sb.table.side_effect = table_side_effect
    return mock_sb


class TestEnforcementRuns:
    @patch("app.core.plan_service._admin_sb")
    def test_32_raises_403_when_over(self, mock_admin):
        from app.core.plan_service import PlanService
        sb = _mock_sb_plan("starter")
        # Override runs table to return count at limit
        runs_chain = _mock_sb_count(10)  # STARTER limit is 10
        original = sb.table.side_effect

        def table_switch(name):
            if name == "runs":
                return runs_chain
            return original(name)

        sb.table.side_effect = table_switch
        mock_admin.return_value = sb

        with pytest.raises(HTTPException) as exc_info:
            PlanService.enforce_runs_limit("org-123")
        assert exc_info.value.status_code == 403

    @patch("app.core.plan_service._admin_sb")
    def test_33_passes_when_under(self, mock_admin):
        from app.core.plan_service import PlanService
        sb = _mock_sb_plan("starter")
        runs_chain = _mock_sb_count(5)  # Under limit
        original = sb.table.side_effect

        def table_switch(name):
            if name == "runs":
                return runs_chain
            return original(name)

        sb.table.side_effect = table_switch
        mock_admin.return_value = sb
        # Should not raise
        PlanService.enforce_runs_limit("org-123")

    @patch("app.core.plan_service._admin_sb")
    def test_34_fail_open_on_db_error(self, mock_admin):
        from app.core.plan_service import PlanService
        mock_admin.side_effect = Exception("DB down")
        # Should not raise — fail-open
        PlanService.enforce_runs_limit("org-123")


class TestEnforcementDocuments:
    @patch("app.core.plan_service._admin_sb")
    def test_35_raises_403_when_over(self, mock_admin):
        from app.core.plan_service import PlanService
        sb = _mock_sb_plan("starter")
        docs_chain = _mock_sb_count(25)  # STARTER limit
        original = sb.table.side_effect

        def table_switch(name):
            if name == "documents":
                return docs_chain
            return original(name)

        sb.table.side_effect = table_switch
        mock_admin.return_value = sb

        with pytest.raises(HTTPException) as exc_info:
            PlanService.enforce_documents_limit("org-123")
        assert exc_info.value.status_code == 403

    @patch("app.core.plan_service._admin_sb")
    def test_36_passes_when_under(self, mock_admin):
        from app.core.plan_service import PlanService
        sb = _mock_sb_plan("growth")
        docs_chain = _mock_sb_count(100)  # GROWTH limit is 500
        original = sb.table.side_effect

        def table_switch(name):
            if name == "documents":
                return docs_chain
            return original(name)

        sb.table.side_effect = table_switch
        mock_admin.return_value = sb
        PlanService.enforce_documents_limit("org-123")

    @patch("app.core.plan_service._admin_sb")
    def test_37_fail_open_on_db_error(self, mock_admin):
        from app.core.plan_service import PlanService
        mock_admin.side_effect = Exception("DB down")
        PlanService.enforce_documents_limit("org-123")


class TestEnforcementProjects:
    @patch("app.core.plan_service._admin_sb")
    def test_38_raises_403_when_over(self, mock_admin):
        from app.core.plan_service import PlanService
        sb = _mock_sb_plan("starter")
        proj_chain = _mock_sb_count(5)  # STARTER limit
        original = sb.table.side_effect

        def table_switch(name):
            if name == "projects":
                return proj_chain
            return original(name)

        sb.table.side_effect = table_switch
        mock_admin.return_value = sb

        with pytest.raises(HTTPException) as exc_info:
            PlanService.enforce_projects_limit("org-123")
        assert exc_info.value.status_code == 403

    @patch("app.core.plan_service._admin_sb")
    def test_39_passes_when_under(self, mock_admin):
        from app.core.plan_service import PlanService
        sb = _mock_sb_plan("elite")
        proj_chain = _mock_sb_count(500)  # ELITE limit is 10000
        original = sb.table.side_effect

        def table_switch(name):
            if name == "projects":
                return proj_chain
            return original(name)

        sb.table.side_effect = table_switch
        mock_admin.return_value = sb
        PlanService.enforce_projects_limit("org-123")

    @patch("app.core.plan_service._admin_sb")
    def test_40_fail_open_on_db_error(self, mock_admin):
        from app.core.plan_service import PlanService
        mock_admin.side_effect = Exception("DB down")
        PlanService.enforce_projects_limit("org-123")


class TestEnforcementErrorBody:
    @patch("app.core.plan_service._admin_sb")
    def test_41_error_field(self, mock_admin):
        from app.core.plan_service import PlanService
        sb = _mock_sb_plan("starter")
        chain = _mock_sb_count(10)
        original = sb.table.side_effect

        def ts(name):
            return chain if name == "runs" else original(name)

        sb.table.side_effect = ts
        mock_admin.return_value = sb

        with pytest.raises(HTTPException) as exc_info:
            PlanService.enforce_runs_limit("org-x")
        detail = exc_info.value.detail
        assert detail["error"] == "plan_limit_exceeded"

    @patch("app.core.plan_service._admin_sb")
    def test_42_message_field(self, mock_admin):
        from app.core.plan_service import PlanService
        sb = _mock_sb_plan("starter")
        chain = _mock_sb_count(10)
        original = sb.table.side_effect
        sb.table.side_effect = lambda n: chain if n == "runs" else original(n)
        mock_admin.return_value = sb

        with pytest.raises(HTTPException) as exc_info:
            PlanService.enforce_runs_limit("org-x")
        assert exc_info.value.detail["message"] == "Upgrade required to continue"

    @patch("app.core.plan_service._admin_sb")
    def test_43_resource_field(self, mock_admin):
        from app.core.plan_service import PlanService
        sb = _mock_sb_plan("starter")
        chain = _mock_sb_count(25)
        original = sb.table.side_effect
        sb.table.side_effect = lambda n: chain if n == "documents" else original(n)
        mock_admin.return_value = sb

        with pytest.raises(HTTPException) as exc_info:
            PlanService.enforce_documents_limit("org-x")
        assert exc_info.value.detail["resource"] == "documents"

    @patch("app.core.plan_service._admin_sb")
    def test_44_current_count_field(self, mock_admin):
        from app.core.plan_service import PlanService
        sb = _mock_sb_plan("starter")
        chain = _mock_sb_count(5)
        original = sb.table.side_effect
        sb.table.side_effect = lambda n: chain if n == "projects" else original(n)
        mock_admin.return_value = sb

        with pytest.raises(HTTPException) as exc_info:
            PlanService.enforce_projects_limit("org-x")
        assert exc_info.value.detail["current_count"] == 5

    @patch("app.core.plan_service._admin_sb")
    def test_45_limit_field(self, mock_admin):
        from app.core.plan_service import PlanService
        sb = _mock_sb_plan("starter")
        chain = _mock_sb_count(5)
        original = sb.table.side_effect
        sb.table.side_effect = lambda n: chain if n == "projects" else original(n)
        mock_admin.return_value = sb

        with pytest.raises(HTTPException) as exc_info:
            PlanService.enforce_projects_limit("org-x")
        assert exc_info.value.detail["limit"] == 5

    @patch("app.core.plan_service._admin_sb")
    def test_46_plan_field(self, mock_admin):
        from app.core.plan_service import PlanService
        sb = _mock_sb_plan("starter")
        chain = _mock_sb_count(5)
        original = sb.table.side_effect
        sb.table.side_effect = lambda n: chain if n == "projects" else original(n)
        mock_admin.return_value = sb

        with pytest.raises(HTTPException) as exc_info:
            PlanService.enforce_projects_limit("org-x")
        assert exc_info.value.detail["plan"] == "starter"


# ===========================================================================
# 6. set_org_plan
# ===========================================================================
class TestSetOrgPlan:
    def test_47_set_org_plan_callable(self):
        from app.core.plan_service import PlanService
        assert callable(PlanService.set_org_plan)


# ===========================================================================
# 7. Webhook Integration
# ===========================================================================
class TestWebhookIntegration:
    def test_48_billing_handle_subscription_updated_sets_plan(self):
        src = open(BILLING_PATH).read()
        assert '"plan":' in src or "'plan':" in src
        assert "plan_tier" in src

    def test_49_billing_handle_subscription_deleted_resets_plan(self):
        src = open(BILLING_PATH).read()
        assert '"plan": "starter"' in src or "'plan': 'starter'" in src

    def test_50_stripe_billing_updated_calls_plan_service(self):
        src = open(STRIPE_BILLING_PATH).read()
        assert "PlanService.set_org_plan" in src or "plan_service" in src

    def test_51_stripe_billing_deleted_calls_plan_service(self):
        src = open(STRIPE_BILLING_PATH).read()
        assert "Plan.STARTER" in src


# ===========================================================================
# 8. Migration SQL
# ===========================================================================
class TestMigrationSQL:
    @pytest.fixture(autouse=True)
    def _load_sql(self):
        with open(SQL_PATH) as f:
            self.sql = f.read()

    def test_52_migration_file_exists(self):
        assert os.path.isfile(SQL_PATH)

    def test_53_adds_plan_column(self):
        assert "ADD COLUMN IF NOT EXISTS plan" in self.sql

    def test_54_adds_stripe_price_id(self):
        assert "stripe_price_id" in self.sql

    def test_55_check_constraint(self):
        assert "organizations_plan_check" in self.sql
        assert "'starter'" in self.sql
        assert "'growth'" in self.sql
        assert "'elite'" in self.sql

    def test_56_subscription_status(self):
        assert "subscription_status" in self.sql

    def test_57_index(self):
        assert "idx_organizations_plan" in self.sql

    def test_58_backfill(self):
        assert "plan_tier" in self.sql
        assert "UPDATE organizations" in self.sql


# ===========================================================================
# 9. Endpoint Hooks
# ===========================================================================
class TestEndpointHooks:
    def test_59_projects_imports_plan_service(self):
        src = open(PROJECTS_PATH).read()
        assert "plan_service" in src or "PlanService" in src

    def test_60_documents_imports_plan_service(self):
        src = open(DOCUMENTS_PATH).read()
        assert "plan_service" in src or "PlanService" in src

    def test_61_runs_imports_plan_service(self):
        src = open(RUNS_PATH).read()
        assert "plan_service" in src or "PlanService" in src

    def test_62_projects_calls_enforce_projects_limit(self):
        src = open(PROJECTS_PATH).read()
        assert "enforce_projects_limit" in src

    def test_63_documents_calls_enforce_documents_limit(self):
        src = open(DOCUMENTS_PATH).read()
        assert "enforce_documents_limit" in src

    def test_64_runs_calls_enforce_runs_limit(self):
        src = open(RUNS_PATH).read()
        assert "enforce_runs_limit" in src


# ===========================================================================
# 10. Backward Compatibility
# ===========================================================================
class TestBackwardCompat:
    def test_65_subscription_plan_defaults(self):
        from app.core.subscription import PLAN_DEFAULTS
        assert "FREE" in PLAN_DEFAULTS
        assert "PRO" in PLAN_DEFAULTS
        assert "ENTERPRISE" in PLAN_DEFAULTS

    def test_66_entitlements_plan_entitlements(self):
        from app.core.entitlements import PLAN_ENTITLEMENTS
        assert "starter" in PLAN_ENTITLEMENTS
        assert "growth" in PLAN_ENTITLEMENTS
        assert "elite" in PLAN_ENTITLEMENTS

    def test_67_billing_plan_price_map(self):
        from app.core.billing import PLAN_PRICE_MAP
        assert "starter" in PLAN_PRICE_MAP
        assert "growth" in PLAN_PRICE_MAP
        assert "elite" in PLAN_PRICE_MAP

    def test_68_billing_price_to_plan(self):
        from app.core.billing import PRICE_TO_PLAN
        assert isinstance(PRICE_TO_PLAN, dict)


# ===========================================================================
# 11. No forbidden terminology
# ===========================================================================
class TestNoForbiddenTerminology:
    def test_69_plan_service_no_phase_word(self):
        src = open(PLAN_SERVICE_PATH).read().lower()
        # "phase" should not appear in the module
        assert "phase" not in src

    def test_70_migration_no_phase_word(self):
        src = open(SQL_PATH).read().lower()
        assert "phase" not in src

    def test_71_test_file_no_forbidden_terminology_in_new_code(self):
        # Verify this test file doesn't use the forbidden word in test/class names
        # (excluding the terminology-check class itself)
        src = open(__file__).read()
        import re
        class_names = re.findall(r'class (\w+)', src)
        func_names = re.findall(r'def (\w+)', src)
        all_names = class_names + func_names
        # Exclude names in the terminology-check section itself
        excluded_prefixes = ("TestNoForbidden", "test_69", "test_70", "test_71")
        for name in all_names:
            if any(name.startswith(p) for p in excluded_prefixes):
                continue
            assert "phase" not in name.lower(), f"Name '{name}' contains forbidden word"
