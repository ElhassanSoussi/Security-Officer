from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import logging

from app.core.auth import get_current_user, require_user_id
from app.core.database import get_supabase, get_supabase_admin
from app.core.audit_events import log_audit_event, log_activity_event
from app.core.org_context import parse_uuid, resolve_org_id_for_user
from app.core.rbac import get_user_role, role_has_permission, Permission
from app.core.expiration import summarize_expirations

router = APIRouter()
security = HTTPBearer()
logger = logging.getLogger("api.projects")


class ProjectCreate(BaseModel):
    org_id: Optional[str] = None
    name: str
    description: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


def _project_row_to_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a projects DB row to API response format."""
    return {
        "org_id": row["org_id"],
        "project_id": row["id"],
        "project_name": row.get("name"),
        "description": row.get("description"),
        "status": row.get("status"),
        "created_at": row.get("created_at"),
    }


@router.get("", response_model=List[Dict[str, Any]])
def list_projects(
    org_id: Optional[str] = Query(None, description="Organization UUID"),
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)
    if org_id:
        org_id = parse_uuid(org_id, "org_id", required=True)
    org_id = resolve_org_id_for_user(sb, user_id, org_id, request=request)
    if not org_id:
        return []

    res = (
        sb.table("projects")
        .select("id, org_id, name, status, created_at")
        .eq("org_id", org_id)
        .order("created_at", desc=True)
        .execute()
    )
    rows = res.data or []
    return [_project_row_to_dict(row) for row in rows]


@router.get("/{project_id}", response_model=Dict[str, Any])
def get_project_detail(
    project_id: str,
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """Get a single project by ID, verifying org membership."""
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)
    project_id = parse_uuid(project_id, "project_id", required=True)

    try:
        res = (
            sb.table("projects")
            .select("id, org_id, name, description, status, created_at")
            .eq("id", project_id)
            .single()
            .execute()
        )
    except Exception:
        raise HTTPException(status_code=404, detail="Project not found")

    if not res.data:
        raise HTTPException(status_code=404, detail="Project not found")

    row = res.data
    # Verify caller belongs to the project's org
    resolve_org_id_for_user(sb, user_id, row["org_id"], request=request)

    return _project_row_to_dict(row)


@router.patch("/{project_id}", response_model=Dict[str, Any])
def update_project(
    project_id: str,
    payload: ProjectUpdate,
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """Update a project's name, description, or status."""
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)
    project_id = parse_uuid(project_id, "project_id", required=True)

    # Verify project exists and caller has access
    try:
        existing = (
            sb.table("projects")
            .select("id, org_id")
            .eq("id", project_id)
            .single()
            .execute()
        )
    except Exception:
        raise HTTPException(status_code=404, detail="Project not found")

    if not existing.data:
        raise HTTPException(status_code=404, detail="Project not found")

    resolve_org_id_for_user(sb, user_id, existing.data["org_id"], request=request)

    # Phase 5: Role enforcement — viewer/reviewer cannot edit projects
    _role = get_user_role(existing.data["org_id"], user_id, token.credentials)
    if not role_has_permission(_role or "", Permission.EDIT_PROJECT):
        raise HTTPException(status_code=403, detail={
            "error": "forbidden",
            "message": f"Insufficient permissions. Required: {Permission.EDIT_PROJECT.value}. Your role: {_role or 'none'}.",
            "required_permission": Permission.EDIT_PROJECT.value,
            "your_role": _role or "none",
        })

    update_data = {}
    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Project name cannot be empty")
        update_data["name"] = name
    if payload.description is not None:
        update_data["description"] = payload.description
    if payload.status is not None:
        if payload.status not in ("active", "archived"):
            raise HTTPException(status_code=400, detail="Status must be 'active' or 'archived'")
        update_data["status"] = payload.status

    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    try:
        res = sb.table("projects").update(update_data).eq("id", project_id).execute()
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Failed to update project: {err}")

    if not res.data:
        raise HTTPException(status_code=500, detail="Failed to update project")

    return _project_row_to_dict(res.data[0])


