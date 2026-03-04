"""
assistant.py — In-app AI Assistant endpoint.

Scope: platform guidance only.
- No access to uploaded document content.
- Hard refusal for legal/attestation questions.
- Deterministic intent routing before response generation.
- All tool helpers are strictly org-scoped.
"""
from __future__ import annotations

import json
import logging
import textwrap
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from app.core.auth import get_current_user, require_user_id
from app.core.database import get_supabase
from app.core.org_context import resolve_org_id_for_user
from app.core.assistant_kb import classify_intent, pick_kb_topics, get_kb
from app.core.audit_events import log_audit_event

logger = logging.getLogger("api.assistant")
router = APIRouter()
security = HTTPBearer()


# ── Models ───────────────────────────────────────────────────────────────────

class AssistantMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    org_id: str
    conversation_id: Optional[str] = None


class AssistantAction(BaseModel):
    label: str
    href: str


class AssistantMessageResponse(BaseModel):
    conversation_id: str
    reply: str
    actions: List[AssistantAction] = []
    intent: str = "unknown"


# ── Safety refusal (fast-path — fires before any tool calls) ──────────────────

_REFUSAL_SNIPPETS = (
    "legal advice", "lawyer", "attest", "attestation",
    "certify", "certification", "guarantee", "guaranteed",
    "compliant", "compliance opinion", "is this compliant",
    "will we pass", "pass the audit", "sign off", "sign-off",
)


def _is_legal_or_attestation_request(text: str) -> bool:
    t = (text or "").lower()
    return any(s in t for s in _REFUSAL_SNIPPETS)


def _refusal_reply() -> str:
    return (
        "I can't help with legal advice or audit attestation. "
        "I can help you use the platform to track work, collect evidence, "
        "and prepare outputs for your own review."
    )


# ── Org-scoped tool helpers (no document content access) ─────────────────────

async def _get_billing_summary(sb, org_id: str) -> Dict[str, Any]:
    try:
        res = sb.table("organizations").select(
            "plan, plan_tier, subscription_status, current_period_end, stripe_customer_id"
        ).eq("id", org_id).single().execute()
        row = res.data or {}
    except Exception:
        row = {}
    raw_plan = (row.get("plan") or row.get("plan_tier") or "starter").strip().lower()
    status = (row.get("subscription_status") or "trialing").strip().lower()
    return {
        "plan": raw_plan,
        "subscription_status": status,
        "current_period_end": row.get("current_period_end"),
        "has_stripe": bool(row.get("stripe_customer_id")),
    }


async def _get_usage_snapshot(sb, org_id: str) -> Dict[str, Any]:
    from app.core.plan_service import PlanService, Plan, _current_month_start

    try:
        org_row = sb.table("organizations").select("plan, plan_tier").eq("id", org_id).single().execute()
        raw_plan = ((org_row.data or {}).get("plan") or (org_row.data or {}).get("plan_tier") or "starter").strip().lower()
    except Exception:
        raw_plan = "starter"

    try:
        plan_enum = Plan(raw_plan)
    except ValueError:
        plan_enum = Plan.STARTER

    limits = PlanService.get_limits(plan_enum)
    month_start = _current_month_start()

    def _safe_count(table: str, monthly: bool = False) -> int:
        try:
            q = sb.table(table).select("id", count="exact").eq("org_id", org_id)
            if monthly:
                q = q.gte("created_at", month_start)
            r = q.execute()
            return r.count if r.count is not None else 0
        except Exception:
            return 0

    return {
        "documents_used": _safe_count("documents"),
        "documents_limit": None if plan_enum == Plan.ELITE else limits.get("max_documents"),
        "projects_used": _safe_count("projects"),
        "projects_limit": None if plan_enum == Plan.ELITE else limits.get("max_projects"),
        "runs_used": _safe_count("runs", monthly=True),
        "runs_limit": None if plan_enum == Plan.ELITE else limits.get("max_runs_per_month"),
        "plan": plan_enum.value,
    }


