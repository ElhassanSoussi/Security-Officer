"""
Compliance Intelligence Engine Tests

All tests are deterministic and require no DB, API, or OpenAI connection.

Coverage:
1.  infer_document_type — known patterns return correct type
2.  infer_document_type — unknown filename returns 'general'
3.  infer_risk_level — high-risk type with imminent expiry → 'high'
4.  infer_risk_level — high-risk type with no expiry → 'medium'
5.  infer_risk_level — medium-risk type, safe expiry → 'low'
6.  extract_expiration_date — parses MM/DD/YYYY format
7.  extract_expiration_date — parses YYYY-MM-DD format
8.  extract_expiration_date — rejects past dates
9.  extract_expiration_date — returns None for no date
10. extract_document_metadata — smoke test returns required keys
11. calculate_project_score — 100 with no issues
12. calculate_project_score — deducts points per severity
13. calculate_project_score — floor at 0
14. calculate_project_score — risk_level classification
15. get_org_compliance_overview — empty org returns zeros
16. _parse_flexible_date — handles multiple formats
17. SCORE_DEDUCTIONS — correct values defined
18. EXPIRY_WARNING_DAYS — set to 60
19. required_types — fire_safety and egress_plan present in check
20. infer_document_type — content text match (fire safety in body)
"""

import sys
import os
import pytest
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ─── 1–2. infer_document_type ─────────────────────────────────────────────────

class TestInferDocumentType:
    def test_fire_safety_filename(self):
        from app.core.compliance_engine import infer_document_type
        assert infer_document_type("fire_safety_inspection.pdf") == "fire_safety"

    def test_egress_plan_filename(self):
        from app.core.compliance_engine import infer_document_type
        assert infer_document_type("egress_plan_2025.pdf") == "egress_plan"

    def test_insurance_filename(self):
        from app.core.compliance_engine import infer_document_type
        assert infer_document_type("general_liability_insurance.pdf") == "insurance"

    def test_electrical_filename(self):
        from app.core.compliance_engine import infer_document_type
        assert infer_document_type("electrical_panel_inspection.docx") == "electrical_inspection"

    def test_unknown_filename(self):
        from app.core.compliance_engine import infer_document_type
        assert infer_document_type("quarterly_report.pdf") == "general"

    def test_content_match(self):
        from app.core.compliance_engine import infer_document_type
        assert infer_document_type("report.pdf", "This document covers fire safety inspection procedures.") == "fire_safety"

    def test_asbestos_content(self):
        from app.core.compliance_engine import infer_document_type
        assert infer_document_type("survey.pdf", "Asbestos hazmat assessment completed.") == "hazmat"


# ─── 3–5. infer_risk_level ────────────────────────────────────────────────────

class TestInferRiskLevel:
    def test_high_risk_type_imminent_expiry(self):
        from app.core.compliance_engine import infer_risk_level, EXPIRY_WARNING_DAYS
        exp = date.today() + timedelta(days=10)
        assert infer_risk_level("fire_safety", exp) == "high"

    def test_high_risk_type_no_expiry(self):
        from app.core.compliance_engine import infer_risk_level
        assert infer_risk_level("fire_safety", None) == "medium"

    def test_high_risk_type_far_expiry(self):
        from app.core.compliance_engine import infer_risk_level
        exp = date.today() + timedelta(days=200)
        assert infer_risk_level("fire_safety", exp) == "medium"

    def test_medium_risk_type_safe_expiry(self):
        from app.core.compliance_engine import infer_risk_level
        exp = date.today() + timedelta(days=200)
        assert infer_risk_level("permit", exp) == "low"

    def test_medium_risk_type_imminent_expiry(self):
        from app.core.compliance_engine import infer_risk_level
        exp = date.today() + timedelta(days=30)
        assert infer_risk_level("permit", exp) == "medium"

    def test_general_type_low_risk(self):
        from app.core.compliance_engine import infer_risk_level
        assert infer_risk_level("general", None) == "low"


# ─── 6–9. extract_expiration_date ─────────────────────────────────────────────

