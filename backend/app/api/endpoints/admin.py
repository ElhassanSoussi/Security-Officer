"""
Phase 21 Part 3 & 4: Admin & SOC2 Compliance Endpoints.

Endpoints:
  POST /admin/run-retention-job  → Admin-only data retention trigger
  GET  /orgs/{org_id}/access-report → Access audit report (JSON or CSV)
"""
import csv
import io
import logging
from datetime import datetime, timezone
from typing import Optional, Any, Dict, List
import asyncio

# Tests may call asyncio.get_event_loop().run_until_complete(...) without
# ensuring a loop exists; create and set a new loop when none is present.
try:
    asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.auth import get_current_user, require_user_id
from app.core.config import get_settings
from app.core.database import get_supabase, get_supabase_admin
from app.core.org_context import resolve_org_id_for_user
from app.core.rbac import Permission, get_user_role, role_has_permission

router = APIRouter()
security = HTTPBearer()
logger = logging.getLogger("api.admin")
settings = get_settings()


# ── Part 3: Retention Job Endpoint ────────────────────────────────────────────

@router.post("/admin/run-retention-job")
def trigger_retention_job(
    org_id: Optional[str] = Query(None, description="Scope to a specific org (optional)"),
    dry_run: bool = Query(False, description="Preview without making changes"),
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Phase 21: Trigger data retention cleanup (admin/owner only).

    Soft-deletes runs older than DATA_RETENTION_DAYS.
    Evidence vault records are preserved.
    """
    user_id = require_user_id(user)

    # If org_id provided, verify membership + admin/owner role
    if org_id:
        sb = get_supabase(token.credentials)
        org_id = resolve_org_id_for_user(sb, user_id, org_id, request=request)
        role = get_user_role(org_id, user_id, token.credentials)
        if role not in ("owner", "admin"):
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "forbidden",
                    "message": "Only owner or admin can run retention jobs",
                    "your_role": role or "none",
                },
            )
    else:
        # Without org_id, only allow if user has admin role in at least one org
        # For simplicity, require org_id for scoped operation
        raise HTTPException(
            status_code=400,
            detail={
                "error": "missing_org_id",
                "message": "org_id is required. Provide the organization to run retention for.",
            },
        )

    from app.core.retention import run_retention_job
    admin_sb = get_supabase_admin()

    # Log the retention trigger
    from app.core.audit_events import log_activity_event
    log_activity_event(
        admin_sb,
        org_id=org_id,
        user_id=user_id,
        action_type="retention_job_triggered",
        entity_type="system",
        metadata={
            "dry_run": dry_run,
            "retention_days": settings.DATA_RETENTION_DAYS,
        },
    )

    result = run_retention_job(admin_sb, org_id=org_id, dry_run=dry_run)
    return result


# ── Part 4: Access Audit Report ───────────────────────────────────────────────

@router.get("/orgs/{org_id}/access-report")
def get_access_report(
    org_id: str,
    format: str = Query("json", description="Output format: json or csv"),
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Phase 21: Access Audit Report for SOC2 compliance.

    Returns all members, roles, last activity, and evidence export summary.
    Supports JSON and CSV formats.
    Only accessible by owner/admin roles.
    """
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)
    org_id = resolve_org_id_for_user(sb, user_id, org_id, request=request)

    # Enforce admin/owner only
    role = get_user_role(org_id, user_id, token.credentials)
    if role not in ("owner", "admin"):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "forbidden",
                "message": "Only owner or admin can access the access audit report",
                "your_role": role or "none",
            },
        )

    admin_sb = get_supabase_admin()

    # Fetch members
    members_resp = (
        admin_sb.table("memberships")
        .select("user_id, role, created_at")
        .eq("org_id", org_id)
        .execute()
    )
    members = members_resp.data or []

    # Enrich with profile info + last activity
    report_rows = []
    for member in members:
        mid = member["user_id"]
        row = {
            "user_id": mid,
            "role": member.get("role", "viewer"),
            "member_since": member.get("created_at", ""),
            "email": "",
            "full_name": "",
            "last_activity": "",
            "activity_count": 0,
            "evidence_exports": 0,
        }

        # Profile lookup (best effort)
        try:
            prof = (
                admin_sb.table("profiles")
                .select("email, full_name")
                .eq("user_id", mid)
                .limit(1)
                .execute()
            )
            if prof.data:
                row["email"] = prof.data[0].get("email", "")
                row["full_name"] = prof.data[0].get("full_name", "")
        except Exception:
            pass

        # Last activity (best effort)
        try:
            act = (
                admin_sb.table("activity_log")
                .select("created_at")
                .eq("org_id", org_id)
                .eq("user_id", mid)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if act.data:
                row["last_activity"] = act.data[0].get("created_at", "")

            # Activity count
            count_resp = (
                admin_sb.table("activity_log")
                .select("id", count="exact")
                .eq("org_id", org_id)
                .eq("user_id", mid)
                .execute()
            )
            row["activity_count"] = count_resp.count or 0
        except Exception:
            pass

        # Evidence exports count (best effort)
        try:
            ev_resp = (
                admin_sb.table("evidence_records")
                .select("id", count="exact")
                .eq("org_id", org_id)
                .eq("generated_by", mid)
                .execute()
            )
            row["evidence_exports"] = ev_resp.count or 0
        except Exception:
            pass

        report_rows.append(row)

    # Log the report generation
    from app.core.audit_events import log_activity_event
    log_activity_event(
        admin_sb,
        org_id=org_id,
        user_id=user_id,
        action_type="access_report_generated",
        entity_type="org",
        entity_id=org_id,
        metadata={"format": format, "member_count": len(report_rows)},
    )

    report = {
        "org_id": org_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "retention_days": settings.DATA_RETENTION_DAYS,
        "total_members": len(report_rows),
        "members": report_rows,
    }

    if format.lower() == "csv":
        return _build_csv_response(report_rows, org_id)

    return report


def _build_csv_response(rows: list, org_id: str) -> StreamingResponse:
    """Build a CSV streaming response for the access report."""
    output = io.StringIO()
    fieldnames = [
        "user_id", "email", "full_name", "role", "member_since",
        "last_activity", "activity_count", "evidence_exports",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k, "") for k in fieldnames})

    output.seek(0)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"access_report_{org_id[:8]}_{timestamp}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Admin Dashboard Analytics ─────────────────────────────────────────────────

