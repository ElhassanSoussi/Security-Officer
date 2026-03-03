from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from app.core.auth import get_current_user, require_user_id
from app.core.database import get_supabase
from app.core.org_context import resolve_org_id_for_user

logger = logging.getLogger("api.assistant")
router = APIRouter()
security = HTTPBearer()


# ── Models ───────────────────────────────────────────────────────────────

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


# ── Safety ───────────────────────────────────────────────────────────────

_REFUSAL_SNIPPETS = (
    "legal advice",
    "lawyer",
    "attest",
    "attestation",
    "certify",
    "certification",
    "guarantee",
    "guaranteed",
    "compliant",
    "compliance opinion",
    "is this compliant",
    "will we pass",
    "pass the audit",
)


def _is_legal_or_attestation_request(text: str) -> bool:
    t = (text or "").lower()
    return any(s in t for s in _REFUSAL_SNIPPETS)


def _refusal_reply() -> str:
    return (
        "I can’t help with legal advice or audit attestation. "
        "I can help you use the platform to track work, collect evidence, and prepare outputs for review."
    )


# ── Org-scoped helpers (no document content access) ───────────────────────

async def _get_projects_summary(sb, org_id: str) -> Dict[str, Any]:
    res = sb.table("projects").select("id, name, created_at").eq("org_id", org_id).order("created_at", desc=True).limit(5).execute()
    items = res.data or []
    count_res = sb.table("projects").select("id", count="exact").eq("org_id", org_id).execute()
    total = (count_res.count or 0) if hasattr(count_res, "count") else len(count_res.data or [])
    return {"count": total, "recent": [{"id": p["id"], "name": p.get("name"), "created_at": p.get("created_at")} for p in items]}


async def _get_usage_snapshot(sb, org_id: str, token: str) -> Dict[str, Any]:
    from app.core.plan_service import PlanService, Plan, _current_month_start

    admin_sb = sb  # token-scoped client is already org-gated by resolve_org_id_for_user, but we still filter by org_id.

    org_row = admin_sb.table("organizations").select("plan, plan_tier").eq("id", org_id).single().execute()
    raw_plan = ((org_row.data or {}).get("plan") or (org_row.data or {}).get("plan_tier") or "starter").strip().lower()
    try:
        plan_enum = Plan(raw_plan)
    except ValueError:
        plan_enum = Plan.STARTER

    limits = PlanService.get_limits(plan_enum)
    month_start = _current_month_start()

    def _safe_count(table: str, monthly: bool = False) -> int:
        try:
            q = admin_sb.table(table).select("id", count="exact").eq("org_id", org_id)
            if monthly:
                q = q.gte("created_at", month_start)
            r = q.execute()
            return r.count if r.count is not None else 0
        except Exception:
            return 0

    docs_used = _safe_count("documents")
    projects_used = _safe_count("projects")
    runs_used = _safe_count("runs", monthly=True)

    return {
        "documents_used": docs_used,
        "documents_limit": None if plan_enum == Plan.ELITE else limits.get("max_documents"),
        "projects_used": projects_used,
        "projects_limit": None if plan_enum == Plan.ELITE else limits.get("max_projects"),
        "runs_used": runs_used,
        "runs_limit": None if plan_enum == Plan.ELITE else limits.get("max_runs_per_month"),
    }


async def _get_billing_summary(sb, org_id: str, token: str) -> Dict[str, Any]:
    res = sb.table("organizations").select("plan, plan_tier, subscription_status, current_period_end, stripe_customer_id").eq("id", org_id).single().execute()
    row = res.data or {}
    raw_plan = (row.get("plan") or row.get("plan_tier") or "starter").strip().lower()
    status = (row.get("subscription_status") or "trialing").strip().lower()
    return {
        "plan": raw_plan,
        "subscription_status": status,
        "current_period_end": row.get("current_period_end"),
        "billing_configured": True,
        "has_stripe": bool(row.get("stripe_customer_id")),
    }


# ── Endpoint ─────────────────────────────────────────────────────────────

@router.post("/message", response_model=AssistantMessageResponse)
async def send_message(
    body: AssistantMessageRequest,
    request: Request,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)

    # Enforce org membership; never trust raw client-provided org_id.
    org_id = resolve_org_id_for_user(sb, user_id, body.org_id, request=request)

    conversation_id = body.conversation_id or f"conv_{org_id}_{user_id}"

    if _is_legal_or_attestation_request(body.message):
        reply = _refusal_reply()
        actions: List[AssistantAction] = [
            AssistantAction(label="Plans & Billing", href="/settings/billing"),
            AssistantAction(label="Projects", href="/projects"),
        ]
        _log_assistant_event(
            org_id=org_id,
            user_id=user_id,
            conversation_id=conversation_id,
            message=body.message,
            tool_calls_used=[],
            reply=reply,
        )
        return AssistantMessageResponse(conversation_id=conversation_id, reply=reply, actions=actions)

    # Minimal tool usage: give platform guidance + cite org-level facts.
    tool_calls_used: List[str] = []
    billing = await _get_billing_summary(sb, org_id, token.credentials)
    tool_calls_used.append("billing_summary")
    usage = await _get_usage_snapshot(sb, org_id, token.credentials)
    tool_calls_used.append("usage_snapshot")
    projects = await _get_projects_summary(sb, org_id)
    tool_calls_used.append("projects_summary")

    plan = (billing.get("plan") or "starter").title()
    status = (billing.get("subscription_status") or "unknown").replace("_", " ").title()

    reply = (
        f"Here’s what I can see for your organization right now: plan **{plan}** (status: **{status}**).\n\n"
        f"Usage: documents **{usage['documents_used']}**"
        f"{'' if usage['documents_limit'] is None else f" / {usage['documents_limit']}"}, "
        f"projects **{usage['projects_used']}" 
        f"{'' if usage['projects_limit'] is None else f" / {usage['projects_limit']}"}, "
        f"runs this month **{usage['runs_used']}" 
        f"{'' if usage['runs_limit'] is None else f" / {usage['runs_limit']}"}.\n\n"
        f"Projects: **{projects['count']}** total. "
        "Tell me what you’re trying to do (for example: start a new run, organize projects, or review usage), "
        "and I’ll point you to the right place in the app."
    )

    actions = [
        AssistantAction(label="Projects", href="/projects"),
        AssistantAction(label="Plans & Billing", href="/settings/billing"),
        AssistantAction(label="Documents", href="/documents"),
    ]

    _log_assistant_event(
        org_id=org_id,
        user_id=user_id,
        conversation_id=conversation_id,
        message=body.message,
        tool_calls_used=tool_calls_used,
        reply=reply,
    )

    return AssistantMessageResponse(conversation_id=conversation_id, reply=reply, actions=actions)


def _log_assistant_event(*, org_id: str, user_id: str, conversation_id: str, message: str, tool_calls_used: List[str], reply: str) -> None:
    # Keep logs minimal and avoid secrets; do not log tokens.
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "org_id": org_id,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "message": message,
        "tool_calls_used": tool_calls_used,
        "reply": reply,
    }
    logger.info("assistant_event=%s", json.dumps(payload, ensure_ascii=False))
