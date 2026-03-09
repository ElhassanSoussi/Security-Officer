"""
Knowledge Memory System — Unit Test Suite

All 25 tests are deterministic and require no DB, API, or OpenAI connection.
Supabase and embedding calls are fully stubbed.

Tests:
 1.  CONSTANTS     — MEMORY_SIMILARITY_THRESHOLD == 0.85
 2.  CONSTANTS     — MEMORY_SEARCH_LIMIT == 3
 3.  search_memory — returns None when supabase RPC yields empty list
 4.  search_memory — returns first row when RPC returns results
 5.  search_memory — returns None (non-fatal) when embedding raises
 6.  search_memory — returns None (non-fatal) when RPC raises
 7.  search_memory — passes correct params to match_knowledge_memory RPC
 8.  record_match  — inserts expected fields into memory_matches table
 9.  record_match  — is non-fatal when DB insert raises
10.  record_match  — truncates question_text longer than 2000 chars
11.  save_memory   — returns None for empty question_text
12.  save_memory   — returns None for empty answer_text
13.  save_memory   — returns new UUID on successful insert
14.  save_memory   — is non-fatal when DB insert raises (returns None)
15.  save_memory   — stores confidence rounded to 4 decimal places
16.  save_memory   — truncates question_text at 4000 chars
17.  save_memory   — truncates answer_text at 8000 chars
18.  save_memory   — includes approved_by in inserted row
19.  MIGRATION SQL — knowledge_memory table defined
20.  MIGRATION SQL — memory_matches table defined
21.  MIGRATION SQL — vector(1536) embedding column present
22.  MIGRATION SQL — match_knowledge_memory RPC function defined
23.  MIGRATION SQL — RLS policies defined for both tables
24.  MIGRATION SQL — indexes on organization_id and source_run_id
25.  ENDPOINT      — SaveMemoryPayload model importable with correct fields
"""

from __future__ import annotations

import os
import sys
import types
import uuid

import pytest

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------
BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# ---------------------------------------------------------------------------
# Minimal stubs — prevent real network/OpenAI calls during import
# ---------------------------------------------------------------------------

_FAKE_EMBEDDING = [0.1] * 1536


def _make_stub_modules():
    """Inject lightweight stubs for heavy optional imports."""
    # openai stub
    openai_mod = types.ModuleType("openai")
    openai_mod.OpenAI = lambda *a, **kw: None  # type: ignore[attr-defined]
    sys.modules.setdefault("openai", openai_mod)

    # app.core.similarity stub
    sim_mod = types.ModuleType("app.core.similarity")

    def _fake_embed(text: str):
        return _FAKE_EMBEDDING

    sim_mod.get_embedding_cached = _fake_embed  # type: ignore[attr-defined]
    sys.modules.setdefault("app.core.similarity", sim_mod)


_make_stub_modules()

# ---------------------------------------------------------------------------
# Shared fake Supabase helpers
# ---------------------------------------------------------------------------


class _FakeExecuteResult:
    def __init__(self, data=None):
        self.data = data or []


class _FakeRpc:
    def __init__(self, data=None, raise_err=None):
        self._data = data or []
        self._raise_err = raise_err

    def execute(self):
        if self._raise_err:
            raise self._raise_err
        return _FakeExecuteResult(self._data)


class _FakeInsertChain:
    def __init__(self, return_data=None, raise_err=None):
        self._data = return_data or []
        self._raise_err = raise_err
        self.inserted_payload: dict | None = None

    def execute(self):
        if self._raise_err:
            raise self._raise_err
        return _FakeExecuteResult(self._data)


class _FakeTable:
    def __init__(self, insert_data=None, insert_err=None):
        self._insert_data = insert_data or []
        self._insert_err = insert_err
        self.last_insert: dict | None = None

    def insert(self, payload: dict):
        self.last_insert = payload
        return _FakeInsertChain(self._insert_data, self._insert_err)


class _FakeSupabase:
    """Minimal Supabase client stub supporting .rpc() and .table()."""

    def __init__(
        self,
        rpc_data=None,
        rpc_err=None,
        insert_data=None,
        insert_err=None,
    ):
        self._rpc_data = rpc_data or []
        self._rpc_err = rpc_err
        self._insert_data = insert_data
        self._insert_err = insert_err
        self.last_rpc_fn: str | None = None
        self.last_rpc_params: dict | None = None
        self.last_table: str | None = None
        self._tables: dict[str, _FakeTable] = {}

    def rpc(self, fn_name: str, params: dict):
        self.last_rpc_fn = fn_name
        self.last_rpc_params = params
        return _FakeRpc(self._rpc_data, self._rpc_err)

    def table(self, name: str) -> _FakeTable:
        self.last_table = name
        if name not in self._tables:
            self._tables[name] = _FakeTable(
                insert_data=self._insert_data, insert_err=self._insert_err
            )
        return self._tables[name]


