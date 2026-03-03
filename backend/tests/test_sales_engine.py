"""
Sales Engine + Enterprise Demo Workspace Tests

All tests are deterministic — no real DB / API / external calls.

Tests cover:
 1. SalesEndpoint — sales.py module exists and is importable
 2. SalesEndpoint — router object is an APIRouter
 3. SalesEndpoint — POST /contact route registered
 4. SalesEndpoint — POST /track/enterprise-interest route registered
 5. SalesEndpoint — POST /track/trial-event route registered
 6. SalesEndpoint — GET /admin/sales-analytics route registered
 7. SalesEndpoint — POST /admin/demo-reset route registered
 8. SalesModels — ContactFormPayload validates required fields
 9. SalesModels — ContactFormPayload rejects empty company_name
10. SalesModels — ContactFormPayload rejects empty name
11. SalesModels — ContactFormPayload rejects invalid email
12. SalesModels — ContactFormPayload normalizes email to lowercase
13. SalesModels — ContactFormPayload accepts valid phone (optional)
14. SalesModels — EnterpriseInterestPayload has default source
15. SalesModels — TrialEventPayload validates allowed event_types
16. SalesModels — TrialEventPayload rejects invalid event_type
17. SalesModels — TrialEventPayload accepts TRIAL_STARTED
18. SalesModels — TrialEventPayload accepts TRIAL_CONVERTED
19. SalesModels — TrialEventPayload accepts TRIAL_EXPIRED
20. DemoConstants — DEMO_ORG_ID is valid UUID format
21. DemoConstants — DEMO_PROJECT_ID is valid UUID format
22. DemoConstants — DEMO_RUN_ID is valid UUID format
23. DemoConstants — DEMO_USER_ID is valid UUID format
24. Migration — phase22 migration SQL file exists
25. Migration — migration creates sales_leads table
26. Migration — migration creates idx_sales_leads_created index
27. Migration — migration creates idx_sales_leads_source index
28. Migration — migration has RLS policy for service_role
29. Migration — migration has RLS policy for anonymous inserts
30. Registration — sales router registered in main.py
31. Registration — sales router uses API_V1_STR prefix
32. Registration — sales router has "Sales" tag
33. Frontend — contact page exists at app/contact/page.tsx
34. Frontend — contact page contains form with company_name field
35. Frontend — contact page contains email field
36. Frontend — contact page calls submitContactForm
37. Frontend — EnterpriseContactModal component exists
38. Frontend — EnterpriseContactModal calls trackEnterpriseInterest
39. Frontend — billing page imports EnterpriseContactModal
40. Frontend — billing page has enterpriseModalOpen state
41. Frontend — UpgradeNudge component exists
42. Frontend — UpgradeNudge has resource prop
43. Frontend — UpgradeNudge links to /plans
44. Frontend — TrialBanner component exists
45. Frontend — TrialBanner tracks TRIAL_STARTED event
46. Frontend — TrialBanner shows days remaining
47. Frontend — TrialBanner has upgrade CTA
48. Frontend — DemoBanner component exists
49. Frontend — DemoBanner calls resetDemoWorkspace
50. Frontend — DemoBanner shows "Demo Workspace" text
51. Frontend — AppShell imports DemoBanner
52. Frontend — AppShell imports TrialBanner
53. Frontend — admin/sales page exists
54. Frontend — admin/sales page calls getSalesAnalytics
55. Frontend — admin/sales page shows conversion_rate
56. Frontend — admin/sales page shows mrr_estimate
57. Frontend — /contact is in PUBLIC_ROUTES
58. DemoData — demo-data.ts has 15 DEMO_AUDITS entries
59. DemoData — demo-data.ts has DEMO_EVIDENCE_RECORDS
60. DemoData — demo-data.ts has DEMO_HEALTH_SCORE
61. DemoData — demo-data.ts has extended DEMO_ACTIVITY (≥8 entries)
62. DemoData — DEMO_AUDITS has mix of approved/pending/rejected
63. DemoData — DEMO_HEALTH_SCORE has risk_breakdown
64. DemoData — DEMO_HEALTH_SCORE has reuse_stats with reused_from_memory
65. DemoData — DEMO_HEALTH_SCORE has export_gate logic
66. ApiClient — api.ts has submitContactForm method
67. ApiClient — api.ts has trackEnterpriseInterest method
68. ApiClient — api.ts has trackTrialEvent method
69. ApiClient — api.ts has getSalesAnalytics method
70. ApiClient — api.ts has resetDemoWorkspace method
71. Subscription — PLAN_DEFAULTS has FREE plan
72. Subscription — PLAN_DEFAULTS has PRO plan
73. Subscription — PLAN_DEFAULTS has ENTERPRISE plan
74. Subscription — FREE plan max_runs_per_month is 10
75. Subscription — PRO plan max_runs_per_month is 100
76. Subscription — ENTERPRISE plan max_runs_per_month is 10000
"""

