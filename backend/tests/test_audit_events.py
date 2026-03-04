"""
Audit Events Endpoint Tests
============================

Deterministic unit tests — no real DB / network calls.

Tests cover:
1.  sanitize_metadata strips password fields
2.  sanitize_metadata strips token fields
3.  sanitize_metadata strips secret fields
4.  sanitize_metadata strips api_key fields
5.  sanitize_metadata strips auth fields
6.  sanitize_metadata preserves safe fields
7.  sanitize_metadata returns {} for None input
8.  sanitize_metadata returns {} for empty dict
9.  log_audit_event is importable and callable
10. log_audit_event no-ops when supabase is None
11. log_audit_event no-ops when org_id is empty
12. log_audit_event no-ops when user_id is empty
13. log_audit_event no-ops when event_type is empty
14. log_audit_event sanitizes metadata before write
15. log_audit_event handles missing-table error gracefully
16. log_activity_event is importable and callable
17. log_activity_event writes to activity_log table
18. log_activity_event payload contains entity_type and entity_id
19. /audit/events endpoint is defined in audit.py
20. /audit/events response shape is {events, total, page, page_size}
21. /audit/events accepts user_id query param
22. /audit/events accepts action_type query param
23. /audit/events accepts project_id query param
24. /audit/events accepts from/to date params
25. /audit/events accepts page/page_size params
26. /audit/export endpoint is defined in audit.py
27. /audit/export streams CSV with correct columns
28. _normalize_event_row maps event_type → action_type
29. _normalize_event_row strips sensitive metadata keys
30. _normalize_event_row filters by project_id when provided
31. _normalize_event_row returns None when project_id doesn't match
32. _validate_iso_date accepts valid date
33. _validate_iso_date returns None for empty string
34. Frontend api.ts has getAuditEvents method
35. Frontend api.ts getAuditEvents calls /audit/events
36. Frontend api.ts has exportAuditCsv method
37. Frontend activity page exists at app/activity/page.tsx
38. Frontend activity page imports ApiClient
39. Frontend activity page has filter bar
40. Frontend activity page has Export CSV button
41. Frontend activity page has pagination
42. Frontend Sidebar links to /activity
43. assistant.py logs assistant_interaction audit event
44. documents.py logs log_activity_event on document_uploaded
45. projects.py logs log_activity_event on project_created
46. Cross-org isolation: _normalize_event_row doesn't expose org_id
47. Metadata sanitisation: jwt field stripped
"""

import sys
import os
import types
import pytest

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------
BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

REPO_ROOT = os.path.join(BACKEND_DIR, "..")
FRONTEND_DIR = os.path.join(REPO_ROOT, "frontend")

AUDIT_ENDPOINT_PATH = os.path.join(BACKEND_DIR, "app", "api", "endpoints", "audit.py")
AUDIT_EVENTS_CORE_PATH = os.path.join(BACKEND_DIR, "app", "core", "audit_events.py")
ASSISTANT_ENDPOINT_PATH = os.path.join(BACKEND_DIR, "app", "api", "endpoints", "assistant.py")
DOCUMENTS_ENDPOINT_PATH = os.path.join(BACKEND_DIR, "app", "api", "endpoints", "documents.py")
PROJECTS_ENDPOINT_PATH = os.path.join(BACKEND_DIR, "app", "api", "endpoints", "projects.py")
API_TS_PATH = os.path.join(FRONTEND_DIR, "lib", "api.ts")
ACTIVITY_PAGE_PATH = os.path.join(FRONTEND_DIR, "app", "activity", "page.tsx")
SIDEBAR_PATH = os.path.join(FRONTEND_DIR, "components", "layout", "Sidebar.tsx")


def _read(path: str) -> str:
    with open(path) as f:
        return f.read()


# ── Fake Supabase helpers ─────────────────────────────────────────────────────

class _FakeInsert:
    def __init__(self, raise_error=None):
        self._raise_error = raise_error

    def execute(self):
        if self._raise_error:
            raise self._raise_error
        return None


