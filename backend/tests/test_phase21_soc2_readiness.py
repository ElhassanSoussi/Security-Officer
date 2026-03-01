"""
Phase 21 Verification: SOC2 Readiness Foundations

All tests are deterministic — no real DB / API / external calls.

Tests cover:
 1. RBAC — viewer cannot approve answers (lacks REVIEW_ANSWER)
 2. RBAC — viewer cannot edit answers (lacks EDIT_ANSWER)
 3. RBAC — viewer cannot generate evidence (lacks RUN_ANALYSIS)
 4. RBAC — viewer cannot delete evidence (lacks ORG_SETTINGS-level)
 5. RBAC — viewer cannot unlock runs
 6. RBAC — viewer cannot manage members (lacks MANAGE_MEMBERS)
 7. RBAC — viewer cannot delete documents (lacks DELETE_DOCUMENT)
 8. RBAC — reviewer can review answers (has REVIEW_ANSWER)
 9. RBAC — reviewer can bulk review (has BULK_REVIEW)
10. RBAC — reviewer can export runs (has EXPORT_RUN)
11. RBAC — reviewer cannot delete documents (lacks DELETE_DOCUMENT)
12. RBAC — reviewer cannot edit answers (lacks EDIT_ANSWER)
13. RBAC — reviewer cannot manage org settings (lacks ORG_SETTINGS)
14. RBAC — reviewer cannot manage members (lacks MANAGE_MEMBERS)
15. RBAC — compliance_manager has full project lifecycle perms
16. RBAC — owner has all permissions
17. RBAC — admin has all permissions
18. RBAC — owner permission set equals admin permission set
19. RBAC — unknown role gets empty permissions
20. RBAC — normalize_role handles legacy "manager" alias
21. RBAC — normalize_role rejects invalid strings
22. Audit — AUDIT_IMMUTABLE flag is True
23. Audit — log_audit_event function exists and is callable
24. Audit — log_activity_event function exists and is callable
25. Audit — log_activity_event does not raise on None supabase
26. Audit — log_audit_event does not raise on None supabase
27. Audit — activity_log has no API write/update/delete endpoint exposed
28. Audit — audit_events has no API write/update/delete endpoint exposed
29. ImmutableLog — migration SQL contains DELETE trigger for activity_log
30. ImmutableLog — migration SQL contains UPDATE trigger for activity_log
31. ImmutableLog — migration SQL contains DELETE trigger for audit_events
32. ImmutableLog — migration SQL contains UPDATE trigger for audit_events
33. ImmutableLog — migration SQL sets created_at NOT NULL on activity_log
34. ImmutableLog — migration SQL sets created_at NOT NULL on audit_events
35. Retention — DATA_RETENTION_DAYS config exists (default 365)
36. Retention — DATA_RETENTION_DAYS is a positive integer
37. Retention — retention module importable
38. Retention — get_retention_cutoff returns datetime in past
39. Retention — run_retention_job returns expected keys
40. Retention — retention job preserves evidence (no evidence_records touch)
41. Retention — admin endpoint registered at /api/v1/admin/run-retention-job
42. Retention — admin endpoint requires org_id parameter
43. AccessReport — endpoint registered at /api/v1/orgs/{org_id}/access-report
44. AccessReport — _build_csv_response returns StreamingResponse
45. AccessReport — CSV output has correct headers
46. Auth — AUTH_MIN_PASSWORD_LENGTH config exists (default 10)
47. Auth — AUTH_REQUIRE_EMAIL_VERIFICATION config exists (default True)
48. Auth — AUTH_MIN_PASSWORD_LENGTH >= 8 (SOC2 minimum)
49. Frontend — EmailVerificationBanner component file exists
50. Frontend — layout.tsx imports EmailVerificationBanner
51. Frontend — security page exists at app/security/page.tsx
52. Frontend — security page contains vendor disclosure table
53. Frontend — security page mentions Supabase vendor
54. Frontend — security page mentions OpenAI vendor
55. Frontend — security page mentions Stripe vendor
56. Frontend — security page mentions Sentry vendor
57. Frontend — settings page has access report download button
58. Frontend — api.ts has downloadAccessReportCSV method
59. Frontend — api.ts has getAccessReport method
60. Frontend — api.ts has triggerRetentionJob method
61. Migration — phase21 migration SQL file exists
62. Migration — migration creates retention_deleted_at column
63. Migration — migration creates retained_until column
64. RBAC — Permission enum has all expected values
65. RBAC — Role enum has exactly 5 roles
"""