async def _get_projects_summary(sb, org_id: str) -> Dict[str, Any]:
    try:
        res = sb.table("projects").select("id, name, created_at").eq("org_id", org_id).order("created_at", desc=True).limit(5).execute()
        items = res.data or []
        count_res = sb.table("projects").select("id", count="exact").eq("org_id", org_id).execute()
        total = count_res.count if count_res.count is not None else len(count_res.data or [])
    except Exception:
        items, total = [], 0
    return {
        "count": total,
        "recent": [{"id": p["id"], "name": p.get("name"), "created_at": p.get("created_at")} for p in items],
    }


async def _get_onboarding_state(sb, org_id: str) -> Dict[str, Any]:
    try:
        res = sb.table("organizations").select("onboarding_completed, onboarding_step").eq("id", org_id).single().execute()
        row = res.data or {}
        return {
            "completed": bool(row.get("onboarding_completed", False)),
            "step": int(row.get("onboarding_step") or 1),
        }
    except Exception:
        return {"completed": False, "step": 1}


async def _get_recent_runs(sb, org_id: str) -> Dict[str, Any]:
    try:
        res = sb.table("runs").select(
            "id, status, created_at, export_count"
        ).eq("org_id", org_id).order("created_at", desc=True).limit(5).execute()
        runs = [
            {
                "id": r["id"],
                "status": r.get("status"),
                "created_at": r.get("created_at"),
                "export_count": r.get("export_count", 0),
            }
            for r in (res.data or [])
        ]
    except Exception:
        runs = []
    return {"runs": runs, "count": len(runs)}


# ── Response builders (one per intent) ───────────────────────────────────────

def _fmt_limit(val: Any) -> str:
    return "Unlimited" if val is None else str(val)


_KB_TOPIC_ROUTES: Dict[str, tuple] = {
    "getting_started": ("Getting Started", "/dashboard"),
    "documents":       ("Documents", "/projects"),
    "projects":        ("Projects", "/projects"),
    "runs":            ("Runs", "/runs"),
    "audit_review":    ("Audit Review", "/audit"),
    "activity_log":    ("Activity Log", "/activity"),
    "exports":         ("Runs & Exports", "/runs"),
    "plans_billing":   ("Plans & Billing", "/settings/billing"),
    "troubleshooting": ("Plans & Billing", "/settings/billing"),
}


def _actions_for_kb_topics(topics: List[str]) -> List[AssistantAction]:
    seen: set = set()
    out: List[AssistantAction] = []
    for t in topics:
        if t in _KB_TOPIC_ROUTES:
            label, href = _KB_TOPIC_ROUTES[t]
            if href not in seen:
                seen.add(href)
                out.append(AssistantAction(label=label, href=href))
    return out[:3]


def _build_status_reply(billing: Dict, usage: Dict, projects: Dict, onboarding: Dict, recent_runs: Dict) -> tuple:
    plan = billing.get("plan", "starter").title()
    status = billing.get("subscription_status", "unknown").replace("_", " ").title()
    period_end = billing.get("current_period_end")
    renews = ""
    if period_end:
        try:
            renews = f"\n- **Renews:** {datetime.fromisoformat(period_end.replace('Z', '+00:00')).strftime('%B %d, %Y')}"
        except Exception:
            pass

    reply = textwrap.dedent(f"""
        Here's your organization's current status:

        **Plan:** {plan} (status: {status}){renews}

        **Usage this period:**
        - Documents: **{usage.get('documents_used', 0)}** / {_fmt_limit(usage.get('documents_limit'))}
        - Projects: **{usage.get('projects_used', 0)}** / {_fmt_limit(usage.get('projects_limit'))}
        - Runs this month: **{usage.get('runs_used', 0)}** / {_fmt_limit(usage.get('runs_limit'))}

        **Activity:**
        - Total projects: **{projects.get('count', 0)}**
        - Recent runs visible: **{recent_runs.get('count', 0)}**

        Let me know if you want to dig into any of these or take action.
    """).strip()

    return reply, [
        AssistantAction(label="Plans & Billing", href="/settings/billing"),
        AssistantAction(label="Projects", href="/projects"),
        AssistantAction(label="Runs", href="/runs"),
    ]


