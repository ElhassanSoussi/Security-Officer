"""
Expiration Tracking, Compliance Pack Builder, and Audit Log Tests

  - Expiration Tracking Engine — compute_expiration_status, classify_documents, summarize_expirations
  - Compliance Pack Builder   — CompliancePackRequest model, zip creation, RBAC, audit event
  - Audit Log Hardening       — /audit/events endpoint, pagination, filters, never-500

Total: deterministic tests.  Zero external dependencies (no DB, no network).
"""
import sys
import os
import pytest
from datetime import date, datetime, timedelta

# Ensure backend app is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _patch_settings(monkeypatch):
    """Prevent Settings from reading .env or requiring real env vars."""
    monkeypatch.setenv("SUPABASE_URL", "http://localhost:54321")
    monkeypatch.setenv("SUPABASE_KEY", "test-anon-key")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-jwt-secret-at-least-32-chars-long")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    from app.core.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ═══════════════════════════════════════════════════════════════════════════════
# Expiration Tracking Engine
# ═══════════════════════════════════════════════════════════════════════════════


class TestComputeExpirationStatus:
    """Test compute_expiration_status for all classification branches."""

    def test_null_expiration_date_returns_no_expiration(self):
        from app.core.expiration import compute_expiration_status
        result = compute_expiration_status(None)
        assert result["status"] == "no_expiration"
        assert result["days_remaining"] is None
        assert result["expiration_date"] is None

    def test_empty_string_returns_no_expiration(self):
        from app.core.expiration import compute_expiration_status
        result = compute_expiration_status("")
        assert result["status"] == "no_expiration"

    def test_invalid_date_string_returns_no_expiration(self):
        from app.core.expiration import compute_expiration_status
        result = compute_expiration_status("not-a-date")
        assert result["status"] == "no_expiration"

    def test_future_date_beyond_reminder_is_valid(self):
        from app.core.expiration import compute_expiration_status
        ref = date(2026, 1, 1)
        exp = "2026-06-15"  # 165 days out
        result = compute_expiration_status(exp, reminder_days_before=30, reference_date=ref)
        assert result["status"] == "valid"
        assert result["days_remaining"] == 165
        assert result["expiration_date"] == "2026-06-15"

    def test_within_reminder_window_is_expiring(self):
        from app.core.expiration import compute_expiration_status
        ref = date(2026, 1, 1)
        exp = "2026-01-20"  # 19 days out, within 30-day window
        result = compute_expiration_status(exp, reminder_days_before=30, reference_date=ref)
        assert result["status"] == "expiring"
        assert result["days_remaining"] == 19

    def test_exactly_on_reminder_boundary_is_expiring(self):
        from app.core.expiration import compute_expiration_status
        ref = date(2026, 1, 1)
        exp = "2026-01-31"  # exactly 30 days
        result = compute_expiration_status(exp, reminder_days_before=30, reference_date=ref)
        assert result["status"] == "expiring"
        assert result["days_remaining"] == 30

    def test_one_day_past_reminder_is_valid(self):
        from app.core.expiration import compute_expiration_status
        ref = date(2026, 1, 1)
        exp = "2026-02-01"  # 31 days out, beyond 30-day window
        result = compute_expiration_status(exp, reminder_days_before=30, reference_date=ref)
        assert result["status"] == "valid"
        assert result["days_remaining"] == 31

    def test_past_date_is_expired(self):
        from app.core.expiration import compute_expiration_status
        ref = date(2026, 3, 1)
        exp = "2026-01-15"  # 45 days ago
        result = compute_expiration_status(exp, reminder_days_before=30, reference_date=ref)
        assert result["status"] == "expired"
        assert result["days_remaining"] < 0

    def test_today_is_expired(self):
        """Expiration date == today means 0 days remaining → expired."""
        from app.core.expiration import compute_expiration_status
        ref = date(2026, 2, 15)
        exp = "2026-02-15"
        result = compute_expiration_status(exp, reminder_days_before=30, reference_date=ref)
        assert result["status"] == "expired"
        assert result["days_remaining"] == 0

    def test_tomorrow_with_zero_reminder_is_valid(self):
        from app.core.expiration import compute_expiration_status
        ref = date(2026, 2, 15)
        exp = "2026-02-16"
        result = compute_expiration_status(exp, reminder_days_before=0, reference_date=ref)
        assert result["status"] == "valid"
        assert result["days_remaining"] == 1

    def test_date_object_input(self):
        from app.core.expiration import compute_expiration_status
        ref = date(2026, 1, 1)
        exp = date(2026, 6, 1)
        result = compute_expiration_status(exp, reference_date=ref)
        assert result["status"] == "valid"
        assert result["days_remaining"] == 151

    def test_datetime_object_input(self):
        from app.core.expiration import compute_expiration_status
        ref = date(2026, 1, 1)
        exp = datetime(2026, 1, 10, 14, 30, 0)
        result = compute_expiration_status(exp, reference_date=ref)
        assert result["status"] == "expiring"
        assert result["days_remaining"] == 9

    def test_iso_datetime_string_input(self):
        from app.core.expiration import compute_expiration_status
        ref = date(2026, 1, 1)
        exp = "2026-01-10T14:30:00"
        result = compute_expiration_status(exp, reference_date=ref)
        assert result["status"] == "expiring"

    def test_iso_datetime_with_tz_input(self):
        from app.core.expiration import compute_expiration_status
        ref = date(2026, 1, 1)
        exp = "2026-07-01T00:00:00+00:00"
        result = compute_expiration_status(exp, reference_date=ref)
        assert result["status"] == "valid"

    def test_negative_reminder_treated_as_zero(self):
        """Negative reminder_days_before should be clamped to 0 via max()."""
        from app.core.expiration import compute_expiration_status
        ref = date(2026, 1, 1)
        exp = "2026-01-02"  # 1 day out
        result = compute_expiration_status(exp, reminder_days_before=-5, reference_date=ref)
        # max(-5, 0) = 0, so 1 > 0 → valid
        assert result["status"] == "valid"


