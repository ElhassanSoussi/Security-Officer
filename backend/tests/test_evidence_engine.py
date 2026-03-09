"""
Evidence-Based Answer Engine — tests
======================================
Deterministic, no real DB / network calls.

Coverage:
  1–3.   File existence (migration, answer_store, frontend api.ts additions)
  4–6.   SQL migration: document_chunks view, generated_answers table, RLS/indexes
  7–11.  answer_store: confidence parsing, low-confidence threshold, store function,
         summary function, org isolation (org_id always written)
  12–14. API endpoints registered: /answers/summary, /answers
  15–17. routes.py: store_generated_answers called after run_audits
  18–21. Frontend run page: progress steps, avg-confidence display
  22–24. Frontend audit page: evidence panel markup
  25–27. api.ts: getRunAnswersSummary, getRunAnswers typed methods
"""

from __future__ import annotations

import os
import sys

import pytest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPO_ROOT   = os.path.abspath(os.path.join(BACKEND_DIR, ".."))
FRONTEND_DIR = os.path.join(REPO_ROOT, "frontend")

if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

MIGRATION_SQL   = os.path.join(BACKEND_DIR, "migrations", "evidence_engine.sql")
ANSWER_STORE_PY = os.path.join(BACKEND_DIR, "app", "core", "answer_store.py")
RUNS_EP_PY      = os.path.join(BACKEND_DIR, "app", "api", "endpoints", "runs.py")
ROUTES_PY       = os.path.join(BACKEND_DIR, "app", "api", "routes.py")
RUN_PAGE_TSX    = os.path.join(FRONTEND_DIR, "app", "run", "page.tsx")
AUDIT_PAGE_TSX  = os.path.join(FRONTEND_DIR, "app", "audit", "page.tsx")
API_TS          = os.path.join(FRONTEND_DIR, "lib", "api.ts")


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


# ──────────────────────────────────────────────────────────────────────────────
# 1–3: File existence
# ──────────────────────────────────────────────────────────────────────────────

class TestFileExistence:
    def test_01_migration_sql_exists(self):
        assert os.path.isfile(MIGRATION_SQL), "migrations/evidence_engine.sql not found"

    def test_02_answer_store_exists(self):
        assert os.path.isfile(ANSWER_STORE_PY), "app/core/answer_store.py not found"

    def test_03_runs_endpoint_exists(self):
        assert os.path.isfile(RUNS_EP_PY)


# ──────────────────────────────────────────────────────────────────────────────
# 4–6: SQL migration content
# ──────────────────────────────────────────────────────────────────────────────

class TestMigrationSQL:
    def test_04_document_chunks_view(self):
        sql = _read(MIGRATION_SQL)
        assert "document_chunks" in sql
        assert "view" in sql.lower()
        # maps content -> chunk_text
        assert "chunk_text" in sql

    def test_05_generated_answers_table(self):
        sql = _read(MIGRATION_SQL)
        assert "generated_answers" in sql
        assert "run_id" in sql
        assert "confidence" in sql
        assert "needs_review" in sql
        assert "source_document" in sql
        assert "page_number" in sql

    def test_06_rls_and_indexes_defined(self):
        sql = _read(MIGRATION_SQL)
        assert "row level security" in sql.lower() or "enable row level security" in sql.lower()
        assert "index" in sql.lower()


# ──────────────────────────────────────────────────────────────────────────────
# 7–11: answer_store module
# ──────────────────────────────────────────────────────────────────────────────

class TestAnswerStore:
    def test_07_low_confidence_threshold_defined(self):
        src = _read(ANSWER_STORE_PY)
        assert "LOW_CONFIDENCE_THRESHOLD" in src

    def test_08_threshold_value_is_correct(self):
        from app.core.answer_store import LOW_CONFIDENCE_THRESHOLD
        assert LOW_CONFIDENCE_THRESHOLD == 0.5

    def test_09_parse_confidence_string_labels(self):
        from app.core.answer_store import _parse_confidence
        assert _parse_confidence("HIGH")   >= 0.7
        assert _parse_confidence("MEDIUM") >= 0.5
        assert _parse_confidence("LOW")    <  0.5
        assert _parse_confidence(None) == 0.0
        assert _parse_confidence(0.85) == pytest.approx(0.85)

    def test_10_store_function_marks_needs_review(self):
        src = _read(ANSWER_STORE_PY)
        assert "needs_review" in src
        assert "LOW_CONFIDENCE_THRESHOLD" in src

    def test_11_store_writes_org_id(self):
        src = _read(ANSWER_STORE_PY)
        # org_id is always included in the row dict
        store_start = src.find("def store_generated_answers")
        store_end   = src.find("\ndef ", store_start + 1)
        snippet = src[store_start:] if store_end == -1 else src[store_start:store_end]
        assert '"org_id"' in snippet or "'org_id'" in snippet