class _FakeTable:
    def __init__(self, raise_error=None):
        self._raise_error = raise_error
        self.last_payload = None

    def insert(self, payload):
        self.last_payload = payload
        return _FakeInsert(raise_error=self._raise_error)


class _FakeSupabase:
    def __init__(self, raise_error=None):
        self._raise_error = raise_error
        self.last_table = None
        self._tables: dict = {}

    def table(self, name: str):
        self.last_table = name
        tbl = _FakeTable(raise_error=self._raise_error)
        self._tables[name] = tbl
        return tbl


# ===========================================================================
# 1–8: sanitize_metadata
# ===========================================================================

class TestSanitizeMetadata:

    def test_01_strips_password(self):
        from app.core.audit_events import sanitize_metadata
        result = sanitize_metadata({"password": "abc123", "name": "alice"})
        assert "password" not in result
        assert result["name"] == "alice"

    def test_02_strips_token(self):
        from app.core.audit_events import sanitize_metadata
        result = sanitize_metadata({"access_token": "xyz", "project_id": "p1"})
        assert "access_token" not in result
        assert result["project_id"] == "p1"

    def test_03_strips_secret(self):
        from app.core.audit_events import sanitize_metadata
        result = sanitize_metadata({"client_secret": "s3cr3t"})
        assert "client_secret" not in result

    def test_04_strips_api_key(self):
        from app.core.audit_events import sanitize_metadata
        result = sanitize_metadata({"api_key": "key123", "event": "test"})
        assert "api_key" not in result

    def test_05_strips_auth_field(self):
        from app.core.audit_events import sanitize_metadata
        result = sanitize_metadata({"authorization": "Bearer tok", "doc": "doc1"})
        assert "authorization" not in result

    def test_06_preserves_safe_fields(self):
        from app.core.audit_events import sanitize_metadata
        result = sanitize_metadata({"project_id": "p1", "filename": "test.pdf", "count": 3})
        assert result == {"project_id": "p1", "filename": "test.pdf", "count": 3}

    def test_07_returns_empty_for_none(self):
        from app.core.audit_events import sanitize_metadata
        assert sanitize_metadata(None) == {}

    def test_08_returns_empty_for_empty_dict(self):
        from app.core.audit_events import sanitize_metadata
        assert sanitize_metadata({}) == {}


# ===========================================================================
# 9–15: log_audit_event
# ===========================================================================

class TestLogAuditEvent:

    def test_09_importable(self):
        from app.core.audit_events import log_audit_event
        assert callable(log_audit_event)

    def test_10_noop_when_supabase_none(self):
        from app.core.audit_events import log_audit_event
        log_audit_event(None, org_id="o1", user_id="u1", event_type="test")

    def test_11_noop_when_org_id_empty(self):
        from app.core.audit_events import log_audit_event
        sb = _FakeSupabase()
        log_audit_event(sb, org_id="", user_id="u1", event_type="test")
        assert sb.last_table is None

    def test_12_noop_when_user_id_empty(self):
        from app.core.audit_events import log_audit_event
        sb = _FakeSupabase()
        log_audit_event(sb, org_id="o1", user_id="", event_type="test")
        assert sb.last_table is None

    def test_13_noop_when_event_type_empty(self):
        from app.core.audit_events import log_audit_event
        sb = _FakeSupabase()
        log_audit_event(sb, org_id="o1", user_id="u1", event_type="")
        assert sb.last_table is None

    def test_14_sanitizes_metadata_before_write(self):
        from app.core.audit_events import log_audit_event
        sb = _FakeSupabase()
        log_audit_event(
            sb,
            org_id="o1",
            user_id="u1",
            event_type="test",
            metadata={"password": "s3cr3t", "doc": "file.pdf"},
        )
        tbl = sb._tables.get("audit_events")
        assert tbl is not None
        payload = tbl.last_payload
        assert "password" not in payload.get("metadata", {})
        assert payload["metadata"].get("doc") == "file.pdf"

    def test_15_handles_missing_table_gracefully(self):
        from app.core.audit_events import log_audit_event
        err = Exception("Could not find the table 'public.audit_events'")
        sb = _FakeSupabase(raise_error=err)
        # Must not raise
        log_audit_event(sb, org_id="o1", user_id="u1", event_type="test")


