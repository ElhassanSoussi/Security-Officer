from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.billing import billing_manager
from app.core.database import get_supabase, get_supabase_admin
from app.core.auth import get_current_user, require_user_id
from app.core.org_context import parse_uuid, resolve_org_id_for_user
from app.core.error_handler import APIError
from app.core.config import get_settings
import logging
import os
from typing import Any, Dict, List
from pydantic import BaseModel

logger = logging.getLogger("api.billing")

router = APIRouter()
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET") or getattr(get_settings(), "STRIPE_WEBHOOK_SECRET", "")
security = HTTPBearer()
settings = get_settings()

_BILLING_ENABLED = bool(getattr(settings, "BILLING_ENABLED", False))
_BILLING_CONFIGURED = _BILLING_ENABLED and bool(getattr(settings, "STRIPE_SECRET_KEY", "") or os.getenv("STRIPE_SECRET_KEY"))
_warned_no_stripe = False

def _billing_fallback(org_id: str | None = None) -> Dict[str, Any]:
    from app.core.entitlements import PLAN_ENTITLEMENTS, get_current_period

    ent = PLAN_ENTITLEMENTS["starter"]
    ps, pe = get_current_period()
    exports_limit = int(ent["exports_per_month"])
    storage_limit_mb = int(round(ent["storage_bytes"] / (1024 * 1024), 0))
    return {
        "org_id": org_id,
        "plan": "starter",
        "plan_id": "starter",
        "status": "trialing",
        "subscription_status": "trialing",
        "billing_enabled": _BILLING_ENABLED,
        "billing_configured": _BILLING_CONFIGURED,
        "has_stripe": False,
        "exports_used": 0,
        "exports_limit": exports_limit,
        "export_limit": exports_limit,
        "period_start": ps.isoformat(),
        "period_end": pe.isoformat(),
        "current_period_start": ps.isoformat(),
        "current_period_end": pe.isoformat(),
        "entitlements": {
            "questionnaires": {"used": 0, "limit": int(ent["questionnaires_per_month"]), "remaining": int(ent["questionnaires_per_month"])},
            "exports": {"used": 0, "limit": exports_limit, "remaining": exports_limit},
            "storage_mb": {"used_mb": 0, "limit_mb": storage_limit_mb, "remaining_mb": storage_limit_mb},
        },
    }

def _ensure_billing_configured():
    global _warned_no_stripe
    if not _BILLING_ENABLED:
        raise APIError(status_code=503, error="billing_disabled", message="Billing is disabled in this environment")
    if not _BILLING_CONFIGURED:
        if not _warned_no_stripe:
            _warned_no_stripe = True
            logger.warning("Stripe not configured; billing endpoints will return 503.")
        raise APIError(status_code=503, error="billing_not_configured", message="Billing is not configured")


# ── Request Models ────────────────────────────────────────────

class CheckoutRequest(BaseModel):
    plan_tier: str  # "starter" | "growth" | "elite"
    org_id: str


# ── Checkout Session ──────────────────────────────────────────

