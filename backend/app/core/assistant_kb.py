"""
assistant_kb — Knowledge Base loader and intent classifier for the in-app assistant.

The KB is loaded once at import time from /backend/kb/*.md files.
If any file is missing the system still starts; that topic returns an empty string.
No external network calls are made.
"""
from __future__ import annotations

import os
import re
import logging
from typing import Dict

logger = logging.getLogger("api.assistant.kb")

# ── KB paths ─────────────────────────────────────────────────────────────────

_KB_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "kb")
_KB_DIR = os.path.normpath(_KB_DIR)

_KB_FILES: Dict[str, str] = {
    "getting_started": "getting_started.md",
    "documents":       "documents.md",
    "projects":        "projects.md",
    "runs":            "runs.md",
    "audit_review":    "audit_review.md",
    "exports":         "exports.md",
    "plans_billing":   "plans_billing.md",
    "troubleshooting": "troubleshooting.md",
}

# Cache: topic -> full text (empty string if file missing)
_KB_CACHE: Dict[str, str] = {}


def _load_kb() -> None:
    for topic, filename in _KB_FILES.items():
        path = os.path.join(_KB_DIR, filename)
        try:
            with open(path, encoding="utf-8") as f:
                _KB_CACHE[topic] = f.read()
        except FileNotFoundError:
            logger.warning("KB file missing: %s — topic '%s' will return empty.", path, topic)
            _KB_CACHE[topic] = ""
        except Exception as exc:
            logger.error("KB load error for '%s': %s", topic, exc)
            _KB_CACHE[topic] = ""


_load_kb()


def get_kb(topic: str) -> str:
    """Return the cached KB text for a topic, or empty string."""
    return _KB_CACHE.get(topic, "")


def get_all_kb() -> Dict[str, str]:
    """Return the full KB cache dict."""
    return dict(_KB_CACHE)


# ── Intent classifier ────────────────────────────────────────────────────────
#
# Deterministic keyword/rule-based classifier.
# Returns one of the canonical intent labels defined in INTENTS.

INTENTS = (
    "legal_attestation",
    "plan_limits",
    "status",
    "how_to",
    "navigation",
    "troubleshooting",
    "unknown",
)

_LEGAL_ATTESTATION_TERMS = (
    "legal advice", "lawyer", "attest", "attestation",
    "certify", "certification", "guarantee", "guaranteed",
    "compliance opinion", "is this compliant", "will we pass",
    "pass the audit", "sign off", "sign-off",
)

_PLAN_LIMITS_TERMS = (
    "limit", "limits", "quota", "blocked", "can't upload", "cannot upload",
    "can't run", "cannot run", "upgrade", "out of", "exceeded", "max",
    "storage full", "plan includes", "what does my plan", "how many",
    "how much", "remaining", "runs left", "exports left",
)

_STATUS_TERMS = (
    "my plan", "current plan", "my usage", "my subscription", "my status",
    "my runs", "my projects", "my documents", "how many runs", "how many docs",
    "show me my", "what is my plan", "plan status",
)

_HOW_TO_TERMS = (
    "how do i", "how to", "how can i", "how should i", "steps to",
    "what steps", "walk me through", "help me", "guide me",
    "what is the process", "how does",
)

_NAVIGATION_TERMS = (
    "where is", "where do i find", "where can i", "take me to",
    "navigate to", "go to", "find the", "show me the", "open the",
    "link to", "page for",
)

_TROUBLESHOOTING_TERMS = (
    "error", "not working", "broken", "bug", "stuck", "failed", "fail",
    "problem", "issue", "wrong", "unexpected", "can't", "cannot",
    "doesn't work", "wont", "won't", "keeps", "why is it", "why does",
    "help me fix", "something went wrong",
)


def classify_intent(message: str) -> str:
    """
    Classify a user message into one of the INTENTS labels.
    Rules are evaluated in priority order; first match wins.
    """
    t = (message or "").lower()

    # Priority 1: legal / attestation — always refuse
    if any(term in t for term in _LEGAL_ATTESTATION_TERMS):
        return "legal_attestation"

    # Priority 2: plan limits / quota / upgrade
    if any(term in t for term in _PLAN_LIMITS_TERMS):
        return "plan_limits"

    # Priority 3: status queries (my plan, my usage)
    if any(term in t for term in _STATUS_TERMS):
        return "status"

    # Priority 4: troubleshooting (before how_to so errors get specific replies)
    if any(term in t for term in _TROUBLESHOOTING_TERMS):
        return "troubleshooting"

    # Priority 5: how-to
    if any(term in t for term in _HOW_TO_TERMS):
        return "how_to"

    # Priority 6: navigation
    if any(term in t for term in _NAVIGATION_TERMS):
        return "navigation"

    return "unknown"


def pick_kb_topics(intent: str, message: str) -> list[str]:
    """
    Return the ordered list of KB topic keys most relevant for the intent + message.
    Used to assemble context for the response builder.
    """
    t = message.lower()

    base: list[str] = []

    if intent == "plan_limits":
        base = ["plans_billing"]
    elif intent == "status":
        base = ["plans_billing"]
    elif intent == "troubleshooting":
        base = ["troubleshooting"]
    elif intent in ("how_to", "navigation", "unknown"):
        # Pick by keyword match in message
        if any(w in t for w in ("document", "upload", "file", "pdf", "docx")):
            base.append("documents")
        if any(w in t for w in ("project", "workspace")):
            base.append("projects")
        if any(w in t for w in ("run", "questionnaire", "question", "answer")):
            base.append("runs")
        if any(w in t for w in ("export", "download", "excel", "report")):
            base.append("exports")
        if any(w in t for w in ("audit", "log", "history", "track")):
            base.append("audit_review")
        if any(w in t for w in ("plan", "billing", "payment", "invoice", "subscription")):
            base.append("plans_billing")
        if any(w in t for w in ("start", "begin", "first", "setup", "onboard", "invite", "team")):
            base.append("getting_started")
        if not base:
            base = ["getting_started"]

    return base