# ===========================================================================
# 16–18: log_activity_event
# ===========================================================================

class TestLogActivityEvent:

    def test_16_importable(self):
        from app.core.audit_events import log_activity_event
        assert callable(log_activity_event)

    def test_17_writes_to_activity_log(self):
        from app.core.audit_events import log_activity_event
        sb = _FakeSupabase()
        log_activity_event(sb, org_id="o1", user_id="u1", action_type="project_created")
        assert sb.last_table == "activity_log"

    def test_18_payload_has_entity_fields(self):
        from app.core.audit_events import log_activity_event
        sb = _FakeSupabase()
        log_activity_event(
            sb,
            org_id="o1",
            user_id="u1",
            action_type="document_uploaded",
            entity_type="document",
            entity_id="doc-123",
        )
        tbl = sb._tables.get("activity_log")
        payload = tbl.last_payload
        assert payload["entity_type"] == "document"
        assert payload["entity_id"] == "doc-123"


# ===========================================================================
# 19–27: audit.py endpoint definitions
# ===========================================================================

class TestAuditEndpointDefinitions:

    def test_19_events_endpoint_defined(self):
        src = _read(AUDIT_ENDPOINT_PATH)
        assert '"/events"' in src or "@router.get(\"/events\")" in src

    def test_20_events_response_has_new_shape(self):
        src = _read(AUDIT_ENDPOINT_PATH)
        assert '"events"' in src
        assert '"page"' in src
        assert '"page_size"' in src

    def test_21_events_accepts_user_id_param(self):
        src = _read(AUDIT_ENDPOINT_PATH)
        assert "user_id" in src

    def test_22_events_accepts_action_type_param(self):
        src = _read(AUDIT_ENDPOINT_PATH)
        assert "action_type" in src

    def test_23_events_accepts_project_id_param(self):
        src = _read(AUDIT_ENDPOINT_PATH)
        assert "project_id" in src

    def test_24_events_accepts_date_range_params(self):
        src = _read(AUDIT_ENDPOINT_PATH)
        assert "start_date" in src or "validated_from" in src
        assert "end_date" in src or "validated_to" in src

    def test_25_events_accepts_page_params(self):
        src = _read(AUDIT_ENDPOINT_PATH)
        assert "page_size" in src

    def test_26_export_endpoint_defined(self):
        src = _read(AUDIT_ENDPOINT_PATH)
        assert '"/export"' in src

    def test_27_export_writes_csv_columns(self):
        src = _read(AUDIT_ENDPOINT_PATH)
        assert "action_type" in src
        assert "entity_type" in src
        assert "entity_id" in src
        # CSV writer should be present
        assert "csv.writer" in src


# ===========================================================================
# 28–33: _normalize_event_row and _validate_iso_date
# ===========================================================================

class TestNormalizeEventRow:

    def _import_normalize(self):
        from app.api.endpoints.audit import _normalize_event_row
        return _normalize_event_row

    def _import_validate(self):
        from app.api.endpoints.audit import _validate_iso_date
        return _validate_iso_date

    def test_28_maps_event_type_to_action_type(self):
        fn = self._import_normalize()
        row = {
            "id": "abc",
            "created_at": "2024-01-01T00:00:00Z",
            "user_id": "u1",
            "event_type": "document_uploaded",
            "metadata": {},
        }
        result = fn(row, None)
        assert result is not None
        assert result["action_type"] == "document_uploaded"

    def test_29_strips_sensitive_metadata_keys(self):
        fn = self._import_normalize()
        row = {
            "id": "abc",
            "created_at": "2024-01-01T00:00:00Z",
            "user_id": "u1",
            "event_type": "test",
            "metadata": {"password": "secret", "project_id": "p1"},
        }
        result = fn(row, None)
        assert result is not None
        assert "password" not in result["metadata"]
        assert result["metadata"].get("project_id") == "p1"

    def test_30_keeps_matching_project_id(self):
        fn = self._import_normalize()
        row = {
            "id": "abc",
            "created_at": "2024-01-01T00:00:00Z",
            "user_id": "u1",
            "event_type": "test",
            "metadata": {"project_id": "proj-123"},
        }
        result = fn(row, "proj-123")
        assert result is not None

    def test_31_returns_none_when_project_id_mismatch(self):
        fn = self._import_normalize()
        row = {
            "id": "abc",
            "created_at": "2024-01-01T00:00:00Z",
            "user_id": "u1",
            "event_type": "test",
            "metadata": {"project_id": "proj-999"},
        }
        result = fn(row, "proj-123")
        assert result is None

    def test_32_validate_iso_date_accepts_valid(self):
        fn = self._import_validate()
        result = fn("2024-06-15", "from")
        assert result == "2024-06-15"

    def test_33_validate_iso_date_none_for_empty(self):
        fn = self._import_validate()
        assert fn("", "from") is None
        assert fn(None, "from") is None