class TestClassifyDocuments:
    """Test classify_documents adds correct status to document dicts."""

    def test_empty_list(self):
        from app.core.expiration import classify_documents
        assert classify_documents([]) == []

    def test_single_doc_with_no_expiration(self):
        from app.core.expiration import classify_documents
        docs = [{"document_id": "abc", "display_name": "test.pdf", "expiration_date": None}]
        result = classify_documents(docs)
        assert len(result) == 1
        assert result[0]["status"] == "no_expiration"
        assert result[0]["document_id"] == "abc"

    def test_mixed_statuses(self):
        from app.core.expiration import classify_documents
        ref = date(2026, 3, 1)
        docs = [
            {"document_id": "1", "expiration_date": "2026-01-01"},   # expired
            {"document_id": "2", "expiration_date": "2026-03-15"},   # expiring (14 days)
            {"document_id": "3", "expiration_date": "2026-12-01"},   # valid
            {"document_id": "4", "expiration_date": None},           # no_expiration
        ]
        result = classify_documents(docs, reminder_days_before=30, reference_date=ref)
        statuses = [r["status"] for r in result]
        assert statuses == ["expired", "expiring", "valid", "no_expiration"]

    def test_per_doc_reminder_override(self):
        from app.core.expiration import classify_documents
        ref = date(2026, 3, 1)
        docs = [
            {"document_id": "1", "expiration_date": "2026-03-10", "reminder_days_before": 5},  # 9 days, but reminder=5 → valid
            {"document_id": "2", "expiration_date": "2026-03-10", "reminder_days_before": 15}, # 9 days, reminder=15 → expiring
        ]
        result = classify_documents(docs, reminder_days_before=30, reference_date=ref)
        assert result[0]["status"] == "valid"
        assert result[1]["status"] == "expiring"

    def test_preserves_original_fields(self):
        from app.core.expiration import classify_documents
        docs = [{"document_id": "x", "display_name": "report.pdf", "file_type": "pdf", "expiration_date": None}]
        result = classify_documents(docs)
        assert result[0]["display_name"] == "report.pdf"
        assert result[0]["file_type"] == "pdf"

    def test_invalid_reminder_falls_back_to_default(self):
        from app.core.expiration import classify_documents
        ref = date(2026, 3, 1)
        docs = [{"document_id": "1", "expiration_date": "2026-03-20", "reminder_days_before": "invalid"}]
        result = classify_documents(docs, reminder_days_before=30, reference_date=ref)
        # Falls back to 30; 19 days within 30 → expiring
        assert result[0]["status"] == "expiring"