import ast
import inspect
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── Setup paths ───────────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

# Ensure env vars so Settings() doesn't crash
for var in ("SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_JWT_SECRET", "SUPABASE_SERVICE_ROLE_KEY"):
    os.environ.setdefault(var, "https://test.supabase.co" if "URL" in var else "test-key-placeholder")


# ══════════════════════════════════════════════════════════════════════════════
# Part 1: Role-Based Access Audit (Tests 1-21)
# ══════════════════════════════════════════════════════════════════════════════

class TestRBACPermissionBoundaries:
    """Verify viewer/reviewer/owner+admin permission boundaries at the source level."""

    def _role_perms(self, role: str):
        from app.core.rbac import _PERMISSION_MATRIX
        return _PERMISSION_MATRIX.get(role, set())

    def _has(self, role: str, perm_name: str) -> bool:
        from app.core.rbac import role_has_permission, Permission
        return role_has_permission(role, Permission(perm_name))

    # ── Viewer restrictions ───────────────────────────────────────────────

    def test_01_viewer_cannot_approve_answers(self):
        assert not self._has("viewer", "review_answer")

    def test_02_viewer_cannot_edit_answers(self):
        assert not self._has("viewer", "edit_answer")

    def test_03_viewer_cannot_run_analysis(self):
        assert not self._has("viewer", "run_analysis")

    def test_04_viewer_cannot_delete_documents(self):
        assert not self._has("viewer", "delete_document")

    def test_05_viewer_cannot_unlock_runs(self):
        """unlock_run requires admin/owner — viewer has no org_settings."""
        assert not self._has("viewer", "org_settings")

    def test_06_viewer_cannot_manage_members(self):
        assert not self._has("viewer", "manage_members")

    def test_07_viewer_cannot_upload_documents(self):
        assert not self._has("viewer", "upload_document")

    # ── Reviewer permissions ──────────────────────────────────────────────

    def test_08_reviewer_can_review_answers(self):
        assert self._has("reviewer", "review_answer")

    def test_09_reviewer_can_bulk_review(self):
        assert self._has("reviewer", "bulk_review")

    def test_10_reviewer_can_export_runs(self):
        assert self._has("reviewer", "export_run")

    def test_11_reviewer_cannot_delete_documents(self):
        assert not self._has("reviewer", "delete_document")

    def test_12_reviewer_cannot_edit_answers(self):
        assert not self._has("reviewer", "edit_answer")

    def test_13_reviewer_cannot_manage_org_settings(self):
        assert not self._has("reviewer", "org_settings")

    def test_14_reviewer_cannot_manage_members(self):
        assert not self._has("reviewer", "manage_members")

    # ── Compliance Manager ────────────────────────────────────────────────

    def test_15_compliance_manager_full_project_lifecycle(self):
        for perm in ("create_project", "edit_project", "view_project",
                      "upload_document", "delete_document", "view_document",
                      "run_analysis", "edit_answer", "view_run",
                      "review_answer", "bulk_review", "export_run"):
            assert self._has("compliance_manager", perm), f"compliance_manager missing {perm}"

    # ── Owner / Admin ─────────────────────────────────────────────────────

    def test_16_owner_has_all_permissions(self):
        from app.core.rbac import Permission
        for p in Permission:
            assert self._has("owner", p.value), f"owner missing {p.value}"

    def test_17_admin_has_all_permissions(self):
        from app.core.rbac import Permission
        for p in Permission:
            assert self._has("admin", p.value), f"admin missing {p.value}"

    def test_18_owner_equals_admin_permissions(self):
        owner = self._role_perms("owner")
        admin = self._role_perms("admin")
        assert owner == admin

    # ── Edge cases ────────────────────────────────────────────────────────

    def test_19_unknown_role_empty_permissions(self):
        from app.core.rbac import get_role_permissions
        assert get_role_permissions("nonexistent") == set()

    def test_20_normalize_role_legacy_manager(self):
        from app.core.rbac import normalize_role
        assert normalize_role("manager") == "compliance_manager"

    def test_21_normalize_role_rejects_invalid(self):
        from app.core.rbac import normalize_role
        assert normalize_role("superuser") is None
        assert normalize_role("") is None
        assert normalize_role(None) is None