@router.post("", response_model=Dict[str, Any])
def create_project(
    payload: ProjectCreate,
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)
    org_id = payload.org_id
    if org_id:
        org_id = parse_uuid(org_id, "org_id", required=True)
    org_id = resolve_org_id_for_user(sb, user_id, org_id, request=request)
    if not org_id:
        raise HTTPException(status_code=400, detail="No organization available for project creation")

    # Subscription tier enforcement — project limit
    from app.core.plan_service import PlanService
    PlanService.enforce_projects_limit(org_id)

    # Role enforcement — viewer/reviewer cannot create projects
    _role = get_user_role(org_id, user_id, token.credentials)
    if not role_has_permission(_role or "", Permission.CREATE_PROJECT):
        raise HTTPException(status_code=403, detail={
            "error": "forbidden",
            "message": f"Insufficient permissions. Required: {Permission.CREATE_PROJECT.value}. Your role: {_role or 'none'}.",
            "required_permission": Permission.CREATE_PROJECT.value,
            "your_role": _role or "none",
        })

    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Project name is required")

    to_insert = {
        "org_id": org_id,
        "name": name,
        "description": (payload.description or None),
        "status": "active",
    }
    cleaned = {k: v for k, v in to_insert.items() if v is not None}
    
    # Prefer RLS-scoped insert; fallback to admin when service_role is configured.
    try:
        res = sb.table("projects").insert(cleaned).execute()
    except Exception as err:
        admin_sb = get_supabase_admin()
        try:
            res = admin_sb.table("projects").insert(cleaned).execute()
        except Exception:
            raise HTTPException(status_code=500, detail=f"Failed to create project: {err}")
    if not res.data:
        raise HTTPException(status_code=500, detail="Failed to create project")

    row = res.data[0]

    # Best-effort audit trail
    log_audit_event(
        sb,
        org_id=org_id,
        user_id=user_id,
        event_type="project_created",
        metadata={"project_id": row["id"], "name": row.get("name")},
    )
    log_activity_event(
        sb,
        org_id=org_id,
        user_id=user_id,
        action_type="project_created",
        entity_type="project",
        entity_id=row["id"],
        metadata={"name": row.get("name")},
    )

    return _project_row_to_dict(row)


# ── Phase 6 Part 1: Project Overview Dashboard ──────────────────────────────

ONBOARDING_STEPS = [
    "connect_org",
    "upload_docs",
    "run_analysis",
    "review_answers",
    "export_pack",
]