class TestExtractExpirationDate:
    def test_parses_mm_dd_yyyy(self):
        from app.core.compliance_engine import extract_expiration_date
        future = date.today() + timedelta(days=180)
        text = f"Expires: {future.strftime('%m/%d/%Y')}"
        result = extract_expiration_date("doc.pdf", text)
        assert result == future

    def test_parses_iso_format(self):
        from app.core.compliance_engine import extract_expiration_date
        future = date.today() + timedelta(days=90)
        text = f"Expiration date: {future.isoformat()}"
        result = extract_expiration_date("doc.pdf", text)
        assert result == future

    def test_rejects_past_date(self):
        from app.core.compliance_engine import extract_expiration_date
        text = "Expires: 01/01/2020"
        result = extract_expiration_date("doc.pdf", text)
        assert result is None

    def test_no_date_returns_none(self):
        from app.core.compliance_engine import extract_expiration_date
        result = extract_expiration_date("generic_report.pdf", "No dates here.")
        assert result is None

    def test_filename_date_extraction(self):
        from app.core.compliance_engine import extract_expiration_date
        future = date.today() + timedelta(days=120)
        result = extract_expiration_date(f"fire_safety_expires_{future.isoformat()}.pdf", "")
        assert result == future


# ─── 10. extract_document_metadata smoke ─────────────────────────────────────

class TestExtractDocumentMetadata:
    def test_returns_required_keys(self):
        from app.core.compliance_engine import extract_document_metadata
        result = extract_document_metadata("fire_safety.pdf", "")
        assert "document_type" in result
        assert "expiration_date" in result
        assert "risk_level" in result

    def test_risk_level_valid_value(self):
        from app.core.compliance_engine import extract_document_metadata
        result = extract_document_metadata("report.pdf", "")
        assert result["risk_level"] in ("low", "medium", "high")

    def test_document_type_string(self):
        from app.core.compliance_engine import extract_document_metadata
        result = extract_document_metadata("report.pdf", "")
        assert isinstance(result["document_type"], str)
        assert len(result["document_type"]) > 0


# ─── 11–14. calculate_project_score (pure logic) ─────────────────────────────

class TestCalculateProjectScore:
    def _mock_sb(self, issues):
        """Return a minimal fake supabase client stub."""
        class FakeExec:
            def __init__(self, data):
                self.data = data

        class FakeQuery:
            def __init__(self, data):
                self._data = data
            def select(self, *a, **k): return self
            def eq(self, *a, **k): return self
            def order(self, *a, **k): return self
            def limit(self, *a, **k): return self
            def execute(self): return FakeExec(self._data)

        class FakeTable:
            def __init__(self, data):
                self._data = data
            def select(self, *a, **k): return FakeQuery(self._data)

        class FakeInsert:
            def __init__(self): pass
            def insert(self, *a, **k): return self
            def execute(self): return FakeExec([])

        class FakeSB:
            def __init__(self, issues):
                self._issues = issues
                self._call_count = 0
            def table(self, name):
                if name == "compliance_issues" and self._call_count == 0:
                    self._call_count += 1
                    return FakeQuery(self._issues)
                return FakeInsert()

        return FakeSB(issues)

    def test_no_issues_score_100(self):
        from app.core.compliance_engine import calculate_project_score
        stub = self._mock_sb([])
        result = calculate_project_score(stub, "org1", "proj1")
        assert result["overall_score"] == 100
        assert result["risk_level"] == "low"
        assert result["open_issues"] == 0

    def test_deducts_high_severity(self):
        from app.core.compliance_engine import calculate_project_score, SCORE_DEDUCTIONS
        issues = [{"id": "1", "severity": "high", "status": "open"}]
        stub = self._mock_sb(issues)
        result = calculate_project_score(stub, "org1", "proj1")
        assert result["overall_score"] == 100 - SCORE_DEDUCTIONS["high"]

    def test_deducts_mixed_severity(self):
        from app.core.compliance_engine import calculate_project_score, SCORE_DEDUCTIONS
        issues = [
            {"id": "1", "severity": "high", "status": "open"},
            {"id": "2", "severity": "medium", "status": "open"},
            {"id": "3", "severity": "low", "status": "open"},
        ]
        stub = self._mock_sb(issues)
        expected = 100 - SCORE_DEDUCTIONS["high"] - SCORE_DEDUCTIONS["medium"] - SCORE_DEDUCTIONS["low"]
        result = calculate_project_score(stub, "org1", "proj1")
        assert result["overall_score"] == expected

    def test_floor_at_zero(self):
        from app.core.compliance_engine import calculate_project_score, SCORE_DEDUCTIONS
        issues = [{"id": str(i), "severity": "high", "status": "open"} for i in range(10)]
        stub = self._mock_sb(issues)
        result = calculate_project_score(stub, "org1", "proj1")
        assert result["overall_score"] == 0

    def test_risk_level_low(self):
        from app.core.compliance_engine import calculate_project_score
        stub = self._mock_sb([])
        assert calculate_project_score(stub, "org1", "proj1")["risk_level"] == "low"

    def test_risk_level_high(self):
        from app.core.compliance_engine import calculate_project_score, SCORE_DEDUCTIONS
        n_issues = (100 - 44) // SCORE_DEDUCTIONS["high"] + 1
        issues = [{"id": str(i), "severity": "high", "status": "open"} for i in range(n_issues)]
        stub = self._mock_sb(issues)
        assert calculate_project_score(stub, "org1", "proj1")["risk_level"] == "high"


