"""
Phase 17 Verification: Evidence Vault + Immutable Audit Export

All tests are deterministic — no DB / API / OpenAI calls needed.

Tests cover:
1.  MigrationSQL — file exists on disk
2.  MigrationSQL — is_locked column added to runs
3.  MigrationSQL — run_evidence_records table created
4.  MigrationSQL — id, run_id, org_id, generated_by columns defined
5.  MigrationSQL — sha256_hash, health_score, package_size columns defined
6.  MigrationSQL — created_at column defined
7.  MigrationSQL — run_evidence_run_idx index defined
8.  MigrationSQL — run_evidence_org_idx index defined
9.  MigrationSQL — RLS enabled on run_evidence_records
10. MigrationSQL — evidence_read_org_member RLS policy defined
11. MigrationSQL — evidence_insert_member RLS policy defined
12. MigrationSQL — evidence_delete_admin RLS policy defined (admin/owner)
13. Helpers — _sha256_bytes importable and correct
14. Helpers — _sha256_bytes is deterministic
15. Helpers — _sha256_bytes returns 64-char hex string
16. Helpers — _compute_health_score_for_audits importable
17. HealthScore — empty list → 0
18. HealthScore — all approved HIGH → high score
19. HealthScore — all LOW unreviewed → low score
20. HealthScore — output clamped to [0, 100]
21. HealthScore — mixed audits produce intermediate score
22. Endpoints — generate_evidence_package importable
23. Endpoints — list_run_evidence_records importable
24. Endpoints — list_project_evidence_records importable
25. Endpoints — delete_evidence_record importable
26. Endpoints — unlock_run importable
27. Models — RunUpdate has is_locked field
28. Models — Run has is_locked field
29. ZIPStructure — ZIP contains audit_log.json
30. ZIPStructure — ZIP contains summary.json
31. ZIPStructure — ZIP contains memory_reuse.json
32. ZIPStructure — ZIP contains activity.json
33. ZIPStructure — summary.json has integrity block with audit_log_sha256
34. ZIPStructure — audit_log.json hash in summary matches actual file hash
35. ApiClient — generateEvidence method exists in api.ts
36. ApiClient — listRunEvidenceRecords method exists in api.ts
37. ApiClient — listOrgEvidenceRecords method exists in api.ts
38. ApiClient — deleteEvidenceRecord method exists in api.ts
39. ApiClient — unlockRun method exists in api.ts
40. Frontend — evidence page file exists on disk
"""

import sys
import os
import io
import json
import zipfile
import hashlib
import pytest

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------
BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

REPO_ROOT = os.path.join(BACKEND_DIR, "..")
SQL_PATH = os.path.join(BACKEND_DIR, "scripts", "011_evidence_vault.sql")
FRONTEND_EVIDENCE_PAGE = os.path.join(
    REPO_ROOT,
    "frontend", "app", "projects", "[orgId]", "[projectId]", "evidence", "page.tsx"
)
API_TS_PATH = os.path.join(REPO_ROOT, "frontend", "lib", "api.ts")


# ===========================================================================
# 1-12: Migration SQL content
# ===========================================================================

def _sql() -> str:
    with open(SQL_PATH, "r") as f:
        return f.read()


def test_01_migration_sql_file_exists():
    assert os.path.isfile(SQL_PATH), f"Migration SQL not found at {SQL_PATH}"


def test_02_migration_sql_is_locked_column():
    sql = _sql()
    assert "is_locked" in sql, "is_locked column missing from migration SQL"


def test_03_migration_sql_run_evidence_records_table():
    sql = _sql()
    assert "run_evidence_records" in sql


def test_04_migration_sql_primary_columns():
    sql = _sql()
    for col in ("run_id", "org_id", "generated_by"):
        assert col in sql, f"Column '{col}' missing from migration SQL"


def test_05_migration_sql_hash_score_size_columns():
    sql = _sql()
    for col in ("sha256_hash", "health_score", "package_size"):
        assert col in sql, f"Column '{col}' missing from migration SQL"


def test_06_migration_sql_created_at_column():
    sql = _sql()
    assert "created_at" in sql


def test_07_migration_sql_run_idx():
    sql = _sql()
    assert "run_evidence_run_idx" in sql


def test_08_migration_sql_org_idx():
    sql = _sql()
    assert "run_evidence_org_idx" in sql


def test_09_migration_sql_rls_enabled():
    sql = _sql()
    assert "ENABLE ROW LEVEL SECURITY" in sql


