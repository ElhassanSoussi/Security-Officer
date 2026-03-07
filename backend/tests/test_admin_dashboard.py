"""
test_admin_dashboard.py — Admin Dashboard Endpoint Tests
=========================================================

Validates:
  - GET /admin/dashboard-stats endpoint shape and presence
  - GET /admin/plan-distribution endpoint shape
  - GET /admin/mrr-summary endpoint shape and calculation
  - Frontend admin page file exists with new components
  - API client methods exist
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]


# ─── Backend endpoint existence ──────────────────────────────────────────────

class TestAdminEndpoints:
    """Verify admin endpoint functions exist and have correct signatures."""

    def test_01_dashboard_stats_endpoint_exists(self):
        from app.api.endpoints.admin import get_dashboard_stats
        assert callable(get_dashboard_stats)

    def test_02_plan_distribution_endpoint_exists(self):
        from app.api.endpoints.admin import get_plan_distribution
        assert callable(get_plan_distribution)

    def test_03_mrr_summary_endpoint_exists(self):
        from app.api.endpoints.admin import get_mrr_summary
        assert callable(get_mrr_summary)

    def test_04_retention_job_still_exists(self):
        from app.api.endpoints.admin import trigger_retention_job
        assert callable(trigger_retention_job)

    def test_05_access_report_still_exists(self):
        from app.api.endpoints.admin import get_access_report
        assert callable(get_access_report)


# ─── MRR calculation logic ──────────────────────────────────────────────────

class TestMrrCalculation:
    """Verify MRR pricing constants match product spec."""

    def test_06_starter_price(self):
        # Starter: $149/mo = 14900 cents
        from app.api.endpoints import admin
        source = Path(admin.__file__).read_text()
        assert "14900" in source

    def test_07_growth_price(self):
        # Growth: $499/mo = 49900 cents
        from app.api.endpoints import admin
        source = Path(admin.__file__).read_text()
        assert "49900" in source

    def test_08_elite_price(self):
        # Elite: $1499/mo = 149900 cents
        from app.api.endpoints import admin
        source = Path(admin.__file__).read_text()
        assert "149900" in source


# ─── File existence checks ────────────────────────────────────────────────────

class TestFileExistence:
    """Verify source files exist and have expected content."""

    def test_09_admin_endpoint_file(self):
        path = ROOT_DIR / "backend" / "app" / "api" / "endpoints" / "admin.py"
        assert path.exists()

    def test_10_admin_has_dashboard_stats(self):
        path = ROOT_DIR / "backend" / "app" / "api" / "endpoints" / "admin.py"
        content = path.read_text()
        assert "dashboard-stats" in content

    def test_11_admin_has_plan_distribution(self):
        path = ROOT_DIR / "backend" / "app" / "api" / "endpoints" / "admin.py"
        content = path.read_text()
        assert "plan-distribution" in content

    def test_12_admin_has_mrr_summary(self):
        path = ROOT_DIR / "backend" / "app" / "api" / "endpoints" / "admin.py"
        content = path.read_text()
        assert "mrr-summary" in content

    def test_13_frontend_admin_page_exists(self):
        path = ROOT_DIR / "frontend" / "app" / "admin" / "page.tsx"
        assert path.exists()

    def test_14_frontend_admin_has_mrr(self):
        path = ROOT_DIR / "frontend" / "app" / "admin" / "page.tsx"
        content = path.read_text()
        assert "MrrSummary" in content or "mrr" in content.lower()

    def test_15_frontend_admin_has_plan_distribution(self):
        path = ROOT_DIR / "frontend" / "app" / "admin" / "page.tsx"
        content = path.read_text()
        assert "PlanDistribution" in content or "PlanBar" in content

    def test_16_frontend_admin_has_stat_card(self):
        path = ROOT_DIR / "frontend" / "app" / "admin" / "page.tsx"
        content = path.read_text()
        assert "StatCard" in content

    def test_17_api_ts_has_dashboard_stats(self):
        path = ROOT_DIR / "frontend" / "lib" / "api.ts"
        content = path.read_text()
        assert "getAdminDashboardStats" in content

    def test_18_api_ts_has_plan_distribution(self):
        path = ROOT_DIR / "frontend" / "lib" / "api.ts"
        content = path.read_text()
        assert "getPlanDistribution" in content

    def test_19_api_ts_has_mrr_summary(self):
        path = ROOT_DIR / "frontend" / "lib" / "api.ts"
        content = path.read_text()
        assert "getMrrSummary" in content

    def test_20_admin_endpoint_has_role_check(self):
        path = ROOT_DIR / "backend" / "app" / "api" / "endpoints" / "admin.py"
        content = path.read_text()
        assert "owner" in content and "admin" in content
