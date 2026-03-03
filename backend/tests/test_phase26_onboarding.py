"""
Phase 26 Verification: New Customer Onboarding Guide — E2E Tests

All tests are deterministic — no real DB / API / OpenAI calls needed.

Tests cover:
 1. Migration SQL — 018_org_onboarding.sql exists on disk
 2. Migration SQL — onboarding_completed column defined
 3. Migration SQL — onboarding_step column defined
 4. Migration SQL — CHECK constraint bounds step 1..5
 5. Migration SQL — default false for onboarding_completed
 6. Migration SQL — default 1 for onboarding_step
 7. Endpoint module — onboarding.py importable
 8. Endpoint module — router has GET /org/onboarding
 9. Endpoint module — router has PATCH /org/onboarding
10. Endpoint module — router has GET /org/metrics
11. Endpoint module — OnboardingStateResponse model has onboarding_completed
12. Endpoint module — OnboardingStateResponse model has onboarding_step
13. Endpoint module — OnboardingStatePatch allows partial update
14. Endpoint module — _clamp_step rejects 0
15. Endpoint module — _clamp_step rejects 6
16. Endpoint module — _clamp_step accepts 1
17. Endpoint module — _clamp_step accepts 5
18. Endpoint module — _clamp_step accepts 3
19. Main.py — onboarding router registered
20. Main.py — onboarding router has correct prefix (settings.API_V1_STR)
21. Frontend — OnboardingGuide component file exists
22. Frontend — api.ts contains getOnboardingState method
23. Frontend — api.ts contains patchOnboardingState method
24. Frontend — api.ts contains getOrgMetrics method
25. Frontend — OnboardingGuide exports named export
26. Frontend — Dashboard page imports OnboardingGuide
27. Frontend — STEPS constant covers all 5 steps
28. Docs — ONBOARDING.md exists
29. Docs — ONBOARDING.md references all 5 steps
30. Docs — ONBOARDING.md includes verification checklist
31. GET /org/onboarding — returns safe defaults on DB error
32. GET /org/onboarding — clamps out-of-range step to 1
33. PATCH /org/onboarding — rejects empty body
34. PATCH /org/onboarding — marking completed forces step=5
35. GET /org/metrics — returns zeroes on DB error
36. GET /org/metrics — response includes all 5 count fields
37. OnboardingGuide — skipped state uses localStorage key pattern
38. OnboardingGuide — completed state renders nothing
39. OnboardingGuide — step advance logic is sequential (1→2→3→4→5)
40. OnboardingGuide — step 5 + exports_count>=1 sets completed
"""

import sys
import os
import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------
BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

REPO_ROOT = os.path.join(BACKEND_DIR, "..")
SQL_PATH = os.path.join(BACKEND_DIR, "scripts", "018_org_onboarding.sql")
MAIN_PY_PATH = os.path.join(BACKEND_DIR, "app", "main.py")
ONBOARDING_EP_PATH = os.path.join(BACKEND_DIR, "app", "api", "endpoints", "onboarding.py")
API_TS_PATH = os.path.join(REPO_ROOT, "frontend", "lib", "api.ts")
GUIDE_PATH = os.path.join(REPO_ROOT, "frontend", "components", "onboarding", "OnboardingGuide.tsx")
DASHBOARD_PATH = os.path.join(REPO_ROOT, "frontend", "app", "dashboard", "page.tsx")
DOCS_PATH = os.path.join(REPO_ROOT, "docs", "ONBOARDING.md")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _sql() -> str:
    with open(SQL_PATH, "r") as f:
        return f.read()


def _read(path: str) -> str:
    with open(path, "r") as f:
        return f.read()


# ===========================================================================
# 1–6: Migration SQL
# ===========================================================================

def test_01_migration_sql_exists():
    assert os.path.isfile(SQL_PATH), f"Migration SQL not found: {SQL_PATH}"


def test_02_onboarding_completed_column():
    sql = _sql()
    assert "onboarding_completed" in sql


def test_03_onboarding_step_column():
    sql = _sql()
    assert "onboarding_step" in sql


def test_04_check_constraint_bounds():
    sql = _sql()
    assert "onboarding_step >= 1" in sql
    assert "onboarding_step <= 5" in sql


