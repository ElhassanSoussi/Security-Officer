"""
Assistant Tests
================
Deterministic — no real DB / network calls.

1.  assistant.py endpoint file exists
2.  POST /message route registered (import)
3.  POST /message route is POST method (import)
4.  AssistantMessageRequest has message + org_id fields
5.  AssistantMessageResponse has conversation_id, reply, actions
6.  AssistantAction has label + href
7.  _REFUSAL_SNIPPETS is non-empty, contains "legal advice"
8.  Safety detector triggers on "legal advice" (import)
9.  Safety detector triggers on "attest" / "certify" / "guarantee"
10. Safety detector passes for normal question (import)
11. _log_assistant_event function exists
12. Log payload includes org_id, user_id, reply
13. Log payload does NOT include "token"
14. main.py imports assistant endpoint
15. main.py registers /assistant prefix
16. HTTPBearer auth present in assistant.py
17. _get_projects_summary filters by org_id
18. _get_billing_summary does not return raw stripe_customer_id
19. _get_usage_snapshot has documents_used, projects_used, runs_used
20. Frontend assistant page exists
21. Frontend page calls sendAssistantMessage
22. Frontend page has SUGGESTED_PROMPTS
23. Frontend page has new-conversation reset control
24. Sidebar has /assistant link + MessageSquare icon
25. api.ts has sendAssistantMessage posting to /assistant/message
"""

import os
import sys
import pytest

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------
BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

REPO_ROOT = os.path.join(BACKEND_DIR, "..")
FRONTEND_DIR = os.path.join(REPO_ROOT, "frontend")
ASSISTANT_SRC = os.path.join(BACKEND_DIR, "app", "api", "endpoints", "assistant.py")
MAIN_SRC      = os.path.join(BACKEND_DIR, "app", "main.py")
PAGE_SRC      = os.path.join(FRONTEND_DIR, "app", "assistant", "page.tsx")
SIDEBAR_SRC   = os.path.join(FRONTEND_DIR, "components", "layout", "Sidebar.tsx")
API_TS_SRC    = os.path.join(FRONTEND_DIR, "lib", "api.ts")


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


# ── File existence ────────────────────────────────────────────────────────────

class TestFileExists:
    def test_01_assistant_endpoint_file_exists(self):
        assert os.path.isfile(ASSISTANT_SRC)

    def test_20_frontend_page_exists(self):
        assert os.path.isfile(PAGE_SRC)


# ── Route registration (import-based) ────────────────────────────────────────

class TestAssistantRouteRegistered:
    def test_02_route_exists(self):
        from app.api.endpoints.assistant import router
        paths = [route.path for route in router.routes]
        assert "/message" in paths

    def test_03_route_is_post(self):
        from app.api.endpoints.assistant import router
        for route in router.routes:
            if getattr(route, "path", None) == "/message":
                assert "POST" in route.methods
                return
        pytest.fail("/message POST route not found")


# ── Models (source-level) ─────────────────────────────────────────────────────

class TestAssistantModels:
    def test_04_request_model_fields(self):
        src = _read(ASSISTANT_SRC)
        assert "AssistantMessageRequest" in src
        assert "message" in src
        assert "org_id" in src

    def test_05_response_model_fields(self):
        src = _read(ASSISTANT_SRC)
        assert "AssistantMessageResponse" in src
        assert "conversation_id" in src
        assert "reply" in src
        assert "actions" in src

    def test_06_action_model_label_href(self):
        src = _read(ASSISTANT_SRC)
        assert "AssistantAction" in src
        assert "label" in src
        assert "href" in src


# ── Safety refusal ────────────────────────────────────────────────────────────