class TestSummarizeExpirations:
    """Test summarize_expirations returns correct counts and structure."""

    def test_empty_docs(self):
        from app.core.expiration import summarize_expirations
        result = summarize_expirations([])
        assert result["total"] == 0
        assert result["counts"] == {"valid": 0, "expiring": 0, "expired": 0, "no_expiration": 0}
        assert result["documents"] == []

    def test_counts_are_correct(self):
        from app.core.expiration import summarize_expirations
        ref = date(2026, 3, 1)
        docs = [
            {"document_id": "1", "expiration_date": "2025-12-01"},  # expired
            {"document_id": "2", "expiration_date": "2025-11-01"},  # expired
            {"document_id": "3", "expiration_date": "2026-03-15"},  # expiring
            {"document_id": "4", "expiration_date": "2026-12-01"},  # valid
            {"document_id": "5", "expiration_date": None},          # no_expiration
            {"document_id": "6", "expiration_date": None},          # no_expiration
        ]
        result = summarize_expirations(docs, reminder_days_before=30, reference_date=ref)
        assert result["total"] == 6
        assert result["counts"]["expired"] == 2
        assert result["counts"]["expiring"] == 1
        assert result["counts"]["valid"] == 1
        assert result["counts"]["no_expiration"] == 2

    def test_documents_enriched_with_status(self):
        from app.core.expiration import summarize_expirations
        ref = date(2026, 3, 1)
        docs = [{"document_id": "1", "expiration_date": "2026-03-10"}]
        result = summarize_expirations(docs, reminder_days_before=30, reference_date=ref)
        assert len(result["documents"]) == 1
        assert result["documents"][0]["status"] == "expiring"
        assert result["documents"][0]["days_remaining"] == 9

    def test_summary_structure_keys(self):
        from app.core.expiration import summarize_expirations
        result = summarize_expirations([])
        assert set(result.keys()) == {"total", "counts", "documents"}
        assert set(result["counts"].keys()) == {"valid", "expiring", "expired", "no_expiration"}


class TestParseDateEdgeCases:
    """Test _parse_date handles various input formats."""

    def test_parse_iso_date(self):
        from app.core.expiration import _parse_date
        assert _parse_date("2026-06-15") == date(2026, 6, 15)

    def test_parse_iso_datetime(self):
        from app.core.expiration import _parse_date
        assert _parse_date("2026-06-15T10:30:00") == date(2026, 6, 15)

    def test_parse_date_object(self):
        from app.core.expiration import _parse_date
        d = date(2026, 1, 1)
        assert _parse_date(d) == d

    def test_parse_datetime_object(self):
        from app.core.expiration import _parse_date
        dt = datetime(2026, 6, 15, 12, 0, 0)
        assert _parse_date(dt) == date(2026, 6, 15)

    def test_parse_none(self):
        from app.core.expiration import _parse_date
        assert _parse_date(None) is None

    def test_parse_empty_string(self):
        from app.core.expiration import _parse_date
        assert _parse_date("") is None

    def test_parse_whitespace(self):
        from app.core.expiration import _parse_date
        assert _parse_date("   ") is None

    def test_parse_garbage(self):
        from app.core.expiration import _parse_date
        assert _parse_date("hello world") is None

    def test_parse_number(self):
        from app.core.expiration import _parse_date
        assert _parse_date(12345) is None

    def test_parse_iso_with_timezone(self):
        from app.core.expiration import _parse_date
        # Should extract date part
        result = _parse_date("2026-06-15T10:30:00+05:00")
        assert result == date(2026, 6, 15)


# ═══════════════════════════════════════════════════════════════════════════════
# Compliance Pack Builder
# ═══════════════════════════════════════════════════════════════════════════════


class TestCompliancePackRequest:
    """Test the Pydantic model for compliance pack requests."""

    def test_valid_request(self):
        from app.api.endpoints.documents import CompliancePackRequest
        req = CompliancePackRequest(document_ids=["abc-123", "def-456"])
        assert len(req.document_ids) == 2
        assert req.document_ids[0] == "abc-123"

    def test_empty_list_is_valid_model(self):
        """Model accepts empty list; endpoint validates non-empty."""
        from app.api.endpoints.documents import CompliancePackRequest
        req = CompliancePackRequest(document_ids=[])
        assert req.document_ids == []

    def test_single_doc(self):
        from app.api.endpoints.documents import CompliancePackRequest
        req = CompliancePackRequest(document_ids=["single-id"])
        assert len(req.document_ids) == 1


