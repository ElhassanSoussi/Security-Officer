"""
coupon_service.py — Stripe Coupon & Promo Code Support
========================================================

Provides:
  • validate_coupon(code) → coupon details or None
  • list_active_coupons() → list of active promotions
  • apply_coupon_to_subscription(org_id, coupon_code) → result
  • get_org_discount(org_id) → current discount info or None

All functions are best-effort and never crash the caller.
Stripe must be configured (STRIPE_SECRET_KEY) for real operations.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger("billing.coupons")

_stripe_warned = False


def _stripe_key() -> str:
    return os.getenv("STRIPE_SECRET_KEY", "")


def _stripe_available() -> bool:
    return bool(_stripe_key())


def _init_stripe():
    """Lazy-init stripe with API key."""
    import stripe
    stripe.api_key = _stripe_key()
    return stripe


# ── Validate a promo/coupon code ──────────────────────────────────────────────


def validate_coupon(code: str) -> Optional[Dict[str, Any]]:
    """
    Validate a Stripe promotion code or coupon ID.

    Returns a dict with coupon details if valid, or None if invalid/expired.
    Shape: {id, code, percent_off, amount_off, currency, duration, duration_in_months, valid}
    """
    if not code or not code.strip():
        return None

    if not _stripe_available():
        logger.debug("validate_coupon: Stripe not configured")
        return None

    code = code.strip().upper()

    try:
        stripe = _init_stripe()

        # First try as a promotion code
        promos = stripe.PromotionCode.list(code=code, active=True, limit=1)
        if promos.data:
            promo = promos.data[0]
            coupon = promo.coupon
            return {
                "id": coupon.id,
                "promo_code_id": promo.id,
                "code": code,
                "percent_off": coupon.percent_off,
                "amount_off": coupon.amount_off,
                "currency": coupon.currency,
                "duration": coupon.duration,
                "duration_in_months": coupon.duration_in_months,
                "valid": coupon.valid,
                "name": coupon.name or code,
            }

        # Fallback: try as a coupon ID directly
        try:
            coupon = stripe.Coupon.retrieve(code)
            if coupon.valid:
                return {
                    "id": coupon.id,
                    "promo_code_id": None,
                    "code": code,
                    "percent_off": coupon.percent_off,
                    "amount_off": coupon.amount_off,
                    "currency": coupon.currency,
                    "duration": coupon.duration,
                    "duration_in_months": coupon.duration_in_months,
                    "valid": True,
                    "name": coupon.name or code,
                }
        except Exception:
            pass

        return None

    except Exception as exc:
        logger.debug("validate_coupon failed code=%s: %s", code[:20], str(exc)[:120])
        return None


# ── List active promotions ────────────────────────────────────────────────────


def list_active_coupons() -> List[Dict[str, Any]]:
    """Return all active Stripe coupons. Returns [] on error."""
    if not _stripe_available():
        return []

    try:
        stripe = _init_stripe()
        coupons = stripe.Coupon.list(limit=50)
        result = []
        for c in coupons.data:
            if not c.valid:
                continue
            result.append({
                "id": c.id,
                "name": c.name or c.id,
                "percent_off": c.percent_off,
                "amount_off": c.amount_off,
                "currency": c.currency,
                "duration": c.duration,
                "duration_in_months": c.duration_in_months,
            })
        return result
    except Exception as exc:
        logger.debug("list_active_coupons failed: %s", str(exc)[:120])
        return []


# ── Apply coupon to existing subscription ─────────────────────────────────────


def apply_coupon_to_subscription(org_id: str, coupon_code: str) -> Dict[str, Any]:
    """
    Apply a coupon/promo code to an org's active Stripe subscription.

    Returns {success: bool, message: str, discount: dict|None}
    """
    if not _stripe_available():
        return {"success": False, "message": "Stripe not configured", "discount": None}

    if not coupon_code or not coupon_code.strip():
        return {"success": False, "message": "Coupon code is required", "discount": None}

    try:
        stripe = _init_stripe()
        from app.core.database import get_supabase_admin

        admin_sb = get_supabase_admin()

        # Get org's Stripe customer ID
        res = (
            admin_sb.table("organizations")
            .select("stripe_customer_id")
            .eq("id", org_id)
            .single()
            .execute()
        )
        customer_id = (res.data or {}).get("stripe_customer_id")
        if not customer_id:
            return {"success": False, "message": "No billing account found", "discount": None}

        # Find active subscription
        subs = stripe.Subscription.list(customer=customer_id, status="active", limit=1)
        if not subs.data:
            subs = stripe.Subscription.list(customer=customer_id, status="trialing", limit=1)
        if not subs.data:
            return {"success": False, "message": "No active subscription found", "discount": None}

        subscription = subs.data[0]

        # Validate the coupon first
        validated = validate_coupon(coupon_code)
        if not validated:
            return {"success": False, "message": "Invalid or expired coupon code", "discount": None}

        # Apply the coupon
        coupon_id = validated["id"]
        stripe.Subscription.modify(subscription.id, coupon=coupon_id)

        discount_info = {
            "coupon_id": coupon_id,
            "code": coupon_code.strip().upper(),
            "percent_off": validated.get("percent_off"),
            "amount_off": validated.get("amount_off"),
            "duration": validated.get("duration"),
        }

        # Log the coupon application
        try:
            from app.core.upgrade_events import log_upgrade_event
            log_upgrade_event(
                "coupon_applied", org_id,
                metadata={"coupon_code": coupon_code, "coupon_id": coupon_id},
            )
        except Exception:
            pass

        return {"success": True, "message": "Coupon applied successfully", "discount": discount_info}

    except Exception as exc:
        logger.warning("apply_coupon failed org=%s: %s", org_id, str(exc)[:200])
        return {"success": False, "message": f"Failed to apply coupon: {str(exc)[:100]}", "discount": None}


# ── Get current discount on org ───────────────────────────────────────────────


def get_org_discount(org_id: str) -> Optional[Dict[str, Any]]:
    """
    Check if the org's subscription has an active discount.
    Returns discount details or None.
    """
    if not _stripe_available():
        return None

    try:
        stripe = _init_stripe()
        from app.core.database import get_supabase_admin

        admin_sb = get_supabase_admin()
        res = (
            admin_sb.table("organizations")
            .select("stripe_customer_id")
            .eq("id", org_id)
            .single()
            .execute()
        )
        customer_id = (res.data or {}).get("stripe_customer_id")
        if not customer_id:
            return None

        subs = stripe.Subscription.list(customer=customer_id, limit=1)
        if not subs.data:
            return None

        sub = subs.data[0]
        discount = getattr(sub, "discount", None)
        if not discount or not discount.coupon:
            return None

        coupon = discount.coupon
        return {
            "coupon_id": coupon.id,
            "name": coupon.name or coupon.id,
            "percent_off": coupon.percent_off,
            "amount_off": coupon.amount_off,
            "currency": coupon.currency,
            "duration": coupon.duration,
            "start": discount.start,
            "end": discount.end,
        }

    except Exception as exc:
        logger.debug("get_org_discount failed org=%s: %s", org_id, str(exc)[:120])
        return None