# ══════════════════════════════════════════════════════════════════════════════
# Part 2: Immutable Activity Log Protection (Tests 22-34)
# ══════════════════════════════════════════════════════════════════════════════

class TestImmutableAuditLog:
    """Verify audit log immutability at code and migration level."""

    def test_22_audit_immutable_flag_is_true(self):
        from app.core.audit_events import AUDIT_IMMUTABLE
        assert AUDIT_IMMUTABLE is True

    def test_23_log_audit_event_exists(self):
        from app.core.audit_events import log_audit_event
        assert callable(log_audit_event)

    def test_24_log_activity_event_exists(self):
        from app.core.audit_events import log_activity_event
        assert callable(log_activity_event)

    def test_25_log_activity_event_safe_on_none(self):
        from app.core.audit_events import log_activity_event
        # Should not raise
        log_activity_event(None, org_id="x", user_id="y", action_type="test")

    def test_26_log_audit_event_safe_on_none(self):
        from app.core.audit_events import log_audit_event
        # Should not raise
        log_audit_event(None, org_id="x", user_id="y", event_type="test")

    def test_27_no_activity_log_write_endpoint(self):
        """Verify no API endpoint exposes PUT/PATCH/DELETE on activity_log directly."""
        from app.main import app
        for route in app.routes:
            path = getattr(route, "path", "")
            methods = getattr(route, "methods", set())
            if "activity_log" in path or "activity-log" in path:
                dangerous = {"PUT", "PATCH", "DELETE"} & methods
                assert not dangerous, f"activity_log exposed via {methods} at {path}"

    def test_28_no_audit_events_write_endpoint(self):
        """Verify no API endpoint exposes PUT/PATCH/DELETE on audit_events directly."""
        from app.main import app
        for route in app.routes:
            path = getattr(route, "path", "")
            methods = getattr(route, "methods", set())
            if "audit_events" in path or "audit-events" in path:
                dangerous = {"PUT", "PATCH", "DELETE"} & methods
                assert not dangerous, f"audit_events exposed via {methods} at {path}"

    def test_29_migration_has_activity_log_delete_trigger(self):
        sql = _read_migration()
        assert "prevent_activity_log_delete" in sql

    def test_30_migration_has_activity_log_update_trigger(self):
        sql = _read_migration()
        assert "prevent_activity_log_update" in sql

    def test_31_migration_has_audit_events_delete_trigger(self):
        sql = _read_migration()
        assert "prevent_audit_events_delete" in sql

    def test_32_migration_has_audit_events_update_trigger(self):
        sql = _read_migration()
        assert "prevent_audit_events_update" in sql

    def test_33_migration_activity_log_created_at_not_null(self):
        sql = _read_migration()
        assert "activity_log" in sql
        assert "created_at SET NOT NULL" in sql

    def test_34_migration_audit_events_created_at_not_null(self):
        sql = _read_migration()
        # Both tables get NOT NULL
        lines = sql.split("\n")
        found = any("audit_events" in l and "created_at" in l for l in lines) or \
                ("ALTER TABLE audit_events" in sql and "NOT NULL" in sql)
        assert found


# ══════════════════════════════════════════════════════════════════════════════
# Part 3: Data Retention Controls (Tests 35-42)
# ══════════════════════════════════════════════════════════════════════════════