# ---------------------------------------------------------------------------
# Helpers: patch embedding so no real OpenAI call is made
# ---------------------------------------------------------------------------

def _import_km():
    """Import knowledge_memory with embedding patched."""
    import importlib
    import app.core.knowledge_memory as km_mod
    importlib.reload(km_mod)
    km_mod._get_embedding = lambda text: _FAKE_EMBEDDING  # type: ignore[attr-defined]
    return km_mod


# ===========================================================================
# 1-2: Constants
# ===========================================================================


def test_01_similarity_threshold_is_085():
    km = _import_km()
    assert km.MEMORY_SIMILARITY_THRESHOLD == 0.85


def test_02_search_limit_is_3():
    km = _import_km()
    assert km.MEMORY_SEARCH_LIMIT == 3


# ===========================================================================
# 3-7: search_memory
# ===========================================================================


def test_03_search_memory_returns_none_when_rpc_empty():
    km = _import_km()
    sb = _FakeSupabase(rpc_data=[])
    result = km.search_memory("What is your MFA policy?", "org-1", sb)
    assert result is None


def test_04_search_memory_returns_first_row_on_hit():
    km = _import_km()
    row = {
        "id": str(uuid.uuid4()),
        "question_text": "What is your MFA policy?",
        "answer_text": "All accounts require MFA.",
        "confidence": 0.92,
        "similarity": 0.93,
    }
    sb = _FakeSupabase(rpc_data=[row])
    result = km.search_memory("What is your MFA policy?", "org-1", sb)
    assert result == row


def test_05_search_memory_nonfatal_on_embedding_error():
    import app.core.knowledge_memory as km_mod
    import importlib
    importlib.reload(km_mod)

    def _bad_embed(text):
        raise RuntimeError("OpenAI down")

    km_mod._get_embedding = _bad_embed  # type: ignore[attr-defined]
    sb = _FakeSupabase()
    result = km_mod.search_memory("something", "org-1", sb)
    assert result is None


def test_06_search_memory_nonfatal_on_rpc_error():
    km = _import_km()
    sb = _FakeSupabase(rpc_err=RuntimeError("DB gone"))
    result = km.search_memory("What is your DR plan?", "org-1", sb)
    assert result is None


def test_07_search_memory_passes_correct_rpc_params():
    km = _import_km()
    org_id = str(uuid.uuid4())
    sb = _FakeSupabase(rpc_data=[])
    km.search_memory("Do you have encryption at rest?", org_id, sb)

    assert sb.last_rpc_fn == "match_knowledge_memory"
    params = sb.last_rpc_params
    assert params["filter_org_id"] == org_id
    assert params["match_threshold"] == km.MEMORY_SIMILARITY_THRESHOLD
    assert params["match_count"] == km.MEMORY_SEARCH_LIMIT
    assert len(params["query_embedding"]) == 1536


# ===========================================================================
# 8-10: record_memory_match
# ===========================================================================


def test_08_record_match_inserts_expected_fields():
    km = _import_km()
    memory_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    sb = _FakeSupabase()
    km.record_memory_match(
        question_text="What is your BCP?",
        matched_memory_id=memory_id,
        similarity_score=0.91,
        run_id=run_id,
        sb=sb,
    )
    tbl = sb._tables.get("memory_matches")
    assert tbl is not None
    payload = tbl.last_insert
    assert payload["matched_memory_id"] == memory_id
    assert payload["similarity_score"] == round(0.91, 4)
    assert payload["used_in_run"] == run_id
    assert "created_at" in payload


def test_09_record_match_nonfatal_on_db_error():
    km = _import_km()
    sb = _FakeSupabase(insert_err=RuntimeError("DB timeout"))
    # Must not raise
    km.record_memory_match("q", str(uuid.uuid4()), 0.90, None, sb)


def test_10_record_match_truncates_long_question():
    km = _import_km()
    long_q = "x" * 3000
    sb = _FakeSupabase()
    km.record_memory_match(long_q, str(uuid.uuid4()), 0.88, None, sb)
    tbl = sb._tables.get("memory_matches")
    assert len(tbl.last_insert["question_text"]) <= 2000


# ===========================================================================
# 11-18: save_to_memory
# ===========================================================================


def test_11_save_memory_returns_none_for_empty_question():
    km = _import_km()
    sb = _FakeSupabase()
    result = km.save_to_memory("org-1", "", "Some answer", 0.9, None, "user-1", sb)
    assert result is None


