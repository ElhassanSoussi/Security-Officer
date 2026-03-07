"""
document_expiry_service.py — Document Expiry & Re-run Alerts
=============================================================

Provides:
  • get_expiring_documents(org_id, days_ahead) → list of expiring/expired docs
  • check_and_notify_expiry(org_id) → sends email alerts for expiring documents
  • get_rerun_candidates(org_id) → docs that need a compliance re-run
  • get_expiry_summary(org_id) → aggregate counts by status

Works org-wide across all projects.
Uses the existing expiration.py engine for classification.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.core.expiration import classify_documents, compute_expiration_status

logger = logging.getLogger("core.document_expiry")

# How many days before expiry to trigger alerts
DEFAULT_ALERT_DAYS = 30

# Re-run threshold: documents whose last run is older than this get flagged
RERUN_STALE_DAYS = 90


def get_expiring_documents(
    org_id: str,
    days_ahead: int = DEFAULT_ALERT_DAYS,
    include_expired: bool = True,
) -> List[Dict[str, Any]]:
    """
    Return all documents in the org that are expiring within `days_ahead` days
    (and optionally already expired).

    Each result has:
      id, filename, project_id, project_name, expiration_date,
      status ('expiring'|'expired'), days_remaining
    """
    try:
        from app.core.database import get_supabase_admin
        admin_sb = get_supabase_admin()

        # Fetch all project_documents for this org that have expiration dates
        res = (
            admin_sb.table("project_documents")
            .select("document_id, display_name, project_id, expiration_date, reminder_days_before, created_at")
            .eq("org_id", org_id)
            .not_.is_("expiration_date", "null")
            .execute()
        )
        docs = res.data or []

        # Enrich with project names
        project_ids = list({d["project_id"] for d in docs if d.get("project_id")})
        project_names: Dict[str, str] = {}
        if project_ids:
            try:
                proj_res = (
                    admin_sb.table("projects")
                    .select("id, name")
                    .in_("id", project_ids)
                    .execute()
                )
                project_names = {p["id"]: p.get("name", "Unknown") for p in (proj_res.data or [])}
            except Exception:
                pass

        # Classify
        classified = classify_documents(docs, reminder_days_before=days_ahead)

        results = []
        for doc in classified:
            status = doc.get("status", "no_expiration")
            if status == "no_expiration" or status == "valid":
                continue
            if status == "expired" and not include_expired:
                continue

            results.append({
                "id": doc.get("document_id"),
                "filename": doc.get("display_name", "Unknown"),
                "project_id": doc.get("project_id"),
                "project_name": project_names.get(doc.get("project_id", ""), "Unknown"),
                "expiration_date": doc.get("expiration_date"),
                "status": status,
                "days_remaining": doc.get("days_remaining"),
                "created_at": doc.get("created_at"),
            })

        # Sort: expired first, then by days_remaining ascending
        results.sort(key=lambda x: (
            0 if x["status"] == "expired" else 1,
            x.get("days_remaining") or 0,
        ))

        return results

    except Exception as exc:
        logger.warning("get_expiring_documents failed org=%s: %s", org_id, str(exc)[:200])
        return []


def get_rerun_candidates(
    org_id: str,
    stale_days: int = RERUN_STALE_DAYS,
) -> List[Dict[str, Any]]:
    """
    Return documents that haven't had a compliance run in `stale_days` days
    and should be re-analyzed.

    Each result: id, filename, project_id, project_name, last_run_at, days_since_run
    """
    try:
        from app.core.database import get_supabase_admin
        admin_sb = get_supabase_admin()

        cutoff = (datetime.now(timezone.utc) - timedelta(days=stale_days)).isoformat()

        # Get all documents in org
        docs_res = (
            admin_sb.table("documents")
            .select("id, filename, project_id, created_at")
            .eq("org_id", org_id)
            .execute()
        )
        docs = docs_res.data or []

        if not docs:
            return []

        # Get latest run per document
        doc_ids = [d["id"] for d in docs]
        last_runs: Dict[str, str] = {}
        try:
            # Get all runs for this org, grouped by document
            runs_res = (
                admin_sb.table("runs")
                .select("id, document_id, created_at")
                .eq("org_id", org_id)
                .order("created_at", desc=True)
                .execute()
            )
            for run in (runs_res.data or []):
                did = run.get("document_id")
                if did and did not in last_runs:
                    last_runs[did] = run["created_at"]
        except Exception:
            pass

        # Get project names
        project_ids = list({d["project_id"] for d in docs if d.get("project_id")})
        project_names: Dict[str, str] = {}
        if project_ids:
            try:
                proj_res = (
                    admin_sb.table("projects")
                    .select("id, name")
                    .in_("id", project_ids)
                    .execute()
                )
                project_names = {p["id"]: p.get("name", "Unknown") for p in (proj_res.data or [])}
            except Exception:
                pass

        results = []
        now = datetime.now(timezone.utc)
        for doc in docs:
            doc_id = doc["id"]
            last_run = last_runs.get(doc_id)

            if last_run:
                try:
                    run_dt = datetime.fromisoformat(last_run.replace("Z", "+00:00"))
                    days_since = (now - run_dt).days
                    if days_since < stale_days:
                        continue
                except Exception:
                    days_since = stale_days + 1
            else:
                # Never run — always a candidate
                days_since = None

            results.append({
                "id": doc_id,
                "filename": doc.get("filename", "Unknown"),
                "project_id": doc.get("project_id"),
                "project_name": project_names.get(doc.get("project_id", ""), "Unknown"),
                "last_run_at": last_run,
                "days_since_run": days_since,
            })

        results.sort(key=lambda x: (x["days_since_run"] is None, -(x["days_since_run"] or 0)))
        return results

    except Exception as exc:
        logger.warning("get_rerun_candidates failed org=%s: %s", org_id, str(exc)[:200])
        return []


def get_expiry_summary(org_id: str, days_ahead: int = DEFAULT_ALERT_DAYS) -> Dict[str, Any]:
    """
    Return aggregate counts for document expiry and re-run status.

    Shape: {
        expiring_count, expired_count, rerun_needed_count,
        total_alerts, expiring_docs, expired_docs, rerun_docs
    }
    """
    expiring_docs = get_expiring_documents(org_id, days_ahead=days_ahead, include_expired=True)
    rerun_docs = get_rerun_candidates(org_id)

    expiring = [d for d in expiring_docs if d["status"] == "expiring"]
    expired = [d for d in expiring_docs if d["status"] == "expired"]

    return {
        "expiring_count": len(expiring),
        "expired_count": len(expired),
        "rerun_needed_count": len(rerun_docs),
        "total_alerts": len(expiring) + len(expired) + len(rerun_docs),
        "expiring_docs": expiring[:20],  # Limit for response size
        "expired_docs": expired[:20],
        "rerun_docs": rerun_docs[:20],
    }


def check_and_notify_expiry(org_id: str, days_ahead: int = DEFAULT_ALERT_DAYS) -> Dict[str, Any]:
    """
    Check for expiring/expired documents and send email alerts.
    Returns summary of what was found and whether notifications were sent.
    """
    summary = get_expiry_summary(org_id, days_ahead)

    if summary["total_alerts"] == 0:
        return {"alerts_found": 0, "notifications_sent": False}

    # Try to send email to org owner
    notifications_sent = False
    try:
        from app.core.database import get_supabase_admin
        from app.core.email_service import send_document_expiry_email

        admin_sb = get_supabase_admin()
        members = (
            admin_sb.table("memberships")
            .select("user_id, role")
            .eq("org_id", org_id)
            .eq("role", "owner")
            .limit(1)
            .execute()
        )
        if members.data:
            owner_id = members.data[0]["user_id"]
            profile = (
                admin_sb.table("profiles")
                .select("email")
                .eq("user_id", owner_id)
                .limit(1)
                .execute()
            )
            email = (profile.data[0].get("email") if profile.data else None)
            if email:
                doc_names = [d["filename"] for d in (summary["expiring_docs"] + summary["expired_docs"])[:5]]
                send_document_expiry_email(
                    to_email=email,
                    documents=doc_names,
                    days_until_expiry=days_ahead,
                )
                notifications_sent = True
    except Exception as exc:
        logger.debug("check_and_notify_expiry email failed: %s", str(exc)[:120])

    return {
        "alerts_found": summary["total_alerts"],
        "expiring_count": summary["expiring_count"],
        "expired_count": summary["expired_count"],
        "rerun_needed_count": summary["rerun_needed_count"],
        "notifications_sent": notifications_sent,
    }