class TestDataRetention:
    """Verify data retention module, config, and endpoint."""

    def test_35_data_retention_days_config_exists(self):
        from app.core.config import Settings
        s = Settings()
        assert hasattr(s, "DATA_RETENTION_DAYS")
        assert s.DATA_RETENTION_DAYS == 365

    def test_36_data_retention_days_positive(self):
        from app.core.config import Settings
        s = Settings()
        assert isinstance(s.DATA_RETENTION_DAYS, int)
        assert s.DATA_RETENTION_DAYS > 0

    def test_37_retention_module_importable(self):
        from app.core.retention import get_retention_cutoff, run_retention_job
        assert callable(get_retention_cutoff)
        assert callable(run_retention_job)

    def test_38_get_retention_cutoff_in_past(self):
        from app.core.retention import get_retention_cutoff
        cutoff = get_retention_cutoff()
        now = datetime.now(timezone.utc)
        assert cutoff < now

    def test_39_run_retention_job_returns_expected_keys(self):
        """run_retention_job with mock supabase returns summary dict."""
        from app.core.retention import run_retention_job

        mock_sb = MagicMock()
        # Simulate no eligible runs
        mock_sb.table.return_value.select.return_value.lt.return_value.is_.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        mock_sb.table.return_value.select.return_value.lt.return_value.is_.return_value.limit.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

        result = run_retention_job(mock_sb, org_id="test-org-id")
        assert "retention_days" in result
        assert "cutoff_date" in result
        assert "runs_processed" in result
        assert "dry_run" in result
        assert result["dry_run"] is False

    def test_40_retention_preserves_evidence(self):
        """Retention job never touches evidence_records table."""
        from app.core.retention import run_retention_job

        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.lt.return_value.is_.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        mock_sb.table.return_value.select.return_value.lt.return_value.is_.return_value.limit.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

        run_retention_job(mock_sb, org_id="test-org")

        # Verify evidence_records was never called
        all_table_calls = [str(c) for c in mock_sb.table.call_args_list]
        evidence_calls = [c for c in all_table_calls if "evidence_records" in c]
        assert len(evidence_calls) == 0, "Retention job must not touch evidence_records"

    def test_41_admin_retention_endpoint_registered(self):
        from app.main import app
        paths = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/api/v1/admin/run-retention-job" in paths

    def test_42_admin_retention_endpoint_requires_org_id(self):
        """The endpoint function signature includes org_id parameter."""
        from app.api.endpoints.admin import trigger_retention_job
        sig = inspect.signature(trigger_retention_job)
        assert "org_id" in sig.parameters


# ══════════════════════════════════════════════════════════════════════════════
# Part 4: Access Audit Report Export (Tests 43-45)
# ══════════════════════════════════════════════════════════════════════════════

class TestAccessAuditReport:
    """Verify access report endpoint and CSV builder."""

    def test_43_access_report_endpoint_registered(self):
        from app.main import app
        paths = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/api/v1/orgs/{org_id}/access-report" in paths

    def test_44_build_csv_response_returns_streaming(self):
        from app.api.endpoints.admin import _build_csv_response
        from fastapi.responses import StreamingResponse
        rows = [
            {
                "user_id": "u1", "email": "a@b.com", "full_name": "Alice",
                "role": "admin", "member_since": "2024-01-01",
                "last_activity": "2024-12-01", "activity_count": 10,
                "evidence_exports": 2,
            }
        ]
        resp = _build_csv_response(rows, "test-org-id")
        assert isinstance(resp, StreamingResponse)
        assert resp.media_type == "text/csv"

    def test_45_csv_has_correct_headers(self):
        from app.api.endpoints.admin import _build_csv_response
        rows = [{"user_id": "u1", "email": "a@b.com", "full_name": "A", "role": "owner",
                 "member_since": "", "last_activity": "", "activity_count": 0, "evidence_exports": 0}]
        resp = _build_csv_response(rows, "org123")
        # Extract body
        import asyncio
        async def get_body():
            body = b""
            async for chunk in resp.body_iterator:
                if isinstance(chunk, str):
                    body += chunk.encode()
                else:
                    body += chunk
            return body.decode()
        body = asyncio.get_event_loop().run_until_complete(get_body())
        first_line = body.strip().split("\n")[0]
        expected_headers = ["user_id", "email", "full_name", "role", "member_since",
                           "last_activity", "activity_count", "evidence_exports"]
        for h in expected_headers:
            assert h in first_line, f"CSV missing header: {h}"


# ══════════════════════════════════════════════════════════════════════════════
# Part 5: Password & Auth Hardening (Tests 46-48)
# ══════════════════════════════════════════════════════════════════════════════

class TestAuthHardening:
    """Verify SOC2-aligned authentication config."""

    def test_46_auth_min_password_length_exists(self):
        from app.core.config import Settings
        s = Settings()
        assert hasattr(s, "AUTH_MIN_PASSWORD_LENGTH")
        assert s.AUTH_MIN_PASSWORD_LENGTH == 10

    def test_47_auth_require_email_verification_exists(self):
        from app.core.config import Settings
        s = Settings()
        assert hasattr(s, "AUTH_REQUIRE_EMAIL_VERIFICATION")
        assert s.AUTH_REQUIRE_EMAIL_VERIFICATION is True

    def test_48_auth_min_password_at_least_8(self):
        """SOC2 requires minimum 8 characters; we enforce 10."""
        from app.core.config import Settings
        s = Settings()
        assert s.AUTH_MIN_PASSWORD_LENGTH >= 8