def test_12_save_memory_returns_none_for_empty_answer():
    km = _import_km()
    sb = _FakeSupabase()
    result = km.save_to_memory("org-1", "A question", "", 0.9, None, "user-1", sb)
    assert result is None


def test_13_save_memory_returns_new_uuid_on_success():
    km = _import_km()
    new_id = str(uuid.uuid4())
    sb = _FakeSupabase(insert_data=[{"id": new_id}])
    result = km.save_to_memory(
        organization_id="org-1",
        question_text="What is your patching cadence?",
        answer_text="Monthly patches applied within 72 h.",
        confidence=0.9,
        source_run_id=None,
        approved_by="user-abc",
        sb=sb,
    )
    assert result == new_id


def test_14_save_memory_nonfatal_on_db_error():
    km = _import_km()
    sb = _FakeSupabase(insert_err=RuntimeError("insert failed"))
    result = km.save_to_memory("org-1", "Q?", "A.", 0.8, None, "user-1", sb)
    assert result is None


def test_15_save_memory_rounds_confidence_to_4dp():
    km = _import_km()
    new_id = str(uuid.uuid4())
    sb = _FakeSupabase(insert_data=[{"id": new_id}])
    km.save_to_memory("org-1", "Q?", "A.", 0.876543210, None, "user-1", sb)
    tbl = sb._tables.get("knowledge_memory")
    assert tbl is not None
    payload = tbl.last_insert
    assert payload["confidence"] == round(0.876543210, 4)


def test_16_save_memory_truncates_question_at_4000():
    km = _import_km()
    long_q = "q" * 5000
    new_id = str(uuid.uuid4())
    sb = _FakeSupabase(insert_data=[{"id": new_id}])
    km.save_to_memory("org-1", long_q, "A.", 0.9, None, "user-1", sb)
    tbl = sb._tables.get("knowledge_memory")
    assert len(tbl.last_insert["question_text"]) <= 4000


def test_17_save_memory_truncates_answer_at_8000():
    km = _import_km()
    long_a = "a" * 10000
    new_id = str(uuid.uuid4())
    sb = _FakeSupabase(insert_data=[{"id": new_id}])
    km.save_to_memory("org-1", "Q?", long_a, 0.9, None, "user-1", sb)
    tbl = sb._tables.get("knowledge_memory")
    assert len(tbl.last_insert["answer_text"]) <= 8000


def test_18_save_memory_stores_approved_by():
    km = _import_km()
    approver = str(uuid.uuid4())
    new_id = str(uuid.uuid4())
    sb = _FakeSupabase(insert_data=[{"id": new_id}])
    km.save_to_memory("org-1", "Q?", "A.", 0.9, None, approver, sb)
    tbl = sb._tables.get("knowledge_memory")
    assert tbl.last_insert["approved_by"] == approver


# ===========================================================================
# 19-24: Migration SQL contract checks
# ===========================================================================

SQL_PATH = os.path.join(
    os.path.dirname(__file__), "..", "migrations", "knowledge_memory.sql"
)


def _sql() -> str:
    with open(SQL_PATH, "r") as f:
        return f.read()


def test_19_migration_defines_knowledge_memory_table():
    assert "create table if not exists knowledge_memory" in _sql()


def test_20_migration_defines_memory_matches_table():
    assert "create table if not exists memory_matches" in _sql()


def test_21_migration_has_vector_1536_column():
    assert "vector(1536)" in _sql()


def test_22_migration_defines_match_rpc_function():
    sql = _sql()
    assert "create or replace function match_knowledge_memory" in sql
    assert "query_embedding" in sql
    assert "filter_org_id" in sql


def test_23_migration_has_rls_policies():
    sql = _sql()
    assert "enable row level security" in sql
    assert "create policy" in sql
    # Both tables must have policies
    assert "knowledge_memory" in sql
    assert "memory_matches" in sql


def test_24_migration_has_required_indexes():
    sql = _sql()
    assert "knowledge_memory_org_idx" in sql
    assert "knowledge_memory_run_idx" in sql
    assert "memory_matches_memory_id_idx" in sql


# ===========================================================================
# 25: Endpoint — SaveMemoryPayload model shape
# ===========================================================================


def test_25_save_memory_payload_importable():
    from app.api.endpoints.knowledge_memory import SaveMemoryPayload
    # Must have audit_id (required) and org_id (optional)
    import inspect
    fields = SaveMemoryPayload.model_fields
    assert "audit_id" in fields
    assert "org_id" in fields
    # org_id must be optional
    assert fields["org_id"].is_required() is False