@router.get("/admin/dashboard-stats")
def get_dashboard_stats(
    org_id: str = Query(..., description="Organization UUID"),
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, Any]:
    """
    Admin dashboard: aggregate platform stats for the org.
    Returns total projects, documents, runs, members, and failed runs.
    """
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)
    resolved_org_id = resolve_org_id_for_user(sb, user_id, org_id, request=request)

    role = get_user_role(resolved_org_id, user_id, token.credentials)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only owner or admin can access dashboard stats")

    admin_sb = get_supabase_admin()

    def _count(table: str, extra_eq: dict | None = None) -> int:
        try:
            q = admin_sb.table(table).select("id", count="exact").eq("org_id", resolved_org_id)
            for k, v in (extra_eq or {}).items():
                q = q.eq(k, v)
            r = q.execute()
            return r.count if r.count is not None else 0
        except Exception:
            return 0

    return {
        "org_id": resolved_org_id,
        "total_projects": _count("projects"),
        "total_documents": _count("documents"),
        "total_runs": _count("runs"),
        "failed_runs": _count("runs", {"status": "FAILED"}),
        "total_members": _count("memberships"),
        "completed_runs": _count("runs", {"status": "COMPLETED"}),
    }


@router.get("/admin/plan-distribution")
def get_plan_distribution(
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, Any]:
    """
    Admin dashboard: plan distribution across all orgs the user owns/admins.
    Returns { plans: {starter: N, growth: N, elite: N}, total_orgs: N }
    """
    user_id = require_user_id(user)
    admin_sb = get_supabase_admin()

    plans: Dict[str, int] = {"starter": 0, "growth": 0, "elite": 0}
    total = 0

    try:
        # Find all orgs where user is owner/admin
        memberships = (
            admin_sb.table("memberships")
            .select("org_id, role")
            .eq("user_id", user_id)
            .execute()
        )
        admin_org_ids = [
            m["org_id"] for m in (memberships.data or [])
            if m.get("role") in ("owner", "admin")
        ]

        if admin_org_ids:
            orgs = (
                admin_sb.table("organizations")
                .select("id, plan_tier")
                .in_("id", admin_org_ids)
                .execute()
            )
            for org in (orgs.data or []):
                tier = (org.get("plan_tier") or "starter").strip().lower()
                plans[tier] = plans.get(tier, 0) + 1
                total += 1
    except Exception as exc:
        logger.debug("plan-distribution failed: %s", str(exc)[:120])

    return {"plans": plans, "total_orgs": total}


