import logging
import stripe
import os
from app.core.database import get_supabase_admin

logger = logging.getLogger("billing.manager")

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# ── Stripe Price ID mapping ──────────────────────────────────
PLAN_PRICE_MAP = {
    "starter": os.getenv("STRIPE_PRICE_STARTER", ""),
    "growth": os.getenv("STRIPE_PRICE_GROWTH", ""),
    "elite": os.getenv("STRIPE_PRICE_ELITE", ""),
}

PRICE_TO_PLAN = {v: k for k, v in PLAN_PRICE_MAP.items() if v}

# Plans page tier → plan_name mapping used for subscriptions table + webhook compatibility
TIER_TO_PLAN_NAME = {
    "starter": "FREE",
    "growth": "PRO",
    "elite": "ENTERPRISE",
}


class BillingManager:
    @staticmethod
    def create_checkout_session(
        org_id: str,
        plan_tier: str,
        success_url: str,
        cancel_url: str,
        customer_email: str | None = None,
        existing_customer_id: str | None = None,
    ) -> str:
        """Create a Stripe Checkout Session and return the URL."""
        if not stripe.api_key:
            raise Exception("Stripe API Key not configured")

        price_id = PLAN_PRICE_MAP.get(plan_tier)
        if not price_id:
            raise ValueError(f"No Stripe Price ID configured for plan: {plan_tier}")

        params: dict = {
            "mode": "subscription",
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "allow_promotion_codes": True,
            "metadata": {
                "org_id": org_id,
                "plan_tier": plan_tier,
                "plan_name": TIER_TO_PLAN_NAME.get(plan_tier, plan_tier.upper()),
            },
        }

        if existing_customer_id:
            params["customer"] = existing_customer_id
        elif customer_email:
            params["customer_email"] = customer_email

        # Best-effort: write a pending subscriptions row so incoming webhooks
        # can map the Stripe customer -> org. Don't fail the checkout on DB errors.
        try:
            admin_sb = get_supabase_admin()
            from app.core.subscription import PLAN_DEFAULTS

            mapped_plan = TIER_TO_PLAN_NAME.get(plan_tier, plan_tier.upper())
            limits = PLAN_DEFAULTS.get(mapped_plan, PLAN_DEFAULTS.get("FREE", {}))
            pending = {
                "org_id": org_id,
                "plan_name": mapped_plan,
                "stripe_status": "pending",
                "max_runs_per_month": limits.get("max_runs_per_month"),
                "max_documents": limits.get("max_documents"),
                "max_memory_entries": limits.get("max_memory_entries"),
            }
            admin_sb.table("subscriptions").upsert(pending, on_conflict="org_id").execute()
        except Exception as e:
            logger.warning("Failed to upsert pending subscription for org=%s: %s", org_id, str(e)[:120])

        session = stripe.checkout.Session.create(**params)
        return session.url

    @staticmethod
    def create_portal_session(customer_id: str, return_url: str) -> str:
        """Create a Stripe Billing Portal session."""
        if not stripe.api_key:
            raise Exception("Stripe API Key not configured")

        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )
        return session.url

    @staticmethod
    def check_export_quota(org_id: str, current_usage: int, limit: int):
        try:
            if current_usage >= limit:
                return False, "Export limit reached. Please upgrade your plan."
            return True, None
        except Exception as e:
            logger.warning("Billing check failed for org=%s: %s", org_id, str(e)[:120])
            return True, "Billing check bypassed"

    @staticmethod
    def construct_event(payload, sig_header, webhook_secret):
        return stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )

    # ── Webhook Event Handlers ────────────────────────────────

    @staticmethod
    def handle_checkout_completed(session_data: dict) -> None:
        """Handle checkout.session.completed — link Stripe customer to org."""
        admin_sb = get_supabase_admin()
        org_id = session_data.get("metadata", {}).get("org_id")
        plan_tier = session_data.get("metadata", {}).get("plan_tier", "starter")
        customer_id = session_data.get("customer")
        subscription_id = session_data.get("subscription")

        if not org_id:
            logger.warning("checkout.session.completed missing org_id in metadata")
            return

        update_data = {
            "stripe_customer_id": customer_id,
            "stripe_subscription_id": subscription_id,
            "plan_tier": plan_tier,
            "plan": plan_tier,
            "subscription_status": "active",
        }

        # Fetch subscription details for period dates
        stripe_price_id = None
        if subscription_id:
            try:
                sub = stripe.Subscription.retrieve(subscription_id)
                update_data["current_period_start"] = _ts_to_iso(sub.current_period_start)
                update_data["current_period_end"] = _ts_to_iso(sub.current_period_end)
                # Extract price ID for deterministic plan resolution
                items = (sub.get("items") or {}).get("data", [])
                if items:
                    stripe_price_id = items[0].get("price", {}).get("id")
            except Exception as e:
                logger.warning("Failed to fetch subscription details: %s", str(e)[:120])

        # Deterministic plan resolution from Stripe price ID
        try:
            from app.core.plan_service import PlanService, resolve_price_id, Plan
            if stripe_price_id:
                resolved = resolve_price_id(stripe_price_id)
                if resolved:
                    update_data["plan"] = resolved.value
                    update_data["plan_tier"] = resolved.value
                    update_data["stripe_price_id"] = stripe_price_id
            PlanService.set_org_plan(
                org_id,
                Plan(update_data.get("plan", plan_tier)),
                stripe_price_id=stripe_price_id,
                subscription_status="active",
            )
        except Exception as e:
            logger.warning("checkout plan resolution failed org=%s: %s", org_id, str(e)[:120])

        admin_sb.table("organizations").update(update_data).eq("id", org_id).execute()
        logger.info("checkout.session.completed: org=%s plan=%s", org_id, update_data.get("plan", plan_tier))

    @staticmethod
    def handle_subscription_updated(sub_data: dict) -> None:
        """Handle customer.subscription.updated — sync plan tier + status."""
        admin_sb = get_supabase_admin()
        customer_id = sub_data.get("customer")
        subscription_id = sub_data.get("id")
        status = sub_data.get("status", "active")

        # Determine plan from price
        price_id = ""
        items = sub_data.get("items", {}).get("data", [])
        if items:
            price_id = items[0].get("price", {}).get("id", "")
        plan_tier = PRICE_TO_PLAN.get(price_id, "starter")

        # Deterministic plan resolution via PlanService
        try:
            from app.core.plan_service import resolve_price_id as _resolve
            resolved = _resolve(price_id)
            if resolved:
                plan_tier = resolved.value
        except Exception:
            pass

        update_data = {
            "subscription_status": status,
            "plan_tier": plan_tier,
            "plan": plan_tier,
            "current_period_start": _ts_to_iso(sub_data.get("current_period_start")),
            "current_period_end": _ts_to_iso(sub_data.get("current_period_end")),
        }
        if price_id:
            update_data["stripe_price_id"] = price_id

        # Find org by stripe_customer_id
        res = admin_sb.table("organizations") \
            .select("id") \
            .eq("stripe_customer_id", customer_id) \
            .execute()

        if res.data:
            org_id = res.data[0]["id"]
            admin_sb.table("organizations").update(update_data).eq("id", org_id).execute()
            logger.info("subscription.updated: org=%s plan=%s status=%s", org_id, plan_tier, status)
        else:
            logger.warning("subscription.updated: no org found for customer=%s", customer_id)

    @staticmethod
    def handle_subscription_deleted(sub_data: dict) -> None:
        """Handle customer.subscription.deleted — downgrade to starter."""
        admin_sb = get_supabase_admin()
        customer_id = sub_data.get("customer")

        res = admin_sb.table("organizations") \
            .select("id") \
            .eq("stripe_customer_id", customer_id) \
            .execute()

        if res.data:
            org_id = res.data[0]["id"]
            admin_sb.table("organizations").update({
                "plan_tier": "starter",
                "plan": "starter",
                "subscription_status": "canceled",
                "stripe_subscription_id": None,
                "stripe_price_id": None,
            }).eq("id", org_id).execute()
            logger.info("subscription.deleted: org=%s → starter", org_id)

    @staticmethod
    def log_billing_event(org_id: str | None, event_id: str, event_type: str, payload: dict) -> None:
        """Log a Stripe event to billing_events table."""
        try:
            admin_sb = get_supabase_admin()
            admin_sb.table("billing_events").upsert({
                "org_id": org_id,
                "stripe_event_id": event_id,
                "type": event_type,
                "raw_payload": payload,
            }, on_conflict="stripe_event_id").execute()
        except Exception as e:
            logger.warning("Failed to log billing event %s: %s", event_id, str(e)[:120])


def _ts_to_iso(ts) -> str | None:
    """Convert a Unix timestamp to ISO string."""
    if not ts:
        return None
    from datetime import datetime, timezone
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()


billing_manager = BillingManager()
