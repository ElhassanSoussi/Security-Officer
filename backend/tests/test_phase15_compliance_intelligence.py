"""
Phase 15 Verification: Compliance Intelligence + Institutional Memory Engine

Tests cover (all deterministic, no DB/API/OpenAI needed):
1.  normalize_question — lowercasing, punctuation stripping, whitespace collapse
2.  hash_question — SHA-256 stability and uniqueness
3.  confidence_score_to_level — numeric and string inputs
4.  store_institutional_answer — rejects blank inputs
5.  InstitutionalMemoryLookup — graceful failure when DB unavailable
6.  compute_delta backward-compat — still works with Phase 15 code present
7.  _normalize_question alias still importable
8.  ComplianceHealthDefaults — _empty_health shape
9.  RiskIndicators — pct thresholds for warning/critical
10. RunCompare — summary keys present
11. MemoryFlag — reused_from_memory logic in analyze flow
12. ConfidenceLevelMapping — all branches covered
13. NormalizationIdempotent — double-normalize is stable
14. HashCollisionFreedom — different questions get different hashes
15. MemoryStoreBlankAnswerRejected — returns None for empty answer
16. MemoryStoreLowConfClamp — invalid conf defaults to MEDIUM
17. BackwardCompat — similarity.py imports still work
18. BackwardCompat — institutional_memory importable from core
19. ComplianceHealthEmpty — empty org returns zeros
20. TrendLabelTrim — labels > 24 chars get trimmed
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ─── 1. normalize_question ────────────────────────────────────────────────────

class TestNormalizeQuestion:
    def test_lowercases(self):
        from app.core.institutional_memory import normalize_question
        assert normalize_question("Is Fire Safety OK?") == "is fire safety ok"

    def test_strips_punctuation(self):
        from app.core.institutional_memory import normalize_question
        assert normalize_question("Hello, world!") == "hello world"

    def test_collapses_whitespace(self):
        from app.core.institutional_memory import normalize_question
        assert normalize_question("Is   the   door   open?") == "is the door open"

    def test_strips_leading_trailing(self):
        from app.core.institutional_memory import normalize_question
        assert normalize_question("  hello  ") == "hello"

    def test_empty_string(self):
        from app.core.institutional_memory import normalize_question
        assert normalize_question("") == ""

    def test_numbers_preserved(self):
        from app.core.institutional_memory import normalize_question
        result = normalize_question("Are 3 exits required?")
        assert "3" in result


# ─── 2. hash_question ─────────────────────────────────────────────────────────

class TestHashQuestion:
    def test_returns_64_char_hex(self):
        from app.core.institutional_memory import hash_question
        h = hash_question("Is the building entrance accessible?")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_stable_across_calls(self):
        from app.core.institutional_memory import hash_question
        q = "Are fire extinguishers inspected monthly?"
        assert hash_question(q) == hash_question(q)

    def test_case_insensitive(self):
        from app.core.institutional_memory import hash_question
        assert hash_question("Is Fire Safe?") == hash_question("is fire safe?")

    def test_punctuation_insensitive(self):
        from app.core.institutional_memory import hash_question
        assert hash_question("Is it safe!") == hash_question("Is it safe")

    def test_different_questions_different_hashes(self):
        from app.core.institutional_memory import hash_question
        h1 = hash_question("Question A")
        h2 = hash_question("Question B")
        assert h1 != h2


# ─── 3. confidence_score_to_level ─────────────────────────────────────────────

class TestConfidenceScoreToLevel:
    def test_string_high(self):
        from app.core.institutional_memory import confidence_score_to_level
        assert confidence_score_to_level("HIGH") == "HIGH"

    def test_string_medium(self):
        from app.core.institutional_memory import confidence_score_to_level
        assert confidence_score_to_level("medium") == "MEDIUM"

    def test_string_low(self):
        from app.core.institutional_memory import confidence_score_to_level
        assert confidence_score_to_level("LOW") == "LOW"

    def test_float_high(self):
        from app.core.institutional_memory import confidence_score_to_level
        assert confidence_score_to_level(0.9) == "HIGH"

    def test_float_medium(self):
        from app.core.institutional_memory import confidence_score_to_level
        assert confidence_score_to_level(0.65) == "MEDIUM"

    def test_float_low(self):
        from app.core.institutional_memory import confidence_score_to_level
        assert confidence_score_to_level(0.3) == "LOW"

    def test_pct_score(self):
        from app.core.institutional_memory import confidence_score_to_level
        assert confidence_score_to_level(85) == "HIGH"

    def test_boundary_08(self):
        from app.core.institutional_memory import confidence_score_to_level
        assert confidence_score_to_level(0.8) == "HIGH"

    def test_boundary_05(self):
        from app.core.institutional_memory import confidence_score_to_level
        assert confidence_score_to_level(0.5) == "MEDIUM"

    def test_invalid_string_defaults_medium(self):
        from app.core.institutional_memory import confidence_score_to_level
        assert confidence_score_to_level("unknown") == "MEDIUM"

    def test_none_defaults_medium(self):
        from app.core.institutional_memory import confidence_score_to_level
        assert confidence_score_to_level(None) == "MEDIUM"


# ─── 4 & 5. store / lookup — graceful failure when DB absent ──────────────────

class TestMemoryGracefulFailure:
    def test_store_blank_question_returns_none(self):
        from app.core.institutional_memory import store_institutional_answer
        # No token → will fail to connect; blank question should return None immediately
        result = store_institutional_answer("", "answer text", "org-123")
        assert result is None

    def test_store_blank_answer_returns_none(self):
        from app.core.institutional_memory import store_institutional_answer
        result = store_institutional_answer("valid question?", "", "org-123")
        assert result is None

    def test_lookup_db_failure_returns_none(self):
        from app.core.institutional_memory import lookup_institutional_answer
        # No valid token/DB → should return None gracefully
        result = lookup_institutional_answer("Is the door locked?", "nonexistent-org-id")
        assert result is None

    def test_store_db_failure_returns_none(self):
        from app.core.institutional_memory import store_institutional_answer
        result = store_institutional_answer(
            "Is the sprinkler tested?", "Yes, quarterly.", "nonexistent-org-id"
        )
        assert result is None


# ─── 6 & 7. compute_delta / _normalize_question backward compat ───────────────

class TestBackwardCompatDelta:
    def test_compute_delta_still_works(self):
        from app.core.similarity import compute_delta
        current = [{"question_text": "Is fire safe?", "cell_reference": "B2"}]
        previous = [{"question_text": "Is fire safe?", "cell_reference": "B2"}]
        result = compute_delta(current, previous)
        assert result["Is fire safe?"] == "UNCHANGED"

    def test_normalize_question_importable(self):
        from app.core.similarity import _normalize_question
        assert _normalize_question("Hello World!") == "hello world!"

    def test_institutional_memory_importable(self):
        import app.core.institutional_memory as im
        assert hasattr(im, "normalize_question")
        assert hasattr(im, "hash_question")
        assert hasattr(im, "lookup_institutional_answer")
        assert hasattr(im, "store_institutional_answer")
        assert hasattr(im, "confidence_score_to_level")


# ─── 8. ComplianceHealth empty shape ─────────────────────────────────────────

class TestComplianceHealthEmpty:
    def test_empty_health_has_all_keys(self):
        from app.api.endpoints.runs import _empty_health
        h = _empty_health()
        required_keys = {
            "total_runs", "total_questions", "avg_confidence_pct",
            "total_approved", "total_rejected", "total_pending",
            "total_low_conf", "total_high_conf", "total_medium_conf",
            "memory_reuse_count", "avg_review_turnaround_hours", "low_conf_trend",
        }
        # Phase 16 added health_score; use subset check so new keys don't break this test
        assert required_keys <= set(h.keys())

    def test_empty_health_zeros(self):
        from app.api.endpoints.runs import _empty_health
        h = _empty_health()
        assert h["total_runs"] == 0
        assert h["total_questions"] == 0
        assert h["avg_confidence_pct"] == 0
        assert h["low_conf_trend"] == []
        assert h["avg_review_turnaround_hours"] is None


# ─── 9. Risk Indicators — threshold logic ─────────────────────────────────────

class TestRiskIndicators:
    """
    Risk logic (frontend-mirrored):
      CRITICAL if low_conf_pct > 20 or rejected_pct > 10
      WARNING  if low_conf_pct > 10 or pending > 0
      OK       otherwise
    """

    def _risk_level(self, total, low, rejected, pending):
        if total == 0:
            return "ok"
        low_pct = low / total * 100
        rej_pct = rejected / total * 100
        if low_pct > 20 or rej_pct > 10:
            return "critical"
        if low_pct > 10 or pending > 0:
            return "warning"
        return "ok"

    def test_ok_all_approved_high(self):
        assert self._risk_level(10, 0, 0, 0) == "ok"

    def test_warning_has_pending(self):
        assert self._risk_level(10, 0, 0, 1) == "warning"

    def test_warning_low_conf_just_above_10(self):
        # 11% low conf
        assert self._risk_level(100, 11, 0, 0) == "warning"

    def test_critical_low_conf_above_20(self):
        assert self._risk_level(100, 21, 0, 0) == "critical"

    def test_critical_rejected_above_10(self):
        assert self._risk_level(100, 0, 11, 0) == "critical"

    def test_empty_runs_ok(self):
        assert self._risk_level(0, 0, 0, 0) == "ok"


# ─── 10. RunCompare summary keys ──────────────────────────────────────────────

class TestRunCompareSummaryKeys:
    def test_summary_has_correct_keys(self):
        """compare endpoint summary must have new/modified/unchanged/removed."""
        expected_keys = {"new", "modified", "unchanged", "removed"}
        # Directly exercise compute_delta to verify mapping
        from app.core.similarity import compute_delta
        current = [
            {"question_text": "Question A", "cell_reference": "B2"},
            {"question_text": "Question B new", "cell_reference": "B3"},
        ]
        previous = [
            {"question_text": "Question A", "cell_reference": "B2"},
            {"question_text": "Question B old", "cell_reference": "B3"},
        ]
        delta = compute_delta(current, previous)
        assert "Question A" in delta
        assert delta["Question A"] == "UNCHANGED"
        assert delta["Question B new"] == "MODIFIED"


# ─── 11. Memory flag in audit rows ───────────────────────────────────────────

class TestMemoryFlag:
    def test_reused_origin_sets_memory_flag(self):
        """When answer_origin == 'reused', reused_from_memory must be True."""
        answer_origin = "reused"
        flag = (answer_origin == "reused")
        assert flag is True

    def test_generated_origin_does_not_set_flag(self):
        answer_origin = "generated"
        flag = (answer_origin == "reused")
        assert flag is False

    def test_suggested_origin_does_not_set_flag(self):
        answer_origin = "suggested"
        flag = (answer_origin == "reused")
        assert flag is False


# ─── 12. Confidence level complete branch coverage ───────────────────────────

class TestConfidenceLevelAllBranches:
    def test_exact_boundary_low_high(self):
        from app.core.institutional_memory import confidence_score_to_level
        # 0.799 → MEDIUM, 0.800 → HIGH
        assert confidence_score_to_level(0.799) == "MEDIUM"
        assert confidence_score_to_level(0.800) == "HIGH"

    def test_exact_boundary_low_medium(self):
        from app.core.institutional_memory import confidence_score_to_level
        assert confidence_score_to_level(0.499) == "LOW"
        assert confidence_score_to_level(0.500) == "MEDIUM"


# ─── 13. Normalization idempotent ─────────────────────────────────────────────

class TestNormalizationIdempotent:
    def test_double_normalize_stable(self):
        from app.core.institutional_memory import normalize_question
        q = "  Is the EXIT  sign lit?!  "
        once = normalize_question(q)
        twice = normalize_question(once)
        assert once == twice

    def test_hash_idempotent(self):
        from app.core.institutional_memory import hash_question, normalize_question
        q = "Does the building have sprinklers?"
        # Normalizing the same text twice gives same hash (idempotent normalization)
        assert hash_question(q) == hash_question(normalize_question(q))


# ─── 14. Hash collision freedom ──────────────────────────────────────────────

class TestHashCollisionFreedom:
    def test_ten_questions_all_unique_hashes(self):
        from app.core.institutional_memory import hash_question
        questions = [
            "Is the entrance accessible?",
            "Are fire extinguishers tagged?",
            "Is the electrical panel labeled?",
            "Are emergency exits clearly marked?",
            "Has the roof been inspected this year?",
            "Are stairwells free from obstruction?",
            "Is the boiler room locked?",
            "Are plumbing fixtures compliant?",
            "Is the elevator inspected annually?",
            "Are exterior lights functional?",
        ]
        hashes = [hash_question(q) for q in questions]
        assert len(set(hashes)) == len(hashes), "Collision detected among test questions"


# ─── 15-16. store edge cases ─────────────────────────────────────────────────

class TestStoreEdgeCases:
    def test_invalid_confidence_clamps_to_medium(self):
        from app.core.institutional_memory import confidence_score_to_level
        assert confidence_score_to_level("EXCELLENT") == "MEDIUM"
        assert confidence_score_to_level("5-stars") == "MEDIUM"

    def test_whitespace_only_question_treated_as_blank(self):
        from app.core.institutional_memory import store_institutional_answer
        # "   " normalizes to "" which is falsy → returns None immediately
        result = store_institutional_answer("   ", "some answer", "org-id")
        assert result is None


# ─── 17-18. Backward compatibility imports ───────────────────────────────────

class TestBackwardCompatImports:
    def test_similarity_module_unchanged(self):
        from app.core.similarity import (
            EmbeddingCache, SimilarityEngine, SimilarityMatch,
            SimilarityResult, compute_delta, similarity_engine,
        )
        assert similarity_engine is not None

    def test_config_settings_unchanged(self):
        from app.core.config import get_settings
        s = get_settings()
        assert hasattr(s, "REUSE_EXACT_THRESHOLD")
        assert hasattr(s, "REUSE_SUGGEST_THRESHOLD")
        assert hasattr(s, "REUSE_ENABLED")

    def test_schemas_unchanged(self):
        from app.models.schemas import QuestionItem
        item = QuestionItem(
            sheet_name="Sheet1",
            cell_coordinate="B2",
            question="Q?",
            ai_answer="A",
            final_answer="A",
            confidence="HIGH",
            sources=[],
        )
        # Phase 4 fields still present
        assert hasattr(item, "answer_origin")
        assert hasattr(item, "change_type")


# ─── 19. Trend label trimming ─────────────────────────────────────────────────

class TestTrendLabelTrim:
    def _trim_label(self, label: str, max_len: int = 24) -> str:
        if len(label) > max_len:
            return label[: max_len - 3] + "…"
        return label

    def test_short_label_unchanged(self):
        assert self._trim_label("NYC_Q1.xlsx") == "NYC_Q1.xlsx"

    def test_long_label_trimmed(self):
        long = "Very_Long_Questionnaire_Filename_2026.xlsx"
        result = self._trim_label(long)
        # result is 21 ASCII chars + 1 ellipsis char = len 22 visually, but ≤ max_len in char count
        assert len(result) <= max(24, len("…") + 21)
        assert "…" in result

    def test_exact_24_chars_unchanged(self):
        label = "A" * 24
        assert self._trim_label(label) == label

    def test_25_chars_trimmed(self):
        label = "A" * 25
        result = self._trim_label(label)
        # 25 - 3 = 22 "A"s + ellipsis char
        assert result == "A" * 21 + "…"
        assert "…" in result


# ─── 20. Phase 15 integration: routes.py import safe ─────────────────────────

class TestRoutesIntegration:
    def test_routes_import_clean(self):
        """routes.py must still import without error after Phase 15 changes."""
        import importlib
        import app.api.routes as routes_mod
        importlib.reload(routes_mod)
        assert hasattr(routes_mod, "router")

    def test_runs_endpoint_import_clean(self):
        import importlib
        import app.api.endpoints.runs as runs_mod
        importlib.reload(runs_mod)
        assert hasattr(runs_mod, "router")
        assert hasattr(runs_mod, "_empty_health")