def _build_plan_limits_reply(billing: Dict, usage: Dict) -> tuple:
    plan = billing.get("plan", "starter").title()
    docs_used, docs_lim = usage.get("documents_used", 0), usage.get("documents_limit")
    runs_used, runs_lim = usage.get("runs_used", 0), usage.get("runs_limit")
    proj_used, proj_lim = usage.get("projects_used", 0), usage.get("projects_limit")

    at_limit = []
    if docs_lim is not None and docs_used >= docs_lim:
        at_limit.append(f"Documents ({docs_used}/{docs_lim})")
    if runs_lim is not None and runs_used >= runs_lim:
        at_limit.append(f"Runs this month ({runs_used}/{runs_lim})")
    if proj_lim is not None and proj_used >= proj_lim:
        at_limit.append(f"Projects ({proj_used}/{proj_lim})")

    limits_line = (
        "You've reached your limit on: **" + "**, **".join(at_limit) + "**."
        if at_limit
        else "You haven't hit any hard limits yet, but you may be approaching them."
    )

    reply = textwrap.dedent(f"""
        You're on the **{plan}** plan. {limits_line}

        **Current usage:**
        - Documents: {docs_used} / {_fmt_limit(docs_lim)}
        - Runs this month: {runs_used} / {_fmt_limit(runs_lim)}
        - Projects: {proj_used} / {_fmt_limit(proj_lim)}

        To increase your limits, upgrade your plan. Run limits reset on the 1st of each month.
    """).strip()

    return reply, [
        AssistantAction(label="Plans & Billing", href="/settings/billing"),
        AssistantAction(label="Upgrade Plan", href="/plans"),
    ]


def _build_how_to_reply(message: str, kb_topics: List[str]) -> tuple:
    kb_text = "\n\n".join(get_kb(t) for t in kb_topics if get_kb(t)).strip()
    if kb_text:
        if "## Steps" in kb_text:
            steps_part = kb_text[kb_text.find("## Steps"):]
            nxt = steps_part.find("\n## ", 4)
            reply = (steps_part[:nxt] if nxt != -1 else steps_part[:900]).strip()
        else:
            reply = kb_text[:800].strip()
    else:
        reply = (
            "I'm not sure about the exact steps for that. "
            "Here are the main areas of the platform where you might find what you need:"
        )
    return reply, _actions_for_kb_topics(kb_topics)


def _build_navigation_reply(message: str, kb_topics: List[str]) -> tuple:
    actions = _actions_for_kb_topics(kb_topics)
    labels = [t.replace("_", " ").title() for t in kb_topics]
    reply = (
        f"Here are the relevant pages for **{', '.join(labels)}** — use the links below to go there directly."
        if labels
        else "Use the links below to navigate to the relevant section."
    )
    return reply, actions


def _build_troubleshooting_reply(message: str, kb_topics: List[str]) -> tuple:
    kb_text = get_kb("troubleshooting")
    if kb_text:
        reply = (
            "Here are the most likely causes and fixes:\n\n"
            + kb_text[:900].strip()
            + "\n\nIf none of these match, share the exact error message and I'll help narrow it down."
        )
    else:
        reply = (
            "To help troubleshoot, please share the exact error message you're seeing. "
            "Common causes include: hitting a plan limit, an unsupported file format, or an expired session."
        )
    return reply, _actions_for_kb_topics(["troubleshooting", "plans_billing"] + kb_topics)


def _build_unknown_reply(kb_topics: List[str]) -> tuple:
    reply = (
        "I can help with platform guidance — uploading documents, starting runs, "
        "managing projects, reviewing usage, or navigating the app. What are you trying to do?"
    )
    return reply, [
        AssistantAction(label="Getting Started", href="/dashboard"),
        AssistantAction(label="Projects", href="/projects"),
        AssistantAction(label="Plans & Billing", href="/settings/billing"),
    ]


