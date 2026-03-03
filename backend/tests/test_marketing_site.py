"""
Marketing Site Tests

All tests are deterministic — no real DB / API / external calls.
Tests verify that all six marketing sections exist as components and
are properly wired into the root page.

Tests cover:
 1. HeroSection — component file exists
 2. HeroSection — exports HeroSection function
 3. HeroSection — has data-testid="marketing-hero"
 4. HeroSection — contains outcome-driven headline
 5. HeroSection — contains pain-focused subheadline
 6. HeroSection — contains Request a Demo CTA
 7. HeroSection — contains Start Free Trial CTA
 8. ProblemSection — component file exists
 9. ProblemSection — exports ProblemSection function
10. ProblemSection — has data-testid="marketing-problem"
11. ProblemSection — mentions manual questionnaire pain
12. ProblemSection — mentions version chaos
13. ProblemSection — mentions audit risk
14. ProblemSection — mentions time waste
15. SolutionSection — component file exists
16. SolutionSection — exports SolutionSection function
17. SolutionSection — has data-testid="marketing-solution"
18. SolutionSection — mentions auto-answer
19. SolutionSection — mentions confidence scoring
20. SolutionSection — mentions evidence vault
21. SolutionSection — mentions audit trail
22. SolutionSection — mentions export-ready compliance
23. SocialProofSection — component file exists
24. SocialProofSection — exports SocialProofSection function
25. SocialProofSection — has data-testid="marketing-social-proof"
26. SocialProofSection — contains case study template blocks
27. SocialProofSection — contains metric placeholders
28. SocialProofSection — contains anonymization disclaimer
29. PricingSection — component file exists
30. PricingSection — exports PricingSection function
31. PricingSection — has data-testid="marketing-pricing"
32. PricingSection — has Starter tier
33. PricingSection — has Growth tier
34. PricingSection — has Enterprise tier
35. PricingSection — Starter price is $149
36. PricingSection — Growth price is $499
37. PricingSection — Enterprise is Custom pricing
38. PricingSection — clear differentiation between tiers
39. EnterpriseCTASection — component file exists
40. EnterpriseCTASection — exports EnterpriseCTASection function
41. EnterpriseCTASection — has data-testid="marketing-enterprise-cta"
42. EnterpriseCTASection — contains Book Compliance Strategy Call
43. EnterpriseCTASection — contains trust bar
44. BarrelExport — index.ts exists
45. BarrelExport — re-exports all 6 components
46. Page — page.tsx imports from @/components/marketing
47. Page — page.tsx renders HeroSection
48. Page — page.tsx renders ProblemSection
49. Page — page.tsx renders SolutionSection
50. Page — page.tsx renders SocialProofSection
51. Page — page.tsx renders PricingSection
52. Page — page.tsx renders EnterpriseCTASection
53. Page — page.tsx has navigation bar
54. Page — page.tsx has footer
55. Page — page.tsx still redirects logged-in users
56. DesignTone — no hype language (revolutionary, game-changing, etc.)
57. DesignTone — enterprise tone (compliance, audit, evidence)
58. DesignTone — minimal style (no excessive exclamation marks)
59. Verify — VERIFY.md contains marketing site section
60. Verify — VERIFY.md marketing section mentions 6 marketing sections
"""

import os
import re
import sys
from pathlib import Path

import pytest

# ── Setup paths ───────────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent
FRONTEND_DIR = ROOT_DIR / "frontend"
MARKETING_DIR = FRONTEND_DIR / "components" / "marketing"
APP_DIR = FRONTEND_DIR / "app"

# Ensure env vars so Settings() doesn't crash
for var in ("SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_JWT_SECRET", "SUPABASE_SERVICE_ROLE_KEY"):
    os.environ.setdefault(var, "https://test.supabase.co" if "URL" in var else "test-key-placeholder")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _read(path: Path) -> str:
    """Read a file and return its contents, or empty string if missing."""
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _read_lower(path: Path) -> str:
    """Read a file and return lowercase contents."""
    return _read(path).lower()


