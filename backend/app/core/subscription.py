"""
Phase 18 — Subscription Plan Model + Usage Metrics Tracking
============================================================

Responsibilities:
  • get_org_subscription(org_id)           → plan dict with limits
  • check_plan_limit(org_id, resource)     → raises 402 if over limit
  • log_usage_metric(org_id, metric_type) → fire-and-forget metric insert
  • get_usage_summary(org_id)              → current-month counts

Resource keys accepted by check_plan_limit / log_usage_metric:
  "runs"      → max_runs_per_month  / RUN_CREATED
  "documents" → max_documents       / DOCUMENT_UPLOADED
  "memory"    → max_memory_entries  / MEMORY_STORED
  "evidence"  → n/a (unmetered)     / EVIDENCE_GENERATED

All DB writes use the admin client to bypass RLS.
All failures degrade gracefully (never crash the calling endpoint).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from fastapi import HTTPException

logger = logging.getLogger("billing.subscription")

# ─── Plan Definitions ─────────────────────────────────────────────────────────

PLAN_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "FREE": {
        "plan_name": "FREE",
        "max_runs_per_month": 10,
        "max_documents": 25,
        "max_memory_entries": 100,
    },
    "PRO": {
        "plan_name": "PRO",
        "max_runs_per_month": 100,
        "max_documents": 500,
        "max_memory_entries": 2000,
    },
    "ENTERPRISE": {
        "plan_name": "ENTERPRISE",
        "max_runs_per_month": 10_000,
        "max_documents": 100_000,
        "max_memory_entries": 1_000_000,
    },
}

# Map resource key → (DB column for counting, limit field, metric_type)
RESOURCE_MAP: Dict[str, tuple] = {
    "runs":      ("RUN_CREATED",       "max_runs_per_month"),
    "documents": ("DOCUMENT_UPLOADED", "max_documents"),
    "memory":    ("MEMORY_STORED",     "max_memory_entries"),
    "evidence":  ("EVIDENCE_GENERATED", None),  # no hard limit, just tracked
}


def _admin_sb():
    from app.core.database import get_supabase_admin
    return get_supabase_admin()


def _current_month_start() -> str:
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()


# ─── Subscription Lookup ──────────────────────────────────────────────────────

def get_org_subscription(org_id: str) -> Dict[str, Any]:
    """
    Return the subscription row for org_id.
    Falls back to FREE defaults if table missing or no row found.
    Never raises — always returns a valid plan dict.
    """
    try:
        sb = _admin_sb()
        res = (
            sb.table("subscriptions")
            .select("plan_name, max_runs_per_month, max_documents, max_memory_entries")
            .eq("org_id", org_id)
            .single()
            .execute()
        )
        if res.data:
            return dict(res.data)
    except Exception as e:
        _table_missing = "Could not find" in str(e) or "does not exist" in str(e)
        if not _table_missing:
            logger.warning("get_org_subscription failed org_id=%s: %s", org_id, str(e)[:120])

    # Default: FREE plan
    return dict(PLAN_DEFAULTS["FREE"])


# ─── Soft Limit Enforcement ───────────────────────────────────────────────────

def check_plan_limit(org_id: str, resource: str) -> None:
    """
    Enforce the subscription limit for the given resource.

    Raises HTTPException 402 with code PLAN_LIMIT_REACHED if over limit.
    Silently passes on any DB error (fail-open for reliability).

    resource: "runs" | "documents" | "memory"
    """
    if resource not in RESOURCE_MAP:
        return  # unknown resource → skip

    metric_type, limit_field = RESOURCE_MAP[resource]
    if limit_field is None:
        return  # unmetered resource

    try:
        plan = get_org_subscription(org_id)
        limit: int = plan.get(limit_field, 10_000)

        # Count current-month usage
        sb = _admin_sb()
        month_start = _current_month_start()

        # For documents and memory: count total, not monthly
        if resource in ("documents", "memory"):
            res = (
                sb.table("usage_metrics")
                .select("id", count="exact")
                .eq("org_id", org_id)
                .eq("metric_type", metric_type)
                .execute()
            )
        else:
            # Runs: monthly count
            res = (
                sb.table("usage_metrics")
                .select("id", count="exact")
                .eq("org_id", org_id)
                .eq("metric_type", metric_type)
                .gte("created_at", month_start)
                .execute()
            )

        count = res.count if res.count is not None else 0

        if count >= limit:
            plan_name = plan.get("plan_name", "FREE")
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "PLAN_LIMIT_REACHED",
                    "detail": f"Upgrade required to create additional {resource}.",
                    "current_count": count,
                    "limit": limit,
                    "plan": plan_name,
                    "resource": resource,
                },
            )
    except HTTPException:
        raise
    except Exception as e:
        _table_missing = "Could not find" in str(e) or "does not exist" in str(e)
        if not _table_missing:
            logger.warning("check_plan_limit failed org_id=%s resource=%s: %s", org_id, resource, str(e)[:120])
        # Fail-open: don't block on DB errors


# ─── Usage Metric Logging ─────────────────────────────────────────────────────

def log_usage_metric(org_id: str, metric_type: str) -> None:
    """
    Fire-and-forget: insert one row into usage_metrics.
    Valid metric_type values: RUN_CREATED, DOCUMENT_UPLOADED, MEMORY_STORED, EVIDENCE_GENERATED.
    Never raises.
    """
    if not org_id or not metric_type:
        return
    try:
        sb = _admin_sb()
        sb.table("usage_metrics").insert(
            {"org_id": org_id, "metric_type": metric_type}
        ).execute()
    except Exception as e:
        _table_missing = "Could not find" in str(e) or "does not exist" in str(e)
        if not _table_missing:
            logger.warning("log_usage_metric failed org_id=%s type=%s: %s", org_id, metric_type, str(e)[:120])


# ─── Usage Summary ────────────────────────────────────────────────────────────

def get_usage_summary(org_id: str) -> Dict[str, Any]:
    """
    Return current-month usage counts for the dashboard Usage panel.
    Returns zero-counts on any error.
    """
    month_start = _current_month_start()
    defaults = {
        "runs_this_month": 0,
        "documents_total": 0,
        "memory_entries_total": 0,
        "evidence_exports_total": 0,
        "plan": "FREE",
        "limits": PLAN_DEFAULTS["FREE"],
    }
    try:
        sb = _admin_sb()

        def _count(metric: str, monthly: bool) -> int:
            q = (
                sb.table("usage_metrics")
                .select("id", count="exact")
                .eq("org_id", org_id)
                .eq("metric_type", metric)
            )
            if monthly:
                q = q.gte("created_at", month_start)
            res = q.execute()
            return res.count or 0

        plan = get_org_subscription(org_id)
        return {
            "runs_this_month": _count("RUN_CREATED", monthly=True),
            "documents_total": _count("DOCUMENT_UPLOADED", monthly=False),
            "memory_entries_total": _count("MEMORY_STORED", monthly=False),
            "evidence_exports_total": _count("EVIDENCE_GENERATED", monthly=False),
            "plan": plan.get("plan_name", "FREE"),
            "limits": plan,
        }
    except Exception as e:
        _table_missing = "Could not find" in str(e) or "does not exist" in str(e)
        if not _table_missing:
            logger.warning("get_usage_summary failed org_id=%s: %s", org_id, str(e)[:120])
        return defaults