# ══════════════════════════════════════════════════════════════════════════════
# Part 6: Frontend — Email Verification Banner & Vendor Disclosure (Tests 49-60)
# ══════════════════════════════════════════════════════════════════════════════

class TestFrontendSOC2:
    """Verify frontend files for SOC2 components."""

    def test_49_email_verification_banner_exists(self):
        path = ROOT_DIR / "frontend" / "components" / "EmailVerificationBanner.tsx"
        assert path.exists(), f"Missing: {path}"

    def test_50_layout_imports_email_banner(self):
        path = ROOT_DIR / "frontend" / "app" / "layout.tsx"
        content = path.read_text()
        assert "EmailVerificationBanner" in content

    def test_51_security_page_exists(self):
        path = ROOT_DIR / "frontend" / "app" / "security" / "page.tsx"
        assert path.exists()

    def test_52_security_page_has_vendor_disclosure(self):
        path = ROOT_DIR / "frontend" / "app" / "security" / "page.tsx"
        content = path.read_text()
        assert "Vendor" in content and "Disclosure" in content

    def test_53_security_page_mentions_supabase(self):
        path = ROOT_DIR / "frontend" / "app" / "security" / "page.tsx"
        content = path.read_text()
        assert "Supabase" in content

    def test_54_security_page_mentions_openai(self):
        path = ROOT_DIR / "frontend" / "app" / "security" / "page.tsx"
        content = path.read_text()
        assert "OpenAI" in content

    def test_55_security_page_mentions_stripe(self):
        path = ROOT_DIR / "frontend" / "app" / "security" / "page.tsx"
        content = path.read_text()
        assert "Stripe" in content

    def test_56_security_page_mentions_sentry(self):
        path = ROOT_DIR / "frontend" / "app" / "security" / "page.tsx"
        content = path.read_text()
        assert "Sentry" in content

    def test_57_settings_page_has_access_report_download(self):
        path = ROOT_DIR / "frontend" / "app" / "settings" / "page.tsx"
        content = path.read_text()
        assert "Access Audit Report" in content
        assert "Download CSV" in content

    def test_58_api_has_download_access_report_csv(self):
        path = ROOT_DIR / "frontend" / "lib" / "api.ts"
        content = path.read_text()
        assert "downloadAccessReportCSV" in content

    def test_59_api_has_get_access_report(self):
        path = ROOT_DIR / "frontend" / "lib" / "api.ts"
        content = path.read_text()
        assert "getAccessReport" in content

    def test_60_api_has_trigger_retention_job(self):
        path = ROOT_DIR / "frontend" / "lib" / "api.ts"
        content = path.read_text()
        assert "triggerRetentionJob" in content


# ══════════════════════════════════════════════════════════════════════════════
# Part 7: Migration & RBAC Enum Completeness (Tests 61-65)
# ══════════════════════════════════════════════════════════════════════════════

class TestMigrationAndEnums:
    """Verify migration SQL and enum completeness."""

    def test_61_migration_file_exists(self):
        path = BACKEND_DIR / "scripts" / "014_soc2_readiness.sql"
        assert path.exists()

    def test_62_migration_creates_retention_deleted_at(self):
        sql = _read_migration()
        assert "retention_deleted_at" in sql

    def test_63_migration_creates_retained_until(self):
        sql = _read_migration()
        assert "retained_until" in sql

    def test_64_permission_enum_has_all_expected_values(self):
        from app.core.rbac import Permission
        expected = {
            "org_settings", "manage_members",
            "create_project", "edit_project", "view_project",
            "upload_document", "delete_document", "view_document",
            "run_analysis", "edit_answer", "view_run",
            "review_answer", "bulk_review", "export_run",
        }
        actual = {p.value for p in Permission}
        assert expected == actual

    def test_65_role_enum_has_five_roles(self):
        from app.core.rbac import Role
        assert len(Role) == 5
        expected_names = {"OWNER", "ADMIN", "COMPLIANCE_MANAGER", "REVIEWER", "VIEWER"}
        assert {r.name for r in Role} == expected_names


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _read_migration() -> str:
    path = BACKEND_DIR / "scripts" / "014_soc2_readiness.sql"
    return path.read_text()