# ══════════════════════════════════════════════════════════════════════════════
# Part 1: HeroSection (Tests 1-7)
# ══════════════════════════════════════════════════════════════════════════════

class TestHeroSection:
    """Verify HeroSection component exists and has required content."""

    HERO_FILE = MARKETING_DIR / "HeroSection.tsx"

    @pytest.fixture(autouse=True)
    def _load(self):
        self.src = _read(self.HERO_FILE)
        self.src_lower = self.src.lower()

    def test_01_file_exists(self):
        assert self.HERO_FILE.exists(), "HeroSection.tsx not found"

    def test_02_exports_hero_section(self):
        assert "export function HeroSection" in self.src or "export const HeroSection" in self.src

    def test_03_has_testid(self):
        assert 'data-testid="marketing-hero"' in self.src

    def test_04_outcome_driven_headline(self):
        # Headline should reference speed/time/efficiency — not hype
        assert "hours, not weeks" in self.src_lower or "submit compliance" in self.src_lower

    def test_05_pain_focused_subheadline(self):
        # Subheadline should reference the pain of manual work
        assert "spreadsheet" in self.src_lower or "copies answers" in self.src_lower or "hunts for" in self.src_lower

    def test_06_request_demo_cta(self):
        assert "request a demo" in self.src_lower or "request demo" in self.src_lower

    def test_07_start_trial_cta(self):
        assert "start free trial" in self.src_lower


# ══════════════════════════════════════════════════════════════════════════════
# Part 2: ProblemSection (Tests 8-14)
# ══════════════════════════════════════════════════════════════════════════════

class TestProblemSection:
    """Verify ProblemSection component addresses four pain points."""

    PROBLEM_FILE = MARKETING_DIR / "ProblemSection.tsx"

    @pytest.fixture(autouse=True)
    def _load(self):
        self.src = _read(self.PROBLEM_FILE)
        self.src_lower = self.src.lower()

    def test_08_file_exists(self):
        assert self.PROBLEM_FILE.exists(), "ProblemSection.tsx not found"

    def test_09_exports_problem_section(self):
        assert "export function ProblemSection" in self.src or "export const ProblemSection" in self.src

    def test_10_has_testid(self):
        assert 'data-testid="marketing-problem"' in self.src

    def test_11_manual_questionnaire_pain(self):
        assert "manual" in self.src_lower and "questionnaire" in self.src_lower

    def test_12_version_chaos(self):
        assert "version" in self.src_lower or "which" in self.src_lower and "current" in self.src_lower

    def test_13_audit_risk(self):
        assert "audit" in self.src_lower and ("risk" in self.src_lower or "liability" in self.src_lower or "disqualify" in self.src_lower)

    def test_14_time_waste(self):
        assert "hours" in self.src_lower or "weeks" in self.src_lower or "time" in self.src_lower


# ══════════════════════════════════════════════════════════════════════════════
# Part 3: SolutionSection (Tests 15-22)
# ══════════════════════════════════════════════════════════════════════════════

class TestSolutionSection:
    """Verify SolutionSection component covers all five capabilities."""

    SOLUTION_FILE = MARKETING_DIR / "SolutionSection.tsx"

    @pytest.fixture(autouse=True)
    def _load(self):
        self.src = _read(self.SOLUTION_FILE)
        self.src_lower = self.src.lower()

    def test_15_file_exists(self):
        assert self.SOLUTION_FILE.exists(), "SolutionSection.tsx not found"

    def test_16_exports_solution_section(self):
        assert "export function SolutionSection" in self.src or "export const SolutionSection" in self.src

    def test_17_has_testid(self):
        assert 'data-testid="marketing-solution"' in self.src

    def test_18_auto_answer(self):
        assert "auto-answer" in self.src_lower or "auto answer" in self.src_lower

    def test_19_confidence_scoring(self):
        assert "confidence scor" in self.src_lower

    def test_20_evidence_vault(self):
        assert "evidence vault" in self.src_lower

    def test_21_audit_trail(self):
        assert "audit trail" in self.src_lower

    def test_22_export_ready(self):
        assert "export-ready" in self.src_lower or "export ready" in self.src_lower or "submission-ready" in self.src_lower


