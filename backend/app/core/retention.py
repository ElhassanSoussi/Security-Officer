"""
Phase 21 Part 3: Data Retention Controls.

Implements configurable data retention with soft-delete for compliance runs.
Evidence vault records are preserved (never auto-deleted).
All retention actions are logged to the audit trail.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

from app.core.config import get_settings

logger = logging.getLogger("core.retention")


def get_retention_cutoff() -> datetime:
    """Return the datetime before which runs are eligible for retention cleanup."""
    settings = get_settings()
    days = settings.DATA_RETENTION_DAYS
    return datetime.now(timezone.utc) - timedelta(days=days)


def run_retention_job(
    supabase_admin,
    *,
    org_id: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Soft-delete runs older than DATA_RETENTION_DAYS.

    Rules:
    - Only marks runs with retention_deleted_at = now() (soft delete)
    - Skips runs that already have retention_deleted_at set
    - Preserves evidence_records (evidence vault is never auto-purged)
    - Logs each retention action to activity_log

    Returns a summary dict with counts.
    """
    settings = get_settings()
    cutoff = get_retention_cutoff()

    result = {
        "retention_days": settings.DATA_RETENTION_DAYS,
        "cutoff_date": cutoff.isoformat(),
        "dry_run": dry_run,
        "runs_processed": 0,
        "runs_skipped": 0,
        "errors": [],
    }

    try:
        # Find eligible runs
        query = (
            supabase_admin.table("runs")
            .select("id, org_id, created_at, status")
            .lt("created_at", cutoff.isoformat())
            .is_("retention_deleted_at", "null")
            .limit(500)
        )
        if org_id:
            query = query.eq("org_id", org_id)

        resp = query.execute()
        eligible_runs = resp.data or []

        if dry_run:
            result["runs_processed"] = len(eligible_runs)
            result["message"] = "Dry run — no changes made"
            return result

        now = datetime.now(timezone.utc).isoformat()
        for run in eligible_runs:
            try:
                supabase_admin.table("runs").update({
                    "retention_deleted_at": now,
                }).eq("id", run["id"]).execute()
                result["runs_processed"] += 1

                # Log retention event (best effort)
                try:
                    from app.core.audit_events import log_activity_event
                    log_activity_event(
                        supabase_admin,
                        org_id=run.get("org_id", ""),
                        user_id="system:retention",
                        action_type="retention_soft_delete",
                        entity_type="run",
                        entity_id=run["id"],
                        metadata={
                            "retention_days": settings.DATA_RETENTION_DAYS,
                            "run_created_at": run.get("created_at"),
                        },
                    )
                except Exception:
                    pass  # Never block retention on audit failure

            except Exception as e:
                result["runs_skipped"] += 1
                result["errors"].append({
                    "run_id": run.get("id"),
                    "error": str(e)[:200],
                })

    except Exception as e:
        result["errors"].append({"error": str(e)[:200]})
        logger.warning("retention_job_failed: %s", str(e)[:200])

    return result