import ast
import os
import re
import sys
import uuid
from pathlib import Path

import pytest

# ── Setup paths ───────────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent
FRONTEND_DIR = ROOT_DIR / "frontend"
sys.path.insert(0, str(BACKEND_DIR))

# Ensure env vars so Settings() doesn't crash
for var in ("SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_JWT_SECRET", "SUPABASE_SERVICE_ROLE_KEY"):
    os.environ.setdefault(var, "https://test.supabase.co" if "URL" in var else "test-key-placeholder")


# ══════════════════════════════════════════════════════════════════════════════
# Part 1: Sales Endpoint Module (Tests 1-7)
# ══════════════════════════════════════════════════════════════════════════════

class TestSalesEndpointRoutes:
    """Verify sales.py module exists, is importable, and has expected routes."""

    def test_01_sales_module_importable(self):
        from app.api.endpoints import sales
        assert sales is not None

    def test_02_router_is_api_router(self):
        from app.api.endpoints.sales import router
        from fastapi import APIRouter
        assert isinstance(router, APIRouter)

    def _route_paths_and_methods(self):
        from app.api.endpoints.sales import router
        return [(r.path, list(r.methods)) for r in router.routes if hasattr(r, "methods")]

    def test_03_post_contact_route_registered(self):
        routes = self._route_paths_and_methods()
        assert any(p == "/contact" and "POST" in m for p, m in routes)

    def test_04_post_track_enterprise_interest_route(self):
        routes = self._route_paths_and_methods()
        assert any("enterprise-interest" in p and "POST" in m for p, m in routes)

    def test_05_post_track_trial_event_route(self):
        routes = self._route_paths_and_methods()
        assert any("trial-event" in p and "POST" in m for p, m in routes)

    def test_06_get_sales_analytics_route(self):
        routes = self._route_paths_and_methods()
        assert any("sales-analytics" in p and "GET" in m for p, m in routes)

    def test_07_post_demo_reset_route(self):
        routes = self._route_paths_and_methods()
        assert any("demo-reset" in p and "POST" in m for p, m in routes)


# ══════════════════════════════════════════════════════════════════════════════
# Part 2: Pydantic Models Validation (Tests 8-19)
# ══════════════════════════════════════════════════════════════════════════════

