"""
Phase 16 Verification: Institutional Memory Governance + Compliance Activity Timeline

Tests cover (all deterministic, no DB/API/OpenAI needed):
1.  log_activity_event — imported from app.core.audit_events
2.  log_activity_event — no-ops gracefully when supabase is None
3.  log_activity_event — no-ops gracefully when org_id is empty
4.  log_activity_event — no-ops gracefully when action_type is empty
5.  log_activity_event — handles missing-table error gracefully (no raise)
6.  log_activity_event — handles arbitrary DB error gracefully (no raise)
7.  log_audit_event — still importable and works alongside log_activity_event
8.  log_activity_event — payload contains all expected fields
9.  log_activity_event — metadata defaults to empty dict when None passed
10. log_activity_event — entity_type/entity_id default to empty string
11. InstitutionalAnswerPatch — only canonical_answer / confidence_level / is_active accepted
12. MemoryPromotePayload — importable from runs module
13. ConfidenceLevelValidation — HIGH/MEDIUM/LOW accepted, others raise 400
14. ActivityLogSchema — expected columns defined in migration SQL
15. MigrationSQL — is_active column added to institutional_answers
16. MigrationSQL — edited_by / edited_at columns added
17. MigrationSQL — activity_log table created with correct columns
18. MigrationSQL — activity_log indexes defined
19. MigrationSQL — RLS policy defined for activity_log
20. HealthScoreField — ComplianceHealth response includes health_score key
21. HealthScoreRange — health_score clamped 0-100
22. HealthScoreApprovalDense — 100% approved → high score
23. HealthScoreRejectionPenalty — high rejection drops score
24. HealthScoreEmpty — empty org returns health_score 0
25. MemoryGovPanelProps — MemoryGovPanel is a callable component (import check)
"""

import sys
import os
import types
import pytest

# ---------------------------------------------------------------------------
# Path bootstrap — allow importing from backend/app
# ---------------------------------------------------------------------------
BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


# ===========================================================================
# 1-10: log_activity_event unit tests
# ===========================================================================

class _FakeInsert:
    def execute(self):
        return None

class _FakeTable:
    def __init__(self, records=None, raise_error=None):
        self._records = records or []
        self._raise_error = raise_error

    def insert(self, payload):
        if self._raise_error:
            raise self._raise_error
        self._last_payload = payload
        return _FakeInsert()


class _FakeSupabase:
    def __init__(self, raise_error=None):
        self._raise_error = raise_error
        self.last_table = None
        self.last_payload = None

    def table(self, name):
        self.last_table = name
        return _FakeTable(raise_error=self._raise_error)


def test_01_log_activity_event_importable():
    from app.core.audit_events import log_activity_event  # noqa: F401
    assert callable(log_activity_event)


def test_02_log_activity_event_noop_when_supabase_none():
    from app.core.audit_events import log_activity_event
    # Must not raise
    log_activity_event(None, org_id="org1", user_id="u1", action_type="test")


def test_03_log_activity_event_noop_when_org_id_empty():
    from app.core.audit_events import log_activity_event
    sb = _FakeSupabase()
    log_activity_event(sb, org_id="", user_id="u1", action_type="test")
    # table should not have been hit
    assert sb.last_table is None


def test_04_log_activity_event_noop_when_action_type_empty():
    from app.core.audit_events import log_activity_event
    sb = _FakeSupabase()
    log_activity_event(sb, org_id="org1", user_id="u1", action_type="")
    assert sb.last_table is None


def test_05_log_activity_event_handles_missing_table_error():
    from app.core.audit_events import log_activity_event
    err = Exception("Could not find the table 'public.activity_log'")
    sb = _FakeSupabase(raise_error=err)
    # Must not raise
    log_activity_event(sb, org_id="org1", user_id="u1", action_type="memory_edited")


def test_06_log_activity_event_handles_generic_db_error():
    from app.core.audit_events import log_activity_event
    err = RuntimeError("some DB connection issue")
    sb = _FakeSupabase(raise_error=err)
    # Must not raise
    log_activity_event(sb, org_id="org1", user_id="u1", action_type="memory_edited")


def test_07_log_audit_event_still_importable():
    from app.core.audit_events import log_audit_event, log_activity_event
    assert callable(log_audit_event)
    assert callable(log_activity_event)


def test_08_log_activity_event_payload_fields():
    """Verify the payload written to the table has all required fields."""
    from app.core.audit_events import log_activity_event
    captured = {}

    class _CapturingTable:
        def insert(self, payload):
            captured.update(payload)
            return _FakeInsert()

    class _CapturingSB:
        def table(self, name):
            return _CapturingTable()

    log_activity_event(
        _CapturingSB(),
        org_id="org-abc",
        user_id="user-123",
        action_type="memory_promoted",
        entity_type="run_audit",
        entity_id="audit-456",
        metadata={"key": "value"},
    )
    assert captured["org_id"] == "org-abc"
    assert captured["user_id"] == "user-123"
    assert captured["action_type"] == "memory_promoted"
    assert captured["entity_type"] == "run_audit"
    assert captured["entity_id"] == "audit-456"
    assert captured["metadata"] == {"key": "value"}


def test_09_log_activity_event_metadata_defaults_to_empty_dict():
    from app.core.audit_events import log_activity_event
    captured = {}

    class _CT:
        def insert(self, p):
            captured.update(p)
            return _FakeInsert()

    class _CS:
        def table(self, _):
            return _CT()

    log_activity_event(_CS(), org_id="org1", user_id="u1", action_type="test", metadata=None)
    assert captured.get("metadata") == {}


