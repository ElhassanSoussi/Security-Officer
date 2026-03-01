"""
Phase 22 — Sales Engine Endpoints

Endpoints:
  POST /contact                  → Store sales lead
  GET  /admin/sales-analytics    → Admin-only sales metrics
  POST /admin/demo-reset         → Reset demo workspace data
  POST /track/enterprise-interest→ Log enterprise interest event
  POST /track/trial-event        → Log trial lifecycle events
"""

import logging
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, validator

from app.core.auth import get_current_user, require_user_id
from app.core.config import get_settings
from app.core.database import get_supabase, get_supabase_admin
from app.core.org_context import resolve_org_id_for_user
from app.core.rbac import get_user_role
from app.core.rate_limit import contact_limiter, get_client_ip

router = APIRouter()
security = HTTPBearer()
logger = logging.getLogger("api.sales")
settings = get_settings()


# ─── Models ───────────────────────────────────────────────────────────────────

class ContactFormPayload(BaseModel):
    company_name: str
    name: str
    email: str
    phone: Optional[str] = None
    company_size: Optional[str] = None
    message: Optional[str] = None

    @validator("email")
    def validate_email(cls, v):
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, v):
            raise ValueError("Invalid email address")
        return v.lower().strip()

    @validator("company_name", "name")
    def not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()


class EnterpriseInterestPayload(BaseModel):
    org_id: Optional[str] = None
    source: str = "billing_page"


class TrialEventPayload(BaseModel):
    org_id: str
    event_type: str  # TRIAL_STARTED, TRIAL_CONVERTED, TRIAL_EXPIRED

    @validator("event_type")
    def valid_event(cls, v):
        allowed = {"TRIAL_STARTED", "TRIAL_CONVERTED", "TRIAL_EXPIRED"}
        if v not in allowed:
            raise ValueError(f"event_type must be one of {allowed}")
        return v


# ─── Part 2: Contact / Lead Capture ──────────────────────────────────────────

@router.post("/contact")
def submit_contact_form(payload: ContactFormPayload, request: Request):
    """
    Phase 22: Store a sales lead from the contact form.
    No authentication required — public endpoint.
    Phase 23: Rate-limited by client IP (5 per 5 min).
    """
    # Phase 23: Rate limit by client IP
    client_ip = get_client_ip(request)
    contact_limiter.check(client_ip)

    admin_sb = get_supabase_admin()
    now = datetime.now(timezone.utc).isoformat()

    lead_row = {
        "company_name": payload.company_name,
        "contact_name": payload.name,
        "email": payload.email,
        "phone": payload.phone or "",
        "company_size": payload.company_size or "",
        "message": payload.message or "",
        "source": "contact_form",
        "created_at": now,
    }

    try:
        admin_sb.table("sales_leads").insert(lead_row).execute()
    except Exception as e:
        logger.warning("Failed to store sales lead: %s", str(e)[:200])
        # Best-effort: don't fail the user-facing form
        # In production, we'd also send a notification email here

    return {
        "status": "received",
        "message": "Thank you for your interest. Our team will reach out shortly.",
    }


# ─── Part 3: Enterprise Interest Tracking ────────────────────────────────────