# ===========================================================================
# 34–42: Frontend file content checks
# ===========================================================================

class TestFrontendAuditFiles:

    def test_34_api_ts_has_get_audit_events(self):
        src = _read(API_TS_PATH)
        assert "getAuditEvents" in src

    def test_35_get_audit_events_calls_audit_events(self):
        src = _read(API_TS_PATH)
        assert "/audit/events" in src

    def test_36_api_ts_has_export_audit_csv(self):
        src = _read(API_TS_PATH)
        assert "exportAuditCsv" in src

    def test_37_activity_page_exists(self):
        assert os.path.exists(ACTIVITY_PAGE_PATH)

    def test_38_activity_page_imports_api_client(self):
        src = _read(ACTIVITY_PAGE_PATH)
        assert "ApiClient" in src

    def test_39_activity_page_has_filter_bar(self):
        src = _read(ACTIVITY_PAGE_PATH)
        assert "action_type" in src or "filterAction" in src

    def test_40_activity_page_has_export_button(self):
        src = _read(ACTIVITY_PAGE_PATH)
        assert "Export CSV" in src or "exportAuditCsv" in src

    def test_41_activity_page_has_pagination(self):
        src = _read(ACTIVITY_PAGE_PATH)
        assert "page_size" in src or "totalPages" in src

    def test_42_sidebar_links_to_activity(self):
        src = _read(SIDEBAR_PATH)
        assert '"/activity"' in src


# ===========================================================================
# 43–45: Event logging in endpoints
# ===========================================================================

class TestEventLoggingInEndpoints:

    def test_43_assistant_logs_audit_event(self):
        src = _read(ASSISTANT_ENDPOINT_PATH)
        assert "log_audit_event" in src
        assert "assistant_interaction" in src

    def test_44_documents_logs_activity_event(self):
        src = _read(DOCUMENTS_ENDPOINT_PATH)
        assert "log_activity_event" in src
        assert "document_uploaded" in src

    def test_45_projects_logs_activity_event(self):
        src = _read(PROJECTS_ENDPOINT_PATH)
        assert "log_activity_event" in src
        assert "project_created" in src


# ===========================================================================
# 46–47: Security / cross-org isolation
# ===========================================================================

class TestCrossOrgIsolation:

    def test_46_normalized_row_does_not_expose_org_id(self):
        """The response shape should not include org_id (it's implicit from the auth context)."""
        from app.api.endpoints.audit import _normalize_event_row
        row = {
            "id": "abc",
            "created_at": "2024-01-01T00:00:00Z",
            "user_id": "u1",
            "org_id": "org-secret-123",
            "event_type": "test",
            "metadata": {},
        }
        result = _normalize_event_row(row, None)
        assert result is not None
        assert "org_id" not in result

    def test_47_jwt_stripped_from_metadata(self):
        from app.core.audit_events import sanitize_metadata
        result = sanitize_metadata({"jwt": "eyJhbGci...", "project_id": "p1"})
        assert "jwt" not in result
        assert result.get("project_id") == "p1"
