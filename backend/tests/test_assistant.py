"""
Assistant Tests (upgraded)
===========================
Deterministic — no real DB / network calls.

Coverage:
 1–2.  File existence (assistant.py, assistant_kb.py, frontend page)
 3–4.  Route registration (import-based)
 5–6.  Models: request + response + action fields
 7–13. Safety refusal (source-level + import-level)
 14–16. Logging: fields present, token excluded, intent logged
 17–18. main.py registration + bearer auth
 19–21. Org-scoped helpers: projects scoped, billing safe, usage keys
 22–25. New helpers: _get_onboarding_state, _get_recent_runs defined + org-scoped
 26–35. Intent classifier (assistant_kb): all intents, edge cases
 36–40. KB loader: all 8 files present, get_kb returns str, pick_kb_topics works
 41–44. Frontend page: HELP_TOPICS, SUGGESTED_PROMPTS, CopyButton, topic buttons
 45–46. Sidebar + api.ts wiring unchanged
"""

import os
import sys
import importlib
import importlib.util
import pytest

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------
BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

REPO_ROOT    = os.path.join(BACKEND_DIR, "..")
FRONTEND_DIR = os.path.join(REPO_ROOT, "frontend")

ASSISTANT_SRC  = os.path.join(BACKEND_DIR, "app", "api", "endpoints", "assistant.py")
KB_MODULE_SRC  = os.path.join(BACKEND_DIR, "app", "core", "assistant_kb.py")
MAIN_SRC       = os.path.join(BACKEND_DIR, "app", "main.py")
PAGE_SRC       = os.path.join(FRONTEND_DIR, "app", "assistant", "page.tsx")
SIDEBAR_SRC    = os.path.join(FRONTEND_DIR, "components", "layout", "Sidebar.tsx")
API_TS_SRC     = os.path.join(FRONTEND_DIR, "lib", "api.ts")
KB_DIR         = os.path.join(BACKEND_DIR, "kb")

_KB_FILES = [
    "getting_started.md", "documents.md", "projects.md", "runs.md",
    "audit_review.md", "exports.md", "plans_billing.md", "troubleshooting.md",
]


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


# ===========================================================================
# 1–2: File existence
# ===========================================================================

class TestFileExistence:
    def test_01_assistant_endpoint_exists(self):
        assert os.path.isfile(ASSISTANT_SRC)

    def test_01b_assistant_kb_module_exists(self):
        assert os.path.isfile(KB_MODULE_SRC)

    def test_02_frontend_page_exists(self):
        assert os.path.isfile(PAGE_SRC)


# ===========================================================================
# 3–4: Route registration
# ===========================================================================

class TestRouteRegistration:
    def test_03_message_route_exists(self):
        from app.api.endpoints.assistant import router
        paths = [r.path for r in router.routes]
        assert "/message" in paths

    def test_04_message_route_is_post(self):
        from app.api.endpoints.assistant import router
        for r in router.routes:
            if getattr(r, "path", None) == "/message":
                assert "POST" in r.methods
                return
        pytest.fail("/message POST route not found")


# ===========================================================================
# 5–6: Models
# ===========================================================================

class TestModels:
    def test_05_request_model_fields(self):
        src = _read(ASSISTANT_SRC)
        assert "AssistantMessageRequest" in src
        assert "message" in src and "org_id" in src

    def test_06_response_and_action_fields(self):
        src = _read(ASSISTANT_SRC)
        assert "AssistantMessageResponse" in src
        assert "conversation_id" in src and "reply" in src and "actions" in src
        assert "AssistantAction" in src
        assert "label" in src and "href" in src


# ===========================================================================
# 7–13: Safety refusal
# ===========================================================================