class TestAssistantSafety:
    def test_07_refusal_snippets_present(self):
        src = _read(ASSISTANT_SRC)
        assert "_REFUSAL_SNIPPETS" in src
        assert '"legal advice"' in src

    def test_08_detector_triggers_legal_advice(self):
        from app.api.endpoints.assistant import _is_legal_or_attestation_request
        assert _is_legal_or_attestation_request("Can you give me legal advice?")

    def test_09_detector_triggers_attest_certify_guarantee(self):
        from app.api.endpoints.assistant import _is_legal_or_attestation_request
        assert _is_legal_or_attestation_request("Can you attest we are compliant?")
        assert _is_legal_or_attestation_request("certify our controls")
        assert _is_legal_or_attestation_request("guarantee this is compliant")

    def test_10_detector_passes_normal_question(self):
        from app.api.endpoints.assistant import _is_legal_or_attestation_request
        assert not _is_legal_or_attestation_request("How do I start a run?")
        assert not _is_legal_or_attestation_request("Show me my usage")


# ── Logging ───────────────────────────────────────────────────────────────────

class TestAssistantLogging:
    def test_11_log_function_exists(self):
        assert "_log_assistant_event" in _read(ASSISTANT_SRC)

    def test_12_log_includes_org_user_reply(self):
        src = _read(ASSISTANT_SRC)
        assert '"org_id"' in src
        assert '"user_id"' in src
        assert '"reply"' in src

    def test_13_log_excludes_token(self):
        src = _read(ASSISTANT_SRC)
        log_start = src.find("def _log_assistant_event")
        snippet = src[log_start:log_start + 600]
        assert '"token"' not in snippet


# ── main.py registration ──────────────────────────────────────────────────────

class TestMainRegistration:
    def test_14_assistant_imported_in_main(self):
        assert "assistant" in _read(MAIN_SRC)

    def test_15_assistant_prefix_registered(self):
        assert "/assistant" in _read(MAIN_SRC)

    def test_16_bearer_auth_in_endpoint(self):
        assert "HTTPBearer" in _read(ASSISTANT_SRC)


# ── Org-scoped helpers ────────────────────────────────────────────────────────

class TestOrgScopedHelpers:
    def test_17_projects_summary_scoped_by_org_id(self):
        src = _read(ASSISTANT_SRC)
        assert "_get_projects_summary" in src
        assert '.eq("org_id", org_id)' in src

    def test_18_billing_summary_no_raw_stripe_customer_id(self):
        src = _read(ASSISTANT_SRC)
        helper_start = src.find("async def _get_billing_summary")
        # Find end of function (next top-level async def or end of file)
        helper_end = src.find("\nasync def ", helper_start + 1)
        helper_src = src[helper_start:] if helper_end == -1 else src[helper_start:helper_end]
        # It may query stripe_customer_id but must not expose it raw (must wrap in bool())
        if '"stripe_customer_id"' in helper_src:
            assert "bool(" in helper_src

    def test_19_usage_snapshot_keys(self):
        src = _read(ASSISTANT_SRC)
        assert "_get_usage_snapshot" in src
        assert "documents_used" in src
        assert "projects_used" in src
        assert "runs_used" in src


# ── Frontend page ─────────────────────────────────────────────────────────────

class TestFrontendAssistantPage:
    def test_21_page_calls_send_assistant_message(self):
        assert "sendAssistantMessage" in _read(PAGE_SRC)

    def test_22_page_has_suggested_prompts(self):
        assert "SUGGESTED_PROMPTS" in _read(PAGE_SRC)

    def test_23_page_has_reset_control(self):
        src = _read(PAGE_SRC)
        assert "New conversation" in src or "RotateCcw" in src


# ── Sidebar ───────────────────────────────────────────────────────────────────

class TestSidebarAssistantLink:
    def test_24a_sidebar_has_assistant_link(self):
        assert "/assistant" in _read(SIDEBAR_SRC)

    def test_24b_sidebar_has_message_square_icon(self):
        assert "MessageSquare" in _read(SIDEBAR_SRC)


# ── API client ────────────────────────────────────────────────────────────────

class TestApiClientAssistant:
    def test_25a_api_ts_has_method(self):
        assert "sendAssistantMessage" in _read(API_TS_SRC)

    def test_25b_api_ts_correct_path(self):
        assert "/assistant/message" in _read(API_TS_SRC)

    def test_25c_return_type_includes_conversation_id(self):
        src = _read(API_TS_SRC)
        idx = src.find("sendAssistantMessage")
        snippet = src[idx:idx + 600]
        assert "conversation_id" in snippet
