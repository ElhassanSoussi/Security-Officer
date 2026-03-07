"""
Test suite — Feature 5: Document Expiry & Re-run Alerts
========================================================

Validates:
  • document_expiry_service.py functions exist and behave correctly
  • admin.py alert endpoints exist
  • frontend API client alert methods
  • frontend alerts page UI
  • Integration with existing expiration.py engine
"""

import os
import sys
import importlib
import pytest
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

# ─── Ensure imports work ─────────────────────────────────────────────────────

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND = os.path.abspath(os.path.join(ROOT, "..", "frontend"))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# ── 1. Service file existence ────────────────────────────────────────────────

def test_document_expiry_service_file_exists():
    path = os.path.join(ROOT, "app", "core", "document_expiry_service.py")
    assert os.path.isfile(path), "document_expiry_service.py must exist"


def test_document_expiry_service_imports():
    mod = importlib.import_module("app.core.document_expiry_service")
    assert hasattr(mod, "get_expiring_documents")
    assert hasattr(mod, "get_rerun_candidates")
    assert hasattr(mod, "get_expiry_summary")
    assert hasattr(mod, "check_and_notify_expiry")


def test_document_expiry_service_constants():
    mod = importlib.import_module("app.core.document_expiry_service")
    assert mod.DEFAULT_ALERT_DAYS == 30
    assert mod.RERUN_STALE_DAYS == 90


# ── 2. Existing expiration engine ────────────────────────────────────────────

def test_compute_expiration_status_expired():
    from app.core.expiration import compute_expiration_status
    past = date.today() - timedelta(days=10)
    result = compute_expiration_status(past.isoformat(), reminder_days_before=30)
    assert result["status"] == "expired"
    assert result["days_remaining"] < 0


def test_compute_expiration_status_expiring():
    from app.core.expiration import compute_expiration_status
    soon = date.today() + timedelta(days=15)
    result = compute_expiration_status(soon.isoformat(), reminder_days_before=30)
    assert result["status"] == "expiring"
    assert 0 < result["days_remaining"] <= 30


def test_compute_expiration_status_valid():
    from app.core.expiration import compute_expiration_status
    far = date.today() + timedelta(days=90)
    result = compute_expiration_status(far.isoformat(), reminder_days_before=30)
    assert result["status"] == "valid"
    assert result["days_remaining"] > 30


def test_compute_expiration_status_no_date():
    from app.core.expiration import compute_expiration_status
    result = compute_expiration_status(None)
    assert result["status"] == "no_expiration"
    assert result["days_remaining"] is None


def test_classify_documents_mixed():
    from app.core.expiration import classify_documents
    docs = [
        {"expiration_date": (date.today() - timedelta(days=5)).isoformat()},
        {"expiration_date": (date.today() + timedelta(days=10)).isoformat()},
        {"expiration_date": (date.today() + timedelta(days=90)).isoformat()},
        {"expiration_date": None},
    ]
    classified = classify_documents(docs, reminder_days_before=30)
    statuses = [d["status"] for d in classified]
    assert "expired" in statuses
    assert "expiring" in statuses
    assert "valid" in statuses
    assert "no_expiration" in statuses


def test_summarize_expirations():
    from app.core.expiration import summarize_expirations
    docs = [
        {"expiration_date": (date.today() - timedelta(days=5)).isoformat()},
        {"expiration_date": (date.today() + timedelta(days=10)).isoformat()},
    ]
    summary = summarize_expirations(docs, reminder_days_before=30)
    assert summary["total"] == 2
    assert summary["counts"]["expired"] == 1
    assert summary["counts"]["expiring"] == 1


# ── 3. get_expiring_documents (mocked DB) ────────────────────────────────────

def test_get_expiring_documents_returns_list():
    from app.core.document_expiry_service import get_expiring_documents
    # Without DB, should return empty list (not crash)
    with patch("app.core.database.get_supabase_admin", side_effect=Exception("no db")):
        result = get_expiring_documents("org-123", days_ahead=30)
    assert isinstance(result, list)
    assert len(result) == 0


def test_get_expiring_documents_with_mock_data():
    """Verify classify_documents logic used by the service returns correct statuses."""
    from app.core.expiration import classify_documents

    expired_date = (date.today() - timedelta(days=5)).isoformat()
    expiring_date = (date.today() + timedelta(days=10)).isoformat()

    docs = [
        {"document_id": "d1", "display_name": "expired.pdf", "project_id": "p1", "expiration_date": expired_date, "reminder_days_before": 30, "created_at": "2025-01-01"},
        {"document_id": "d2", "display_name": "expiring.pdf", "project_id": "p1", "expiration_date": expiring_date, "reminder_days_before": 30, "created_at": "2025-02-01"},
    ]
    classified = classify_documents(docs, reminder_days_before=30)
    statuses = {d["status"] for d in classified}
    assert "expired" in statuses
    assert "expiring" in statuses
    assert len(classified) == 2


# ── 4. get_rerun_candidates ──────────────────────────────────────────────────

def test_get_rerun_candidates_returns_list():
    from app.core.document_expiry_service import get_rerun_candidates
    with patch("app.core.database.get_supabase_admin", side_effect=Exception("no db")):
        result = get_rerun_candidates("org-123", stale_days=90)
    assert isinstance(result, list)