class TestCompliancePackRBACPermissions:
    """Verify that compliance pack requires EXPORT_RUN permission."""

    def test_owner_can_export(self):
        from app.core.rbac import role_has_permission, Permission
        assert role_has_permission("owner", Permission.EXPORT_RUN)

    def test_admin_can_export(self):
        from app.core.rbac import role_has_permission, Permission
        assert role_has_permission("admin", Permission.EXPORT_RUN)

    def test_compliance_manager_can_export(self):
        from app.core.rbac import role_has_permission, Permission
        assert role_has_permission("compliance_manager", Permission.EXPORT_RUN)

    def test_reviewer_can_export(self):
        from app.core.rbac import role_has_permission, Permission
        assert role_has_permission("reviewer", Permission.EXPORT_RUN)

    def test_viewer_cannot_export(self):
        from app.core.rbac import role_has_permission, Permission
        assert not role_has_permission("viewer", Permission.EXPORT_RUN)


class TestCompliancePackZipCreation:
    """Test that zip creation logic works correctly."""

    def test_create_zip_in_memory(self):
        import io
        import zipfile

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("doc1.txt", "Hello, World!")
            zf.writestr("doc2.pdf", b"fake pdf content")
            zf.writestr("_manifest.txt", "Pack manifest")
        buf.seek(0)

        # Verify we can read it back
        with zipfile.ZipFile(buf, "r") as zf:
            names = zf.namelist()
            assert "doc1.txt" in names
            assert "doc2.pdf" in names
            assert "_manifest.txt" in names
            assert zf.read("doc1.txt") == b"Hello, World!"

    def test_empty_zip_with_manifest_only(self):
        import io
        import zipfile

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("_manifest.txt", "Empty pack")
        buf.seek(0)

        with zipfile.ZipFile(buf, "r") as zf:
            assert len(zf.namelist()) == 1

    def test_zip_contains_bytes_content(self):
        import io
        import zipfile

        content = b"\x00\x01\x02\x03"
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("binary.bin", content)
        buf.seek(0)

        with zipfile.ZipFile(buf, "r") as zf:
            assert zf.read("binary.bin") == content


class TestFetchDocumentContentFallback:
    """Test _fetch_document_content graceful fallback."""

    def test_fallback_returns_placeholder(self):
        from app.api.endpoints.documents import _fetch_document_content

        class FakeSB:
            class storage:
                @staticmethod
                def from_(bucket):
                    raise Exception("no storage")
            def table(self, name):
                raise Exception("no table")

        result = _fetch_document_content(FakeSB(), "org1", "proj1", "doc1", "test.pdf")
        assert b"Content unavailable" in result
        assert b"test.pdf" in result


# ═══════════════════════════════════════════════════════════════════════════════
# Audit Log Hardening
# ═══════════════════════════════════════════════════════════════════════════════


class TestValidateIsoDate:
    """Test the _validate_iso_date helper."""

    def test_valid_date(self):
        from app.api.endpoints.audit import _validate_iso_date
        assert _validate_iso_date("2026-01-15", "from") == "2026-01-15"

    def test_none_returns_none(self):
        from app.api.endpoints.audit import _validate_iso_date
        assert _validate_iso_date(None, "from") is None

    def test_empty_string_returns_none(self):
        from app.api.endpoints.audit import _validate_iso_date
        assert _validate_iso_date("", "from") is None

    def test_whitespace_returns_none(self):
        from app.api.endpoints.audit import _validate_iso_date
        assert _validate_iso_date("   ", "from") is None

    def test_invalid_format_raises_400(self):
        from app.api.endpoints.audit import _validate_iso_date
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _validate_iso_date("not-a-date", "from")
        assert exc_info.value.status_code == 400

    def test_short_string_raises_400(self):
        from app.api.endpoints.audit import _validate_iso_date
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _validate_iso_date("2026", "from")
        assert exc_info.value.status_code == 400

    def test_invalid_month_raises_400(self):
        from app.api.endpoints.audit import _validate_iso_date
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _validate_iso_date("2026-13-01", "from")
        assert exc_info.value.status_code == 400

    def test_invalid_day_raises_400(self):
        from app.api.endpoints.audit import _validate_iso_date
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _validate_iso_date("2026-02-30", "from")
        assert exc_info.value.status_code == 400

    def test_accepts_datetime_prefix(self):
        from app.api.endpoints.audit import _validate_iso_date
        # "2026-01-15T10:30:00" → extracts "2026-01-15"
        assert _validate_iso_date("2026-01-15T10:30:00", "from") == "2026-01-15"