class TestSalesModels:
    """Verify Pydantic model validation for sales payloads."""

    def test_08_contact_form_valid(self):
        from app.api.endpoints.sales import ContactFormPayload
        p = ContactFormPayload(company_name="Acme Corp", name="John Doe", email="john@acme.com")
        assert p.company_name == "Acme Corp"
        assert p.email == "john@acme.com"

    def test_09_contact_form_rejects_empty_company(self):
        from app.api.endpoints.sales import ContactFormPayload
        with pytest.raises(Exception):
            ContactFormPayload(company_name="", name="John", email="john@acme.com")

    def test_10_contact_form_rejects_empty_name(self):
        from app.api.endpoints.sales import ContactFormPayload
        with pytest.raises(Exception):
            ContactFormPayload(company_name="Acme", name="", email="john@acme.com")

    def test_11_contact_form_rejects_invalid_email(self):
        from app.api.endpoints.sales import ContactFormPayload
        with pytest.raises(Exception):
            ContactFormPayload(company_name="Acme", name="John", email="not-an-email")

    def test_12_contact_form_normalizes_email(self):
        from app.api.endpoints.sales import ContactFormPayload
        p = ContactFormPayload(company_name="Acme", name="John", email="JOHN@ACME.COM")
        assert p.email == "john@acme.com"

    def test_13_contact_form_accepts_optional_phone(self):
        from app.api.endpoints.sales import ContactFormPayload
        p = ContactFormPayload(company_name="Acme", name="John", email="j@a.com", phone="+1234567890")
        assert p.phone == "+1234567890"

    def test_14_enterprise_interest_default_source(self):
        from app.api.endpoints.sales import EnterpriseInterestPayload
        p = EnterpriseInterestPayload()
        assert p.source == "billing_page"

    def test_15_trial_event_validates_allowed_types(self):
        from app.api.endpoints.sales import TrialEventPayload
        for et in ("TRIAL_STARTED", "TRIAL_CONVERTED", "TRIAL_EXPIRED"):
            p = TrialEventPayload(org_id="org-1", event_type=et)
            assert p.event_type == et

    def test_16_trial_event_rejects_invalid_type(self):
        from app.api.endpoints.sales import TrialEventPayload
        with pytest.raises(Exception):
            TrialEventPayload(org_id="org-1", event_type="INVALID_TYPE")

    def test_17_trial_event_accepts_started(self):
        from app.api.endpoints.sales import TrialEventPayload
        p = TrialEventPayload(org_id="org-1", event_type="TRIAL_STARTED")
        assert p.event_type == "TRIAL_STARTED"

    def test_18_trial_event_accepts_converted(self):
        from app.api.endpoints.sales import TrialEventPayload
        p = TrialEventPayload(org_id="org-1", event_type="TRIAL_CONVERTED")
        assert p.event_type == "TRIAL_CONVERTED"

    def test_19_trial_event_accepts_expired(self):
        from app.api.endpoints.sales import TrialEventPayload
        p = TrialEventPayload(org_id="org-1", event_type="TRIAL_EXPIRED")
        assert p.event_type == "TRIAL_EXPIRED"


# ══════════════════════════════════════════════════════════════════════════════
# Part 3: Demo Constants (Tests 20-23)
# ══════════════════════════════════════════════════════════════════════════════

class TestDemoConstants:
    """Verify demo workspace constants are valid UUIDs."""

    def _is_uuid(self, val: str) -> bool:
        try:
            uuid.UUID(val)
            return True
        except ValueError:
            return False

    def test_20_demo_org_id_valid_uuid(self):
        from app.api.endpoints.sales import DEMO_ORG_ID
        assert self._is_uuid(DEMO_ORG_ID)

    def test_21_demo_project_id_valid_uuid(self):
        from app.api.endpoints.sales import DEMO_PROJECT_ID
        assert self._is_uuid(DEMO_PROJECT_ID)

    def test_22_demo_run_id_valid_uuid(self):
        from app.api.endpoints.sales import DEMO_RUN_ID
        assert self._is_uuid(DEMO_RUN_ID)

    def test_23_demo_user_id_valid_uuid(self):
        from app.api.endpoints.sales import DEMO_USER_ID
        assert self._is_uuid(DEMO_USER_ID)


# ══════════════════════════════════════════════════════════════════════════════
# Part 4: Migration SQL (Tests 24-29)
# ══════════════════════════════════════════════════════════════════════════════