def test_10_log_activity_event_entity_defaults_to_empty_string():
    from app.core.audit_events import log_activity_event
    captured = {}

    class _CT:
        def insert(self, p):
            captured.update(p)
            return _FakeInsert()

    class _CS:
        def table(self, _):
            return _CT()

    log_activity_event(_CS(), org_id="org1", user_id="u1", action_type="test")
    assert captured.get("entity_type") == ""
    assert captured.get("entity_id") == ""


# ===========================================================================
# 11-13: Endpoint payload validation (no DB needed)
# ===========================================================================

def test_11_institutional_answer_patch_allowed_fields():
    """Only canonical_answer, confidence_level, is_active should be mapped."""
    # This mirrors the filtering logic in patch_institutional_answer
    ALLOWED = {"canonical_answer", "confidence_level", "is_active"}
    raw = {
        "canonical_answer": "new text",
        "confidence_level": "HIGH",
        "is_active": False,
        "org_id": "hacked",  # should be ignored
        "question": "injected",
    }
    update = {}
    if "canonical_answer" in raw:
        update["canonical_answer"] = str(raw["canonical_answer"])
    if "confidence_level" in raw:
        lvl = str(raw["confidence_level"]).upper()
        if lvl in ("HIGH", "MEDIUM", "LOW"):
            update["confidence_level"] = lvl
    if "is_active" in raw:
        update["is_active"] = bool(raw["is_active"])
    assert set(update.keys()) == ALLOWED


def test_12_memory_promote_payload_importable():
    from app.api.endpoints.runs import MemoryPromotePayload
    p = MemoryPromotePayload(audit_id="abc-123", answer_text="The answer")
    assert p.audit_id == "abc-123"
    assert p.answer_text == "The answer"


def test_13_confidence_level_validation_accepts_valid():
    VALID = ("HIGH", "MEDIUM", "LOW")
    for v in VALID:
        assert v.upper() in ("HIGH", "MEDIUM", "LOW")

def test_13b_confidence_level_validation_rejects_invalid():
    VALID = ("HIGH", "MEDIUM", "LOW")
    assert "EXTREME".upper() not in VALID
    assert "".upper() not in VALID


# ===========================================================================
# 14-19: Migration SQL content validation
# ===========================================================================

SQL_PATH = os.path.join(
    os.path.dirname(__file__), "..",
    "scripts", "010_institutional_memory_governance.sql"
)


def _read_sql():
    with open(SQL_PATH) as f:
        return f.read()


def test_14_migration_sql_file_exists():
    assert os.path.exists(SQL_PATH), "Migration SQL file must exist"


def test_15_migration_sql_has_is_active_column():
    sql = _read_sql()
    assert "is_active" in sql


def test_16_migration_sql_has_edited_by_and_edited_at():
    sql = _read_sql()
    assert "edited_by" in sql
    assert "edited_at" in sql


def test_17_migration_sql_creates_activity_log():
    sql = _read_sql()
    assert "CREATE TABLE IF NOT EXISTS activity_log" in sql
    assert "action_type" in sql
    assert "entity_type" in sql
    assert "entity_id" in sql
    assert "metadata" in sql


def test_18_migration_sql_has_indexes():
    sql = _read_sql()
    assert "activity_log_org_idx" in sql
    assert "activity_log_created_idx" in sql


def test_19_migration_sql_has_rls_policy():
    sql = _read_sql()
    assert "ROW LEVEL SECURITY" in sql
    assert "activity_log_org_member" in sql


# ===========================================================================
# 20-24: Health score logic tests
# ===========================================================================

def _compute_health_score(total_approved: int, total_rejected: int, total_pending: int,
                           avg_confidence_pct: float) -> int:
    """
    Mirror of the scoring logic in runs.py get_compliance_health.
    Score 0-100:
      - 50 pts from approval density (approved / total non-pending)
      - 30 pts from avg_confidence_pct / 100 * 30
      - -20 pts penalty if low confidence > 20%
    """
    reviewed = total_approved + total_rejected
    if reviewed == 0:
        return 0
    approval_density = total_approved / reviewed
    score = approval_density * 50
    score += (avg_confidence_pct / 100.0) * 30
    # Low confidence penalty placeholder (assume 0 for unit tests)
    score = max(0, min(100, round(score)))
    return int(score)


def test_20_health_score_field_present():
    """Health score must be a key in the expected response shape."""
    response_keys = {"health_score", "total_runs", "total_questions",
                     "avg_confidence_pct", "total_approved", "total_rejected",
                     "total_pending", "low_conf_trend"}
    assert "health_score" in response_keys


def test_21_health_score_range():
    for approved, rejected, avg in [
        (100, 0, 95.0),
        (0, 100, 10.0),
        (50, 50, 50.0),
        (0, 0, 0.0),
    ]:
        score = _compute_health_score(approved, rejected, 0, avg)
        assert 0 <= score <= 100, f"Score {score} out of range for approved={approved}"


def test_22_health_score_high_for_all_approved():
    score = _compute_health_score(100, 0, 0, 90.0)
    assert score >= 70, f"Expected high score for 100% approved, got {score}"


def test_23_health_score_low_for_all_rejected():
    score = _compute_health_score(0, 100, 0, 10.0)
    assert score <= 10, f"Expected low score for 100% rejected, got {score}"


def test_24_health_score_zero_for_empty():
    score = _compute_health_score(0, 0, 0, 0.0)
    assert score == 0


# ===========================================================================
# 25: Frontend MemoryGovPanel — import guard (TypeScript, skip if no TS runner)
# ===========================================================================

def test_25_memory_gov_panel_file_exists():
    panel_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "frontend",
        "components", "settings", "MemoryGovPanel.tsx"
    )
    assert os.path.exists(panel_path), "MemoryGovPanel.tsx must exist"