@router.get("/{project_id}/overview")
def get_project_overview(
    project_id: str,
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Aggregated project dashboard payload.
    Never returns 500 — all sub-queries are best-effort with safe defaults.
    """
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)
    project_id = parse_uuid(project_id, "project_id", required=True)

    # Verify project + membership
    try:
        proj = (
            sb.table("projects")
            .select("id, org_id, name, status, created_at")
            .eq("id", project_id)
            .single()
            .execute()
        )
    except Exception:
        raise HTTPException(status_code=404, detail="Project not found")

    if not proj.data:
        raise HTTPException(status_code=404, detail="Project not found")

    row = proj.data
    org_id = row["org_id"]
    resolve_org_id_for_user(sb, user_id, org_id, request=request)

    # RBAC: VIEW_PROJECT is sufficient
    role = get_user_role(org_id, user_id, token.credentials)
    if not role_has_permission(role or "", Permission.VIEW_PROJECT):
        raise HTTPException(status_code=403, detail={
            "error": "forbidden",
            "message": f"Insufficient permissions. Required: {Permission.VIEW_PROJECT.value}. Your role: {role or 'none'}.",
            "required_permission": Permission.VIEW_PROJECT.value,
            "your_role": role or "none",
        })

    # ── Org name (best-effort) ─────────────────
    org_name = ""
    try:
        org_res = sb.table("organizations").select("name").eq("id", org_id).single().execute()
        org_name = (org_res.data or {}).get("name", "")
    except Exception:
        pass

    # ── Documents + expiration counts (best-effort) ─────
    docs_total = 0
    expiring_count = 0
    expired_count = 0
    try:
        pd_res = (
            sb.table("project_documents")
            .select("document_id, display_name, expiration_date, reminder_days_before")
            .eq("project_id", project_id)
            .execute()
        )
        docs_data = pd_res.data or []
        docs_total = len(docs_data)
        if docs_data:
            summary = summarize_expirations(docs_data)
            expiring_count = summary["counts"].get("expiring", 0)
            expired_count = summary["counts"].get("expired", 0)
    except Exception:
        # Fallback: try documents table
        try:
            d_res = (
                sb.table("documents")
                .select("id")
                .eq("project_id", project_id)
                .execute()
            )
            docs_total = len(d_res.data or [])
        except Exception:
            pass

    # ── Runs summary (best-effort) ─────────────
    runs_total = 0
    last_run_at = None
    last_export_at = None
    try:
        runs_res = (
            sb.table("runs")
            .select("id, status, created_at, export_filename")
            .eq("project_id", project_id)
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        runs_data = runs_res.data or []
        runs_total = len(runs_data)
        if runs_data:
            last_run_at = runs_data[0].get("created_at")
            for r in runs_data:
                if r.get("export_filename"):
                    last_export_at = r.get("created_at")
                    break
    except Exception:
        pass

    # ── Audit preview (last 10 events, best-effort) ─────
    audit_preview = []
    try:
        ae_res = (
            sb.table("audit_events")
            .select("id, event_type, created_at, user_id, metadata")
            .eq("org_id", org_id)
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )
        for ev in (ae_res.data or []):
            audit_preview.append({
                "id": ev.get("id"),
                "event_type": ev.get("event_type"),
                "created_at": ev.get("created_at"),
                "user_id": ev.get("user_id"),
                "metadata": ev.get("metadata"),
            })
    except Exception:
        pass

    # ── Onboarding state (best-effort) ─────────
    onboarding = _get_onboarding_state(sb, project_id, org_id, docs_total, runs_total)

    return {
        "project": {"id": project_id, "name": row.get("name"), "status": row.get("status")},
        "org": {"id": org_id, "name": org_name},
        "role": role or "none",
        "docs": {"total": docs_total, "expiring_count": expiring_count, "expired_count": expired_count},
        "runs": {"total": runs_total, "last_run_at": last_run_at, "last_export_at": last_export_at},
        "audit_preview": audit_preview,
        "onboarding": onboarding,
    }


# ── Phase 6 Part 2: Onboarding Checklist ────────────────────────────────────

def _get_onboarding_state(sb, project_id: str, org_id: str, docs_total: int, runs_total: int) -> dict:
    """
    Compute onboarding checklist. Uses stored completion flags if available,
    otherwise auto-detects from existing data.
    """
    steps = {}

    # Try to load stored onboarding state
    stored = {}
    try:
        ob_res = (
            sb.table("project_onboarding")
            .select("step, completed_at")
            .eq("project_id", project_id)
            .execute()
        )
        for row in (ob_res.data or []):
            stored[row["step"]] = row.get("completed_at")
    except Exception:
        pass

    # Auto-detect completion where possible
    steps["connect_org"] = {
        "completed": bool(org_id) or "connect_org" in stored,
        "completed_at": stored.get("connect_org"),
        "label": "Connect Organization",
    }
    steps["upload_docs"] = {
        "completed": docs_total > 0 or "upload_docs" in stored,
        "completed_at": stored.get("upload_docs"),
        "label": "Upload Documents",
    }
    steps["run_analysis"] = {
        "completed": runs_total > 0 or "run_analysis" in stored,
        "completed_at": stored.get("run_analysis"),
        "label": "Run Analysis",
    }

    # Review + export need explicit completion or stored flag
    has_review = False
    has_export = False
    try:
        ra_res = (
            sb.table("run_audits")
            .select("id")
            .eq("project_id", project_id)
            .eq("review_status", "approved")
            .limit(1)
            .execute()
        )
        has_review = bool(ra_res.data)
    except Exception:
        pass

    try:
        ex_res = (
            sb.table("runs")
            .select("id")
            .eq("project_id", project_id)
            .not_.is_("export_filename", "null")
            .limit(1)
            .execute()
        )
        has_export = bool(ex_res.data)
    except Exception:
        pass

    steps["review_answers"] = {
        "completed": has_review or "review_answers" in stored,
        "completed_at": stored.get("review_answers"),
        "label": "Review Answers",
    }
    steps["export_pack"] = {
        "completed": has_export or "export_pack" in stored,
        "completed_at": stored.get("export_pack"),
        "label": "Export Compliance Pack",
    }

    completed_count = sum(1 for s in steps.values() if s["completed"])
    return {
        "steps": steps,
        "completed_count": completed_count,
        "total_steps": len(ONBOARDING_STEPS),
        "all_complete": completed_count == len(ONBOARDING_STEPS),
    }


@router.get("/{project_id}/onboarding")
def get_project_onboarding(
    project_id: str,
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """Get onboarding checklist for a project."""
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

    # Counts for auto-detect
    docs_total = 0
    runs_total = 0
    try:
        d = sb.table("project_documents").select("document_id").eq("project_id", project_id).execute()
        docs_total = len(d.data or [])
    except Exception:
        try:
            d = sb.table("documents").select("id").eq("project_id", project_id).execute()
            docs_total = len(d.data or [])
        except Exception:
            pass
    try:
        r = sb.table("runs").select("id").eq("project_id", project_id).execute()
        runs_total = len(r.data or [])
    except Exception:
        pass

    return _get_onboarding_state(sb, project_id, org_id, docs_total, runs_total)


class OnboardingCompleteRequest(BaseModel):
    step: str


@router.post("/{project_id}/onboarding/complete")
def complete_onboarding_step(
    project_id: str,
    body: OnboardingCompleteRequest,
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """Mark an onboarding step as complete."""
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)
    project_id = parse_uuid(project_id, "project_id", required=True)

    if body.step not in ONBOARDING_STEPS:
        raise HTTPException(status_code=400, detail=f"Invalid step. Allowed: {ONBOARDING_STEPS}")

    try:
        proj = sb.table("projects").select("id, org_id").eq("id", project_id).single().execute()
    except Exception:
        raise HTTPException(status_code=404, detail="Project not found")
    if not proj.data:
        raise HTTPException(status_code=404, detail="Project not found")

    org_id = proj.data["org_id"]
    resolve_org_id_for_user(sb, user_id, org_id, request=request)

    # Upsert the onboarding step
    try:
        sb.table("project_onboarding").upsert({
            "project_id": project_id,
            "step": body.step,
            "completed_by": user_id,
        }, on_conflict="project_id,step").execute()
    except Exception as e:
        # Table may not exist — non-fatal, return success anyway
        logger.warning("project_onboarding upsert failed (non-fatal): %s", e)

    return {"status": "completed", "step": body.step}