# ─── 15. get_org_compliance_overview — empty org ──────────────────────────────

class TestGetOrgComplianceOverview:
    def test_empty_org_returns_zeros(self):
        from app.core.compliance_engine import get_org_compliance_overview

        class FakeExec:
            def __init__(self):
                self.data = []

        class FakeQuery:
            def select(self, *a, **k): return self
            def eq(self, *a, **k): return self
            def execute(self): return FakeExec()

        class FakeSB:
            def table(self, _): return FakeQuery()

        result = get_org_compliance_overview(FakeSB(), "org-empty")
        assert result["active_issues"] == 0
        assert result["expiring_documents"] == 0
        assert result["avg_score"] is None
        assert result["top_risks"] == []
        assert result["issues_by_severity"] == {"high": 0, "medium": 0, "low": 0}


# ─── 16. _parse_flexible_date ─────────────────────────────────────────────────

class TestParseFlexibleDate:
    def test_mm_dd_yyyy(self):
        from app.core.compliance_engine import _parse_flexible_date
        assert _parse_flexible_date("12/31/2027") == date(2027, 12, 31)

    def test_iso(self):
        from app.core.compliance_engine import _parse_flexible_date
        assert _parse_flexible_date("2027-06-15") == date(2027, 6, 15)

    def test_month_name(self):
        from app.core.compliance_engine import _parse_flexible_date
        assert _parse_flexible_date("January 15, 2028") == date(2028, 1, 15)

    def test_invalid_returns_none(self):
        from app.core.compliance_engine import _parse_flexible_date
        assert _parse_flexible_date("not-a-date") is None


# ─── 17–19. Constants & configuration ────────────────────────────────────────

class TestEngineConstants:
    def test_score_deductions_defined(self):
        from app.core.compliance_engine import SCORE_DEDUCTIONS
        assert SCORE_DEDUCTIONS["high"] > SCORE_DEDUCTIONS["medium"] > SCORE_DEDUCTIONS["low"]

    def test_expiry_warning_days(self):
        from app.core.compliance_engine import EXPIRY_WARNING_DAYS
        assert EXPIRY_WARNING_DAYS == 60

    def test_outdated_safety_days(self):
        from app.core.compliance_engine import OUTDATED_SAFETY_DAYS
        assert OUTDATED_SAFETY_DAYS == 365

    def test_required_types_include_fire_safety(self):
        import inspect
        from app.core import compliance_engine
        src = inspect.getsource(compliance_engine.generate_compliance_issues)
        assert "fire_safety" in src

    def test_required_types_include_egress_plan(self):
        import inspect
        from app.core import compliance_engine
        src = inspect.getsource(compliance_engine.generate_compliance_issues)
        assert "egress_plan" in src


# ─── 20. Endpoint importable ──────────────────────────────────────────────────

class TestEndpointImport:
    def test_compliance_router_importable(self):
        from app.api.endpoints.compliance import router
        assert router is not None

    def test_router_has_routes(self):
        from app.api.endpoints.compliance import router
        paths = [r.path for r in router.routes]
        assert any("overview" in p for p in paths)
        assert any("issues" in p for p in paths)
        assert any("scan" in p for p in paths)
