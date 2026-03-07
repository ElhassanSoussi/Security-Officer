"""
test_onboarding_enhanced.py — Enhanced Onboarding Flow Tests
=============================================================

Validates:
  - 4-step onboarding page exists with Welcome, Org, Docs, Checklist
  - Step indicators with icons
  - Compliance checklist items
  - Backend onboarding endpoints still work
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]


class TestOnboardingPageStructure:
    """Verify the enhanced onboarding page has all 4 steps."""

    def test_01_onboarding_page_exists(self):
        path = ROOT_DIR / "frontend" / "app" / "onboarding" / "page.tsx"
        assert path.exists()

    def test_02_has_welcome_step(self):
        content = (ROOT_DIR / "frontend" / "app" / "onboarding" / "page.tsx").read_text()
        assert "Welcome" in content

    def test_03_has_organization_step(self):
        content = (ROOT_DIR / "frontend" / "app" / "onboarding" / "page.tsx").read_text()
        assert "Organization" in content

    def test_04_has_documents_step(self):
        content = (ROOT_DIR / "frontend" / "app" / "onboarding" / "page.tsx").read_text()
        assert "Documents" in content

    def test_05_has_ready_step(self):
        content = (ROOT_DIR / "frontend" / "app" / "onboarding" / "page.tsx").read_text()
        assert "Ready" in content

    def test_06_has_step_type_4(self):
        content = (ROOT_DIR / "frontend" / "app" / "onboarding" / "page.tsx").read_text()
        assert "Step = 1 | 2 | 3 | 4" in content

    def test_07_has_step_indicators(self):
        content = (ROOT_DIR / "frontend" / "app" / "onboarding" / "page.tsx").read_text()
        assert "STEPS" in content

    def test_08_has_checklist(self):
        content = (ROOT_DIR / "frontend" / "app" / "onboarding" / "page.tsx").read_text()
        assert "CHECKLIST" in content

    def test_09_checklist_has_org_item(self):
        content = (ROOT_DIR / "frontend" / "app" / "onboarding" / "page.tsx").read_text()
        assert "Create your organization" in content

    def test_10_checklist_has_docs_item(self):
        content = (ROOT_DIR / "frontend" / "app" / "onboarding" / "page.tsx").read_text()
        assert "Upload baseline compliance docs" in content

    def test_11_checklist_has_run_item(self):
        content = (ROOT_DIR / "frontend" / "app" / "onboarding" / "page.tsx").read_text()
        assert "Run your first compliance analysis" in content

    def test_12_checklist_has_kb_item(self):
        content = (ROOT_DIR / "frontend" / "app" / "onboarding" / "page.tsx").read_text()
        assert "knowledge base" in content

    def test_13_has_rocket_icon(self):
        content = (ROOT_DIR / "frontend" / "app" / "onboarding" / "page.tsx").read_text()
        assert "Rocket" in content

    def test_14_has_sparkles_icon(self):
        content = (ROOT_DIR / "frontend" / "app" / "onboarding" / "page.tsx").read_text()
        assert "Sparkles" in content

    def test_15_has_go_to_dashboard_button(self):
        content = (ROOT_DIR / "frontend" / "app" / "onboarding" / "page.tsx").read_text()
        assert "Go to Dashboard" in content


class TestOnboardingBackend:
    """Verify backend onboarding endpoints still exist."""

    def test_16_onboarding_endpoint_exists(self):
        path = ROOT_DIR / "backend" / "app" / "api" / "endpoints" / "onboarding.py"
        assert path.exists()

    def test_17_api_ts_has_onboarding_state(self):
        content = (ROOT_DIR / "frontend" / "lib" / "api.ts").read_text()
        assert "getOnboardingState" in content

    def test_18_api_ts_has_patch_onboarding(self):
        content = (ROOT_DIR / "frontend" / "lib" / "api.ts").read_text()
        assert "patchOnboardingState" in content

    def test_19_has_back_button(self):
        content = (ROOT_DIR / "frontend" / "app" / "onboarding" / "page.tsx").read_text()
        assert "Back" in content

    def test_20_has_skip_button(self):
        content = (ROOT_DIR / "frontend" / "app" / "onboarding" / "page.tsx").read_text()
        assert "Skip" in content