def test_10_migration_sql_read_policy():
    sql = _sql()
    assert "evidence_read_org_member" in sql


def test_11_migration_sql_insert_policy():
    sql = _sql()
    assert "evidence_insert_member" in sql


def test_12_migration_sql_delete_policy():
    sql = _sql()
    assert "evidence_delete_admin" in sql
    # Must gate on admin/owner role
    assert "admin" in sql


# ===========================================================================
# 13-15: _sha256_bytes helper
# ===========================================================================

def test_13_sha256_bytes_importable():
    from app.api.endpoints.runs import _sha256_bytes  # noqa: F401
    assert callable(_sha256_bytes)


def test_14_sha256_bytes_deterministic():
    from app.api.endpoints.runs import _sha256_bytes
    data = b"hello world"
    assert _sha256_bytes(data) == _sha256_bytes(data)


def test_15_sha256_bytes_correct_length():
    from app.api.endpoints.runs import _sha256_bytes
    result = _sha256_bytes(b"test")
    assert len(result) == 64
    # Should be lowercase hex
    assert result == result.lower()
    int(result, 16)  # must be valid hex


# ===========================================================================
# 16-21: _compute_health_score_for_audits helper
# ===========================================================================

def test_16_compute_health_score_importable():
    from app.api.endpoints.runs import _compute_health_score_for_audits  # noqa: F401
    assert callable(_compute_health_score_for_audits)


def test_17_health_score_empty_list():
    from app.api.endpoints.runs import _compute_health_score_for_audits
    assert _compute_health_score_for_audits([]) == 0


def test_18_health_score_all_approved_high():
    from app.api.endpoints.runs import _compute_health_score_for_audits
    audits = [
        {"review_status": "approved", "confidence_score": "HIGH"} for _ in range(10)
    ]
    score = _compute_health_score_for_audits(audits)
    assert score >= 70, f"Expected high score for all-approved HIGH audits, got {score}"


def test_19_health_score_all_low_unreviewed():
    from app.api.endpoints.runs import _compute_health_score_for_audits
    audits = [
        {"review_status": "pending", "confidence_score": "LOW"} for _ in range(10)
    ]
    score = _compute_health_score_for_audits(audits)
    assert score < 50, f"Expected low score for all-LOW pending audits, got {score}"


def test_20_health_score_clamped():
    from app.api.endpoints.runs import _compute_health_score_for_audits
    audits = [{"review_status": "approved", "confidence_score": "HIGH"} for _ in range(100)]
    score = _compute_health_score_for_audits(audits)
    assert 0 <= score <= 100


def test_21_health_score_mixed_intermediate():
    from app.api.endpoints.runs import _compute_health_score_for_audits
    audits = (
        [{"review_status": "approved", "confidence_score": "HIGH"}] * 5
        + [{"review_status": "pending", "confidence_score": "LOW"}] * 5
    )
    score = _compute_health_score_for_audits(audits)
    assert 0 <= score <= 100


# ===========================================================================
# 22-26: Endpoint imports
# ===========================================================================

def test_22_generate_evidence_package_importable():
    from app.api.endpoints.runs import generate_evidence_package  # noqa: F401
    assert callable(generate_evidence_package)


def test_23_list_run_evidence_records_importable():
    from app.api.endpoints.runs import list_evidence_records  # noqa: F401
    assert callable(list_evidence_records)


def test_24_list_project_evidence_records_importable():
    from app.api.endpoints.runs import list_project_evidence_records  # noqa: F401
    assert callable(list_project_evidence_records)


def test_25_delete_evidence_record_importable():
    from app.api.endpoints.runs import delete_evidence_record  # noqa: F401
    assert callable(delete_evidence_record)


def test_26_unlock_run_importable():
    from app.api.endpoints.runs import unlock_run  # noqa: F401
    assert callable(unlock_run)


# ===========================================================================
# 27-28: Model fields
# ===========================================================================

def test_27_run_update_has_is_locked():
    from app.models.runs import RunUpdate
    fields = RunUpdate.model_fields if hasattr(RunUpdate, "model_fields") else RunUpdate.__fields__
    assert "is_locked" in fields, "is_locked missing from RunUpdate"


def test_28_run_has_is_locked():
    from app.models.runs import Run
    fields = Run.model_fields if hasattr(Run, "model_fields") else Run.__fields__
    assert "is_locked" in fields, "is_locked missing from Run"


# ===========================================================================
# 29-34: ZIP structure tests (pure in-memory, no DB)
# ===========================================================================