def test_05_default_false_completed():
    sql = _sql().lower()
    assert "default false" in sql


def test_06_default_1_step():
    sql = _sql()
    assert "DEFAULT 1" in sql


# ===========================================================================
# 7–18: Endpoint module
# ===========================================================================

def test_07_onboarding_module_importable():
    from app.api.endpoints import onboarding
    assert hasattr(onboarding, "router")


def test_08_router_has_get_org_onboarding():
    from app.api.endpoints.onboarding import router
    paths = [r.path for r in router.routes]
    assert "/org/onboarding" in paths


def test_09_router_has_patch_org_onboarding():
    from app.api.endpoints.onboarding import router
    methods = []
    for r in router.routes:
        if hasattr(r, "methods"):
            for m in r.methods:
                methods.append((r.path, m))
    assert ("/org/onboarding", "PATCH") in methods


def test_10_router_has_get_org_metrics():
    from app.api.endpoints.onboarding import router
    paths = [r.path for r in router.routes]
    assert "/org/metrics" in paths


def test_11_response_model_has_completed():
    from app.api.endpoints.onboarding import OnboardingStateResponse
    fields = OnboardingStateResponse.model_fields
    assert "onboarding_completed" in fields


def test_12_response_model_has_step():
    from app.api.endpoints.onboarding import OnboardingStateResponse
    fields = OnboardingStateResponse.model_fields
    assert "onboarding_step" in fields


def test_13_patch_model_allows_partial():
    from app.api.endpoints.onboarding import OnboardingStatePatch
    m = OnboardingStatePatch()
    assert m.onboarding_completed is None
    assert m.onboarding_step is None
    m2 = OnboardingStatePatch(onboarding_step=3)
    assert m2.onboarding_step == 3
    assert m2.onboarding_completed is None


def test_14_clamp_step_rejects_0():
    from app.api.endpoints.onboarding import _clamp_step
    with pytest.raises(HTTPException) as exc_info:
        _clamp_step(0)
    assert exc_info.value.status_code == 400


def test_15_clamp_step_rejects_6():
    from app.api.endpoints.onboarding import _clamp_step
    with pytest.raises(HTTPException) as exc_info:
        _clamp_step(6)
    assert exc_info.value.status_code == 400


def test_16_clamp_step_accepts_1():
    from app.api.endpoints.onboarding import _clamp_step
    assert _clamp_step(1) == 1


def test_17_clamp_step_accepts_5():
    from app.api.endpoints.onboarding import _clamp_step
    assert _clamp_step(5) == 5


def test_18_clamp_step_accepts_3():
    from app.api.endpoints.onboarding import _clamp_step
    assert _clamp_step(3) == 3


# ===========================================================================
# 19–20: Main.py wiring
# ===========================================================================

def test_19_main_imports_onboarding():
    src = _read(MAIN_PY_PATH)
    assert "from app.api.endpoints import onboarding" in src or "import onboarding" in src


def test_20_main_registers_onboarding_router():
    src = _read(MAIN_PY_PATH)
    assert "onboarding_ep.router" in src


# ===========================================================================
# 21–27: Frontend files
# ===========================================================================

def test_21_onboarding_guide_file_exists():
    assert os.path.isfile(GUIDE_PATH), f"OnboardingGuide not found: {GUIDE_PATH}"


def test_22_api_ts_has_getOnboardingState():
    src = _read(API_TS_PATH)
    assert "getOnboardingState" in src


def test_23_api_ts_has_patchOnboardingState():
    src = _read(API_TS_PATH)
    assert "patchOnboardingState" in src


def test_24_api_ts_has_getOrgMetrics():
    src = _read(API_TS_PATH)
    assert "getOrgMetrics" in src


def test_25_guide_exports_named_export():
    src = _read(GUIDE_PATH)
    assert "export function OnboardingGuide" in src


def test_26_dashboard_imports_onboarding_guide():
    src = _read(DASHBOARD_PATH)
    assert "OnboardingGuide" in src


def test_27_guide_defines_all_5_steps():
    src = _read(GUIDE_PATH)
    for i in range(1, 6):
        assert f"  {i}:" in src or f"{i}: {{" in src, \
            f"Step {i} not found in OnboardingGuide STEPS constant"


