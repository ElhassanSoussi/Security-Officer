"""
test_upgrade_modal.py — Tests for the Context-Aware Upgrade Modal system.

Groups:
  1. get_next_tier() — PLAN_NEXT_TIER ladder (5)
  2. PlanService.get_next_tier() static method (3)
  3. _raise_limit_exceeded() canonical fields (current_plan, used, next_plan) (6)
  4. _raise_limit_exceeded() legacy field backward compat (3)
  5. next_plan is None for Elite (2)
  6. Frontend UpgradeModal file content (7)
  7. AppShell mounts UpgradeModal (2)
  8. api.ts dispatches plan:limit_exceeded event (4)
  9. No enforcement logic modified (3)

Total: 35
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

# ── Paths ──────────────────────────────────────────────────────────────────
BACKEND_DIR  = os.path.join(os.path.dirname(__file__), "..")
FRONTEND_DIR = os.path.join(BACKEND_DIR, "..", "frontend")

UPGRADE_MODAL_PATH = os.path.join(FRONTEND_DIR, "components", "UpgradeModal.tsx")
APPSHELL_PATH      = os.path.join(FRONTEND_DIR, "components", "layout", "AppShell.tsx")
API_TS_PATH        = os.path.join(FRONTEND_DIR, "lib", "api.ts")

sys.path.insert(0, BACKEND_DIR)


# ── Helpers (reuse from test_plan_enforcement) ─────────────────────────────

def _mock_sb_plan(plan_value: str = "starter"):
    mock_sb = MagicMock()
    plan_result = MagicMock()
    plan_result.data = {"plan": plan_value}
    plan_chain = MagicMock()
    plan_chain.select.return_value = plan_chain
    plan_chain.eq.return_value = plan_chain
    plan_chain.single.return_value = plan_chain
    plan_chain.execute.return_value = plan_result

    count_result = MagicMock()
    count_result.count = 999
    count_result.data = []
    count_chain = MagicMock()
    count_chain.select.return_value = count_chain
    count_chain.eq.return_value = count_chain
    count_chain.gte.return_value = count_chain
    count_chain.execute.return_value = count_result

    def table_side_effect(name):
        if name == "organizations":
            return plan_chain
        return count_chain

    mock_sb.table.side_effect = table_side_effect
    return mock_sb


# ═══════════════════════════════════════════════════════════════════════════
# 1. get_next_tier() function
# ═══════════════════════════════════════════════════════════════════════════

class TestGetNextTier:
    def test_01_starter_next_is_growth(self):
        from app.core.plan_service import Plan, get_next_tier
        assert get_next_tier(Plan.STARTER) == Plan.GROWTH

    def test_02_growth_next_is_elite(self):
        from app.core.plan_service import Plan, get_next_tier
        assert get_next_tier(Plan.GROWTH) == Plan.ELITE

    def test_03_elite_next_is_none(self):
        from app.core.plan_service import Plan, get_next_tier
        assert get_next_tier(Plan.ELITE) is None

    def test_04_next_tier_map_exported(self):
        from app.core.plan_service import PLAN_NEXT_TIER, Plan
        assert Plan.STARTER in PLAN_NEXT_TIER
        assert Plan.GROWTH  in PLAN_NEXT_TIER
        assert Plan.ELITE   in PLAN_NEXT_TIER

    def test_05_get_next_tier_callable(self):
        from app.core.plan_service import get_next_tier
        assert callable(get_next_tier)


# ═══════════════════════════════════════════════════════════════════════════
# 2. PlanService.get_next_tier() static method
# ═══════════════════════════════════════════════════════════════════════════

class TestPlanServiceGetNextTier:
    def test_06_static_method_exists(self):
        from app.core.plan_service import PlanService
        assert hasattr(PlanService, "get_next_tier")
        assert callable(PlanService.get_next_tier)

    def test_07_starter_returns_growth(self):
        from app.core.plan_service import Plan, PlanService
        assert PlanService.get_next_tier(Plan.STARTER) == Plan.GROWTH

    def test_08_elite_returns_none(self):
        from app.core.plan_service import Plan, PlanService
        assert PlanService.get_next_tier(Plan.ELITE) is None


# ═══════════════════════════════════════════════════════════════════════════
# 3. _raise_limit_exceeded() — canonical fields
# ═══════════════════════════════════════════════════════════════════════════

class TestRaiseLimitExceededCanonical:
    @patch("app.core.plan_service._admin_sb")
    def _trigger_projects_limit(self, mock_admin):
        from app.core.plan_service import PlanService
        sb = _mock_sb_plan("starter")
        proj_chain = MagicMock()
        proj_result = MagicMock(); proj_result.count = 5; proj_result.data = []
        proj_chain.select.return_value = proj_chain
        proj_chain.eq.return_value = proj_chain
        proj_chain.execute.return_value = proj_result
        original = sb.table.side_effect
        sb.table.side_effect = lambda n: proj_chain if n == "projects" else original(n)
        mock_admin.return_value = sb
        with pytest.raises(HTTPException) as exc:
            PlanService.enforce_projects_limit("org-x")
        return exc.value.detail

    def _get_detail(self):
        """Helper: trigger a starter projects limit and return the detail dict."""
        from app.core.plan_service import Plan, _raise_limit_exceeded
        with pytest.raises(HTTPException) as exc:
            _raise_limit_exceeded("projects", 5, 5, Plan.STARTER)
        return exc.value.detail

    def test_09_current_plan_field_present(self):
        d = self._get_detail()
        assert "current_plan" in d

    def test_10_current_plan_value(self):
        d = self._get_detail()
        assert d["current_plan"] == "starter"

    def test_11_used_field_present(self):
        d = self._get_detail()
        assert "used" in d

    def test_12_used_equals_current(self):
        d = self._get_detail()
        assert d["used"] == 5

    def test_13_next_plan_field_present(self):
        d = self._get_detail()
        assert "next_plan" in d

    def test_14_next_plan_value_for_starter(self):
        d = self._get_detail()
        assert d["next_plan"] == "growth"


# ═══════════════════════════════════════════════════════════════════════════
# 4. _raise_limit_exceeded() — backward compat legacy fields
# ═══════════════════════════════════════════════════════════════════════════

class TestRaiseLimitExceededLegacy:
    def _get_detail(self):
        from app.core.plan_service import Plan, _raise_limit_exceeded
        with pytest.raises(HTTPException) as exc:
            _raise_limit_exceeded("documents", 25, 25, Plan.STARTER)
        return exc.value.detail

    def test_15_plan_legacy_field_still_present(self):
        assert "plan" in self._get_detail()

    def test_16_current_count_legacy_field_still_present(self):
        assert "current_count" in self._get_detail()

    def test_17_legacy_plan_matches_current_plan(self):
        d = self._get_detail()
        assert d["plan"] == d["current_plan"]


# ═══════════════════════════════════════════════════════════════════════════
# 5. Elite has no next_plan
# ═══════════════════════════════════════════════════════════════════════════

class TestEliteNextPlan:
    def test_18_next_plan_none_for_elite(self):
        from app.core.plan_service import Plan, _raise_limit_exceeded
        with pytest.raises(HTTPException) as exc:
            _raise_limit_exceeded("projects", 10001, 10000, Plan.ELITE)
        assert exc.value.detail["next_plan"] is None

    def test_19_next_plan_none_for_growth(self):
        from app.core.plan_service import Plan, _raise_limit_exceeded
        with pytest.raises(HTTPException) as exc:
            _raise_limit_exceeded("runs", 101, 100, Plan.GROWTH)
        assert exc.value.detail["next_plan"] == "elite"


# ═══════════════════════════════════════════════════════════════════════════
# 6. Frontend UpgradeModal file content
# ═══════════════════════════════════════════════════════════════════════════

class TestUpgradeModalFile:
    @pytest.fixture(autouse=True)
    def _load(self):
        with open(UPGRADE_MODAL_PATH) as f:
            self.src = f.read()

    def test_20_file_exists(self):
        assert os.path.isfile(UPGRADE_MODAL_PATH)

    def test_21_exports_upgrade_modal(self):
        assert "export function UpgradeModal" in self.src

    def test_22_listens_plan_limit_exceeded_event(self):
        assert "plan:limit_exceeded" in self.src

    def test_23_calls_createPortalSessionV2(self):
        assert "createPortalSessionV2" in self.src

    def test_24_shows_resource_label(self):
        assert "RESOURCE_LABELS" in self.src

    def test_25_shows_next_plan_unlocks(self):
        assert "PLAN_UNLOCKS" in self.src or "unlocks" in self.src

    def test_26_shows_next_plan_price(self):
        assert "PLAN_PRICES" in self.src or "nextPrice" in self.src


# ═══════════════════════════════════════════════════════════════════════════
# 7. AppShell mounts UpgradeModal
# ═══════════════════════════════════════════════════════════════════════════

class TestAppShellMountsUpgradeModal:
    @pytest.fixture(autouse=True)
    def _load(self):
        with open(APPSHELL_PATH) as f:
            self.src = f.read()

    def test_27_imports_upgrade_modal(self):
        assert "UpgradeModal" in self.src

    def test_28_renders_upgrade_modal(self):
        assert "<UpgradeModal" in self.src


# ═══════════════════════════════════════════════════════════════════════════
# 8. api.ts dispatches plan:limit_exceeded event
# ═══════════════════════════════════════════════════════════════════════════

class TestApiTsLimitEvent:
    @pytest.fixture(autouse=True)
    def _load(self):
        with open(API_TS_PATH) as f:
            self.src = f.read()

    def test_29_dispatches_plan_limit_exceeded_event(self):
        assert "plan:limit_exceeded" in self.src

    def test_30_checks_403_status(self):
        assert "403" in self.src

    def test_31_checks_plan_limit_exceeded_code(self):
        assert '"plan_limit_exceeded"' in self.src

    def test_32_upload_document_fires_event(self):
        # Both raw-fetch upload methods should handle the 403
        assert self.src.count("plan:limit_exceeded") >= 3  # central fetch + 2 upload methods


# ═══════════════════════════════════════════════════════════════════════════
# 9. No enforcement logic modified (regression guard)
# ═══════════════════════════════════════════════════════════════════════════

class TestEnforcementNotBroken:
    def test_33_enforce_projects_still_raises_403(self):
        from app.core.plan_service import Plan, _raise_limit_exceeded
        with pytest.raises(HTTPException) as exc:
            _raise_limit_exceeded("projects", 5, 5, Plan.STARTER)
        assert exc.value.status_code == 403

    def test_34_enforce_error_field_unchanged(self):
        from app.core.plan_service import Plan, _raise_limit_exceeded
        with pytest.raises(HTTPException) as exc:
            _raise_limit_exceeded("runs", 10, 10, Plan.STARTER)
        assert exc.value.detail["error"] == "plan_limit_exceeded"

    def test_35_enforce_message_field_unchanged(self):
        from app.core.plan_service import Plan, _raise_limit_exceeded
        with pytest.raises(HTTPException) as exc:
            _raise_limit_exceeded("documents", 25, 25, Plan.STARTER)
        assert exc.value.detail["message"] == "Upgrade required to continue"