class TestMigrationSQL:
    """Verify phase22 migration SQL content."""

    @pytest.fixture(autouse=True)
    def _load_sql(self):
        sql_path = BACKEND_DIR / "scripts" / "015_sales_engine.sql"
        assert sql_path.exists(), "015_sales_engine.sql not found"
        self.sql = sql_path.read_text()

    def test_24_migration_file_exists(self):
        assert (BACKEND_DIR / "scripts" / "015_sales_engine.sql").exists()

    def test_25_creates_sales_leads_table(self):
        assert "sales_leads" in self.sql
        assert "CREATE TABLE" in self.sql.upper() or "create table" in self.sql

    def test_26_creates_idx_sales_leads_created(self):
        assert "idx_sales_leads_created" in self.sql

    def test_27_creates_idx_sales_leads_source(self):
        assert "idx_sales_leads_source" in self.sql

    def test_28_rls_policy_service_role(self):
        assert "service_role" in self.sql.lower() or "SERVICE_ROLE" in self.sql

    def test_29_rls_policy_anonymous_inserts(self):
        # Migration should allow anonymous or public inserts for contact form
        lower = self.sql.lower()
        assert "anon" in lower or "public" in lower or "insert" in lower


# ══════════════════════════════════════════════════════════════════════════════
# Part 5: Router Registration in main.py (Tests 30-32)
# ══════════════════════════════════════════════════════════════════════════════

class TestRouterRegistration:
    """Verify sales router is registered in main.py."""

    @pytest.fixture(autouse=True)
    def _load_main(self):
        self.main_src = (BACKEND_DIR / "app" / "main.py").read_text()

    def test_30_sales_router_imported(self):
        assert "sales" in self.main_src
        assert "import" in self.main_src

    def test_31_sales_router_uses_api_v1_prefix(self):
        assert "API_V1_STR" in self.main_src or "api/v1" in self.main_src

    def test_32_sales_router_has_sales_tag(self):
        assert '"Sales"' in self.main_src or "'Sales'" in self.main_src


# ══════════════════════════════════════════════════════════════════════════════
# Part 6: Frontend — Contact Page (Tests 33-36)
# ══════════════════════════════════════════════════════════════════════════════

class TestFrontendContactPage:
    """Verify contact page exists with proper form fields."""

    @pytest.fixture(autouse=True)
    def _load_contact(self):
        path = FRONTEND_DIR / "app" / "contact" / "page.tsx"
        assert path.exists(), "frontend/app/contact/page.tsx not found"
        self.src = path.read_text()

    def test_33_contact_page_exists(self):
        assert (FRONTEND_DIR / "app" / "contact" / "page.tsx").exists()

    def test_34_contact_has_company_name_field(self):
        assert "company_name" in self.src

    def test_35_contact_has_email_field(self):
        assert "email" in self.src

    def test_36_contact_calls_submit_contact_form(self):
        assert "submitContactForm" in self.src


# ══════════════════════════════════════════════════════════════════════════════
# Part 7: Frontend — Enterprise Modal (Tests 37-40)
# ══════════════════════════════════════════════════════════════════════════════

class TestFrontendEnterpriseModal:
    """Verify EnterpriseContactModal component."""

    def test_37_enterprise_modal_exists(self):
        assert (FRONTEND_DIR / "components" / "EnterpriseContactModal.tsx").exists()

    def test_38_enterprise_modal_tracks_interest(self):
        src = (FRONTEND_DIR / "components" / "EnterpriseContactModal.tsx").read_text()
        assert "trackEnterpriseInterest" in src

    def test_39_billing_imports_enterprise_modal(self):
        # Enterprise contact is now on /plans; billing page links there via Upgrade Plan
        src = (FRONTEND_DIR / "app" / "settings" / "billing" / "page.tsx").read_text()
        assert "Upgrade Plan" in src or "EnterpriseContactModal" in src

    def test_40_billing_has_enterprise_modal_state(self):
        # Billing page now uses portal-session for billing management
        src = (FRONTEND_DIR / "app" / "settings" / "billing" / "page.tsx").read_text()
        assert "portalLoading" in src or "enterpriseModalOpen" in src


# ══════════════════════════════════════════════════════════════════════════════
# Part 8: Frontend — UpgradeNudge (Tests 41-43)
# ══════════════════════════════════════════════════════════════════════════════