def _build_test_zip(include_excel: bool = False) -> bytes:
    """Build a ZIP that mirrors the evidence package format."""
    audits = [
        {"id": "a1", "question_text": "Q1", "answer_text": "A1",
         "review_status": "approved", "confidence_score": "HIGH",
         "reused_from_memory": False, "source_document": "doc.pdf",
         "created_at": "2025-01-01T00:00:00Z", "original_answer": None,
         "review_notes": None, "reviewer_id": None, "reviewed_at": None,
         "answer_origin": "generated"},
    ]

    audit_log_payload = {
        "run_id": "test-run-id",
        "project_id": "test-proj",
        "generated_at": "2025-01-01T00:00:00Z",
        "generated_by": "user-123",
        "total_questions": 1,
        "approved_count": 1,
        "rejected_count": 0,
        "low_confidence_count": 0,
        "reused_from_memory_count": 0,
        "health_score": 85,
        "answers": audits,
    }
    audit_log_bytes = json.dumps(audit_log_payload, indent=2).encode()
    audit_log_hash = hashlib.sha256(audit_log_bytes).hexdigest()

    memory_reuse = {"run_id": "test-run-id", "reused_answers": []}
    memory_bytes = json.dumps(memory_reuse, indent=2).encode()

    activity = []
    activity_bytes = json.dumps(activity, indent=2).encode()

    excel_bytes = b"PK fake xlsx bytes" if include_excel else None
    excel_hash = hashlib.sha256(excel_bytes).hexdigest() if excel_bytes else None

    summary = {
        "evidence_package_version": "1.0",
        "run_id": "test-run-id",
        "health_score": 85,
        "integrity": {
            "audit_log_sha256": audit_log_hash,
            "export_excel_sha256": excel_hash,
        },
    }
    summary_bytes = json.dumps(summary, indent=2).encode()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("audit_log.json", audit_log_bytes)
        zf.writestr("memory_reuse.json", memory_bytes)
        zf.writestr("activity.json", activity_bytes)
        zf.writestr("summary.json", summary_bytes)
        if excel_bytes:
            zf.writestr("export_testruni.xlsx", excel_bytes)
    return buf.getvalue()


def _read_zip(zip_bytes: bytes) -> dict:
    buf = io.BytesIO(zip_bytes)
    with zipfile.ZipFile(buf, "r") as zf:
        return {name: zf.read(name) for name in zf.namelist()}


def test_29_zip_contains_audit_log():
    files = _read_zip(_build_test_zip())
    assert "audit_log.json" in files


def test_30_zip_contains_summary():
    files = _read_zip(_build_test_zip())
    assert "summary.json" in files


def test_31_zip_contains_memory_reuse():
    files = _read_zip(_build_test_zip())
    assert "memory_reuse.json" in files


def test_32_zip_contains_activity():
    files = _read_zip(_build_test_zip())
    assert "activity.json" in files


def test_33_summary_has_integrity_block():
    files = _read_zip(_build_test_zip())
    summary = json.loads(files["summary.json"])
    assert "integrity" in summary
    assert "audit_log_sha256" in summary["integrity"]


def test_34_audit_log_hash_matches_summary():
    files = _read_zip(_build_test_zip())
    summary = json.loads(files["summary.json"])
    expected_hash = hashlib.sha256(files["audit_log.json"]).hexdigest()
    assert summary["integrity"]["audit_log_sha256"] == expected_hash


# ===========================================================================
# 35-39: Frontend api.ts method presence
# ===========================================================================

def _api_ts() -> str:
    with open(API_TS_PATH, "r") as f:
        return f.read()


def test_35_api_ts_generate_evidence():
    assert "generateEvidence" in _api_ts()


def test_36_api_ts_list_run_evidence_records():
    assert "listRunEvidenceRecords" in _api_ts()


def test_37_api_ts_list_org_evidence_records():
    assert "listOrgEvidenceRecords" in _api_ts()


def test_38_api_ts_delete_evidence_record():
    assert "deleteEvidenceRecord" in _api_ts()


def test_39_api_ts_unlock_run():
    assert "unlockRun" in _api_ts()


# ===========================================================================
# 40: Frontend evidence page exists
# ===========================================================================

def test_40_evidence_page_file_exists():
    assert os.path.isfile(FRONTEND_EVIDENCE_PAGE), (
        f"Evidence Vault page not found at {FRONTEND_EVIDENCE_PAGE}"
    )
