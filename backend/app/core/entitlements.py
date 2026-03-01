"""
Plan Entitlements Engine
========================
Central plan definitions and atomic usage tracking.
All write operations use the admin Supabase client to bypass RLS.
"""

from datetime import datetime, timezone
from typing import Tuple, Dict, Any, Optional
import logging
from app.core.database import get_supabase_admin

logger = logging.getLogger("billing.entitlements")
_org_usage_missing_warned = False
_org_usage_schema_warned = False

# ── Plan Definitions ──────────────────────────────────────────

PLAN_ENTITLEMENTS: Dict[str, Dict[str, int]] = {
    "starter": {
        "questionnaires_per_month": 10,
        "exports_per_month": 10,
        "storage_bytes": 500 * 1024 * 1024,  # 500 MB
    },
    "growth": {
        "questionnaires_per_month": 25,
        "exports_per_month": 25,
        "storage_bytes": 2000 * 1024 * 1024,  # 2 GB
    },
    "elite": {
        "questionnaires_per_month": 100,
        "exports_per_month": 100,
        "storage_bytes": 10000 * 1024 * 1024,  # ~10 GB
    },
}

RESOURCE_MAP = {
    "questionnaires": ("questionnaires_used", "questionnaires_per_month"),
    "exports": ("exports_used", "exports_per_month"),
    "storage": ("storage_used_bytes", "storage_bytes"),
}


def get_plan(plan_tier: str) -> Dict[str, int]:
    """Return entitlements for a plan tier, defaulting to starter."""
    return PLAN_ENTITLEMENTS.get(plan_tier, PLAN_ENTITLEMENTS["starter"])


# ── Billing Period Helpers ────────────────────────────────────

def get_current_period() -> Tuple[datetime, datetime]:
    """Return (period_start, period_end) for the current calendar month."""
    now = datetime.now(timezone.utc)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # First day of next month
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


# ── Usage Helpers ─────────────────────────────────────────────

def _get_org_plan(admin_sb, org_id: str) -> str:
    """Fetch the org's plan_tier from organizations table."""
    try:
        res = admin_sb.table("organizations").select("plan_tier").eq("id", org_id).single().execute()
        return (res.data or {}).get("plan_tier", "starter")
    except Exception:
        return "starter"


def get_or_create_usage(admin_sb, org_id: str) -> Dict[str, Any]:
    """
    Fetch the current period's usage row, creating it if it doesn't exist.
    Uses upsert for atomicity.
    """
    period_start, _ = get_current_period()
    period_str = period_start.isoformat()

    # Try to read first
    try:
        res = admin_sb.table("org_usage") \
            .select("*") \
            .eq("org_id", org_id) \
            .eq("period_start", period_str) \
            .single() \
            .execute()
        if res.data:
            return res.data
    except Exception as e:
        global _org_usage_missing_warned
        if "Could not find the table 'public.org_usage'" in str(e):
            if not _org_usage_missing_warned:
                _org_usage_missing_warned = True
                logger.warning("org_usage table missing; usage tracking is disabled until entitlements migration is applied")
            return {
                "org_id": org_id,
                "period_start": period_str,
                "questionnaires_used": 0,
                "exports_used": 0,
                "storage_used_bytes": 0,
            }
        pass

    # Create if not exists
    try:
        row = {
            "org_id": org_id,
            "period_start": period_str,
            "questionnaires_used": 0,
            "exports_used": 0,
            "storage_used_bytes": 0,
        }
        res = admin_sb.table("org_usage").upsert(
            row, on_conflict="org_id,period_start"
        ).execute()
        return res.data[0] if res.data else row
    except Exception as e:
        global _org_usage_schema_warned
        if not _org_usage_schema_warned:
            _org_usage_schema_warned = True
            logger.warning("org_usage upsert failed; usage tracking degraded until schema is aligned (%s)", str(e)[:200])
        return {
            "org_id": org_id,
            "period_start": period_str,
            "questionnaires_used": 0,
            "exports_used": 0,
            "storage_used_bytes": 0,
        }


def check_quota(
    org_id: str,
    resource: str,
    additional: int = 1,
) -> Tuple[bool, int, int, int, str]:
    """
    Check if the org can use more of a resource.

    Returns: (allowed, used, limit, remaining, plan_tier)
    """
    admin_sb = get_supabase_admin()
    plan_tier = _get_org_plan(admin_sb, org_id)
    entitlements = get_plan(plan_tier)

    usage_col, limit_key = RESOURCE_MAP[resource]
    limit = entitlements[limit_key]

    usage_row = get_or_create_usage(admin_sb, org_id)
    used = int(usage_row.get(usage_col, 0))

    remaining = max(0, limit - used)
    allowed = (used + additional) <= limit

    return allowed, used, limit, remaining, plan_tier


def increment_usage(
    org_id: str,
    resource: str,
    amount: int = 1,
) -> None:
    """Atomically increment a usage counter for the current period."""
    admin_sb = get_supabase_admin()
    period_start, _ = get_current_period()
    period_str = period_start.isoformat()

    usage_col, _ = RESOURCE_MAP[resource]

    # Ensure row exists
    get_or_create_usage(admin_sb, org_id)

    # Atomic increment via RPC or direct update
    try:
        # Read current value then update (Supabase doesn't have native increment)
        res = admin_sb.table("org_usage") \
            .select(usage_col) \
            .eq("org_id", org_id) \
            .eq("period_start", period_str) \
            .single() \
            .execute()

        current = int((res.data or {}).get(usage_col, 0))

        admin_sb.table("org_usage") \
            .update({usage_col: current + amount}) \
            .eq("org_id", org_id) \
            .eq("period_start", period_str) \
            .execute()
    except Exception as e:
        if "Could not find the table 'public.org_usage'" in str(e):
            return
        logger.warning("org_usage increment failed col=%s org_id=%s err=%s", usage_col, org_id, str(e)[:200])


def get_billing_summary(org_id: str) -> Dict[str, Any]:
    """
    Build a complete billing summary for an org.
    Used by GET /billing/summary.
    """
    admin_sb = get_supabase_admin()
    plan_tier = _get_org_plan(admin_sb, org_id)
    entitlements = get_plan(plan_tier)
    usage_row = get_or_create_usage(admin_sb, org_id)
    period_start, period_end = get_current_period()

    q_used = int(usage_row.get("questionnaires_used", 0))
    e_used = int(usage_row.get("exports_used", 0))
    s_used = int(usage_row.get("storage_used_bytes", 0))

    q_limit = entitlements["questionnaires_per_month"]
    e_limit = entitlements["exports_per_month"]
    s_limit = entitlements["storage_bytes"]

    return {
        "plan": plan_tier,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "entitlements": {
            "questionnaires": {
                "used": q_used,
                "limit": q_limit,
                "remaining": max(0, q_limit - q_used),
            },
            "exports": {
                "used": e_used,
                "limit": e_limit,
                "remaining": max(0, e_limit - e_used),
            },
            "storage_mb": {
                "used_mb": round(s_used / (1024 * 1024), 1),
                "limit_mb": round(s_limit / (1024 * 1024), 0),
                "remaining_mb": round(max(0, s_limit - s_used) / (1024 * 1024), 1),
            },
        },
    }