class TestSafetyRefusal:
    def test_07_refusal_snippets_in_source(self):
        src = _read(ASSISTANT_SRC)
        assert "_REFUSAL_SNIPPETS" in src
        assert '"legal advice"' in src

    def test_08_triggers_legal_advice(self):
        from app.api.endpoints.assistant import _is_legal_or_attestation_request
        assert _is_legal_or_attestation_request("Give me legal advice")

    def test_09_triggers_attest(self):
        from app.api.endpoints.assistant import _is_legal_or_attestation_request
        assert _is_legal_or_attestation_request("Can you attest we are compliant?")

    def test_10_triggers_certify(self):
        from app.api.endpoints.assistant import _is_legal_or_attestation_request
        assert _is_legal_or_attestation_request("certify our controls")

    def test_11_triggers_guarantee(self):
        from app.api.endpoints.assistant import _is_legal_or_attestation_request
        assert _is_legal_or_attestation_request("guarantee this is fine")

    def test_12_passes_normal_question(self):
        from app.api.endpoints.assistant import _is_legal_or_attestation_request
        assert not _is_legal_or_attestation_request("How do I start a run?")
        assert not _is_legal_or_attestation_request("Show me my usage")

    def test_13_refusal_fires_before_tool_calls_documented(self):
        # Confirm safety check is positioned before any await in the source.
        src = _read(ASSISTANT_SRC)
        safety_pos = src.find("_is_legal_or_attestation_request")
        first_await = src.find("await _get_billing_summary")
        assert safety_pos < first_await, "Safety check must run before tool calls"


# ===========================================================================
# 14–16: Logging
# ===========================================================================

class TestLogging:
    def test_14_log_function_exists(self):
        assert "_log" in _read(ASSISTANT_SRC) or "_log_assistant_event" in _read(ASSISTANT_SRC)

    def test_15_log_includes_required_fields(self):
        src = _read(ASSISTANT_SRC)
        for field in ('"org_id"', '"user_id"', '"reply"', '"intent"'):
            assert field in src, f"Log payload missing field: {field}"

    def test_16_log_excludes_token(self):
        src = _read(ASSISTANT_SRC)
        log_start = src.find("def _log(") 
        snippet = src[log_start:log_start + 700]
        assert '"token"' not in snippet


# ===========================================================================
# 17–18: main.py + auth
# ===========================================================================

class TestMainRegistration:
    def test_17_assistant_registered_in_main(self):
        src = _read(MAIN_SRC)
        assert "assistant" in src and "/assistant" in src

    def test_18_bearer_auth_present(self):
        assert "HTTPBearer" in _read(ASSISTANT_SRC)


# ===========================================================================
# 19–21: Original org-scoped helpers
# ===========================================================================

class TestOrgScopedHelpers:
    def test_19_projects_summary_org_scoped(self):
        src = _read(ASSISTANT_SRC)
        assert "_get_projects_summary" in src
        assert '.eq("org_id", org_id)' in src

    def test_20_billing_summary_no_raw_stripe_id(self):
        src = _read(ASSISTANT_SRC)
        start = src.find("async def _get_billing_summary")
        end = src.find("\nasync def ", start + 1)
        snippet = src[start:] if end == -1 else src[start:end]
        if '"stripe_customer_id"' in snippet:
            assert "bool(" in snippet

    def test_21_usage_snapshot_keys_present(self):
        src = _read(ASSISTANT_SRC)
        assert "documents_used" in src
        assert "projects_used" in src
        assert "runs_used" in src


# ===========================================================================
# 22–25: New helpers
# ===========================================================================

class TestNewHelpers:
    def test_22_get_onboarding_state_exists(self):
        assert "_get_onboarding_state" in _read(ASSISTANT_SRC)

    def test_23_get_onboarding_state_org_scoped(self):
        src = _read(ASSISTANT_SRC)
        start = src.find("async def _get_onboarding_state")
        end = src.find("\nasync def ", start + 1)
        snippet = src[start:] if end == -1 else src[start:end]
        assert "org_id" in snippet

    def test_24_get_recent_runs_exists(self):
        assert "_get_recent_runs" in _read(ASSISTANT_SRC)

    def test_25_get_recent_runs_org_scoped(self):
        src = _read(ASSISTANT_SRC)
        start = src.find("async def _get_recent_runs")
        end = src.find("\nasync def ", start + 1)
        snippet = src[start:] if end == -1 else src[start:end]
        assert ".eq(\"org_id\", org_id)" in snippet