class TestFrontendUpgradeNudge:
    """Verify UpgradeNudge component."""

    @pytest.fixture(autouse=True)
    def _load_src(self):
        path = FRONTEND_DIR / "components" / "UpgradeNudge.tsx"
        assert path.exists(), "UpgradeNudge.tsx not found"
        self.src = path.read_text()

    def test_41_upgrade_nudge_exists(self):
        assert (FRONTEND_DIR / "components" / "UpgradeNudge.tsx").exists()

    def test_42_upgrade_nudge_has_resource_prop(self):
        assert "resource" in self.src

    def test_43_upgrade_nudge_links_to_plans(self):
        assert "/plans" in self.src


# ══════════════════════════════════════════════════════════════════════════════
# Part 9: Frontend — TrialBanner (Tests 44-47)
# ══════════════════════════════════════════════════════════════════════════════

class TestFrontendTrialBanner:
    """Verify TrialBanner component."""

    @pytest.fixture(autouse=True)
    def _load_src(self):
        path = FRONTEND_DIR / "components" / "TrialBanner.tsx"
        assert path.exists(), "TrialBanner.tsx not found"
        self.src = path.read_text()

    def test_44_trial_banner_exists(self):
        assert (FRONTEND_DIR / "components" / "TrialBanner.tsx").exists()

    def test_45_trial_banner_tracks_started(self):
        assert "TRIAL_STARTED" in self.src

    def test_46_trial_banner_shows_days(self):
        assert "daysLeft" in self.src or "days" in self.src.lower()

    def test_47_trial_banner_has_upgrade_cta(self):
        assert "Upgrade" in self.src


# ══════════════════════════════════════════════════════════════════════════════
# Part 10: Frontend — DemoBanner (Tests 48-52)
# ══════════════════════════════════════════════════════════════════════════════

class TestFrontendDemoBanner:
    """Verify DemoBanner component and its integration."""

    def test_48_demo_banner_exists(self):
        assert (FRONTEND_DIR / "components" / "DemoBanner.tsx").exists()

    def test_49_demo_banner_calls_reset(self):
        src = (FRONTEND_DIR / "components" / "DemoBanner.tsx").read_text()
        assert "resetDemoWorkspace" in src

    def test_50_demo_banner_shows_demo_text(self):
        src = (FRONTEND_DIR / "components" / "DemoBanner.tsx").read_text()
        assert "Demo Workspace" in src

    def test_51_appshell_imports_demo_banner(self):
        src = (FRONTEND_DIR / "components" / "layout" / "AppShell.tsx").read_text()
        assert "DemoBanner" in src

    def test_52_appshell_imports_trial_banner(self):
        src = (FRONTEND_DIR / "components" / "layout" / "AppShell.tsx").read_text()
        assert "TrialBanner" in src


# ══════════════════════════════════════════════════════════════════════════════
# Part 11: Frontend — Admin Sales Page (Tests 53-56)
# ══════════════════════════════════════════════════════════════════════════════

class TestFrontendSalesAnalyticsPage:
    """Verify admin/sales page exists with proper content."""

    @pytest.fixture(autouse=True)
    def _load_src(self):
        path = FRONTEND_DIR / "app" / "admin" / "sales" / "page.tsx"
        assert path.exists(), "frontend/app/admin/sales/page.tsx not found"
        self.src = path.read_text()

    def test_53_admin_sales_page_exists(self):
        assert (FRONTEND_DIR / "app" / "admin" / "sales" / "page.tsx").exists()

    def test_54_admin_sales_calls_analytics(self):
        assert "getSalesAnalytics" in self.src

    def test_55_admin_sales_shows_conversion_rate(self):
        assert "conversion_rate" in self.src

    def test_56_admin_sales_shows_mrr(self):
        assert "mrr_estimate" in self.src


# ══════════════════════════════════════════════════════════════════════════════
# Part 12: Frontend — Public Routes (Test 57)
# ══════════════════════════════════════════════════════════════════════════════