# ── 5. get_expiry_summary ────────────────────────────────────────────────────

def test_get_expiry_summary_returns_dict():
    from app.core.document_expiry_service import get_expiry_summary
    with patch("app.core.document_expiry_service.get_expiring_documents", return_value=[]):
        with patch("app.core.document_expiry_service.get_rerun_candidates", return_value=[]):
            result = get_expiry_summary("org-123")
    assert isinstance(result, dict)
    assert result["total_alerts"] == 0
    assert result["expiring_count"] == 0
    assert result["expired_count"] == 0
    assert result["rerun_needed_count"] == 0


def test_get_expiry_summary_with_alerts():
    from app.core.document_expiry_service import get_expiry_summary
    expiring = [{"id": "d1", "filename": "a.pdf", "status": "expiring", "days_remaining": 10, "project_id": "p1", "project_name": "P1", "expiration_date": "2026-04-01", "created_at": "2025-01-01"}]
    expired = [{"id": "d2", "filename": "b.pdf", "status": "expired", "days_remaining": -5, "project_id": "p1", "project_name": "P1", "expiration_date": "2026-03-01", "created_at": "2025-01-01"}]
    rerun = [{"id": "d3", "filename": "c.pdf", "project_id": "p1", "project_name": "P1", "last_run_at": None, "days_since_run": None}]

    with patch("app.core.document_expiry_service.get_expiring_documents", return_value=expiring + expired):
        with patch("app.core.document_expiry_service.get_rerun_candidates", return_value=rerun):
            result = get_expiry_summary("org-123")
    assert result["total_alerts"] == 3
    assert result["expiring_count"] == 1
    assert result["expired_count"] == 1
    assert result["rerun_needed_count"] == 1


# ── 6. check_and_notify_expiry ───────────────────────────────────────────────

def test_check_and_notify_no_alerts():
    from app.core.document_expiry_service import check_and_notify_expiry
    with patch("app.core.document_expiry_service.get_expiry_summary", return_value={"total_alerts": 0, "expiring_count": 0, "expired_count": 0, "rerun_needed_count": 0, "expiring_docs": [], "expired_docs": [], "rerun_docs": []}):
        result = check_and_notify_expiry("org-123")
    assert result["alerts_found"] == 0
    assert result["notifications_sent"] is False


# ── 7. Backend endpoint existence ────────────────────────────────────────────

def test_admin_has_document_expiry_endpoint():
    src = open(os.path.join(ROOT, "app", "api", "endpoints", "admin.py")).read()
    assert "document-expiry" in src
    assert "alerts" in src


def test_admin_has_check_expiry_endpoint():
    src = open(os.path.join(ROOT, "app", "api", "endpoints", "admin.py")).read()
    assert "check-expiry" in src


def test_admin_has_rerun_candidates_endpoint():
    src = open(os.path.join(ROOT, "app", "api", "endpoints", "admin.py")).read()
    assert "rerun-candidates" in src


# ── 8. Frontend API methods ──────────────────────────────────────────────────

def test_frontend_api_has_get_document_expiry_alerts():
    src = open(os.path.join(FRONTEND, "lib", "api.ts")).read()
    assert "getDocumentExpiryAlerts" in src
    assert "document-expiry" in src


def test_frontend_api_has_check_and_notify_expiry():
    src = open(os.path.join(FRONTEND, "lib", "api.ts")).read()
    assert "checkAndNotifyExpiry" in src
    assert "check-expiry" in src


def test_frontend_api_has_get_rerun_candidates():
    src = open(os.path.join(FRONTEND, "lib", "api.ts")).read()
    assert "getRerunCandidates" in src
    assert "rerun-candidates" in src


# ── 9. Frontend alerts page ──────────────────────────────────────────────────

def test_alerts_page_exists():
    path = os.path.join(FRONTEND, "app", "alerts", "page.tsx")
    assert os.path.isfile(path), "alerts/page.tsx must exist"


def test_alerts_page_has_expired_section():
    src = open(os.path.join(FRONTEND, "app", "alerts", "page.tsx")).read()
    assert "Expired Documents" in src
    assert "expired_docs" in src


def test_alerts_page_has_expiring_section():
    src = open(os.path.join(FRONTEND, "app", "alerts", "page.tsx")).read()
    assert "Expiring Soon" in src
    assert "expiring_docs" in src


def test_alerts_page_has_rerun_section():
    src = open(os.path.join(FRONTEND, "app", "alerts", "page.tsx")).read()
    assert "Re-run" in src
    assert "rerun_docs" in src


def test_alerts_page_has_notify_button():
    src = open(os.path.join(FRONTEND, "app", "alerts", "page.tsx")).read()
    assert "Send Alert Emails" in src
    assert "handleNotify" in src


def test_alerts_page_has_all_clear_state():
    src = open(os.path.join(FRONTEND, "app", "alerts", "page.tsx")).read()
    assert "All Clear" in src


def test_alerts_page_imports_correct_icons():
    src = open(os.path.join(FRONTEND, "app", "alerts", "page.tsx")).read()
    assert "ShieldAlert" in src
    assert "RotateCcw" in src
    assert "Bell" in src
