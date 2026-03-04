"""
upgrade_events.py — Upgrade Funnel Analytics Tracker
=====================================================

Best-effort, non-blocking writer for upgrade funnel events.
Writes to the ``upgrade_events`` table (created by migration 021).
Never raises — all errors are swallowed after one warning.

Usage::

    from app.core.upgrade_events import log_upgrade_event, get_upgrade_analytics

    log_upgrade_event("limit_hit", org_id, metadata={"resource": "projects", ...})
    analytics = get_upgrade_analytics(org_id)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from app.core.database import get_supabase_admin  # noqa: F401 — re-exported for test patching
from app.core.audit_events import sanitize_metadata  # noqa: F401

logger = logging.getLogger("billing.upgrade_events")

_missing_table_warned = False

# ── Allowed event types ───────────────────────────────────────────────────────

UPGRADE_EVENT_TYPES = frozenset(
    {
        "limit_hit",
        "upgrade_modal_shown",
        "upgrade_clicked",
        "stripe_portal_redirected",
        "stripe_portal_returned",
        "plan_upgraded",
    }
)


# ── Writer ────────────────────────────────────────────────────────────────────


def log_upgrade_event(
    event_type: str,
    org_id: str,
    user_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Append one upgrade-funnel event row.  Org-scoped only.
    Silent on table-missing; logs a one-time warning.
    """
    if not event_type or not org_id:
        return
    if event_type not in UPGRADE_EVENT_TYPES:
        logger.debug("log_upgrade_event: unknown event_type=%s — skipped", event_type)
        return

    payload: Dict[str, Any] = {
        "org_id": org_id,
        "event_type": event_type,
        "user_id": user_id or "",
        "metadata": sanitize_metadata(metadata) or {},
    }

    try:
        sb = get_supabase_admin()
        sb.table("upgrade_events").insert(payload).execute()
    except Exception as exc:
        global _missing_table_warned
        err = str(exc)
        if "Could not find the table" in err or "upgrade_events" in err or "does not exist" in err:
            if not _missing_table_warned:
                _missing_table_warned = True
                logger.warning(
                    "upgrade_events table missing; "
                    "run backend/scripts/021_upgrade_analytics.sql to enable analytics"
                )
            return
        logger.debug("log_upgrade_event failed event_type=%s: %s", event_type, err[:200])


# ── Reader / aggregator ───────────────────────────────────────────────────────


def get_upgrade_analytics(org_id: str, days: int = 30) -> Dict[str, Any]:
    """
    Aggregate upgrade-funnel counts for *org_id* over the last *days* days.

    Returns::

        {
            "limit_hits":      int,
            "modal_shown":     int,
            "upgrade_clicks":  int,
            "conversions":     int,   # plan_upgraded events
            "top_resource":    str|None,
            "resource_hits":   {resource: count, ...},
        }

    Degrades gracefully on DB error (returns zeros).
    """
    _default: Dict[str, Any] = {
        "limit_hits": 0,
        "modal_shown": 0,
        "upgrade_clicks": 0,
        "conversions": 0,
        "top_resource": None,
        "resource_hits": {},
    }

    try:
        sb = get_supabase_admin()
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        res = (
            sb.table("upgrade_events")
            .select("event_type, metadata")
            .eq("org_id", org_id)
            .gte("created_at", since)
            .execute()
        )
        rows: list[dict] = res.data or []
    except Exception as exc:
        logger.warning("get_upgrade_analytics failed org=%s: %s", org_id, str(exc)[:200])
        return _default

    counts: Dict[str, int] = {}
    resource_hits: Dict[str, int] = {}

    for row in rows:
        et = row.get("event_type", "")
        counts[et] = counts.get(et, 0) + 1
        if et == "limit_hit":
            resource = str((row.get("metadata") or {}).get("resource", "unknown"))
            resource_hits[resource] = resource_hits.get(resource, 0) + 1

    top_resource: Optional[str] = (
        max(resource_hits, key=lambda k: resource_hits[k]) if resource_hits else None
    )

    return {
        "limit_hits": counts.get("limit_hit", 0),
        "modal_shown": counts.get("upgrade_modal_shown", 0),
        "upgrade_clicks": counts.get("upgrade_clicked", 0),
        "conversions": counts.get("plan_upgraded", 0),
        "top_resource": top_resource,
        "resource_hits": resource_hits,
    }