@router.post("/create-checkout-session")
def create_checkout_session(
    body: CheckoutRequest,
    request: Request,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """Create a Stripe Checkout Session for upgrading plans."""
    _ensure_billing_configured()
    user_id = require_user_id(user)
    org_id = parse_uuid(body.org_id, "org_id", required=True)

    sb = get_supabase(token.credentials)
    resolve_org_id_for_user(sb, user_id, org_id, request=request)

    # Get existing stripe_customer_id if any
    admin_sb = get_supabase_admin()
    res = admin_sb.table("organizations") \
        .select("stripe_customer_id") \
        .eq("id", org_id) \
        .single() \
        .execute()

    existing_customer = (res.data or {}).get("stripe_customer_id")

    # Get user email for checkout
    user_email = user.get("email") if isinstance(user, dict) else None

    # Build URLs
    base_url = settings.FRONTEND_URL.rstrip("/")
    success_url = f"{base_url}/plans?checkout=success&session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{base_url}/plans?checkout=canceled"

    try:
        url = billing_manager.create_checkout_session(
            org_id=org_id,
            plan_tier=body.plan_tier,
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=user_email,
            existing_customer_id=existing_customer,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stripe error: {str(e)}")

    return {"url": url}


# ── Webhook ───────────────────────────────────────────────────

@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not WEBHOOK_SECRET:
        raise APIError(status_code=503, error="billing_not_configured", message="Webhook secret not configured")

    try:
        event = billing_manager.construct_event(payload, sig_header, WEBHOOK_SECRET)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event["type"]
    event_data = event["data"]["object"]
    event_id = event.get("id", "unknown")

    # Determine org_id for logging
    org_id = None
    if event_type == "checkout.session.completed":
        org_id = event_data.get("metadata", {}).get("org_id")
    else:
        # Look up org by stripe_customer_id
        customer_id = event_data.get("customer")
        if customer_id:
            admin_sb = get_supabase_admin()
            res = admin_sb.table("organizations") \
                .select("id") \
                .eq("stripe_customer_id", customer_id) \
                .execute()
            if res.data:
                org_id = res.data[0]["id"]

    # Log the event
    billing_manager.log_billing_event(org_id, event_id, event_type, event_data)

    # Handle specific event types
    if event_type == "checkout.session.completed":
        billing_manager.handle_checkout_completed(event_data)
    elif event_type == "customer.subscription.updated":
        billing_manager.handle_subscription_updated(event_data)
    elif event_type == "customer.subscription.deleted":
        billing_manager.handle_subscription_deleted(event_data)
    else:
        logger.debug("Unhandled Stripe event: %s", event_type)

    return {"status": "success"}


# ── Portal ────────────────────────────────────────────────────

@router.post("/portal")
def create_portal_session(
    org_id: str,
    request: Request,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    _ensure_billing_configured()
    user_id = require_user_id(user)
    org_id = parse_uuid(org_id, "org_id", required=True)

    supabase = get_supabase(token.credentials)
    resolve_org_id_for_user(supabase, user_id, org_id, request=request)
    res = supabase.table("organizations") \
        .select("stripe_customer_id") \
        .eq("id", org_id) \
        .single() \
        .execute()

    if not res.data or not res.data.get("stripe_customer_id"):
        raise HTTPException(status_code=400, detail="Organization has no billing account")

    base_url = settings.FRONTEND_URL.rstrip("/")
    url = billing_manager.create_portal_session(
        customer_id=res.data["stripe_customer_id"],
        return_url=f"{base_url}/plans",
    )
    return {"url": url}


# ── Plans ─────────────────────────────────────────────────────

@router.get("/plans", response_model=List[Dict[str, Any]])
def list_plans(
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """Return available plan tiers."""
    # Source of truth for public pricing (UI + API).
    # Keep these consistent with the product spec:
    # Starter: $149/mo, Growth: $499/mo, Elite: $1499/mo.
    DEFAULT_PLANS: List[Dict[str, Any]] = [
        {
            "id": "starter",
            "name": "Starter",
            "price_cents": 14900,
            "billing_interval": "month",
            "questionnaires_limit": 10,
            "knowledge_storage_mb": 500,
            "exports_limit": 10,
        },
        {
            "id": "growth",
            "name": "Growth",
            "price_cents": 49900,
            "billing_interval": "month",
            "questionnaires_limit": 25,
            "knowledge_storage_mb": 2000,
            "exports_limit": 25,
        },
        {
            "id": "elite",
            "name": "Elite",
            "price_cents": 149900,
            "billing_interval": "month",
            "questionnaires_limit": 100,
            "knowledge_storage_mb": 10000,
            "exports_limit": 100,
        },
    ]
    defaults_by_id = {p["id"]: p for p in DEFAULT_PLANS}

    try:
        sb = get_supabase(token.credentials)
    except Exception:
        sb = None

    try:
        if sb is not None:
            res = sb.table("plans").select("*").order("price_cents").execute()
            if res.data:
                # If the plans table exists, we still enforce canonical pricing
                # so environments with old seed data don't show outdated prices.
                normalized: List[Dict[str, Any]] = []
                seen = set()
                for row in (res.data or []):
                    pid = str(row.get("id") or "").strip().lower()
                    if not pid:
                        continue
                    seen.add(pid)
                    d = defaults_by_id.get(pid)
                    if d:
                        row["price_cents"] = d["price_cents"]
                        row["billing_interval"] = d["billing_interval"]
                        # Ensure required fields exist for frontend rendering.
                        row["name"] = row.get("name") or d["name"]
                        row["questionnaires_limit"] = row.get("questionnaires_limit") or d["questionnaires_limit"]
                        row["knowledge_storage_mb"] = row.get("knowledge_storage_mb") or d["knowledge_storage_mb"]
                        row["exports_limit"] = row.get("exports_limit") or d["exports_limit"]
                    normalized.append(row)

                # Add any missing defaults.
                for pid, d in defaults_by_id.items():
                    if pid not in seen:
                        normalized.append(dict(d))

                normalized.sort(key=lambda x: int(x.get("price_cents") or 0))
                # Inject billing state hint for frontend
                for row in normalized:
                    row["billing_enabled"] = _BILLING_ENABLED
                    row["billing_configured"] = _BILLING_CONFIGURED
                return normalized
    except Exception:
        pass

    # Include billing state hint for frontend.
    plans = [dict(p) for p in DEFAULT_PLANS]
    for p in plans:
        p["billing_enabled"] = _BILLING_ENABLED
        p["billing_configured"] = _BILLING_CONFIGURED
    return plans


# ── Subscription ──────────────────────────────────────────────

@router.get("/subscription", response_model=Dict[str, Any])
def get_subscription(
    org_id: str | None = None,
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """Return the caller's subscription record for an org (RLS enforced)."""
    if not _BILLING_ENABLED or not _BILLING_CONFIGURED:
        return _billing_fallback(org_id)
    user_id = require_user_id(user)

    try:
        sb = get_supabase(token.credentials)
    except Exception:
        sb = None

    if not org_id or not str(org_id).strip():
        raise HTTPException(status_code=400, detail="org_id is required")

    resolved_org_id = None
    if sb is not None:
        resolved_org_id = resolve_org_id_for_user(sb, user_id, org_id, request=request)
    if not resolved_org_id:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Read from organizations table (Stripe-managed fields)
    admin_sb = get_supabase_admin()
    try:
        # Stripe-managed fields are optional in early setups.
        try:
            res = (
                admin_sb.table("organizations")
                .select("plan_tier, subscription_status, current_period_start, current_period_end, stripe_customer_id")
                .eq("id", resolved_org_id)
                .single()
                .execute()
            )
            org_data = res.data or {}
        except Exception:
            res = (
                admin_sb.table("organizations")
                .select("plan_tier")
                .eq("id", resolved_org_id)
                .single()
                .execute()
            )
            org_data = res.data or {}

        plan = (org_data.get("plan_tier") or "starter").strip().lower()
        status = (org_data.get("subscription_status") or "trialing").strip().lower()

        from app.core.entitlements import get_billing_summary, get_current_period

        summary = get_billing_summary(resolved_org_id)
        exports_used = int(((summary.get("entitlements") or {}).get("exports") or {}).get("used") or 0)
        exports_limit = int(((summary.get("entitlements") or {}).get("exports") or {}).get("limit") or 0)
        ps, pe = get_current_period()

        return {
            "org_id": resolved_org_id,
            "plan": plan,
            "plan_id": plan,
            "status": status,
            "subscription_status": status,
            "billing_configured": _BILLING_CONFIGURED,
            "has_stripe": bool(org_data.get("stripe_customer_id")),
            "current_period_start": org_data.get("current_period_start") or ps.isoformat(),
            "current_period_end": org_data.get("current_period_end") or pe.isoformat(),
            "period_start": org_data.get("current_period_start") or ps.isoformat(),
            "period_end": org_data.get("current_period_end") or pe.isoformat(),
            "exports_used": exports_used,
            "exports_limit": exports_limit,
            "export_limit": exports_limit,
        }
    except Exception:
        pass

    return {
        "org_id": resolved_org_id,
        "status": "trialing",
        "plan_id": "starter",
        "plan": "starter",
        "exports_used": 0,
        "exports_limit": 0,
        "export_limit": 0,
        "period_end": None,
        "billing_configured": _BILLING_CONFIGURED,
    }


@router.get("/plan", response_model=Dict[str, Any])
def get_plan_summary(
    org_id: str | None = None,
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Paid-SaaS stable plan/usage response.
    Always returns a predictable shape for the Plans page.
    """
    if not _BILLING_ENABLED or not _BILLING_CONFIGURED:
        return _billing_fallback(org_id)
    if not org_id or not str(org_id).strip():
        raise HTTPException(status_code=400, detail="org_id is required")

    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)
    resolved_org_id = resolve_org_id_for_user(sb, user_id, org_id, request=request)

    from app.core.entitlements import get_billing_summary, get_current_period

    summary = get_billing_summary(resolved_org_id)
    ps, pe = get_current_period()
    ent = summary.get("entitlements") or {}
    exports = ent.get("exports") or {}

    return {
        "org_id": resolved_org_id,
        "plan": summary.get("plan") or "starter",
        "status": "trial",
        "billing_configured": _BILLING_CONFIGURED,
        "exports_used": int(exports.get("used") or 0),
        "export_limit": int(exports.get("limit") or 0),
        "exports_limit": int(exports.get("limit") or 0),
        "period_start": summary.get("period_start") or ps.isoformat(),
        "period_end": summary.get("period_end") or pe.isoformat(),
    }


# ── Billing Summary ──────────────────────────────────────────

@router.get("/summary", response_model=Dict[str, Any])
def get_billing_summary_endpoint(
    org_id: str | None = None,
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """Return the caller's plan tier, current billing period, and real-time usage."""
    if not _BILLING_ENABLED or not _BILLING_CONFIGURED:
        return _billing_fallback(org_id)
    from app.core.entitlements import get_billing_summary
    user_id = require_user_id(user)

    try:
        sb = get_supabase(token.credentials)
    except Exception:
        sb = None

    resolved_org_id = None
    if sb is not None:
        try:
            resolved_org_id = resolve_org_id_for_user(sb, user_id, org_id, request=request)
        except HTTPException:
            raise
        except Exception:
            pass

    if not resolved_org_id:
        from app.core.entitlements import get_current_period, PLAN_ENTITLEMENTS
        ps, pe = get_current_period()
        ent = PLAN_ENTITLEMENTS["starter"]
        return {
            "plan": "starter",
            "period_start": ps.isoformat(),
            "period_end": pe.isoformat(),
            "entitlements": {
                "questionnaires": {"used": 0, "limit": ent["questionnaires_per_month"], "remaining": ent["questionnaires_per_month"]},
                "exports": {"used": 0, "limit": ent["exports_per_month"], "remaining": ent["exports_per_month"]},
                "storage_mb": {"used_mb": 0, "limit_mb": round(ent["storage_bytes"] / (1024*1024), 0), "remaining_mb": round(ent["storage_bytes"] / (1024*1024), 0)},
            },
        }

    return get_billing_summary(resolved_org_id)


@router.get("/current", response_model=Dict[str, Any])
def get_current_billing(
    org_id: str | None = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """Alias endpoint used by ops verification and frontend integrations."""
    return get_subscription(org_id=org_id, user=user, token=token)


# ══════════════════════════════════════════════════════════════════════════════
# Phase 19 — Stripe Billing Endpoints
# ══════════════════════════════════════════════════════════════════════════════

from app.core.stripe_billing import (
    create_checkout_session as _stripe_checkout,
    handle_webhook_event as _stripe_webhook,
    get_subscription_status as _stripe_status,
    start_pro_trial as _start_trial,
)


class Phase19CheckoutRequest(BaseModel):
    """Phase 19 checkout request — uses Phase-18 plan names."""
    org_id: str
    plan_name: str  # "FREE" | "PRO" | "ENTERPRISE"


@router.post("/checkout")
def phase19_create_checkout(
    body: Phase19CheckoutRequest,
    request: Request,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Phase 19 Part 3 — Create a Stripe Checkout Session.
    Accepts plan_name (FREE/PRO/ENTERPRISE) and returns a hosted checkout URL.
    503 if BILLING_ENABLED=false or Stripe not configured.
    400 if plan_name is unknown or price ID is unconfigured.
    """
    _ensure_billing_configured()
    user_id = require_user_id(user)
    org_id = parse_uuid(body.org_id, "org_id", required=True)

    sb = get_supabase(token.credentials)
    resolve_org_id_for_user(sb, user_id, org_id, request=request)

    # Fetch existing Stripe customer ID from subscriptions table (Phase 19)
    admin_sb = get_supabase_admin()
    existing_customer: str | None = None
    try:
        res = (
            admin_sb.table("subscriptions")
            .select("stripe_customer_id")
            .eq("org_id", org_id)
            .single()
            .execute()
        )
        existing_customer = (res.data or {}).get("stripe_customer_id")
    except Exception:
        pass

    user_email = user.get("email") if isinstance(user, dict) else None
    base_url = settings.FRONTEND_URL.rstrip("/")
    success_url = f"{base_url}/settings/billing?checkout=success"
    cancel_url = f"{base_url}/settings/billing?checkout=canceled"

    try:
        url = _stripe_checkout(
            org_id=org_id,
            plan_name=body.plan_name,
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=user_email,
            existing_customer_id=existing_customer,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stripe error: {str(e)}")

    return {"url": url, "plan_name": body.plan_name}


@router.post("/webhook19")
async def phase19_stripe_webhook(request: Request):
    """
    Phase 19 Part 3 — Stripe webhook receiver.
    Validates signature, then dispatches:
      • checkout.session.completed
      • customer.subscription.created / updated / deleted
      • invoice.payment_failed
    Writes results into Phase-18 subscriptions table.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    result = _stripe_webhook(payload, sig_header)
    return {"status": "ok", **result}


@router.get("/status")
def phase19_subscription_status(
    org_id: str | None = None,
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Phase 19 Part 3 — Return live Stripe subscription status for an org.
    Returns plan_name, stripe_status, current_period_end, is_active.
    Never raises on DB errors (fail-open).
    """
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)
    if org_id:
        org_id = parse_uuid(org_id, "org_id", required=True)
    org_id = resolve_org_id_for_user(sb, user_id, org_id, request=request)
    if not org_id:
        raise HTTPException(status_code=400, detail="org_id required")

    return _stripe_status(org_id)


@router.post("/trial")
def phase19_start_trial(
    org_id: str | None = None,
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Phase 19 Part 6 — Manually start a 14-day PRO trial (admin-granted or Stripe-less).
    Sets stripe_status=trialing, plan_name=PRO on the subscriptions row.
    """
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)
    if org_id:
        org_id = parse_uuid(org_id, "org_id", required=True)
    org_id = resolve_org_id_for_user(sb, user_id, org_id, request=request)
    if not org_id:
        raise HTTPException(status_code=400, detail="org_id required")

    return _start_trial(org_id)
