"""
Deterministic Subscription Tier Enforcement
============================================

Canonical Plan enum, Stripe price-ID mapping, and server-side
feature-limit enforcement.

Usage::

    from app.core.plan_service import Plan, PlanService

    PlanService.enforce_runs_limit(org_id)      # raises HTTP 403 when over
    PlanService.enforce_documents_limit(org_id)  # raises HTTP 403 when over
    PlanService.enforce_projects_limit(org_id)   # raises HTTP 403 when over

    limits = PlanService.get_limits(Plan.GROWTH)
    plan   = PlanService.resolve_price_id("price_abc123")

All DB reads use the admin client (bypass RLS).
All failures degrade gracefully — never crash the calling endpoint.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from fastapi import HTTPException

logger = logging.getLogger("billing.plan_service")


# ─── Plan Enum ─────────────────────────────────────────────────────────────────

class Plan(str, Enum):
    """Canonical subscription tier."""
    STARTER = "starter"
    GROWTH = "growth"
    ELITE = "elite"


# ─── Feature Limits per Plan ──────────────────────────────────────────────────

PLAN_LIMITS: Dict[Plan, Dict[str, int]] = {
    Plan.STARTER: {
        "max_projects": 5,
        "max_documents": 25,
        "max_runs_per_month": 10,
    },
    Plan.GROWTH: {
        "max_projects": 25,
        "max_documents": 500,
        "max_runs_per_month": 100,
    },
    Plan.ELITE: {
        "max_projects": 10_000,
        "max_documents": 100_000,
        "max_runs_per_month": 10_000,
    },
}

# ─── Next-Tier Ladder ────────────────────────────────────────────────────────

PLAN_NEXT_TIER: Dict[Plan, Optional[Plan]] = {
    Plan.STARTER: Plan.GROWTH,
    Plan.GROWTH:  Plan.ELITE,
    Plan.ELITE:   None,
}


def get_next_tier(plan: Plan) -> Optional[Plan]:
    """Return the next upgrade tier, or None if already at the top."""
    return PLAN_NEXT_TIER.get(plan)


# ─── Stripe Price ID → Plan Mapping ──────────────────────────────────────────

def _build_price_to_plan() -> Dict[str, Plan]:
    """
    Build a deterministic mapping of Stripe Price IDs → Plan enum values.

    Reads from environment variables:
        STRIPE_PRICE_STARTER  → Plan.STARTER
        STRIPE_PRICE_GROWTH   → Plan.GROWTH
        STRIPE_PRICE_ELITE    → Plan.ELITE

    Also supports the legacy FREE/PRO/ENTERPRISE naming:
        STRIPE_PRICE_FREE       → Plan.STARTER
        STRIPE_PRICE_PRO        → Plan.GROWTH
        STRIPE_PRICE_ENTERPRISE → Plan.ELITE
    """
    mapping: Dict[str, Plan] = {}

    pairs = [
        ("STRIPE_PRICE_STARTER", Plan.STARTER),
        ("STRIPE_PRICE_GROWTH", Plan.GROWTH),
        ("STRIPE_PRICE_ELITE", Plan.ELITE),
        # Legacy aliases
        ("STRIPE_PRICE_FREE", Plan.STARTER),
        ("STRIPE_PRICE_PRO", Plan.GROWTH),
        ("STRIPE_PRICE_ENTERPRISE", Plan.ELITE),
    ]
    for env_key, plan in pairs:
        price_id = os.getenv(env_key, "").strip()
        if price_id:
            mapping[price_id] = plan

    return mapping


def resolve_price_id(price_id: str) -> Optional[Plan]:
    """Return the Plan for a Stripe price ID, or None if unknown."""
    return _build_price_to_plan().get(price_id)


# ─── Internal Helpers ─────────────────────────────────────────────────────────

def _admin_sb():
    from app.core.database import get_supabase_admin
    return get_supabase_admin()


def _get_org_plan(org_id: str) -> Plan:
    """Read the org's plan from the organizations table.  Defaults to STARTER."""
    try:
        sb = _admin_sb()
        res = (
            sb.table("organizations")
            .select("plan")
            .eq("id", org_id)
            .single()
            .execute()
        )
        raw = (res.data or {}).get("plan", "starter")
        return Plan(raw)
    except (ValueError, KeyError):
        return Plan.STARTER
    except Exception as e:
        # Fallback: try plan_tier column for backward compat
        try:
            sb = _admin_sb()
            res = (
                sb.table("organizations")
                .select("plan_tier")
                .eq("id", org_id)
                .single()
                .execute()
            )
            raw = (res.data or {}).get("plan_tier", "starter")
            return Plan(raw)
        except Exception:
            pass
        _table_missing = "Could not find" in str(e) or "does not exist" in str(e)
        if not _table_missing:
            logger.warning("_get_org_plan failed org=%s: %s", org_id, str(e)[:120])
        return Plan.STARTER


def _current_month_start() -> str:
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()


def _raise_limit_exceeded(resource: str, current: int, limit: int, plan: Plan) -> None:
    """Raise a structured HTTP 403 when a plan limit is exceeded."""
    next_plan = get_next_tier(plan)
    raise HTTPException(
        status_code=403,
        detail={
            "error": "plan_limit_exceeded",
            "message": "Upgrade required to continue",
            "resource": resource,
            # Canonical fields (new)
            "current_plan": plan.value,
            "used": current,
            "limit": limit,
            "next_plan": next_plan.value if next_plan else None,
            # Legacy aliases — kept for backward compat
            "plan": plan.value,
            "current_count": current,
        },
    )