# ── Logging ───────────────────────────────────────────────────────────────────

def _log_assistant_event(
    *,
    org_id: str,
    user_id: str,
    conversation_id: str,
    message: str,
    intent: str,
    kb_topics: List[str],
    tool_calls_used: List[str],
    reply: str,
) -> None:
    logger.info("assistant_event=%s", json.dumps({
        "ts": datetime.now(timezone.utc).isoformat(),
        "org_id": org_id,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "message": message,
        "intent": intent,
        "kb_topics": kb_topics,
        "tool_calls_used": tool_calls_used,
        "reply": reply,
    }, ensure_ascii=False))


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/message", response_model=AssistantMessageResponse)
async def send_message(
    body: AssistantMessageRequest,
    request: Request,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)

    # Enforce org membership — never trust raw client-provided org_id.
    org_id = resolve_org_id_for_user(sb, user_id, body.org_id, request=request)
    conversation_id = body.conversation_id or f"conv_{org_id}_{user_id}"

    # Safety: legal/attestation check fires BEFORE any tool calls or KB access.
    if _is_legal_or_attestation_request(body.message):
        reply = _refusal_reply()
        _log_assistant_event(
            org_id=org_id, user_id=user_id, conversation_id=conversation_id,
            message=body.message, intent="legal_attestation", kb_topics=[],
            tool_calls_used=[], reply=reply,
        )
        return AssistantMessageResponse(
            conversation_id=conversation_id, reply=reply, intent="legal_attestation",
            actions=[
                AssistantAction(label="Plans & Billing", href="/settings/billing"),
                AssistantAction(label="Projects", href="/projects"),
            ],
        )

    # Intent classification
    intent = classify_intent(body.message)
    kb_topics = pick_kb_topics(intent, body.message)
    tool_calls_used: List[str] = []

    # Tool calls — gated by intent to avoid unnecessary DB queries
    billing: Dict[str, Any] = {}
    usage: Dict[str, Any] = {}
    projects: Dict[str, Any] = {}
    onboarding: Dict[str, Any] = {}
    recent_runs: Dict[str, Any] = {}

    if intent in ("status", "plan_limits"):
        billing = await _get_billing_summary(sb, org_id)
        tool_calls_used.append("billing_summary")
        usage = await _get_usage_snapshot(sb, org_id)
        tool_calls_used.append("usage_snapshot")

    if intent == "status":
        projects = await _get_projects_summary(sb, org_id)
        tool_calls_used.append("projects_summary")
        onboarding = await _get_onboarding_state(sb, org_id)
        tool_calls_used.append("onboarding_state")
        recent_runs = await _get_recent_runs(sb, org_id)
        tool_calls_used.append("recent_runs")

    # Build reply
    if intent == "status":
        reply, actions = _build_status_reply(billing, usage, projects, onboarding, recent_runs)
    elif intent == "plan_limits":
        reply, actions = _build_plan_limits_reply(billing, usage)
    elif intent == "how_to":
        reply, actions = _build_how_to_reply(body.message, kb_topics)
    elif intent == "navigation":
        reply, actions = _build_navigation_reply(body.message, kb_topics)
    elif intent == "troubleshooting":
        reply, actions = _build_troubleshooting_reply(body.message, kb_topics)
    else:
        reply, actions = _build_unknown_reply(kb_topics)

    _log_assistant_event(
        org_id=org_id, user_id=user_id, conversation_id=conversation_id,
        message=body.message, intent=intent, kb_topics=kb_topics,
        tool_calls_used=tool_calls_used, reply=reply,
    )

    # Audit trail — intent only, never message text
    log_audit_event(
        sb,
        org_id=org_id,
        user_id=user_id,
        event_type="assistant_interaction",
        metadata={
            "intent": intent,
            "kb_topics": kb_topics,
            "conversation_id": conversation_id,
        },
    )

    return AssistantMessageResponse(
        conversation_id=conversation_id, reply=reply, actions=actions, intent=intent,
    )
