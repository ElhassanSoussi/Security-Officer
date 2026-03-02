"""
Phase 19 — Stripe Billing Integration (Production-Ready Foundation)
===================================================================

Responsibilities:
  • create_checkout_session(org_id, plan_name, success_url, cancel_url, email)
      → returns Stripe checkout URL; writes pending record to subscriptions table
  • handle_webhook_event(payload, sig_header)
      → validates signature; dispatches to typed handlers; idempotent
  • get_subscription_status(org_id)
      → returns live status dict from subscriptions table (never raises)
  • check_subscription_active(org_id)
      → raises HTTP 402 SUBSCRIPTION_INACTIVE if stripe_status is not
         active or trialing; fail-open on DB errors

All DB writes use the admin client to bypass RLS.
All failures degrade gracefully (never crash the calling endpoint).

Phase-18 plan names (FREE / PRO / ENTERPRISE) map 1-to-1 to Stripe Price IDs
read from the config ENV variables STRIPE_PRICE_FREE / _PRO / _ENTERPRISE.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import stripe
from fastapi import HTTPException

logger = logging.getLogger("billing.stripe")

# ─── Stripe initialisation ────────────────────────────────────────────────────

def _stripe_key() -> str:
    return os.getenv("STRIPE_SECRET_KEY", "")


def _webhook_secret() -> str:
    return os.getenv("STRIPE_WEBHOOK_SECRET", "")


def _price_map() -> Dict[str, str]:
    """Return mapping of plan_name → Stripe Price ID from environment."""
    return {
        "FREE":       os.getenv("STRIPE_PRICE_FREE", ""),
        "PRO":        os.getenv("STRIPE_PRICE_PRO", ""),
        "ENTERPRISE": os.getenv("STRIPE_PRICE_ENTERPRISE", ""),
    }


def _price_to_plan() -> Dict[str, str]:
    """Reverse map: Stripe Price ID → plan_name."""
    return {v: k for k, v in _price_map().items() if v}


def _admin_sb():
    from app.core.database import get_supabase_admin
    return get_supabase_admin()


def _ts_to_iso(ts: Any) -> Optional[str]:
    """Convert Unix timestamp (int/float) to ISO-8601 string. Returns None if ts is falsy."""
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
    except Exception:
        return None


# ─── Stripe availability guard ────────────────────────────────────────────────

def _stripe_available() -> bool:
    """Return True only when a non-empty secret key is configured."""
    return bool(_stripe_key())


# ─── Checkout Session ─────────────────────────────────────────────────────────

def create_checkout_session(
    org_id: str,
    plan_name: str,          # "FREE" | "PRO" | "ENTERPRISE"
    success_url: str,
    cancel_url: str,
    customer_email: Optional[str] = None,
    existing_customer_id: Optional[str] = None,
) -> str:
    """
    Create a Stripe Checkout Session for the given org + plan.
    Returns the hosted checkout URL.

    Raises ValueError for unknown plan names.
    Raises RuntimeError when Stripe is not configured.
    """
    if not _stripe_available():
        raise RuntimeError("Stripe is not configured (STRIPE_SECRET_KEY missing)")

    stripe.api_key = _stripe_key()

    price_map = _price_map()
    price_id = price_map.get(plan_name.upper(), "")
    if not price_id:
        raise ValueError(
            f"No Stripe Price ID configured for plan '{plan_name}'. "
            f"Set STRIPE_PRICE_{plan_name.upper()} in your environment."
        )

    from app.core.config import get_settings
    trial_days = getattr(get_settings(), "STRIPE_TRIAL_DAYS", 14)

    params: Dict[str, Any] = {
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": success_url,
        "cancel_url": cancel_url,
        "metadata": {"org_id": org_id, "plan_name": plan_name.upper()},
    }

    # Add trial only for PRO plan
    if plan_name.upper() == "PRO" and trial_days > 0:
        params["subscription_data"] = {"trial_period_days": trial_days}

    if existing_customer_id:
        params["customer"] = existing_customer_id
    elif customer_email:
        params["customer_email"] = customer_email

    # Write a pending subscription row so the org is associated with this
    # checkout attempt. This helps map the eventual Stripe customer → org in
    # webhook handlers. Do not fail the checkout if the DB write errors.
    try:
        from app.core.subscription import PLAN_DEFAULTS

        limits = PLAN_DEFAULTS.get(plan_name.upper(), PLAN_DEFAULTS["FREE"])
        pending_record: Dict[str, Any] = {
            "org_id": org_id,
            "plan_name": plan_name.upper(),
            "stripe_status": "pending",
            "max_runs_per_month": limits.get("max_runs_per_month"),
            "max_documents": limits.get("max_documents"),
            "max_memory_entries": limits.get("max_memory_entries"),
        }
        _upsert_subscription(org_id, pending_record)
    except Exception as e:
        logger.warning("create_checkout_session: failed to upsert pending subscription for org=%s: %s", org_id, str(e)[:120])

    session = stripe.checkout.Session.create(**params)
    return session.url


# ─── Webhook Handling ─────────────────────────────────────────────────────────

def handle_webhook_event(payload: bytes, sig_header: str) -> Dict[str, Any]:
    """
    Validate Stripe webhook signature and dispatch to typed handlers.
    Returns {"status": "handled", "type": event_type} on success.
    Raises HTTPException 400 on invalid payload or signature.
    """
    secret = _webhook_secret()
    if not secret:
        raise HTTPException(status_code=503, detail="Webhook secret not configured")

    stripe.api_key = _stripe_key()

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, secret)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook signature")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid webhook payload")

    event_type: str = event["type"]
    event_data: Dict[str, Any] = event["data"]["object"]
    event_id: str = event.get("id", "unknown")

    logger.info("Stripe webhook received: type=%s id=%s", event_type, event_id)

    # Idempotency: log event first (upsert on stripe_event_id)
    _log_billing_event(event_id, event_type, event_data)

    # Dispatch
    if event_type == "checkout.session.completed":
        _handle_checkout_completed(event_data)
    elif event_type in ("customer.subscription.created", "customer.subscription.updated"):
        _handle_subscription_updated(event_data)
    elif event_type == "customer.subscription.deleted":
        _handle_subscription_deleted(event_data)
    elif event_type == "invoice.payment_failed":
        _handle_payment_failed(event_data)
    else:
        logger.debug("Unhandled Stripe event type: %s", event_type)

    return {"status": "handled", "type": event_type}


# ─── Webhook Handlers ─────────────────────────────────────────────────────────

def _handle_checkout_completed(session_data: Dict[str, Any]) -> None:
    """checkout.session.completed → write active subscription to subscriptions table."""
    org_id = (session_data.get("metadata") or {}).get("org_id")
    plan_name = (session_data.get("metadata") or {}).get("plan_name", "PRO").upper()
    customer_id: Optional[str] = session_data.get("customer")
    subscription_id: Optional[str] = session_data.get("subscription")

    if not org_id:
        logger.warning("checkout.session.completed: missing org_id in metadata")
        return

    update: Dict[str, Any] = {
        "org_id": org_id,
        "plan_name": plan_name,
        "stripe_customer_id": customer_id,
        "stripe_subscription_id": subscription_id,
        "stripe_status": "active",
    }

    # Fetch subscription period dates from Stripe
    if subscription_id:
        try:
            stripe.api_key = _stripe_key()
            sub = stripe.Subscription.retrieve(subscription_id)
            update["current_period_end"] = _ts_to_iso(sub.current_period_end)
            status = sub.status  # may be "trialing" if trial was applied
            update["stripe_status"] = status
            # Update plan limits in subscriptions table to match plan_name
            from app.core.subscription import PLAN_DEFAULTS
            limits = PLAN_DEFAULTS.get(plan_name, PLAN_DEFAULTS["FREE"])
            update["max_runs_per_month"] = limits["max_runs_per_month"]
            update["max_documents"] = limits["max_documents"]
            update["max_memory_entries"] = limits["max_memory_entries"]
        except Exception as e:
            logger.warning("Failed to fetch Stripe subscription details: %s", e)

    _upsert_subscription(org_id, update)
    logger.info("checkout.session.completed: org=%s plan=%s", org_id, plan_name)


def _handle_subscription_updated(sub_data: Dict[str, Any]) -> None:
    """customer.subscription.created/updated → sync status + period to subscriptions table."""
    customer_id: Optional[str] = sub_data.get("customer")
    subscription_id: Optional[str] = sub_data.get("id")
    status: str = sub_data.get("status", "active")

    # Derive plan from price
    items = (sub_data.get("items") or {}).get("data", [])
    price_id = items[0].get("price", {}).get("id", "") if items else ""
    plan_name = _price_to_plan().get(price_id, "PRO").upper()

    org_id = _org_id_for_customer(customer_id)
    if not org_id:
        logger.warning("subscription.updated: no org found for customer=%s", customer_id)
        return

    from app.core.subscription import PLAN_DEFAULTS
    limits = PLAN_DEFAULTS.get(plan_name, PLAN_DEFAULTS["FREE"])

    update: Dict[str, Any] = {
        "org_id": org_id,
        "plan_name": plan_name,
        "stripe_customer_id": customer_id,
        "stripe_subscription_id": subscription_id,
        "stripe_status": status,
        "current_period_end": _ts_to_iso(sub_data.get("current_period_end")),
        "max_runs_per_month": limits["max_runs_per_month"],
        "max_documents": limits["max_documents"],
        "max_memory_entries": limits["max_memory_entries"],
    }
    _upsert_subscription(org_id, update)
    logger.info("subscription.updated: org=%s plan=%s status=%s", org_id, plan_name, status)


def _handle_subscription_deleted(sub_data: Dict[str, Any]) -> None:
    """customer.subscription.deleted → mark canceled, downgrade to FREE."""
    customer_id: Optional[str] = sub_data.get("customer")
    org_id = _org_id_for_customer(customer_id)
    if not org_id:
        logger.warning("subscription.deleted: no org found for customer=%s", customer_id)
        return

    from app.core.subscription import PLAN_DEFAULTS
    limits = PLAN_DEFAULTS["FREE"]
    update: Dict[str, Any] = {
        "org_id": org_id,
        "plan_name": "FREE",
        "stripe_status": "canceled",
        "stripe_subscription_id": None,
        "max_runs_per_month": limits["max_runs_per_month"],
        "max_documents": limits["max_documents"],
        "max_memory_entries": limits["max_memory_entries"],
    }
    _upsert_subscription(org_id, update)
    logger.info("subscription.deleted: org=%s → FREE / canceled", org_id)


def _handle_payment_failed(invoice_data: Dict[str, Any]) -> None:
    """invoice.payment_failed → set stripe_status to past_due."""
    customer_id: Optional[str] = invoice_data.get("customer")
    org_id = _org_id_for_customer(customer_id)
    if not org_id:
        logger.warning("invoice.payment_failed: no org found for customer=%s", customer_id)
        return

    _upsert_subscription(org_id, {"org_id": org_id, "stripe_status": "past_due"})
    logger.info("invoice.payment_failed: org=%s → past_due", org_id)


# ─── Subscription Status ──────────────────────────────────────────────────────

def get_subscription_status(org_id: str) -> Dict[str, Any]:
    """
    Return the live subscription status for an org from the subscriptions table.
    Never raises — returns a safe default dict on any error.
    """
    defaults: Dict[str, Any] = {
        "org_id": org_id,
        "plan_name": "FREE",
        "stripe_status": None,
        "stripe_customer_id": None,
        "stripe_subscription_id": None,
        "current_period_end": None,
        "is_active": True,  # fail-open
    }
    try:
        sb = _admin_sb()
        res = (
            sb.table("subscriptions")
            .select(
                "plan_name, stripe_customer_id, stripe_subscription_id, "
                "stripe_status, current_period_end, max_runs_per_month, "
                "max_documents, max_memory_entries"
            )
            .eq("org_id", org_id)
            .single()
            .execute()
        )
        if not res.data:
            return defaults

        data = dict(res.data)
        stripe_status = data.get("stripe_status") or ""
        data["is_active"] = stripe_status in ("active", "trialing", "")
        data["org_id"] = org_id
        return data
    except Exception as e:
        _table_missing = "Could not find" in str(e) or "does not exist" in str(e)
        if not _table_missing:
            logger.warning("get_subscription_status failed org=%s: %s", org_id, str(e)[:120])
        return defaults


# ─── Enforcement ──────────────────────────────────────────────────────────────

# stripe_status values that are considered active (allow access)
ACTIVE_STATUSES = {"active", "trialing", ""}


def check_subscription_active(org_id: str) -> None:
    """
    Raise HTTP 402 SUBSCRIPTION_INACTIVE if the org's Stripe subscription
    is not in an active/trialing state.

    Fail-open: any DB error → passes silently (avoids blocking legitimate users
    during DB outages).

    Called at the top of: /analyze-excel, /ingest, /generate-evidence.
    """
    try:
        sb = _admin_sb()
        res = (
            sb.table("subscriptions")
            .select("stripe_status")
            .eq("org_id", org_id)
            .single()
            .execute()
        )
        if not res.data:
            return  # no subscription row → treat as active (new org)

        stripe_status: str = res.data.get("stripe_status") or ""
        if stripe_status and stripe_status not in ACTIVE_STATUSES:
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "SUBSCRIPTION_INACTIVE",
                    "detail": "Your subscription is inactive. Please update your billing to continue.",
                    "stripe_status": stripe_status,
                },
            )
    except HTTPException:
        raise
    except Exception as e:
        _table_missing = "Could not find" in str(e) or "does not exist" in str(e)
        if not _table_missing:
            logger.warning("check_subscription_active failed org=%s: %s", org_id, str(e)[:120])
        # Fail-open: don't block on DB errors


# ─── Trial Logic ──────────────────────────────────────────────────────────────

def start_pro_trial(org_id: str) -> Dict[str, Any]:
    """
    Manually start a 14-day PRO trial for an org (used when Stripe is not yet
    configured or for admin-granted trials).

    Inserts/updates the subscriptions row with:
      plan_name=PRO, stripe_status=trialing
    Returns the upserted record.
    Never raises.
    """
    from app.core.subscription import PLAN_DEFAULTS
    from datetime import timedelta

    limits = PLAN_DEFAULTS["PRO"]
    trial_end = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()

    record: Dict[str, Any] = {
        "org_id": org_id,
        "plan_name": "PRO",
        "stripe_status": "trialing",
        "current_period_end": trial_end,
        "max_runs_per_month": limits["max_runs_per_month"],
        "max_documents": limits["max_documents"],
        "max_memory_entries": limits["max_memory_entries"],
    }
    try:
        _upsert_subscription(org_id, record)
        logger.info("start_pro_trial: org=%s trial_end=%s", org_id, trial_end)
    except Exception as e:
        logger.warning("start_pro_trial failed org=%s: %s", org_id, e)
    return record


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _upsert_subscription(org_id: str, data: Dict[str, Any]) -> None:
    """Upsert into the Phase-18 subscriptions table keyed on org_id."""
    try:
        sb = _admin_sb()
        # Remove None values to avoid overwriting existing DB fields with NULL
        clean = {k: v for k, v in data.items() if v is not None or k == "stripe_subscription_id"}
        sb.table("subscriptions").upsert(clean, on_conflict="org_id").execute()
    except Exception as e:
        logger.warning("_upsert_subscription failed org=%s: %s", org_id, str(e)[:120])


def _org_id_for_customer(customer_id: Optional[str]) -> Optional[str]:
    """Look up org_id by stripe_customer_id in the subscriptions table."""
    if not customer_id:
        return None
    try:
        sb = _admin_sb()
        res = (
            sb.table("subscriptions")
            .select("org_id")
            .eq("stripe_customer_id", customer_id)
            .single()
            .execute()
        )
        return (res.data or {}).get("org_id")
    except Exception:
        return None


def _log_billing_event(event_id: str, event_type: str, payload: Dict[str, Any]) -> None:
    """Idempotently log a Stripe event to billing_events table."""
    try:
        sb = _admin_sb()
        sb.table("billing_events").upsert(
            {
                "stripe_event_id": event_id,
                "type": event_type,
                "raw_payload": payload,
            },
            on_conflict="stripe_event_id",
        ).execute()
    except Exception as e:
        logger.warning("_log_billing_event failed event_id=%s: %s", event_id, str(e)[:80])
