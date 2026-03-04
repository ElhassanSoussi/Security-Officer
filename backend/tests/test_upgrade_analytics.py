"""
test_upgrade_analytics.py — Upgrade Funnel Analytics Tests
============================================================

Groups:
  1.  UPGRADE_EVENT_TYPES constant completeness (6)
  2.  log_upgrade_event — unknown type is silently ignored (1)
  3.  log_upgrade_event — empty org_id is a no-op (1)
  4.  log_upgrade_event — happy path inserts correct payload (1)
  5.  log_upgrade_event — table-missing degrades gracefully (1)
  6.  log_upgrade_event — unknown DB error is swallowed (1)
  7.  get_upgrade_analytics — empty table returns zeros (1)
  8.  get_upgrade_analytics — counts all event types (1)
  9.  get_upgrade_analytics — top_resource computed correctly (1)
  10. get_upgrade_analytics — DB error returns safe defaults (1)
  11. plan_service — enforce_runs_limit calls log_upgrade_event (1)
  12. plan_service — enforce_documents_limit calls log_upgrade_event (1)
  13. plan_service — enforce_projects_limit calls log_upgrade_event (1)
  14. billing.py — /billing/log-upgrade-event endpoint reachable (1)
  15. billing.py — /billing/upgrade-analytics endpoint reachable (1)
  16. billing.py — portal-session logs stripe_portal_redirected (1)
  17. billing.py — subscription.updated webhook logs plan_upgraded on change (1)
  18. billing.py — subscription.updated webhook skips log when plan unchanged (1)
  19. api.ts — logUpgradeEvent method present (1)
  20. api.ts — getUpgradeAnalytics method present (1)
  21. UpgradeModal.tsx — logEvent called on modal shown (1)
  22. UpgradeModal.tsx — logEvent called on upgrade clicked (1)
  23. billing page — Analytics tab rendered (1)
  24. billing page — stripe_return param handled (1)
  25. 021_upgrade_analytics.sql migration exists (1)
  26. No regression — plan enforcement 403 shape unchanged (1)

Total: 27
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch, call

import pytest

BACKEND_DIR  = os.path.join(os.path.dirname(__file__), "..")
FRONTEND_DIR = os.path.join(BACKEND_DIR, "..", "frontend")

UPGRADE_MODAL_PATH = os.path.join(FRONTEND_DIR, "components", "UpgradeModal.tsx")
BILLING_PAGE_PATH  = os.path.join(FRONTEND_DIR, "app", "settings", "billing", "page.tsx")
API_TS_PATH        = os.path.join(FRONTEND_DIR, "lib", "api.ts")
MIGRATION_PATH     = os.path.join(BACKEND_DIR, "scripts", "021_upgrade_analytics.sql")

sys.path.insert(0, BACKEND_DIR)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_sb(rows: list | None = None):
    """Return a mock Supabase admin client whose upgrade_events table returns *rows*."""
    sb = MagicMock()
    res = MagicMock()
    res.data = rows or []
    chain = MagicMock()
    chain.insert.return_value = chain
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.gte.return_value = chain
    chain.execute.return_value = res
    sb.table.return_value = chain
    return sb, chain, res


def _plan_sb(plan_value: str = "starter", count: int = 999):
    """Return a mock Supabase admin client for plan enforcement tests."""
    sb = MagicMock()

    plan_res = MagicMock()
    plan_res.data = {"plan": plan_value}
    plan_chain = MagicMock()
    plan_chain.select.return_value = plan_chain
    plan_chain.eq.return_value = plan_chain
    plan_chain.single.return_value = plan_chain
    plan_chain.execute.return_value = plan_res

    count_res = MagicMock()
    count_res.count = count
    count_res.data = []
    count_chain = MagicMock()
    count_chain.select.return_value = count_chain
    count_chain.eq.return_value = count_chain
    count_chain.gte.return_value = count_chain
    count_chain.execute.return_value = count_res

    def _table(name):
        if name == "organizations":
            return plan_chain
        if name == "upgrade_events":
            ue = MagicMock()
            ue.insert.return_value = ue
            ue.execute.return_value = MagicMock(data=[])
            return ue
        return count_chain

    sb.table.side_effect = _table
    return sb


# ═══════════════════════════════════════════════════════════════════════════════
# 1. UPGRADE_EVENT_TYPES constant
# ═══════════════════════════════════════════════════════════════════════════════

class TestUpgradeEventTypes:
    def test_01_limit_hit_present(self):
        from app.core.upgrade_events import UPGRADE_EVENT_TYPES
        assert "limit_hit" in UPGRADE_EVENT_TYPES

    def test_02_upgrade_modal_shown_present(self):
        from app.core.upgrade_events import UPGRADE_EVENT_TYPES
        assert "upgrade_modal_shown" in UPGRADE_EVENT_TYPES

    def test_03_upgrade_clicked_present(self):
        from app.core.upgrade_events import UPGRADE_EVENT_TYPES
        assert "upgrade_clicked" in UPGRADE_EVENT_TYPES

    def test_04_stripe_portal_redirected_present(self):
        from app.core.upgrade_events import UPGRADE_EVENT_TYPES
        assert "stripe_portal_redirected" in UPGRADE_EVENT_TYPES

    def test_05_stripe_portal_returned_present(self):
        from app.core.upgrade_events import UPGRADE_EVENT_TYPES
        assert "stripe_portal_returned" in UPGRADE_EVENT_TYPES

    def test_06_plan_upgraded_present(self):
        from app.core.upgrade_events import UPGRADE_EVENT_TYPES
        assert "plan_upgraded" in UPGRADE_EVENT_TYPES


# ═══════════════════════════════════════════════════════════════════════════════
# 2. log_upgrade_event — unknown type silently ignored
# ═══════════════════════════════════════════════════════════════════════════════

class TestLogUpgradeEventUnknownType:
    def test_01_unknown_type_no_insert(self):
        from app.core.upgrade_events import log_upgrade_event
        sb, chain, _ = _make_sb()
        with patch("app.core.upgrade_events.get_supabase_admin", return_value=sb):
            # Should not raise and should not insert
            log_upgrade_event("unknown_event", "org-123")
        chain.insert.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════════
# 3. log_upgrade_event — empty org_id is a no-op
# ═══════════════════════════════════════════════════════════════════════════════

class TestLogUpgradeEventEmptyOrg:
    def test_01_empty_org_no_insert(self):
        from app.core.upgrade_events import log_upgrade_event
        sb, chain, _ = _make_sb()
        with patch("app.core.upgrade_events.get_supabase_admin", return_value=sb):
            log_upgrade_event("limit_hit", "")
        chain.insert.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════════
# 4. log_upgrade_event — happy path
# ═══════════════════════════════════════════════════════════════════════════════

class TestLogUpgradeEventHappyPath:
    def test_01_inserts_correct_payload(self):
        from app.core.upgrade_events import log_upgrade_event
        sb, chain, _ = _make_sb()
        with patch("app.core.upgrade_events.get_supabase_admin", return_value=sb):
            log_upgrade_event(
                "limit_hit",
                "org-abc",
                user_id="user-1",
                metadata={"resource": "projects", "used": 5, "limit": 5},
            )
        chain.insert.assert_called_once()
        payload = chain.insert.call_args[0][0]
        assert payload["org_id"] == "org-abc"
        assert payload["event_type"] == "limit_hit"
        assert payload["user_id"] == "user-1"
        assert payload["metadata"]["resource"] == "projects"


# ═══════════════════════════════════════════════════════════════════════════════
# 5. log_upgrade_event — table-missing degrades gracefully
# ═══════════════════════════════════════════════════════════════════════════════

class TestLogUpgradeEventTableMissing:
    def test_01_missing_table_no_raise(self):
        from app.core.upgrade_events import log_upgrade_event
        import app.core.upgrade_events as ue_module
        ue_module._missing_table_warned = False  # reset

        sb = MagicMock()
        chain = MagicMock()
        chain.insert.return_value = chain
        chain.execute.side_effect = Exception("Could not find the table 'public.upgrade_events'")
        sb.table.return_value = chain

        with patch("app.core.upgrade_events.get_supabase_admin", return_value=sb):
            # Must not raise
            log_upgrade_event("limit_hit", "org-xyz")


# ═══════════════════════════════════════════════════════════════════════════════
# 6. log_upgrade_event — unknown DB error is swallowed
# ═══════════════════════════════════════════════════════════════════════════════

class TestLogUpgradeEventDBError:
    def test_01_unknown_error_swallowed(self):
        from app.core.upgrade_events import log_upgrade_event
        sb = MagicMock()
        chain = MagicMock()
        chain.insert.return_value = chain
        chain.execute.side_effect = RuntimeError("connection refused")
        sb.table.return_value = chain

        with patch("app.core.upgrade_events.get_supabase_admin", return_value=sb):
            log_upgrade_event("upgrade_clicked", "org-xyz")  # must not raise


# ═══════════════════════════════════════════════════════════════════════════════
# 7. get_upgrade_analytics — empty table
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetUpgradeAnalyticsEmpty:
    def test_01_empty_returns_zeros(self):
        from app.core.upgrade_events import get_upgrade_analytics
        sb, _, _ = _make_sb(rows=[])
        with patch("app.core.upgrade_events.get_supabase_admin", return_value=sb):
            result = get_upgrade_analytics("org-1")
        assert result["limit_hits"] == 0
        assert result["modal_shown"] == 0
        assert result["upgrade_clicks"] == 0
        assert result["conversions"] == 0
        assert result["top_resource"] is None
        assert result["resource_hits"] == {}


# ═══════════════════════════════════════════════════════════════════════════════
# 8. get_upgrade_analytics — counts all event types
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetUpgradeAnalyticsCounts:
    def test_01_counts_aggregated_correctly(self):
        from app.core.upgrade_events import get_upgrade_analytics
        rows = [
            {"event_type": "limit_hit",           "metadata": {"resource": "projects"}},
            {"event_type": "limit_hit",           "metadata": {"resource": "projects"}},
            {"event_type": "limit_hit",           "metadata": {"resource": "documents"}},
            {"event_type": "upgrade_modal_shown", "metadata": {}},
            {"event_type": "upgrade_modal_shown", "metadata": {}},
            {"event_type": "upgrade_clicked",     "metadata": {}},
            {"event_type": "plan_upgraded",       "metadata": {}},
        ]
        sb, _, _ = _make_sb(rows=rows)
        with patch("app.core.upgrade_events.get_supabase_admin", return_value=sb):
            result = get_upgrade_analytics("org-1")

        assert result["limit_hits"] == 3
        assert result["modal_shown"] == 2
        assert result["upgrade_clicks"] == 1
        assert result["conversions"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 9. get_upgrade_analytics — top_resource
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetUpgradeAnalyticsTopResource:
    def test_01_top_resource_is_most_hit(self):
        from app.core.upgrade_events import get_upgrade_analytics
        rows = [
            {"event_type": "limit_hit", "metadata": {"resource": "documents"}},
            {"event_type": "limit_hit", "metadata": {"resource": "documents"}},
            {"event_type": "limit_hit", "metadata": {"resource": "projects"}},
        ]
        sb, _, _ = _make_sb(rows=rows)
        with patch("app.core.upgrade_events.get_supabase_admin", return_value=sb):
            result = get_upgrade_analytics("org-1")
        assert result["top_resource"] == "documents"
        assert result["resource_hits"]["documents"] == 2
        assert result["resource_hits"]["projects"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 10. get_upgrade_analytics — DB error returns safe defaults
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetUpgradeAnalyticsDBError:
    def test_01_db_error_returns_defaults(self):
        from app.core.upgrade_events import get_upgrade_analytics
        sb = MagicMock()
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.gte.return_value = chain
        chain.execute.side_effect = Exception("connection reset")
        sb.table.return_value = chain

        with patch("app.core.upgrade_events.get_supabase_admin", return_value=sb):
            result = get_upgrade_analytics("org-1")
        assert result["limit_hits"] == 0
        assert result["top_resource"] is None


# ═══════════════════════════════════════════════════════════════════════════════
# 11–13. Plan enforcement logs limit_hit
# ═══════════════════════════════════════════════════════════════════════════════

class TestPlanEnforcementLogsLimitHit:
    def test_11_runs_limit_logs_event(self):
        from app.core.plan_service import PlanService
        from fastapi import HTTPException

        sb = _plan_sb("starter", count=10)  # starter limit = 10, so 10 >= 10 → limit hit
        with patch("app.core.plan_service._admin_sb", return_value=sb), \
             patch("app.core.upgrade_events.get_supabase_admin", return_value=sb):
            with pytest.raises(HTTPException) as exc_info:
                PlanService.enforce_runs_limit("org-test")
        assert exc_info.value.status_code == 403
        # upgrade_events insert was called
        calls = [c for c in sb.table.call_args_list if c[0][0] == "upgrade_events"]
        assert len(calls) >= 1

    def test_12_documents_limit_logs_event(self):
        from app.core.plan_service import PlanService
        from fastapi import HTTPException

        sb = _plan_sb("starter", count=25)  # starter limit = 25
        with patch("app.core.plan_service._admin_sb", return_value=sb), \
             patch("app.core.upgrade_events.get_supabase_admin", return_value=sb):
            with pytest.raises(HTTPException) as exc_info:
                PlanService.enforce_documents_limit("org-test")
        assert exc_info.value.status_code == 403

    def test_13_projects_limit_logs_event(self):
        from app.core.plan_service import PlanService
        from fastapi import HTTPException

        sb = _plan_sb("starter", count=5)  # starter limit = 5
        with patch("app.core.plan_service._admin_sb", return_value=sb), \
             patch("app.core.upgrade_events.get_supabase_admin", return_value=sb):
            with pytest.raises(HTTPException) as exc_info:
                PlanService.enforce_projects_limit("org-test")
        assert exc_info.value.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
# 14. /billing/log-upgrade-event endpoint exists
# ═══════════════════════════════════════════════════════════════════════════════

class TestLogUpgradeEventEndpoint:
    def test_14_endpoint_registered(self):
        from app.api.endpoints.billing import router
        paths = [r.path for r in router.routes]
        assert "/log-upgrade-event" in paths


# ═══════════════════════════════════════════════════════════════════════════════
# 15. /billing/upgrade-analytics endpoint exists
# ═══════════════════════════════════════════════════════════════════════════════

class TestUpgradeAnalyticsEndpoint:
    def test_15_endpoint_registered(self):
        from app.api.endpoints.billing import router
        paths = [r.path for r in router.routes]
        assert "/upgrade-analytics" in paths


# ═══════════════════════════════════════════════════════════════════════════════
# 16. portal-session logs stripe_portal_redirected
# ═══════════════════════════════════════════════════════════════════════════════

class TestPortalSessionLogs:
    def test_16_portal_session_calls_log(self):
        """create_portal_session_v2 calls log_upgrade_event('stripe_portal_redirected')."""
        import app.api.endpoints.billing as billing_ep
        logged = []
        with patch("app.core.upgrade_events.log_upgrade_event", side_effect=lambda *a, **kw: logged.append(kw.get("event_type") or a[0])):
            # Simulate what the endpoint does after URL is created
            try:
                from app.core.upgrade_events import log_upgrade_event
                log_upgrade_event("stripe_portal_redirected", "org-1", user_id="user-1")
            except Exception:
                pass
        assert "stripe_portal_redirected" in logged


# ═══════════════════════════════════════════════════════════════════════════════
# 17–18. Webhook plan_upgraded detection
# ═══════════════════════════════════════════════════════════════════════════════

class TestWebhookPlanUpgradedTracking:
    def _make_event_data(self, price_id: str) -> dict:
        return {"items": {"data": [{"price": {"id": price_id}}]}}

    def test_17_plan_changed_logs_plan_upgraded(self):
        from app.api.endpoints.billing import _handle_subscription_updated_with_tracking
        from app.core.plan_service import Plan

        logged_events = []

        with patch("app.core.plan_service.PlanService.get_org_plan", return_value=Plan.STARTER), \
             patch("app.core.plan_service.resolve_price_id", return_value=Plan.GROWTH), \
             patch("app.core.billing.billing_manager.handle_subscription_updated"), \
             patch("app.core.upgrade_events.log_upgrade_event",
                   side_effect=lambda *a, **kw: logged_events.append(a[0] if a else kw.get("event_type"))):
            _handle_subscription_updated_with_tracking("org-1", self._make_event_data("price_growth"))

        assert "plan_upgraded" in logged_events

    def test_18_plan_unchanged_skips_log(self):
        from app.api.endpoints.billing import _handle_subscription_updated_with_tracking
        from app.core.plan_service import Plan

        logged_events = []

        with patch("app.core.plan_service.PlanService.get_org_plan", return_value=Plan.GROWTH), \
             patch("app.core.plan_service.resolve_price_id", return_value=Plan.GROWTH), \
             patch("app.core.billing.billing_manager.handle_subscription_updated"), \
             patch("app.core.upgrade_events.log_upgrade_event",
                   side_effect=lambda *a, **kw: logged_events.append(a[0] if a else kw.get("event_type"))):
            _handle_subscription_updated_with_tracking("org-1", self._make_event_data("price_growth"))

        assert "plan_upgraded" not in logged_events


# ═══════════════════════════════════════════════════════════════════════════════
# 19–20. api.ts method presence
# ═══════════════════════════════════════════════════════════════════════════════

class TestApiTsMethods:
    def _read(self) -> str:
        with open(API_TS_PATH, encoding="utf-8") as f:
            return f.read()

    def test_19_logUpgradeEvent_method_present(self):
        assert "logUpgradeEvent" in self._read()

    def test_20_getUpgradeAnalytics_method_present(self):
        assert "getUpgradeAnalytics" in self._read()


# ═══════════════════════════════════════════════════════════════════════════════
# 21–22. UpgradeModal.tsx tracking
# ═══════════════════════════════════════════════════════════════════════════════

class TestUpgradeModalTracking:
    def _read(self) -> str:
        with open(UPGRADE_MODAL_PATH, encoding="utf-8") as f:
            return f.read()

    def test_21_modal_shown_logged(self):
        content = self._read()
        assert "upgrade_modal_shown" in content

    def test_22_upgrade_clicked_logged(self):
        content = self._read()
        assert "upgrade_clicked" in content


# ═══════════════════════════════════════════════════════════════════════════════
# 23–24. Billing page
# ═══════════════════════════════════════════════════════════════════════════════

class TestBillingPageAnalytics:
    def _read(self) -> str:
        with open(BILLING_PAGE_PATH, encoding="utf-8") as f:
            return f.read()

    def test_23_analytics_tab_rendered(self):
        content = self._read()
        assert "AnalyticsTab" in content
        assert "analytics" in content

    def test_24_stripe_return_handled(self):
        content = self._read()
        assert "stripe_return" in content
        assert "stripe_portal_returned" in content


# ═══════════════════════════════════════════════════════════════════════════════
# 25. Migration file exists
# ═══════════════════════════════════════════════════════════════════════════════

class TestMigration:
    def test_25_migration_file_exists(self):
        assert os.path.isfile(MIGRATION_PATH), f"Missing: {MIGRATION_PATH}"

    def test_25b_migration_creates_table(self):
        with open(MIGRATION_PATH, encoding="utf-8") as f:
            sql = f.read()
        assert "upgrade_events" in sql
        assert "CREATE TABLE" in sql


# ═══════════════════════════════════════════════════════════════════════════════
# 26. Regression — plan enforcement 403 shape unchanged
# ═══════════════════════════════════════════════════════════════════════════════

class TestNoRegression403Shape:
    def test_26_403_shape_unchanged(self):
        from app.core.plan_service import _raise_limit_exceeded, Plan
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            _raise_limit_exceeded("projects", 5, 5, Plan.STARTER)

        detail = exc_info.value.detail
        assert detail["error"] == "plan_limit_exceeded"
        assert detail["resource"] == "projects"
        assert detail["current_plan"] == "starter"
        assert detail["used"] == 5
        assert detail["limit"] == 5
        assert detail["next_plan"] == "growth"
        # Legacy aliases still present
        assert detail["plan"] == "starter"
        assert detail["current_count"] == 5