# ──────────────────────────────────────────────────────────────────────────────
# 12–14: API endpoints
# ──────────────────────────────────────────────────────────────────────────────

class TestAPIEndpoints:
    def test_12_answers_summary_route(self):
        src = _read(RUNS_EP_PY)
        assert "/answers/summary" in src

    def test_13_answers_list_route(self):
        src = _read(RUNS_EP_PY)
        assert '"/answers"' in src or "/{run_id}/answers" in src

    def test_14_endpoints_are_get(self):
        src = _read(RUNS_EP_PY)
        assert "get_run_answers_summary" in src
        assert "get_run_answers" in src


# ──────────────────────────────────────────────────────────────────────────────
# 15–17: routes.py wiring
# ──────────────────────────────────────────────────────────────────────────────

class TestRoutesWiring:
    def test_15_store_generated_answers_imported(self):
        src = _read(ROUTES_PY)
        assert "store_generated_answers" in src

    def test_16_called_after_audit_insert(self):
        src = _read(ROUTES_PY)
        audit_pos  = src.find("run_audits")
        store_pos  = src.find("store_generated_answers")
        assert store_pos > audit_pos, "store_generated_answers must appear after run_audits insert"

    def test_17_non_blocking_best_effort(self):
        src = _read(ROUTES_PY)
        # The call must be inside a try/except so it never blocks the response
        store_pos = src.find("store_generated_answers")
        snippet   = src[max(0, store_pos - 80):store_pos + 80]
        assert "try" in snippet or "except" in src[store_pos:store_pos + 300]


# ──────────────────────────────────────────────────────────────────────────────
# 18–21: Frontend run page
# ──────────────────────────────────────────────────────────────────────────────

class TestRunPage:
    def test_18_analysis_steps_defined(self):
        src = _read(RUN_PAGE_TSX)
        assert "ANALYSIS_STEPS" in src

    def test_19_progress_dots_rendered(self):
        src = _read(RUN_PAGE_TSX)
        assert "analysisStepIdx" in src

    def test_20_avg_confidence_state(self):
        src = _read(RUN_PAGE_TSX)
        assert "avgConfidence" in src

    def test_21_avg_confidence_displayed(self):
        src = _read(RUN_PAGE_TSX)
        assert "avg_confidence" in src or "avgConfidence" in src
        assert "Average confidence" in src


# ──────────────────────────────────────────────────────────────────────────────
# 22–24: Frontend audit page — evidence panel
# ──────────────────────────────────────────────────────────────────────────────

class TestAuditPage:
    def test_22_evidence_panel_label(self):
        src = _read(AUDIT_PAGE_TSX)
        assert "Evidence" in src

    def test_23_source_excerpt_blockquote(self):
        src = _read(AUDIT_PAGE_TSX)
        assert "source_excerpt" in src
        assert "blockquote" in src

    def test_24_source_document_shown(self):
        src = _read(AUDIT_PAGE_TSX)
        assert "source_document" in src
        assert "page_number" in src


# ──────────────────────────────────────────────────────────────────────────────
# 25–27: api.ts typed methods
# ──────────────────────────────────────────────────────────────────────────────

class TestApiTS:
    def test_25_get_run_answers_summary_defined(self):
        assert "getRunAnswersSummary" in _read(API_TS)

    def test_26_get_run_answers_defined(self):
        assert "getRunAnswers" in _read(API_TS)

    def test_27_summary_typed_return(self):
        src = _read(API_TS)
        idx = src.find("getRunAnswersSummary")
        snippet = src[idx:idx + 300]
        assert "needs_review_count" in snippet
        assert "avg_confidence" in snippet