@router.get("/admin/mrr-summary")
def get_mrr_summary(
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, Any]:
    """
    Admin dashboard: Monthly Recurring Revenue (MRR) summary.
    Calculates MRR from plan distribution × plan prices.
    """
    user_id = require_user_id(user)
    admin_sb = get_supabase_admin()

    PLAN_PRICES_CENTS: Dict[str, int] = {
        "starter": 14900,
        "growth": 49900,
        "elite": 149900,
    }

    plans: Dict[str, int] = {"starter": 0, "growth": 0, "elite": 0}
    total_mrr_cents = 0

    try:
        memberships = (
            admin_sb.table("memberships")
            .select("org_id, role")
            .eq("user_id", user_id)
            .execute()
        )
        admin_org_ids = [
            m["org_id"] for m in (memberships.data or [])
            if m.get("role") in ("owner", "admin")
        ]

        if admin_org_ids:
            orgs = (
                admin_sb.table("organizations")
                .select("id, plan_tier, subscription_status")
                .in_("id", admin_org_ids)
                .execute()
            )
            for org in (orgs.data or []):
                tier = (org.get("plan_tier") or "starter").strip().lower()
                status = (org.get("subscription_status") or "").strip().lower()
                plans[tier] = plans.get(tier, 0) + 1
                # Only count active/trialing subscriptions in MRR
                if status in ("active", "trialing"):
                    total_mrr_cents += PLAN_PRICES_CENTS.get(tier, 0)
    except Exception as exc:
        logger.debug("mrr-summary failed: %s", str(exc)[:120])

    return {
        "mrr_cents": total_mrr_cents,
        "mrr_dollars": round(total_mrr_cents / 100, 2),
        "plan_counts": plans,
        "total_active_orgs": sum(plans.values()),
    }


# ── Document Expiry & Re-run Alerts ──────────────────────────────────────────


@router.get("/alerts/document-expiry")
def get_document_expiry_alerts(
    org_id: str = Query(..., description="Organization ID"),
    days_ahead: int = Query(30, ge=1, le=365, description="Days ahead to check for expiring docs"),
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """
    GET /alerts/document-expiry?org_id=...&days_ahead=30

    Returns expiring and expired documents across all projects in the org,
    plus documents needing a compliance re-run.
    """
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)
    resolved_org_id = resolve_org_id_for_user(sb, user_id, org_id, request=request)
    if not resolved_org_id:
        raise HTTPException(status_code=404, detail="Organization not found")

    from app.core.document_expiry_service import get_expiry_summary
    return get_expiry_summary(resolved_org_id, days_ahead=days_ahead)


@router.post("/alerts/check-expiry")
def check_and_send_expiry_alerts(
    org_id: str = Query(..., description="Organization ID"),
    days_ahead: int = Query(30, ge=1, le=365),
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """
    POST /alerts/check-expiry?org_id=...

    Triggers a document expiry check and sends email notifications
    to the org owner if any documents are expiring or expired.
    """
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)
    resolved_org_id = resolve_org_id_for_user(sb, user_id, org_id, request=request)
    if not resolved_org_id:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Require owner/admin role
    role = get_user_role(resolved_org_id, user_id, token.credentials)
    if not role_has_permission(role or "", Permission.MANAGE_BILLING):
        raise HTTPException(status_code=403, detail="Owner or admin role required")

    from app.core.document_expiry_service import check_and_notify_expiry
    return check_and_notify_expiry(resolved_org_id, days_ahead=days_ahead)


@router.get("/alerts/rerun-candidates")
def get_rerun_candidates_endpoint(
    org_id: str = Query(..., description="Organization ID"),
    stale_days: int = Query(90, ge=1, le=730, description="Days since last run to flag as stale"),
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """
    GET /alerts/rerun-candidates?org_id=...&stale_days=90

    Returns documents that haven't had a compliance run in the specified window.
    """
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)
    resolved_org_id = resolve_org_id_for_user(sb, user_id, org_id, request=request)
    if not resolved_org_id:
        raise HTTPException(status_code=404, detail="Organization not found")

    from app.core.document_expiry_service import get_rerun_candidates
    return get_rerun_candidates(resolved_org_id, stale_days=stale_days)