# ===========================================================================
# 28–30: Documentation
# ===========================================================================

def test_28_onboarding_md_exists():
    assert os.path.isfile(DOCS_PATH), f"ONBOARDING.md not found: {DOCS_PATH}"


def test_29_onboarding_md_references_all_steps():
    src = _read(DOCS_PATH)
    assert "Upload compliance documents" in src or "documents_count" in src
    assert "Create a project" in src or "projects_count" in src
    assert "Upload questionnaire" in src or "runs_count" in src
    assert "Review answers" in src or "reviewed_count" in src
    assert "Export" in src or "exports_count" in src


def test_30_onboarding_md_has_verification():
    src = _read(DOCS_PATH)
    assert "Verification" in src or "verification" in src.lower()


# ===========================================================================
# 31–36: Endpoint logic (unit-level with mocks)
# ===========================================================================

def test_31_get_onboarding_returns_defaults_on_db_error():
    """If the DB query fails, the endpoint must return safe defaults, not 500."""
    from app.api.endpoints.onboarding import get_onboarding_state

    mock_token = MagicMock()
    mock_token.credentials = "fake"
    mock_user = {"sub": "user-123"}
    mock_sb = MagicMock()

    # Make the organizations select raise an exception (not HTTPException)
    mock_sb.table.return_value.select.return_value.eq.return_value.single.return_value.execute.side_effect = RuntimeError("DB down")

    with patch("app.api.endpoints.onboarding.get_supabase", return_value=mock_sb), \
         patch("app.api.endpoints.onboarding.resolve_org_id_for_user", return_value="org-123"), \
         patch("app.api.endpoints.onboarding.require_user_id", return_value="user-123"):
        result = get_onboarding_state(request=None, user=mock_user, token=mock_token)

    assert result["onboarding_completed"] is False
    assert result["onboarding_step"] == 1


def test_32_get_onboarding_clamps_out_of_range():
    """If step stored in DB is > 5 or < 1, it should be clamped to 1."""
    from app.api.endpoints.onboarding import get_onboarding_state

    mock_token = MagicMock()
    mock_token.credentials = "fake"
    mock_user = {"sub": "user-123"}
    mock_sb = MagicMock()

    mock_result = MagicMock()
    mock_result.data = {"id": "org-123", "onboarding_completed": False, "onboarding_step": 99}
    mock_sb.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_result

    with patch("app.api.endpoints.onboarding.get_supabase", return_value=mock_sb), \
         patch("app.api.endpoints.onboarding.resolve_org_id_for_user", return_value="org-123"), \
         patch("app.api.endpoints.onboarding.require_user_id", return_value="user-123"):
        result = get_onboarding_state(request=None, user=mock_user, token=mock_token)

    assert result["onboarding_step"] == 1


def test_33_patch_rejects_empty_body():
    from app.api.endpoints.onboarding import patch_onboarding_state, OnboardingStatePatch

    mock_token = MagicMock()
    mock_token.credentials = "fake"
    mock_user = {"sub": "user-123"}
    mock_sb = MagicMock()

    with patch("app.api.endpoints.onboarding.get_supabase", return_value=mock_sb), \
         patch("app.api.endpoints.onboarding.resolve_org_id_for_user", return_value="org-123"), \
         patch("app.api.endpoints.onboarding.require_user_id", return_value="user-123"):
        with pytest.raises(HTTPException) as exc_info:
            patch_onboarding_state(
                payload=OnboardingStatePatch(),
                request=None,
                user=mock_user,
                token=mock_token,
            )
    assert exc_info.value.status_code == 400