# ══════════════════════════════════════════════════════════════════════════════
# Part 4: SocialProofSection (Tests 23-28)
# ══════════════════════════════════════════════════════════════════════════════

class TestSocialProofSection:
    """Verify SocialProofSection has case study placeholders."""

    SOCIAL_FILE = MARKETING_DIR / "SocialProofSection.tsx"

    @pytest.fixture(autouse=True)
    def _load(self):
        self.src = _read(self.SOCIAL_FILE)
        self.src_lower = self.src.lower()

    def test_23_file_exists(self):
        assert self.SOCIAL_FILE.exists(), "SocialProofSection.tsx not found"

    def test_24_exports_social_proof(self):
        assert "export function SocialProofSection" in self.src or "export const SocialProofSection" in self.src

    def test_25_has_testid(self):
        assert 'data-testid="marketing-social-proof"' in self.src

    def test_26_case_study_blocks(self):
        # Should have multiple case study entries
        assert "case_studies" in self.src_lower or "case studies" in self.src_lower

    def test_27_metric_placeholders(self):
        assert "metric" in self.src_lower or "faster" in self.src_lower or "hours saved" in self.src_lower

    def test_28_anonymization_disclaimer(self):
        assert "anonymize" in self.src_lower or "template" in self.src_lower or "representative" in self.src_lower


# ══════════════════════════════════════════════════════════════════════════════
# Part 5: PricingSection (Tests 29-38)
# ══════════════════════════════════════════════════════════════════════════════

class TestPricingSection:
    """Verify PricingSection has three tiers with clear differentiation."""

    PRICING_FILE = MARKETING_DIR / "PricingSection.tsx"

    @pytest.fixture(autouse=True)
    def _load(self):
        self.src = _read(self.PRICING_FILE)
        self.src_lower = self.src.lower()

    def test_29_file_exists(self):
        assert self.PRICING_FILE.exists(), "PricingSection.tsx not found"

    def test_30_exports_pricing_section(self):
        assert "export function PricingSection" in self.src or "export const PricingSection" in self.src

    def test_31_has_testid(self):
        assert 'data-testid="marketing-pricing"' in self.src

    def test_32_has_starter_tier(self):
        assert "starter" in self.src_lower

    def test_33_has_growth_tier(self):
        assert "growth" in self.src_lower

    def test_34_has_enterprise_tier(self):
        assert "enterprise" in self.src_lower

    def test_35_starter_price(self):
        assert "$149" in self.src

    def test_36_growth_price(self):
        assert "$499" in self.src

    def test_37_enterprise_custom_pricing(self):
        assert "custom" in self.src_lower

    def test_38_tier_differentiation(self):
        # Each tier should have different project limits
        assert "3 active project" in self.src_lower
        assert "15 active project" in self.src_lower
        assert "unlimited project" in self.src_lower


# ══════════════════════════════════════════════════════════════════════════════
# Part 6: EnterpriseCTASection (Tests 39-43)
# ══════════════════════════════════════════════════════════════════════════════

class TestEnterpriseCTASection:
    """Verify EnterpriseCTA has strategy call CTA and trust bar."""

    CTA_FILE = MARKETING_DIR / "EnterpriseCTASection.tsx"

    @pytest.fixture(autouse=True)
    def _load(self):
        self.src = _read(self.CTA_FILE)
        self.src_lower = self.src.lower()

    def test_39_file_exists(self):
        assert self.CTA_FILE.exists(), "EnterpriseCTASection.tsx not found"

    def test_40_exports_enterprise_cta(self):
        assert "export function EnterpriseCTASection" in self.src or "export const EnterpriseCTASection" in self.src

    def test_41_has_testid(self):
        assert 'data-testid="marketing-enterprise-cta"' in self.src

    def test_42_book_strategy_call(self):
        assert "book compliance strategy call" in self.src_lower

    def test_43_trust_bar(self):
        assert "encryption" in self.src_lower
        assert "soc 2" in self.src_lower
        assert "uptime" in self.src_lower