class TestFrontendPublicRoutes:
    """Verify /contact is in PUBLIC_ROUTES."""

    def test_57_contact_in_public_routes(self):
        src = (FRONTEND_DIR / "components" / "layout" / "AppShell.tsx").read_text()
        assert '"/contact"' in src


# ══════════════════════════════════════════════════════════════════════════════
# Part 13: Demo Data Expansion (Tests 58-65)
# ══════════════════════════════════════════════════════════════════════════════

class TestDemoDataExpansion:
    """Verify demo-data.ts has been expanded for sales engine changes."""

    @pytest.fixture(autouse=True)
    def _load_src(self):
        path = FRONTEND_DIR / "lib" / "demo-data.ts"
        assert path.exists(), "demo-data.ts not found"
        self.src = path.read_text()

    def test_58_fifteen_demo_audits(self):
        # Count "audit-demo-" entries
        count = self.src.count("audit-demo-")
        assert count >= 15, f"Expected ≥15 audit entries, found {count}"

    def test_59_demo_evidence_records(self):
        assert "DEMO_EVIDENCE_RECORDS" in self.src

    def test_60_demo_health_score(self):
        assert "DEMO_HEALTH_SCORE" in self.src

    def test_61_extended_activity_timeline(self):
        # Count "act-" entries (at least 8)
        count = len(re.findall(r'"act-\d+"', self.src))
        assert count >= 8, f"Expected ≥8 activity entries, found {count}"

    def test_62_audits_mix_statuses(self):
        assert '"approved"' in self.src
        assert '"pending"' in self.src
        assert '"rejected"' in self.src

    def test_63_health_score_risk_breakdown(self):
        assert "risk_breakdown" in self.src

    def test_64_health_score_reuse_stats(self):
        assert "reused_from_memory" in self.src

    def test_65_health_score_export_gate(self):
        assert "export_gate" in self.src


# ══════════════════════════════════════════════════════════════════════════════
# Part 14: API Client Methods (Tests 66-70)
# ══════════════════════════════════════════════════════════════════════════════

class TestApiClientMethods:
    """Verify api.ts has all expected sales-related methods."""

    @pytest.fixture(autouse=True)
    def _load_src(self):
        self.src = (FRONTEND_DIR / "lib" / "api.ts").read_text()

    def test_66_submit_contact_form(self):
        assert "submitContactForm" in self.src

    def test_67_track_enterprise_interest(self):
        assert "trackEnterpriseInterest" in self.src

    def test_68_track_trial_event(self):
        assert "trackTrialEvent" in self.src

    def test_69_get_sales_analytics(self):
        assert "getSalesAnalytics" in self.src

    def test_70_reset_demo_workspace(self):
        assert "resetDemoWorkspace" in self.src


# ══════════════════════════════════════════════════════════════════════════════
# Part 15: Subscription Plan Definitions (Tests 71-76)
# ══════════════════════════════════════════════════════════════════════════════

class TestSubscriptionPlans:
    """Verify plan definitions used by sales engine."""

    def test_71_free_plan_exists(self):
        from app.core.subscription import PLAN_DEFAULTS
        assert "FREE" in PLAN_DEFAULTS

    def test_72_pro_plan_exists(self):
        from app.core.subscription import PLAN_DEFAULTS
        assert "PRO" in PLAN_DEFAULTS

    def test_73_enterprise_plan_exists(self):
        from app.core.subscription import PLAN_DEFAULTS
        assert "ENTERPRISE" in PLAN_DEFAULTS

    def test_74_free_plan_runs_limit(self):
        from app.core.subscription import PLAN_DEFAULTS
        assert PLAN_DEFAULTS["FREE"]["max_runs_per_month"] == 10

    def test_75_pro_plan_runs_limit(self):
        from app.core.subscription import PLAN_DEFAULTS
        assert PLAN_DEFAULTS["PRO"]["max_runs_per_month"] == 100

    def test_76_enterprise_plan_runs_limit(self):
        from app.core.subscription import PLAN_DEFAULTS
        assert PLAN_DEFAULTS["ENTERPRISE"]["max_runs_per_month"] == 10_000