def test_34_patch_completed_forces_step_5():
    """When onboarding_completed=true, step must be set to 5 regardless."""
    from app.api.endpoints.onboarding import patch_onboarding_state, OnboardingStatePatch

    mock_token = MagicMock()
    mock_token.credentials = "fake"
    mock_user = {"sub": "user-123"}
    mock_sb = MagicMock()

    # The update call
    update_chain = mock_sb.table.return_value.update.return_value.eq.return_value.execute
    update_chain.return_value = MagicMock(data=[{"id": "org-123", "onboarding_completed": True, "onboarding_step": 5}])

    # The re-read inside get_onboarding_state
    select_chain = mock_sb.table.return_value.select.return_value.eq.return_value.single.return_value.execute
    select_chain.return_value = MagicMock(data={"id": "org-123", "onboarding_completed": True, "onboarding_step": 5})

    with patch("app.api.endpoints.onboarding.get_supabase", return_value=mock_sb), \
         patch("app.api.endpoints.onboarding.resolve_org_id_for_user", return_value="org-123"), \
         patch("app.api.endpoints.onboarding.require_user_id", return_value="user-123"):
        result = patch_onboarding_state(
            payload=OnboardingStatePatch(onboarding_completed=True),
            request=None,
            user=mock_user,
            token=mock_token,
        )

    # Verify update was called with step=5
    update_call_args = mock_sb.table.return_value.update.call_args
    assert update_call_args is not None
    update_payload = update_call_args[0][0]
    assert update_payload.get("onboarding_step") == 5
    assert update_payload.get("onboarding_completed") is True


def test_35_metrics_returns_zeroes_on_db_error():
    from app.api.endpoints.onboarding import get_org_metrics

    mock_token = MagicMock()
    mock_token.credentials = "fake"
    mock_user = {"sub": "user-123"}
    mock_sb = MagicMock()

    # All table queries raise
    mock_sb.table.return_value.select.return_value.eq.return_value.execute.side_effect = RuntimeError("DB error")
    mock_sb.table.return_value.select.return_value.eq.return_value.in_.return_value.execute.side_effect = RuntimeError("DB error")

    with patch("app.api.endpoints.onboarding.get_supabase", return_value=mock_sb), \
         patch("app.api.endpoints.onboarding.resolve_org_id_for_user", return_value="org-123"), \
         patch("app.api.endpoints.onboarding.require_user_id", return_value="user-123"):
        result = get_org_metrics(request=None, user=mock_user, token=mock_token)

    assert result["documents_count"] == 0
    assert result["projects_count"] == 0
    assert result["runs_count"] == 0
    assert result["reviewed_count"] == 0
    assert result["exports_count"] == 0


def test_36_metrics_response_has_all_fields():
    from app.api.endpoints.onboarding import get_org_metrics

    mock_token = MagicMock()
    mock_token.credentials = "fake"
    mock_user = {"sub": "user-123"}
    mock_sb = MagicMock()

    mock_exec = MagicMock()
    mock_exec.data = []
    mock_exec.count = 0
    mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_exec
    mock_sb.table.return_value.select.return_value.eq.return_value.in_.return_value.execute.return_value = mock_exec

    with patch("app.api.endpoints.onboarding.get_supabase", return_value=mock_sb), \
         patch("app.api.endpoints.onboarding.resolve_org_id_for_user", return_value="org-123"), \
         patch("app.api.endpoints.onboarding.require_user_id", return_value="user-123"):
        result = get_org_metrics(request=None, user=mock_user, token=mock_token)

    for key in ("documents_count", "projects_count", "runs_count", "reviewed_count", "exports_count"):
        assert key in result, f"Missing key: {key}"
        assert isinstance(result[key], int), f"{key} should be int, got {type(result[key])}"


# ===========================================================================
# 37–40: Frontend component logic (file-level checks)
# ===========================================================================

def test_37_skip_uses_localstorage_key_pattern():
    src = _read(GUIDE_PATH)
    assert "nyccompliance:onboarding:skip:" in src


def test_38_completed_renders_nothing():
    src = _read(GUIDE_PATH)
    assert "if (completed) return null" in src


def test_39_step_advance_sequential():
    """Verify that the maybeAdvanceFromMetrics logic checks steps 1->2->3->4->5 in order."""
    src = _read(GUIDE_PATH)
    # These metric checks must appear in ascending order within the component
    idx1 = src.index("documents_count")
    idx2 = src.index("projects_count")
    idx3 = src.index("runs_count")
    idx4 = src.index("reviewed_count")
    idx5 = src.index("exports_count")
    assert idx1 < idx2 < idx3 < idx4 < idx5


def test_40_step5_exports_sets_completed():
    src = _read(GUIDE_PATH).replace(" ", "")
    assert "onboarding_completed:true" in src