# ─── PlanService ──────────────────────────────────────────────────────────────

class PlanService:
    """Server-side feature-limit enforcement tied to the org's subscription plan."""

    # ── Read ──────────────────────────────────────────────────

    @staticmethod
    def get_limits(plan: Plan) -> Dict[str, int]:
        """Return the feature-limit dict for a plan."""
        return dict(PLAN_LIMITS.get(plan, PLAN_LIMITS[Plan.STARTER]))

    @staticmethod
    def get_next_tier(plan: Plan) -> Optional[Plan]:
        """Return the next upgrade tier above *plan*, or None if already at Elite."""
        return get_next_tier(plan)

    @staticmethod
    def get_org_plan(org_id: str) -> Plan:
        """Public accessor: return the Plan enum for an org."""
        return _get_org_plan(org_id)

    @staticmethod
    def resolve_price_id(price_id: str) -> Optional[Plan]:
        """Map a Stripe Price ID to a Plan."""
        return resolve_price_id(price_id)

    # ── Write (called from webhook handlers) ──────────────────

    @staticmethod
    def set_org_plan(org_id: str, plan: Plan, stripe_price_id: Optional[str] = None,
                     subscription_status: Optional[str] = None) -> None:
        """
        Persist the plan determination on the organizations row.
        Updates both ``plan`` and legacy ``plan_tier`` for backward compat.
        """
        try:
            sb = _admin_sb()
            update: Dict[str, Any] = {"plan": plan.value, "plan_tier": plan.value}
            if stripe_price_id is not None:
                update["stripe_price_id"] = stripe_price_id
            if subscription_status is not None:
                update["subscription_status"] = subscription_status
            sb.table("organizations").update(update).eq("id", org_id).execute()
        except Exception as e:
            logger.warning("set_org_plan failed org=%s plan=%s: %s", org_id, plan.value, str(e)[:120])

    # ── Enforcement ───────────────────────────────────────────

    @staticmethod
    def enforce_runs_limit(org_id: str) -> None:
        """Raise HTTP 403 if the org has reached its monthly run limit."""
        try:
            plan = _get_org_plan(org_id)
            limits = PLAN_LIMITS[plan]
            max_runs = limits["max_runs_per_month"]

            sb = _admin_sb()
            month_start = _current_month_start()
            res = (
                sb.table("runs")
                .select("id", count="exact")
                .eq("org_id", org_id)
                .gte("created_at", month_start)
                .execute()
            )
            count = res.count if res.count is not None else 0

            if count >= max_runs:
                try:
                    from app.core.upgrade_events import log_upgrade_event
                    log_upgrade_event(
                        "limit_hit", org_id,
                        metadata={"resource": "runs", "current_plan": plan.value,
                                  "used": count, "limit": max_runs},
                    )
                except Exception:
                    pass
                _raise_limit_exceeded("runs", count, max_runs, plan)
        except HTTPException:
            raise
        except Exception as e:
            _table_missing = "Could not find" in str(e) or "does not exist" in str(e)
            if not _table_missing:
                logger.warning("enforce_runs_limit failed org=%s: %s", org_id, str(e)[:120])
            # Fail-open

    @staticmethod
    def enforce_documents_limit(org_id: str) -> None:
        """Raise HTTP 403 if the org has reached its total document limit."""
        try:
            plan = _get_org_plan(org_id)
            limits = PLAN_LIMITS[plan]
            max_docs = limits["max_documents"]

            sb = _admin_sb()
            res = (
                sb.table("documents")
                .select("id", count="exact")
                .eq("org_id", org_id)
                .execute()
            )
            count = res.count if res.count is not None else 0

            if count >= max_docs:
                try:
                    from app.core.upgrade_events import log_upgrade_event
                    log_upgrade_event(
                        "limit_hit", org_id,
                        metadata={"resource": "documents", "current_plan": plan.value,
                                  "used": count, "limit": max_docs},
                    )
                except Exception:
                    pass
                _raise_limit_exceeded("documents", count, max_docs, plan)
        except HTTPException:
            raise
        except Exception as e:
            _table_missing = "Could not find" in str(e) or "does not exist" in str(e)
            if not _table_missing:
                logger.warning("enforce_documents_limit failed org=%s: %s", org_id, str(e)[:120])

    @staticmethod
    def enforce_projects_limit(org_id: str) -> None:
        """Raise HTTP 403 if the org has reached its project limit."""
        try:
            plan = _get_org_plan(org_id)
            limits = PLAN_LIMITS[plan]
            max_projects = limits["max_projects"]

            sb = _admin_sb()
            res = (
                sb.table("projects")
                .select("id", count="exact")
                .eq("org_id", org_id)
                .execute()
            )
            count = res.count if res.count is not None else 0

            if count >= max_projects:
                try:
                    from app.core.upgrade_events import log_upgrade_event
                    log_upgrade_event(
                        "limit_hit", org_id,
                        metadata={"resource": "projects", "current_plan": plan.value,
                                  "used": count, "limit": max_projects},
                    )
                except Exception:
                    pass
                _raise_limit_exceeded("projects", count, max_projects, plan)
        except HTTPException:
            raise
        except Exception as e:
            _table_missing = "Could not find" in str(e) or "does not exist" in str(e)
            if not _table_missing:
                logger.warning("enforce_projects_limit failed org=%s: %s", org_id, str(e)[:120])