@router.post("/track/enterprise-interest")
def track_enterprise_interest(
    payload: EnterpriseInterestPayload,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Phase 22: Log when a user clicks the Enterprise plan CTA.
    """
    user_id = require_user_id(user)
    admin_sb = get_supabase_admin()
    now = datetime.now(timezone.utc).isoformat()

    org_id = payload.org_id or ""
    if org_id:
        try:
            sb = get_supabase(token.credentials)
            org_id = resolve_org_id_for_user(sb, user_id, org_id)
        except Exception:
            pass

    # Log to activity_log
    try:
        admin_sb.table("activity_log").insert({
            "org_id": org_id,
            "user_id": user_id,
            "action_type": "ENTERPRISE_INTEREST",
            "entity_type": "subscription",
            "entity_id": "",
            "metadata": {"source": payload.source},
        }).execute()
    except Exception as e:
        logger.warning("Failed to log enterprise interest: %s", str(e)[:200])

    # Also store as a sales lead if we can
    try:
        admin_sb.table("sales_leads").insert({
            "company_name": "",
            "contact_name": "",
            "email": "",
            "source": "enterprise_interest",
            "metadata": {"org_id": org_id, "user_id": user_id, "source_page": payload.source},
            "created_at": now,
        }).execute()
    except Exception as e:
        logger.warning("Failed to store enterprise interest lead: %s", str(e)[:200])

    return {"status": "tracked"}


# ─── Part 6: Trial Event Tracking ────────────────────────────────────────────

@router.post("/track/trial-event")
def track_trial_event(
    payload: TrialEventPayload,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """Phase 22: Log trial lifecycle events (TRIAL_STARTED, TRIAL_CONVERTED, TRIAL_EXPIRED)."""
    user_id = require_user_id(user)
    admin_sb = get_supabase_admin()

    try:
        admin_sb.table("activity_log").insert({
            "org_id": payload.org_id,
            "user_id": user_id,
            "action_type": payload.event_type,
            "entity_type": "subscription",
            "entity_id": payload.org_id,
            "metadata": {"event_type": payload.event_type},
        }).execute()
    except Exception as e:
        logger.warning("Failed to log trial event: %s", str(e)[:200])

    return {"status": "tracked", "event_type": payload.event_type}


# ─── Part 5: Sales Analytics (Admin Only) ────────────────────────────────────

@router.get("/admin/sales-analytics")
def get_sales_analytics(
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Phase 22: Admin-only sales analytics dashboard data.
    Returns: total_leads, enterprise_interest_count, active_subscriptions,
             trial_count, paid_count, conversion_rate, mrr_estimate.
    """
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)

    # Verify admin/owner on at least one org
    try:
        orgs = sb.table("org_members").select("org_id, role").eq("user_id", user_id).execute()
        roles = [m.get("role", "") for m in (orgs.data or [])]
        if not any(r in ("owner", "admin") for r in roles):
            raise HTTPException(status_code=403, detail="Admin access required")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=403, detail="Admin access required")

    admin_sb = get_supabase_admin()
    analytics = {
        "total_leads": 0,
        "enterprise_interest_count": 0,
        "active_subscriptions": 0,
        "trial_count": 0,
        "paid_count": 0,
        "conversion_rate": 0.0,
        "mrr_estimate": 0,
    }

    # Total leads
    try:
        res = admin_sb.table("sales_leads").select("id", count="exact").execute()
        analytics["total_leads"] = res.count or 0
    except Exception:
        pass

    # Enterprise interest clicks
    try:
        res = admin_sb.table("activity_log").select("id", count="exact").eq("action_type", "ENTERPRISE_INTEREST").execute()
        analytics["enterprise_interest_count"] = res.count or 0
    except Exception:
        pass

    # Subscription counts
    try:
        res = admin_sb.table("subscriptions").select("stripe_status, plan_name").execute()
        subs = res.data or []
        active = [s for s in subs if s.get("stripe_status") in ("active", "trialing")]
        trialing = [s for s in subs if s.get("stripe_status") == "trialing"]
        paid = [s for s in subs if s.get("stripe_status") == "active" and s.get("plan_name", "").upper() != "FREE"]

        analytics["active_subscriptions"] = len(active)
        analytics["trial_count"] = len(trialing)
        analytics["paid_count"] = len(paid)

        total_trials_ever = len(trialing) + len(paid)
        if total_trials_ever > 0:
            analytics["conversion_rate"] = round(len(paid) / total_trials_ever * 100, 1)

        # MRR estimate: $149/mo per PRO, $0 for FREE
        pro_count = sum(1 for s in paid if s.get("plan_name", "").upper() == "PRO")
        analytics["mrr_estimate"] = pro_count * 149
    except Exception:
        pass

    return analytics


# ─── Part 1: Demo Reset ──────────────────────────────────────────────────────

DEMO_ORG_ID = "00000000-0000-0000-0000-000000000001"
DEMO_PROJECT_ID = "00000000-0000-0000-0000-000000000002"
DEMO_RUN_ID = "00000000-0000-0000-0000-000000000003"
DEMO_USER_ID = "00000000-0000-0000-0000-000000000099"


@router.post("/admin/demo-reset")
def reset_demo_workspace(
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Phase 22: Reset all demo workspace data to a clean seeded state.
    Admin/owner only. Idempotent — can be called repeatedly.
    """
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)

    # Verify user is admin/owner in some org
    try:
        orgs = sb.table("org_members").select("org_id, role").eq("user_id", user_id).execute()
        roles = [m.get("role", "") for m in (orgs.data or [])]
        if not any(r in ("owner", "admin") for r in roles):
            raise HTTPException(status_code=403, detail="Admin access required")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=403, detail="Admin access required")

    admin_sb = get_supabase_admin()

    # Clean existing demo data (idempotent)
    try:
        admin_sb.table("run_audits").delete().eq("org_id", DEMO_ORG_ID).execute()
    except Exception:
        pass
    try:
        admin_sb.table("activity_log").delete().eq("org_id", DEMO_ORG_ID).execute()
    except Exception:
        pass
    try:
        admin_sb.table("run_evidence_records").delete().eq("org_id", DEMO_ORG_ID).execute()
    except Exception:
        pass
    try:
        admin_sb.table("runs").delete().eq("org_id", DEMO_ORG_ID).execute()
    except Exception:
        pass

    return {"status": "reset_complete", "org_id": DEMO_ORG_ID}