# ══════════════════════════════════════════════════════════════════════════════
# Part 7: Barrel Export + Page Wiring (Tests 44-55)
# ══════════════════════════════════════════════════════════════════════════════

class TestBarrelExportAndPageWiring:
    """Verify barrel export and page.tsx wiring of all six sections."""

    INDEX_FILE = MARKETING_DIR / "index.ts"
    PAGE_FILE = APP_DIR / "page.tsx"

    @pytest.fixture(autouse=True)
    def _load(self):
        self.index_src = _read(self.INDEX_FILE)
        self.page_src = _read(self.PAGE_FILE)
        self.page_lower = self.page_src.lower()

    def test_44_barrel_file_exists(self):
        assert self.INDEX_FILE.exists(), "marketing/index.ts not found"

    def test_45_barrel_exports_all_six(self):
        for component in [
            "HeroSection",
            "ProblemSection",
            "SolutionSection",
            "SocialProofSection",
            "PricingSection",
            "EnterpriseCTASection",
        ]:
            assert component in self.index_src, f"{component} not exported from index.ts"

    def test_46_page_imports_marketing(self):
        assert "@/components/marketing" in self.page_src

    def test_47_page_renders_hero(self):
        assert "<HeroSection" in self.page_src

    def test_48_page_renders_problem(self):
        assert "<ProblemSection" in self.page_src

    def test_49_page_renders_solution(self):
        assert "<SolutionSection" in self.page_src

    def test_50_page_renders_social_proof(self):
        assert "<SocialProofSection" in self.page_src

    def test_51_page_renders_pricing(self):
        assert "<PricingSection" in self.page_src

    def test_52_page_renders_enterprise_cta(self):
        assert "<EnterpriseCTASection" in self.page_src

    def test_53_page_has_nav(self):
        assert "<nav" in self.page_lower

    def test_54_page_has_footer(self):
        assert "<footer" in self.page_lower

    def test_55_page_redirects_logged_in_users(self):
        assert 'redirect("/dashboard")' in self.page_src or "redirect('/dashboard')" in self.page_src


# ══════════════════════════════════════════════════════════════════════════════
# Part 8: Design Tone + VERIFY.md (Tests 56-60)
# ══════════════════════════════════════════════════════════════════════════════

class TestDesignToneAndVerify:
    """Verify enterprise tone, no hype language, and VERIFY.md updated."""

    VERIFY_FILE = ROOT_DIR / "VERIFY.md"

    @pytest.fixture(autouse=True)
    def _load(self):
        # Collect all marketing component text
        self.all_marketing_text = ""
        for tsx_file in MARKETING_DIR.glob("*.tsx"):
            self.all_marketing_text += _read(tsx_file)
        self.all_lower = self.all_marketing_text.lower()
        self.verify_src = _read(self.VERIFY_FILE)
        self.verify_lower = self.verify_src.lower()

    def test_56_no_hype_language(self):
        """Marketing copy should not contain hype words."""
        hype_words = ["revolutionary", "game-changing", "disruptive", "synergy", "paradigm", "magic"]
        for word in hype_words:
            assert word not in self.all_lower, f"Hype word '{word}' found in marketing components"

    def test_57_enterprise_tone(self):
        """Marketing copy should include enterprise-appropriate language."""
        enterprise_words = ["compliance", "audit", "evidence"]
        for word in enterprise_words:
            assert word in self.all_lower, f"Enterprise word '{word}' missing from marketing components"

    def test_58_minimal_style_no_excessive_exclamation(self):
        """No more than 2 exclamation marks across all marketing components."""
        count = self.all_marketing_text.count("!")
        assert count <= 2, f"Found {count} exclamation marks — enterprise tone should be restrained"

    def test_59_verify_has_marketing_section(self):
        assert "marketing" in self.verify_lower, "VERIFY.md missing marketing site section"

    def test_60_verify_mentions_six_sections(self):
        assert "6" in self.verify_src or "six" in self.verify_lower, "VERIFY.md should mention 6 marketing sections"