class TestAuditEventsEndpointExists:
    """Verify the /audit/events endpoint is registered on the router."""

    def test_events_route_registered(self):
        from app.api.endpoints.audit import router
        paths = [route.path for route in router.routes]
        assert "/events" in paths

    def test_events_route_is_get(self):
        from app.api.endpoints.audit import router
        for route in router.routes:
            if getattr(route, "path", None) == "/events":
                assert "GET" in route.methods
                break
        else:
            pytest.fail("/events route not found")

    def test_log_route_still_exists(self):
        from app.api.endpoints.audit import router
        paths = [route.path for route in router.routes]
        assert "/log" in paths

    def test_exports_route_still_exists(self):
        from app.api.endpoints.audit import router
        paths = [route.path for route in router.routes]
        assert "/exports" in paths


class TestAuditEventsNormalization:
    """Test _normalize_confidence_score hardening."""

    def test_none_returns_none(self):
        from app.api.endpoints.audit import _normalize_confidence_score
        assert _normalize_confidence_score(None) is None

    def test_numeric_passthrough(self):
        from app.api.endpoints.audit import _normalize_confidence_score
        assert _normalize_confidence_score(0.85) == 0.85

    def test_zero_is_valid(self):
        from app.api.endpoints.audit import _normalize_confidence_score
        assert _normalize_confidence_score(0) == 0.0

    def test_one_is_valid(self):
        from app.api.endpoints.audit import _normalize_confidence_score
        assert _normalize_confidence_score(1) == 1.0

    def test_percentage_normalized(self):
        from app.api.endpoints.audit import _normalize_confidence_score
        assert _normalize_confidence_score(85) == 0.85

    def test_string_number(self):
        from app.api.endpoints.audit import _normalize_confidence_score
        assert _normalize_confidence_score("0.75") == 0.75

    def test_string_percentage(self):
        from app.api.endpoints.audit import _normalize_confidence_score
        assert _normalize_confidence_score("92") == 0.92

    def test_legacy_label_returns_none(self):
        from app.api.endpoints.audit import _normalize_confidence_score
        assert _normalize_confidence_score("HIGH") is None
        assert _normalize_confidence_score("LOW") is None

    def test_empty_string_returns_none(self):
        from app.api.endpoints.audit import _normalize_confidence_score
        assert _normalize_confidence_score("") is None

    def test_negative_returns_none(self):
        from app.api.endpoints.audit import _normalize_confidence_score
        assert _normalize_confidence_score(-0.5) is None

    def test_over_100_returns_none(self):
        from app.api.endpoints.audit import _normalize_confidence_score
        assert _normalize_confidence_score(150) is None


class TestAuditEndpointPagination:
    """Verify pagination parameters are accepted on the route."""

    def test_events_route_accepts_page_page_size(self):
        """The /events endpoint function signature includes page and page_size (replaces limit/offset)."""
        from app.api.endpoints.audit import get_audit_events
        import inspect
        sig = inspect.signature(get_audit_events)
        params = list(sig.parameters.keys())
        assert "page" in params
        assert "page_size" in params

    def test_events_route_accepts_action_type(self):
        """The /events endpoint uses action_type (replaces event_type)."""
        from app.api.endpoints.audit import get_audit_events
        import inspect
        sig = inspect.signature(get_audit_events)
        assert "action_type" in sig.parameters

    def test_events_route_accepts_start_date(self):
        """The /events endpoint uses start_date (replaces date_from)."""
        from app.api.endpoints.audit import get_audit_events
        import inspect
        sig = inspect.signature(get_audit_events)
        assert "start_date" in sig.parameters

    def test_events_route_accepts_end_date(self):
        """The /events endpoint uses end_date (replaces date_to)."""
        from app.api.endpoints.audit import get_audit_events
        import inspect
        sig = inspect.signature(get_audit_events)
        assert "end_date" in sig.parameters

    def test_events_route_accepts_org_id(self):
        from app.api.endpoints.audit import get_audit_events
        import inspect
        sig = inspect.signature(get_audit_events)
        assert "org_id" in sig.parameters


