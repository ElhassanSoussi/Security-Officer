"""
Compliance Intelligence API Endpoints

GET  /compliance/overview          → org-level dashboard summary
GET  /compliance/projects/{id}     → project-level score + issues
POST /compliance/projects/{id}/scan → trigger a compliance scan for a project
GET  /compliance/issues            → list open issues for the org (with filters)
PATCH /compliance/issues/{id}/resolve → mark an issue resolved
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Any, Dict, List, Optional
import logging

from app.core.auth import get_current_user, require_user_id
from app.core.database import get_supabase, get_supabase_admin
from app.core.org_context import parse_uuid, resolve_org_id_for_user
from app.core.audit_events import log_audit_event

router = APIRouter()
security = HTTPBearer()
logger = logging.getLogger("api.compliance")


@router.get("/overview")
def get_compliance_overview(
    org_id: Optional[str] = Query(None),
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, Any]:
    """Return org-level compliance overview for the dashboard."""
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)
    org_id = resolve_org_id_for_user(sb, user_id, org_id, request=request)
    if not org_id:
        raise HTTPException(status_code=400, detail="org_id is required")

    from app.core.compliance_engine import get_org_compliance_overview
    admin_sb = get_supabase_admin()
    return get_org_compliance_overview(admin_sb, org_id)


@router.get("/projects/{project_id}")
def get_project_compliance(
    project_id: str,
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, Any]:
    """Return the latest compliance score and open issues for a project."""
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)
    project_id = parse_uuid(project_id, "project_id", required=True)

    try:
        proj = sb.table("projects").select("id, org_id").eq("id", project_id).single().execute()
    except Exception:
        raise HTTPException(status_code=404, detail="Project not found")

    if not proj.data:
        raise HTTPException(status_code=404, detail="Project not found")

    org_id = proj.data["org_id"]
    resolve_org_id_for_user(sb, user_id, org_id, request=request)

    from app.core.compliance_engine import get_project_compliance_summary
    admin_sb = get_supabase_admin()
    return get_project_compliance_summary(admin_sb, org_id, project_id)


@router.post("/projects/{project_id}/scan")
def scan_project_compliance(
    project_id: str,
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, Any]:
    """
    Trigger a compliance scan for a project.
    Generates issues from current document metadata and recalculates the score.
    """
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)
    project_id = parse_uuid(project_id, "project_id", required=True)

    try:
        proj = sb.table("projects").select("id, org_id").eq("id", project_id).single().execute()
    except Exception:
        raise HTTPException(status_code=404, detail="Project not found")

    if not proj.data:
        raise HTTPException(status_code=404, detail="Project not found")

    org_id = proj.data["org_id"]
    resolve_org_id_for_user(sb, user_id, org_id, request=request)

    from app.core.compliance_engine import generate_compliance_issues, calculate_project_score
    admin_sb = get_supabase_admin()

    new_issues = generate_compliance_issues(admin_sb, org_id, project_id)
    score_result = calculate_project_score(admin_sb, org_id, project_id)

    log_audit_event(
        admin_sb,
        org_id=org_id,
        user_id=user_id,
        action="compliance_scan",
        resource_type="project",
        resource_id=project_id,
        metadata={
            "overall_score": score_result["overall_score"],
            "risk_level": score_result["risk_level"],
            "open_issues": score_result["open_issues"],
            "new_issues_created": len(new_issues),
        },
    )

    return {
        "project_id": project_id,
        "overall_score": score_result["overall_score"],
        "risk_level": score_result["risk_level"],
        "open_issues": score_result["open_issues"],
        "new_issues_created": len(new_issues),
    }


@router.get("/issues")
def list_compliance_issues(
    org_id: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    severity: Optional[str] = Query(None, pattern="^(low|medium|high)$"),
    status: Optional[str] = Query("open", pattern="^(open|resolved|all)$"),
    limit: int = Query(50, ge=1, le=200),
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
) -> List[Dict[str, Any]]:
    """List compliance issues for the org, with optional filters."""
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)
    org_id = resolve_org_id_for_user(sb, user_id, org_id, request=request)
    if not org_id:
        raise HTTPException(status_code=400, detail="org_id is required")

    admin_sb = get_supabase_admin()
    query = (
        admin_sb.table("compliance_issues")
        .select("id, project_id, issue_type, severity, description, status, created_at")
        .eq("org_id", org_id)
        .order("created_at", desc=True)
        .limit(limit)
    )

    if project_id:
        project_id = parse_uuid(project_id, "project_id", required=False)
        if project_id:
            query = query.eq("project_id", project_id)

    if severity:
        query = query.eq("severity", severity)

    if status and status != "all":
        query = query.eq("status", status)

    try:
        res = query.execute()
        return res.data or []
    except Exception as exc:
        logger.warning("list_compliance_issues failed: %s", exc)
        return []


@router.patch("/issues/{issue_id}/resolve")
def resolve_compliance_issue(
    issue_id: str,
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, Any]:
    """Mark a compliance issue as resolved."""
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)
    issue_id = parse_uuid(issue_id, "issue_id", required=True)

    admin_sb = get_supabase_admin()

    try:
        existing = (
            admin_sb.table("compliance_issues")
            .select("id, org_id, project_id, status")
            .eq("id", issue_id)
            .single()
            .execute()
        )
    except Exception:
        raise HTTPException(status_code=404, detail="Issue not found")

    if not existing.data:
        raise HTTPException(status_code=404, detail="Issue not found")

    org_id = existing.data["org_id"]
    resolve_org_id_for_user(sb, user_id, org_id, request=request)

    if existing.data["status"] == "resolved":
        return existing.data

    try:
        res = (
            admin_sb.table("compliance_issues")
            .update({"status": "resolved"})
            .eq("id", issue_id)
            .execute()
        )
        updated = (res.data or [existing.data])[0]
    except Exception as exc:
        logger.warning("resolve_compliance_issue failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to resolve issue")

    log_audit_event(
        admin_sb,
        org_id=org_id,
        user_id=user_id,
        action="compliance_issue_resolved",
        resource_type="compliance_issue",
        resource_id=issue_id,
        metadata={"project_id": existing.data.get("project_id")},
    )

    return updated