# ===========================================================================
# 26–35: Intent classifier (assistant_kb)
# ===========================================================================

class TestIntentClassifier:
    def setup_method(self):
        from app.core.assistant_kb import classify_intent
        self.classify = classify_intent

    def test_26_legal_attestation_intent(self):
        assert self.classify("Can you attest we are compliant?") == "legal_attestation"

    def test_27_plan_limits_intent(self):
        assert self.classify("I've hit my limit, can't upload") == "plan_limits"

    def test_28_plan_limits_upgrade(self):
        assert self.classify("How do I upgrade my plan?") == "plan_limits"

    def test_29_status_intent(self):
        assert self.classify("What is my current plan?") == "status"

    def test_30_status_my_usage(self):
        assert self.classify("Show me my usage") == "status"

    def test_31_troubleshooting_intent(self):
        assert self.classify("I'm getting an error uploading") == "troubleshooting"

    def test_32_how_to_intent(self):
        assert self.classify("How do I start a run?") == "how_to"

    def test_33_navigation_intent(self):
        assert self.classify("Where is the audit log?") == "navigation"

    def test_34_legal_takes_priority_over_how_to(self):
        # "how do I certify" — legal_attestation wins over how_to
        assert self.classify("how do I certify our controls?") == "legal_attestation"

    def test_35_unknown_fallback(self):
        result = self.classify("hello")
        assert result in ("unknown", "how_to", "navigation")  # benign fallback


# ===========================================================================
# 36–40: KB loader
# ===========================================================================

class TestKBLoader:
    def test_36_all_kb_files_present(self):
        for fname in _KB_FILES:
            path = os.path.join(KB_DIR, fname)
            assert os.path.isfile(path), f"KB file missing: {fname}"

    def test_37_get_kb_returns_string(self):
        from app.core.assistant_kb import get_kb
        result = get_kb("getting_started")
        assert isinstance(result, str) and len(result) > 0

    def test_38_get_kb_unknown_topic_returns_empty(self):
        from app.core.assistant_kb import get_kb
        assert get_kb("nonexistent_topic_xyz") == ""

    def test_39_pick_kb_topics_plan_limits(self):
        from app.core.assistant_kb import pick_kb_topics
        topics = pick_kb_topics("plan_limits", "I hit my limit")
        assert "plans_billing" in topics

    def test_40_pick_kb_topics_how_to_run(self):
        from app.core.assistant_kb import pick_kb_topics
        topics = pick_kb_topics("how_to", "How do I start a run?")
        assert "runs" in topics


# ===========================================================================
# 41–44: Frontend page upgrades
# ===========================================================================

class TestFrontendPageUpgrades:
    def test_41_help_topics_defined(self):
        assert "HELP_TOPICS" in _read(PAGE_SRC)

    def test_42_copy_button_present(self):
        src = _read(PAGE_SRC)
        assert "CopyButton" in src or "Copy" in src

    def test_43_topic_buttons_rendered(self):
        src = _read(PAGE_SRC)
        assert "HELP_TOPICS" in src
        # Topics bar renders each topic label
        assert "Getting Started" in src

    def test_44_suggested_prompts_updated(self):
        src = _read(PAGE_SRC)
        assert "SUGGESTED_PROMPTS" in src
        assert "blocked" in src.lower() or "upload" in src.lower()


# ===========================================================================
# 45–46: Sidebar + api.ts unchanged
# ===========================================================================

class TestSidebarAndApiClient:
    def test_45_sidebar_still_has_assistant_link(self):
        assert "/assistant" in _read(SIDEBAR_SRC)

    def test_46_api_ts_posts_to_assistant_message(self):
        assert "/assistant/message" in _read(API_TS_SRC)