# ═══════════════════════════════════════════════════════════════════════════════
# Endpoint Registration Verification
# ═══════════════════════════════════════════════════════════════════════════════


class TestDocumentsRouterEndpoints:
    """Verify new endpoints are registered on the documents router."""

    def test_expirations_route_registered(self):
        from app.api.endpoints.documents import router
        paths = [route.path for route in router.routes]
        assert "/{project_id}/expirations" in paths

    def test_compliance_pack_route_registered(self):
        from app.api.endpoints.documents import router
        paths = [route.path for route in router.routes]
        assert "/{project_id}/compliance-pack" in paths

    def test_expirations_is_get(self):
        from app.api.endpoints.documents import router
        for route in router.routes:
            if getattr(route, "path", None) == "/{project_id}/expirations":
                assert "GET" in route.methods
                break
        else:
            pytest.fail("expirations route not found")

    def test_compliance_pack_is_post(self):
        from app.api.endpoints.documents import router
        for route in router.routes:
            if getattr(route, "path", None) == "/{project_id}/compliance-pack":
                assert "POST" in route.methods
                break
        else:
            pytest.fail("compliance-pack route not found")


class TestExpirationExportPermissions:
    """Verify that expirations endpoint uses VIEW_DOCUMENT permission."""

    def test_all_roles_can_view_documents(self):
        from app.core.rbac import role_has_permission, Permission
        # All roles should be able to view documents (and thus expirations)
        assert role_has_permission("owner", Permission.VIEW_DOCUMENT)
        assert role_has_permission("admin", Permission.VIEW_DOCUMENT)
        assert role_has_permission("compliance_manager", Permission.VIEW_DOCUMENT)
        assert role_has_permission("reviewer", Permission.VIEW_DOCUMENT)
        assert role_has_permission("viewer", Permission.VIEW_DOCUMENT)


# ═══════════════════════════════════════════════════════════════════════════════
# Backward Compatibility — ensure earlier features still healthy
# ═══════════════════════════════════════════════════════════════════════════════


class TestBackwardCompatibilityPhase5:
    """Verify that recent changes do not break existing modules."""

    def test_rbac_module_unchanged(self):
        from app.core.rbac import Role, Permission, normalize_role, role_has_permission
        assert len(Role) == 5
        assert len(Permission) == 14
        assert normalize_role("manager") == "compliance_manager"
        assert role_has_permission("owner", Permission.RUN_ANALYSIS)

    def test_question_item_schema_unchanged(self):
        from app.models.schemas import QuestionItem
        q = QuestionItem(
            sheet_name="Sheet1",
            cell_coordinate="B2",
            question="Test?",
            ai_answer="Yes",
            final_answer="Yes",
            confidence="HIGH",
            sources=["doc.pdf"],
        )
        assert q.question == "Test?"

    def test_existing_documents_endpoints_preserved(self):
        from app.api.endpoints.documents import router
        paths = [route.path for route in router.routes]
        assert "/{project_id}/documents" in paths
        assert "/{project_id}/documents/{document_id}" in paths

    def test_existing_audit_endpoints_preserved(self):
        from app.api.endpoints.audit import router
        paths = [route.path for route in router.routes]
        assert "/log" in paths
        assert "/exports" in paths

    def test_expiration_module_importable(self):
        from app.core.expiration import (
            compute_expiration_status,
            classify_documents,
            summarize_expirations,
            _parse_date,
        )
        assert callable(compute_expiration_status)
        assert callable(classify_documents)
        assert callable(summarize_expirations)

    def test_audit_events_endpoint_importable(self):
        from app.api.endpoints.audit import get_audit_events, _validate_iso_date
        assert callable(get_audit_events)
        assert callable(_validate_iso_date)

    def test_compliance_pack_model_importable(self):
        from app.api.endpoints.documents import CompliancePackRequest
        r = CompliancePackRequest(document_ids=["a", "b"])
        assert len(r.document_ids) == 2
