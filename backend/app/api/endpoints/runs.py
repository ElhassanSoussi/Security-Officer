from fastapi import APIRouter, HTTPException, Query, Response, Depends, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Optional, Dict, Any
from app.core.database import get_supabase, get_supabase_admin
import zipfile
import hashlib
import json as _json
from app.core.auth import get_current_user, require_user_id
from app.core.audit_events import log_audit_event, log_activity_event
from app.core.org_context import parse_uuid, resolve_org_id_for_user
from app.core.rbac import get_user_role, role_has_permission, Permission
from app.models.runs import Run, RunUpdate
import logging
import io
import os
from datetime import datetime, timezone
from pydantic import BaseModel
from uuid import UUID


# Run state machine constants
RUN_STATES = ["queued", "processing", "completed", "failed"]
TERMINAL_STATES = ["completed", "failed"]
LEGACY_STATUS_MAP = {
    "queued": "queued",
    "running": "processing",
    "processing": "processing",
    "analyzed": "completed",
    "exported": "completed",
    "completed": "completed",
    "failed": "failed",
}


def _normalize_status(value: str) -> str:
    if not value:
        return ""
    raw = value.strip().lower()
    return LEGACY_STATUS_MAP.get(raw, raw)


def _validate_transition(current: str, new: str):
    c = _normalize_status(current)
    n = _normalize_status(new)

    if c not in RUN_STATES:
        raise HTTPException(status_code=400, detail={"error": "invalid_run_state", "message": f"Unknown state '{current}'"})
    if n not in RUN_STATES:
        raise HTTPException(status_code=400, detail={"error": "invalid_run_state", "message": f"Unknown state '{new}'"})

    # Allowed: queued -> processing -> completed|failed
    if c == n:
        return
    if c == "queued" and n == "processing":
        return
    if c == "processing" and n in ("completed", "failed"):
        return

    # Any transition out of terminal is invalid
    if c in TERMINAL_STATES:
        raise HTTPException(status_code=409, detail={"error": "invalid_run_transition", "message": f"Cannot move from {current} to {new}"})

    raise HTTPException(status_code=409, detail={"error": "invalid_run_transition", "message": f"Cannot move from {current} to {new}"})

router = APIRouter()
security = HTTPBearer()
logger = logging.getLogger("api.runs")


# ─── Phase 4: Helper to store approved Q&A as embeddings ─────────────────────

def _store_approved_embedding(audit_row: dict, run_id: str, token: str) -> None:
    """
    Best-effort: store an approved audit row's Q&A pair as an embedding
    in question_embeddings for future reuse.
    """
    try:
        from app.core.similarity import similarity_engine
        question_text = audit_row.get("question_text", "")
        answer_text = audit_row.get("answer_text", "")
        if not question_text or not answer_text:
            return

        similarity_engine.store_approved_answer(
            org_id=audit_row.get("org_id", ""),
            project_id=audit_row.get("project_id"),
            run_id=run_id,
            audit_id=audit_row.get("id", ""),
            question_text=question_text,
            answer_text=answer_text,
            source_document=audit_row.get("source_document"),
            source_excerpt=audit_row.get("source_excerpt"),
            confidence_score=audit_row.get("confidence_score") if isinstance(audit_row.get("confidence_score"), (int, float)) else None,
            similarity_score=audit_row.get("embedding_similarity_score"),
            token=token,
        )
    except Exception as e:
        logger.warning("Phase 4: Failed to store approved embedding for audit %s: %s", audit_row.get("id"), e)


class ProjectCreate(BaseModel):
    org_id: Optional[str] = None
    name: str
    description: Optional[str] = None

class RunCreatePayload(BaseModel):
    org_id: Optional[str] = None
    project_id: Optional[str] = None
    questionnaire_filename: Optional[str] = None
    status: str = "queued"
    progress: int = 0
    error_message: Optional[str] = None

# --- RUNS ENDPOINTS ---

@router.post("", response_model=Run)
def create_run(
    payload: RunCreatePayload,
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    user_id = require_user_id(user)
    supabase = get_supabase(token.credentials)
    org_id = payload.org_id
    if org_id:
        org_id = parse_uuid(org_id, "org_id", required=True)
    resolved_org_id = resolve_org_id_for_user(supabase, user_id, org_id, request=request)
    if not resolved_org_id:
        raise HTTPException(status_code=400, detail={"error": "org_required", "message": "No organization available"})

    # Subscription tier enforcement — run limit
    from app.core.plan_service import PlanService
    PlanService.enforce_runs_limit(resolved_org_id)

    # Existing subscription.check_plan_limit for backward compat
    from app.core.subscription import check_plan_limit, log_usage_metric
    check_plan_limit(resolved_org_id, "runs")

    # Phase 5: Role enforcement — viewer/reviewer cannot create runs
    _role = get_user_role(resolved_org_id, user_id, token.credentials)
    if not role_has_permission(_role or "", Permission.RUN_ANALYSIS):
        raise HTTPException(status_code=403, detail={
            "error": "forbidden",
            "message": f"Insufficient permissions. Required: {Permission.RUN_ANALYSIS.value}. Your role: {_role or 'none'}.",
            "required_permission": Permission.RUN_ANALYSIS.value,
            "your_role": _role or "none",
        })

    project_id = None
    if payload.project_id:
        try:
            project_id = parse_uuid(payload.project_id, "project_id", required=True)
        except HTTPException:
            project_id = None

    status = _normalize_status(payload.status or "queued")
    if status not in RUN_STATES:
        raise HTTPException(status_code=400, detail={"error": "invalid_run_state", "message": f"Unknown state '{payload.status}'"})
    progress = max(0, min(100, int(payload.progress or 0)))
    now_iso = datetime.now(timezone.utc).isoformat()

    row = {
        "org_id": resolved_org_id,
        "project_id": project_id,
        "questionnaire_filename": payload.questionnaire_filename or "questionnaire.xlsx",
        "status": status.upper(),
        "progress": progress,
        "error_message": payload.error_message,
        "created_at": now_iso,
        "updated_at": now_iso,
        "completed_at": now_iso if status in TERMINAL_STATES else None,
    }
    cleaned = {k: v for k, v in row.items() if v is not None}

    try:
        res = supabase.table("runs").insert(cleaned).execute()
    except Exception as e:
        # Backward-compatible fallback for databases missing newer columns.
        logger.warning("create_run full insert failed, retrying minimal payload: %s", e)
        minimal = {
            "org_id": resolved_org_id,
            "project_id": project_id,
            "questionnaire_filename": payload.questionnaire_filename or "questionnaire.xlsx",
            "status": status.upper(),
            "error_message": payload.error_message,
        }
        try:
            res = supabase.table("runs").insert({k: v for k, v in minimal.items() if v is not None}).execute()
        except Exception as inner:
            logger.error("create_run failed: %s", inner)
            raise HTTPException(status_code=500, detail={"error": "run_create_failed", "message": "Failed to create run"})

    if not res.data:
        raise HTTPException(status_code=500, detail={"error": "run_create_failed", "message": "Failed to create run"})

    created = res.data[0]
    if created.get("status"):
        created["status"] = _normalize_status(created["status"]).upper()

    # Phase 18: log usage metric
    try:
        log_usage_metric(resolved_org_id, "RUN_CREATED")
    except Exception:
        pass

    return created

@router.get("", response_model=List[Run])
def get_runs(
    org_id: Optional[str] = Query(None, description="Organization UUID"),
    project_id: Optional[str] = Query(None, description="Project ID filter"),
    limit: int = 50,
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    user_id = require_user_id(user)
    if org_id:
        org_id = parse_uuid(org_id, "org_id", required=True)
    supabase = get_supabase(token.credentials)
    resolved_org_id = resolve_org_id_for_user(supabase, user_id, org_id, request=request)
    if not resolved_org_id:
        return []
    query = supabase.table("runs").select("*").eq("org_id", resolved_org_id).order("created_at", desc=True).limit(limit)
    if project_id:
        try:
            project_id = parse_uuid(project_id, "project_id", required=True)
            query = query.eq("project_id", project_id)
        except HTTPException:
            # Ignore legacy/non-UUID project slugs rather than crashing feed pages.
            pass
    result = query.execute()
    rows = result.data or []
    for row in rows:
        if row.get("status"):
            row["status"] = _normalize_status(row["status"]).upper()
    return rows

@router.get("/stats")
def get_stats(
    org_id: Optional[str] = Query(None, description="Organization UUID"),
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Get aggregated stats for dashboard using server-side counts.
    """
    user_id = require_user_id(user)
    supabase = get_supabase(token.credentials)
    if org_id:
        org_id = parse_uuid(org_id, "org_id", required=True)
    org_id = resolve_org_id_for_user(supabase, user_id, org_id, request=request)
    if not org_id:
        return {
            "active_projects": 0,
            "documents_ingested": 0,
            "runs_completed": 0
        }
    
    # Active Projects (direct count from projects table OR distinct docs as fallback)
    try:
        res_projs = supabase.table("projects").select("id", count="exact").eq("org_id", org_id).eq("status", "active").execute()
        active_projects = res_projs.count
    except Exception:
        try:
            res_docs = supabase.table("documents").select("project_id").eq("org_id", org_id).neq("project_id", "null").execute()
            project_ids = set([item['project_id'] for item in res_docs.data if item.get('project_id')])
        except Exception:
            project_ids = set()
        active_projects = len(project_ids)
    
    try:
        res_runs = supabase.table("runs").select("id, status").eq("org_id", org_id).execute()
        completed_statuses = {"COMPLETED", "ANALYZED", "EXPORTED"}
        runs_completed = len([r for r in (res_runs.data or []) if str(r.get("status") or "").upper() in completed_statuses])
    except Exception:
        runs_completed = 0
    
    try:
        res_docs = supabase.table("documents").select("id", count="exact").eq("org_id", org_id).execute()
        documents_ingested = res_docs.count if res_docs.count is not None else 0
    except Exception:
        documents_ingested = 0
    
    return {
        "active_projects": active_projects,
        "documents_ingested": documents_ingested,
        "runs_completed": runs_completed
    }


# --- Phase 18: Usage Summary Endpoint ---
@router.get("/usage")
def get_usage_summary(
    org_id: Optional[str] = Query(None, description="Organization UUID"),
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Phase 18: Return current-month usage + plan limits for the Usage Panel.
    Returns: runs_this_month, documents_total, memory_entries_total,
             evidence_exports_total, plan, limits.
    """
    user_id = require_user_id(user)
    supabase = get_supabase(token.credentials)
    if org_id:
        org_id = parse_uuid(org_id, "org_id", required=True)
    org_id = resolve_org_id_for_user(supabase, user_id, org_id, request=request)
    if not org_id:
        raise HTTPException(status_code=400, detail={"error": "org_required", "message": "No organization available"})

    from app.core.subscription import get_usage_summary as _get_summary
    return _get_summary(org_id)


# --- PROJECTS HELPER ---
@router.get("/projects", response_model=List[dict])
def get_projects(
    org_id: Optional[str] = Query(None, description="Organization UUID"),
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    user_id = require_user_id(user)
    supabase = get_supabase(token.credentials)
    if org_id:
        org_id = parse_uuid(org_id, "org_id", required=True)
    org_id = resolve_org_id_for_user(supabase, user_id, org_id, request=request)
    if not org_id:
        return []

    # Prefer canonical projects table.
    try:
        res_projects = (
            supabase
            .table("projects")
            .select("id, org_id, name, status, created_at")
            .eq("org_id", org_id)
            .order("created_at", desc=True)
            .execute()
        )
        if res_projects.data:
            return [
                {
                    "org_id": row["org_id"],
                    "project_id": row["id"],
                    "project_name": row.get("name"),
                    "status": row.get("status"),
                    "created_at": row.get("created_at"),
                }
                for row in res_projects.data
            ]
    except Exception as e:
        logger.warning("Projects table lookup failed, falling back to documents: %s", e)

    # Fallback for legacy environments where projects table is missing/empty.
    res_docs = supabase.table("documents").select("project_id").eq("org_id", org_id).neq("project_id", "null").execute()
    doc_projects = [item["project_id"] for item in res_docs.data if item.get("project_id")]
    all_projects = sorted(list(set(doc_projects)))
    return [{"org_id": org_id, "project_id": pid, "project_name": pid} for pid in all_projects]

@router.post("/projects", response_model=Dict[str, Any])
def create_project(
    project: ProjectCreate,
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Create a project inside an organization the caller belongs to.
    """
    user_id = require_user_id(user)
    name = (project.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Project name is required")

    supabase_read = get_supabase(token.credentials)
    org_id = project.org_id
    if org_id:
        org_id = parse_uuid(org_id, "org_id", required=True)
    org_id = resolve_org_id_for_user(supabase_read, user_id, org_id, request=request)
    if not org_id:
        raise HTTPException(status_code=400, detail="No organization available for project creation")

    payload = {
        "org_id": org_id,
        "name": name,
        "description": project.description,
        "status": "active",
    }
    cleaned = {k: v for k, v in payload.items() if v is not None}
    
    # Prefer RLS-scoped insert; fallback to admin when service_role is configured.
    try:
        res = supabase_read.table("projects").insert(cleaned).execute()
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
        supabase_read,
        org_id=org_id,
        user_id=user_id,
        event_type="project_created",
        metadata={"project_id": row["id"], "name": row.get("name")},
    )
    # Phase 16: compliance activity timeline
    try:
        log_activity_event(supabase_read, org_id=org_id, user_id=user_id, action_type="project_created", entity_type="project", entity_id=row["id"], metadata={"name": row.get("name")})
    except Exception:
        pass

    return {
        "org_id": row["org_id"],
        "project_id": row["id"],
        "project_name": row.get("name"),
        "status": row.get("status"),
        "created_at": row.get("created_at"),
    }

# --- ACTIVITY FEED ---
@router.get("/activities", response_model=List[dict])
def get_activities(
    org_id: Optional[str] = Query(None, description="Organization UUID"),
    limit: int = 20,
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Fetch recent activities for the dashboard feed.
    """
    user_id = require_user_id(user)
    supabase = get_supabase(token.credentials)
    if org_id:
        org_id = parse_uuid(org_id, "org_id", required=True)
    org_id = resolve_org_id_for_user(supabase, user_id, org_id, request=request)
    if not org_id:
        return []
    # Join with projects table to get the name
    try:
        result = (
            supabase
            .table("activities")
            .select("*, projects(name)")
            .eq("org_id", org_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        data = result.data
    except Exception:
        return []
    # Flatten project name for easier frontend consumption
    for item in data:
        if item.get("projects"):
            item["project_name"] = item["projects"]["name"]
            # Keep project_id as is (UUID)
        else:
            item["project_name"] = None
            
    return data

# --- SAMPLE DOWNLOAD ---
@router.get("/samples/questionnaire")
def download_sample_questionnaire():
    try:
        # Avoid pandas/numpy dependency (often breaks on fresh Macs without wheels).
        # We generate the workbook directly with openpyxl.
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = "Questionnaire"

        headers_row = ["Question ID", "Category", "Question Text", "Compliance Answer", "Citations"]
        ws.append(headers_row)

        rows = [
            ["Q1", "General", "Is the building entrance accessible?", "", ""],
            ["Q2", "Fire Safety", "Are fire extinguishers inspected monthly?", "", ""],
            ["Q3", "Electrical", "Is the main electrical panel labeled?", "", ""],
        ]
        for r in rows:
            ws.append(r)

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        headers = {'Content-Disposition': 'attachment; filename="Sample_Questionnaire.xlsx"'}
        return Response(content=output.getvalue(), media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers=headers)
    except Exception as e:
        logger.error("Error generating sample: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to generate sample: {str(e)}")

@router.get("/{run_id}/download")
def download_run_export(
    run_id: str,
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Download the file associated with a run (if EXPORTED).
    Serves from local 'exports/' directory.
    """
    user_id = require_user_id(user)
    supabase = get_supabase(token.credentials)

    # Resolve org context from the run itself (never trust caller-supplied org_id).
    try:
        run_res = supabase.table("runs").select("org_id, output_filename, status").eq("id", run_id).single().execute()
        if not run_res.data or not run_res.data.get("org_id"):
            raise HTTPException(status_code=404, detail={"error": "run_not_found", "message": "Run not found"})
        resolve_org_id_for_user(supabase, user_id, run_res.data["org_id"], request=request)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("download_run_export lookup failed for run_id=%s: %s", run_id, e)
        raise HTTPException(status_code=404, detail={"error": "run_not_found", "message": "Run not found or invalid ID"})

    # Enforce readiness: run must be completed
    status = _normalize_status(run_res.data.get("status"))
    if status != "completed":
        raise HTTPException(status_code=409, detail={"error": "export_not_ready", "message": "Run not completed yet"})

    # Determine storage path (local prototype)
    file_path = os.path.join("exports", f"{run_id}.xlsx")
    if not os.path.exists(file_path):
        logger.info("Export file missing for run_id=%s path=%s", run_id, file_path)
        raise HTTPException(status_code=404, detail={"error": "export_missing", "message": "No export generated for this run"})

    # Best-effort audit trail
    log_audit_event(
        supabase,
        org_id=run_res.data["org_id"],
        user_id=user_id,
        event_type="export_downloaded",
        metadata={"run_id": run_id},
    )
    # Phase 16: compliance activity timeline
    try:
        log_activity_event(supabase, org_id=run_res.data["org_id"], user_id=user_id, action_type="export_downloaded", entity_type="run", entity_id=run_id)
    except Exception:
        pass
    
    filename = run_res.data.get("output_filename") or f"run_export_{run_id}.xlsx"
    try:
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        logger.error("Failed to stream export for run_id=%s: %s", run_id, e)
        raise HTTPException(status_code=500, detail={"error": "export_stream_failed", "message": "Failed to download export"})

# ─── Static-prefix routes (MUST be declared before GET /{run_id} catch-all) ──

@router.get("/compliance-health")
def get_compliance_health(
    org_id: Optional[str] = Query(None, description="Organization UUID"),
    limit: int = Query(10, ge=1, le=50, description="Number of recent runs for trend"),
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Phase 15: Org-level compliance health metrics + low-confidence trend.

    Returns:
      - total_runs, total_questions, avg_confidence_pct
      - total_approved, total_pending, total_rejected, total_low_conf
      - avg_review_turnaround_hours (approximated from reviewed_at - created_at)
      - memory_reuse_count (answers reused from institutional memory)
      - low_conf_trend: list of {run_label, low_conf, total} for last N runs
    """
    user_id = require_user_id(user)
    supabase = get_supabase(token.credentials)
    if org_id:
        org_id = parse_uuid(org_id, "org_id", required=True)
    org_id = resolve_org_id_for_user(supabase, user_id, org_id, request=request)
    if not org_id:
        return _empty_health()

    # --- Fetch recent runs (ordered newest first) ---
    try:
        runs_res = (
            supabase.table("runs")
            .select("id, questionnaire_filename, created_at, status")
            .eq("org_id", org_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        runs = runs_res.data or []
    except Exception as e:
        logger.warning("compliance_health: failed to fetch runs: %s", e)
        return _empty_health()

    if not runs:
        return _empty_health()

    run_ids = [r["id"] for r in runs]

    # --- Fetch all audits for those runs ---
    try:
        audits_res = (
            supabase.table("run_audits")
            .select(
                "run_id, confidence_score, review_status, "
                "reviewed_at, created_at, reused_from_memory"
            )
            .in_("run_id", run_ids)
            .execute()
        )
        audits = audits_res.data or []
    except Exception:
        # Fallback without Phase 15 columns
        try:
            audits_res = (
                supabase.table("run_audits")
                .select("run_id, confidence_score, review_status, reviewed_at, created_at")
                .in_("run_id", run_ids)
                .execute()
            )
            audits = audits_res.data or []
        except Exception as e2:
            logger.warning("compliance_health: failed to fetch audits: %s", e2)
            audits = []

    # --- Aggregate totals ---
    total_questions = len(audits)
    total_approved = sum(1 for a in audits if (a.get("review_status") or "") == "approved")
    total_rejected = sum(1 for a in audits if (a.get("review_status") or "") == "rejected")
    total_pending  = total_questions - total_approved - total_rejected
    memory_reused  = sum(1 for a in audits if a.get("reused_from_memory"))

    # Confidence level buckets
    from app.core.institutional_memory import confidence_score_to_level
    total_high = total_medium = total_low = 0
    for a in audits:
        lvl = confidence_score_to_level(a.get("confidence_score", "MEDIUM"))
        if lvl == "HIGH":
            total_high += 1
        elif lvl == "MEDIUM":
            total_medium += 1
        else:
            total_low += 1

    # Approximate avg confidence as weighted mean
    avg_conf_pct = 0
    if total_questions > 0:
        weighted = total_high * 90 + total_medium * 65 + total_low * 30
        avg_conf_pct = round(weighted / total_questions)

    # Avg review turnaround (hours) for reviewed entries
    turnaround_hours_list = []
    from datetime import datetime, timezone
    for a in audits:
        if a.get("reviewed_at") and a.get("created_at"):
            try:
                created  = datetime.fromisoformat(a["created_at"].replace("Z", "+00:00"))
                reviewed = datetime.fromisoformat(a["reviewed_at"].replace("Z", "+00:00"))
                diff_h   = (reviewed - created).total_seconds() / 3600
                if 0 <= diff_h <= 24 * 90:   # sanity cap: 90 days
                    turnaround_hours_list.append(diff_h)
            except Exception:
                pass
    avg_turnaround = round(sum(turnaround_hours_list) / len(turnaround_hours_list), 1) \
        if turnaround_hours_list else None

    # --- Per-run trend (ordered oldest → newest for charting) ---
    audits_by_run: dict = {}
    for a in audits:
        audits_by_run.setdefault(a["run_id"], []).append(a)

    trend = []
    for run in reversed(runs):   # oldest first for chart
        rid = run["id"]
        run_audits_list = audits_by_run.get(rid, [])
        run_total = len(run_audits_list)
        run_low   = sum(
            1 for a in run_audits_list
            if confidence_score_to_level(a.get("confidence_score", "MEDIUM")) == "LOW"
        )
        label = (run.get("questionnaire_filename") or rid[:8])
        # Trim long filenames
        if len(label) > 24:
            label = label[:21] + "…"
        trend.append({
            "run_id": rid,
            "label": label,
            "total": run_total,
            "low_conf": run_low,
            "low_conf_pct": round(run_low / run_total * 100) if run_total else 0,
        })

    # Add phase 16 compliance health score computation mapping to 0-100 logic
    health_score = 0
    if total_questions > 0:
        approved_ratio = total_approved / total_questions
        conf_ratio = avg_conf_pct / 100
        low_penalty = (total_low / total_questions) * 0.5
        raw_score = ((approved_ratio * 0.4) + (conf_ratio * 0.4) - low_penalty + 0.2) * 100
        health_score = max(0, min(100, int(raw_score)))

    return {
        "health_score": health_score,
        "total_runs": len(runs),
        "total_questions": total_questions,
        "avg_confidence_pct": avg_conf_pct,
        "total_approved": total_approved,
        "total_rejected": total_rejected,
        "total_pending": total_pending,
        "total_low_conf": total_low,
        "total_high_conf": total_high,
        "total_medium_conf": total_medium,
        "memory_reuse_count": memory_reused,
        "avg_review_turnaround_hours": avg_turnaround,
        "low_conf_trend": trend,
    }


def _empty_health() -> dict:
    return {
        "health_score": 0,
        "total_runs": 0,
        "total_questions": 0,
        "avg_confidence_pct": 0,
        "total_approved": 0,
        "total_rejected": 0,
        "total_pending": 0,
        "total_low_conf": 0,
        "total_high_conf": 0,
        "total_medium_conf": 0,
        "memory_reuse_count": 0,
        "avg_review_turnaround_hours": None,
        "low_conf_trend": [],
    }


# --- Phase 16: Institutional Memory Governance & Activity Log ---

@router.get('/institutional-answers')
def list_institutional_answers(
    org_id: Optional[str] = Query(None, description='Organization ID'),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)
    if org_id:
        org_id = parse_uuid(org_id, 'org_id', required=True)
    org_id = resolve_org_id_for_user(sb, user_id, org_id)
    if not org_id:
        raise HTTPException(status_code=400, detail='org_id required')
    try:
        res = (
            sb.table('institutional_answers')
            .select('id, canonical_question_text, canonical_answer, confidence_level, source_doc_ids, use_count, last_used_at, created_at, is_active, edited_by, edited_at')
            .eq('org_id', org_id)
            .order('last_used_at', desc=True)
            .limit(limit)
            .offset(offset)
            .execute()
        )
        return res.data or []
    except Exception as e:
        logger.warning('list_institutional_answers failed: %s', e)
        return []


@router.patch('/institutional-answers/{answer_id}')
def patch_institutional_answer(
    answer_id: str,
    payload: dict,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)
    # Resolve org via existing row to enforce membership
    try:
        existing = sb.table('institutional_answers').select('org_id').eq('id', answer_id).single().execute()
    except Exception:
        existing = None
    if not existing or not existing.data:
        raise HTTPException(status_code=404, detail='Not found')
    org_id = existing.data.get('org_id')
    org_id = resolve_org_id_for_user(sb, user_id, org_id)
    if not org_id:
        raise HTTPException(status_code=403, detail='forbidden')

    # Only allow editing canonical_answer and confidence_level and is_active
    update = {}
    if 'canonical_answer' in payload:
        update['canonical_answer'] = str(payload['canonical_answer'])
    if 'confidence_level' in payload:
        lvl = str(payload['confidence_level']).upper()
        if lvl not in ('HIGH', 'MEDIUM', 'LOW'):
            raise HTTPException(status_code=400, detail='invalid confidence_level')
        update['confidence_level'] = lvl
    if 'is_active' in payload:
        update['is_active'] = bool(payload['is_active'])

    if not update:
        return {'updated': 0}

    from datetime import datetime, timezone
    update['edited_by'] = user_id
    update['edited_at'] = datetime.now(timezone.utc).isoformat()

    try:
        res = sb.table('institutional_answers').update(update).eq('id', answer_id).execute()
        # Log to audit_events and activity_log
        try:
            log_audit_event(sb, org_id=org_id, user_id=user_id, event_type='memory_edited', metadata={'answer_id': answer_id, 'changes': list(update.keys())})
        except Exception:
            pass
        try:
            log_activity_event(sb, org_id=org_id, user_id=user_id, action_type='memory_edited', entity_type='institutional_answer', entity_id=answer_id, metadata={'changes': list(update.keys())})
        except Exception:
            pass
        return {'updated': len(res.data) if res.data else 0}
    except Exception as e:
        logger.warning('patch_institutional_answer failed: %s', e)
        raise HTTPException(status_code=500, detail='update_failed')


@router.delete('/institutional-answers/{answer_id}')
def delete_institutional_answer(
    answer_id: str,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)
    
    # Require Admin or Owner
    from app.core.rbac import get_user_role
    
    try:
        # Get answer to find org_id
        ans = sb.table('institutional_answers').select('org_id').eq('id', answer_id).single().execute()
        if not ans.data:
            raise HTTPException(status_code=404, detail='Not found')
        org_id = ans.data['org_id']
        role = get_user_role(sb, user_id, org_id)
        if role not in ('owner', 'admin'):
            raise HTTPException(status_code=403, detail='Requires admin role to delete memory')
        
        # Hard delete
        sb.table('institutional_answers').delete().eq('id', answer_id).execute()
        
        try:
            log_audit_event(sb, org_id=org_id, user_id=user_id, event_type='memory_deleted', metadata={'answer_id': answer_id})
        except Exception:
            pass
        try:
            log_activity_event(sb, org_id=org_id, user_id=user_id, action_type='memory_deleted', entity_type='institutional_answer', entity_id=answer_id)
        except Exception:
            pass
        return {'status': 'deleted'}
    except HTTPException:
        raise
    except Exception as e:
        logger.warning('delete_institutional_answer failed: %s', e)
        raise HTTPException(status_code=500, detail='delete_failed')


class MemoryPromotePayload(BaseModel):
    audit_id: str
    answer_text: str

@router.post('/institutional-answers/promote')
def promote_institutional_answer(
    payload: MemoryPromotePayload,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)
    
    try:
        audit = sb.table("run_audits").select("*").eq("id", payload.audit_id).single().execute()
        if not audit.data:
            raise HTTPException(status_code=404, detail="Audit entry not found")
            
        audit_row = audit.data
        audit_row["answer_text"] = payload.answer_text # Use the edited answer
        
        # Phase 18: Check memory limit before storing
        from app.core.subscription import check_plan_limit, log_usage_metric
        _mem_org_id = audit_row.get("org_id", "")
        if _mem_org_id:
            check_plan_limit(_mem_org_id, "memory")
        
        # Best-effort store embedding
        _store_approved_embedding(audit_row, audit_row.get("run_id", ""), token.credentials)
        
        try:
            log_audit_event(sb, org_id=audit_row.get("org_id", ""), user_id=user_id, event_type='memory_promoted', metadata={'audit_id': payload.audit_id})
        except Exception:
            pass
        try:
            log_activity_event(sb, org_id=audit_row.get("org_id", ""), user_id=user_id, action_type='memory_promoted', entity_type='run_audit', entity_id=payload.audit_id)
        except Exception:
            pass
        
        # Phase 18: log memory usage metric (fire-and-forget)
        try:
            log_usage_metric(_mem_org_id, "MEMORY_STORED")
        except Exception:
            pass
            
        return {"status": "promoted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to promote to memory: %s", e)
        raise HTTPException(status_code=500, detail="Failed to promote into memory")


@router.get('/activity')
def list_activity(
    org_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    filter_type: Optional[str] = Query(None, description='Filter by action_type category'),
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)
    if org_id:
        org_id = parse_uuid(org_id, 'org_id')
    org_id = resolve_org_id_for_user(sb, user_id, org_id)
    if not org_id:
        raise HTTPException(status_code=400, detail='org_id required')
    try:
        q = sb.table('activity_log').select('*').eq('org_id', org_id).order('created_at', desc=True).limit(limit).offset(offset)
        if filter_type:
            q = q.eq('action_type', filter_type)
        res = q.execute()
        return res.data or []
    except Exception as e:
        logger.warning('list_activity failed: %s', e)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Phase 17: Evidence Vault + Immutable Audit Export
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/evidence-records")
def list_project_evidence_records(
    org_id: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """List all evidence records for an org (optionally filtered by project)."""
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)
    if org_id:
        org_id = parse_uuid(org_id, "org_id")
    org_id = resolve_org_id_for_user(sb, user_id, org_id)
    if not org_id:
        raise HTTPException(status_code=400, detail="org_id required")

    try:
        # Join with runs to get project_id and filename context
        ev_res = (
            sb.table("run_evidence_records")
            .select("*")
            .eq("org_id", org_id)
            .order("created_at", desc=True)
            .limit(200)
            .execute()
        )
        records = ev_res.data or []

        # If project filter requested, enrich with run data and filter
        if project_id and records:
            run_ids = list({r["run_id"] for r in records})
            run_res = (
                sb.table("runs")
                .select("id, project_id, questionnaire_filename, output_filename")
                .in_("id", run_ids)
                .execute()
            )
            run_map = {r["id"]: r for r in (run_res.data or [])}
            enriched = []
            for rec in records:
                run_data = run_map.get(rec["run_id"], {})
                rec["run_project_id"] = run_data.get("project_id")
                rec["questionnaire_filename"] = run_data.get("questionnaire_filename")
                rec["output_filename"] = run_data.get("output_filename")
                if project_id and rec.get("run_project_id") != project_id:
                    continue
                enriched.append(rec)
            return enriched

        return records
    except Exception as e:
        logger.warning("list_project_evidence_records failed: %s", e)
        return []


@router.delete("/evidence-records/{record_id}")
def delete_evidence_record(
    record_id: str,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """Delete an evidence record — admin/owner only."""
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)

    try:
        rec_res = sb.table("run_evidence_records").select("org_id, run_id").eq("id", record_id).single().execute()
        if not rec_res.data:
            raise HTTPException(status_code=404, detail="Evidence record not found")
        org_id = rec_res.data["org_id"]
        run_id_ref = rec_res.data["run_id"]
        resolve_org_id_for_user(sb, user_id, org_id)
        role = get_user_role(org_id, user_id, token.credentials)
        if role not in ("owner", "admin"):
            raise HTTPException(status_code=403, detail="Only admin/owner can delete evidence records")
        sb.table("run_evidence_records").delete().eq("id", record_id).execute()
        try:
            log_activity_event(
                sb, org_id=org_id, user_id=user_id,
                action_type="evidence_deleted",
                entity_type="run_evidence_record", entity_id=record_id,
                metadata={"run_id": run_id_ref},
            )
        except Exception:
            pass
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("delete_evidence_record failed: %s", e)
        raise HTTPException(status_code=500, detail="delete_failed")



@router.get("/{run_id}")
def get_run_details(
    run_id: str,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    supabase = get_supabase(token.credentials)
    try:
        response = supabase.table("runs").select("*").eq("id", run_id).single().execute()
        if not response.data:
            raise HTTPException(status_code=404, detail={"error": "run_not_found", "message": "Run not found"})
        row = response.data
        if row.get("status"):
            row["status"] = _normalize_status(row["status"]).upper()
        return row
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching run %s: %s", run_id, e)
        raise HTTPException(status_code=404, detail={"error": "run_not_found", "message": "Run not found or invalid ID"})

@router.get("/{run_id}/audits")
def get_run_audits(
    run_id: str,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    supabase = get_supabase(token.credentials)
    try:
        response = supabase.table("run_audits").select("*").eq("run_id", run_id).order("id").execute()
        return response.data
    except Exception as e:
        logger.error("Error fetching audits for %s: %s", run_id, e)
        return []

class AuditUpdate(BaseModel):
    answer_text: str

@router.patch("/{run_id}/audits/{audit_id}")
def update_audit_entry(
    run_id: str, 
    audit_id: str, 
    update: AuditUpdate, 
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Manually override an AI answer.
    """
    user_id = require_user_id(user)
    supabase = get_supabase(token.credentials)

    # Phase 5: Role enforcement — resolve org from run, then check permission
    try:
        run_res = supabase.table("runs").select("org_id").eq("id", run_id).single().execute()
        if run_res.data and run_res.data.get("org_id"):
            _role = get_user_role(run_res.data["org_id"], user_id, token.credentials)
            if not role_has_permission(_role or "", Permission.EDIT_ANSWER):
                raise HTTPException(status_code=403, detail={
                    "error": "forbidden",
                    "message": f"Insufficient permissions. Required: {Permission.EDIT_ANSWER.value}. Your role: {_role or 'none'}.",
                    "required_permission": Permission.EDIT_ANSWER.value,
                    "your_role": _role or "none",
                })
    except HTTPException:
        raise
    except Exception:
        pass  # Best-effort; RLS will catch unauthorized access anyway
    
    # Fetch original to save if not yet saved
    existing = supabase.table("run_audits").select("answer_text, original_answer").eq("id", audit_id).single().execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Audit entry not found")
        
    row = existing.data
    original = row.get("original_answer") or row.get("answer_text")
    
    # Update
    payload = {
        "answer_text": update.answer_text,
        "original_answer": original,
        "is_overridden": True,
        # Use explicit timestamp rather than PostgREST function string.
        "edited_at": datetime.now(timezone.utc).isoformat(),
        "editor_id": require_user_id(user),
    }
    
    res = supabase.table("run_audits").update(payload).eq("id", audit_id).execute()
    return res.data


class ReviewUpdate(BaseModel):
    review_status: str  # "approved" | "rejected"
    review_notes: Optional[str] = None

@router.patch("/{run_id}/audits/{audit_id}/review")
def review_audit_entry(
    run_id: str,
    audit_id: str,
    review: ReviewUpdate,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Approve or reject an audit answer.
    Sets reviewer_id, review_status, review_notes, and reviewed_at.
    """
    if review.review_status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="review_status must be 'approved' or 'rejected'")

    user_id = require_user_id(user)
    supabase = get_supabase(token.credentials)

    # Phase 5: Role enforcement — resolve org from run, then check review permission
    try:
        run_res = supabase.table("runs").select("org_id").eq("id", run_id).single().execute()
        if run_res.data and run_res.data.get("org_id"):
            _role = get_user_role(run_res.data["org_id"], user_id, token.credentials)
            if not role_has_permission(_role or "", Permission.REVIEW_ANSWER):
                raise HTTPException(status_code=403, detail={
                    "error": "forbidden",
                    "message": f"Insufficient permissions. Required: {Permission.REVIEW_ANSWER.value}. Your role: {_role or 'none'}.",
                    "required_permission": Permission.REVIEW_ANSWER.value,
                    "your_role": _role or "none",
                })
    except HTTPException:
        raise
    except Exception:
        pass  # Best-effort; RLS will catch unauthorized access anyway

    # Verify audit entry exists and get full data for Phase 4 embedding store
    existing = supabase.table("run_audits").select("*").eq("id", audit_id).single().execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Audit entry not found")

    payload = {
        "review_status": review.review_status,
        "review_notes": review.review_notes or "",
        "reviewer_id": user_id,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
    }

    res = supabase.table("run_audits").update(payload).eq("id", audit_id).execute()

    # Phase 4: On approval, store the Q&A pair as an embedding for future reuse
    if review.review_status == "approved":
        _store_approved_embedding(existing.data, run_id, token.credentials)

    # Phase 16: Log to compliance activity timeline
    _org_id_for_log = (existing.data or {}).get("org_id", "")
    try:
        log_activity_event(
            supabase,
            org_id=_org_id_for_log,
            user_id=user_id,
            action_type=f"audit_{review.review_status}",
            entity_type="run_audit",
            entity_id=audit_id,
            metadata={"run_id": run_id, "review_status": review.review_status},
        )
    except Exception:
        pass

    return res.data


class BulkReviewUpdate(BaseModel):
    review_status: str  # "approved" | "rejected"
    review_notes: Optional[str] = None


@router.post("/{run_id}/audits/bulk-review")
def bulk_review_audits(
    run_id: str,
    review: BulkReviewUpdate,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Approve or reject ALL pending audit entries for a run in one call.
    Only updates entries whose review_status is currently 'pending'.
    """
    if review.review_status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="review_status must be 'approved' or 'rejected'")

    user_id = require_user_id(user)
    supabase = get_supabase(token.credentials)

    # Phase 5: Role enforcement — resolve org from run, then check bulk review permission
    try:
        run_res = supabase.table("runs").select("org_id").eq("id", run_id).single().execute()
        if run_res.data and run_res.data.get("org_id"):
            _role = get_user_role(run_res.data["org_id"], user_id, token.credentials)
            if not role_has_permission(_role or "", Permission.BULK_REVIEW):
                raise HTTPException(status_code=403, detail={
                    "error": "forbidden",
                    "message": f"Insufficient permissions. Required: {Permission.BULK_REVIEW.value}. Your role: {_role or 'none'}.",
                    "required_permission": Permission.BULK_REVIEW.value,
                    "your_role": _role or "none",
                })
    except HTTPException:
        raise
    except Exception:
        pass  # Best-effort; RLS will catch unauthorized access anyway

    payload = {
        "review_status": review.review_status,
        "review_notes": review.review_notes or "",
        "reviewer_id": user_id,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
    }

    # Phase 4: Fetch pending audits before bulk update so we can store embeddings
    pending_audits = []
    if review.review_status == "approved":
        try:
            pending_res = (
                supabase.table("run_audits")
                .select("*")
                .eq("run_id", run_id)
                .eq("review_status", "pending")
                .execute()
            )
            pending_audits = pending_res.data or []
        except Exception as fetch_err:
            logger.warning("Failed to fetch pending audits for embedding store: %s", fetch_err)

    res = (
        supabase.table("run_audits")
        .update(payload)
        .eq("run_id", run_id)
        .eq("review_status", "pending")
        .execute()
    )

    # Phase 4: Store approved answers as embeddings for future reuse
    if review.review_status == "approved" and pending_audits:
        for audit_row in pending_audits:
            _store_approved_embedding(audit_row, run_id, token.credentials)

    updated_count = len(res.data) if res.data else 0

    # Phase 16: Log bulk review to compliance activity timeline
    _run_org_id = ""
    try:
        _run_org_id = (supabase.table("runs").select("org_id").eq("id", run_id).single().execute().data or {}).get("org_id", "")
    except Exception:
        pass
    try:
        log_activity_event(
            supabase,
            org_id=_run_org_id,
            user_id=user_id,
            action_type=f"bulk_audit_{review.review_status}",
            entity_type="run",
            entity_id=run_id,
            metadata={"updated_count": updated_count, "review_status": review.review_status},
        )
    except Exception:
        pass

    return {"updated": updated_count, "review_status": review.review_status}


@router.get("/{run_id}/export-readiness")
def get_export_readiness(
    run_id: str,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Check how many audit entries are approved/pending/rejected for a run.
    Helps the UI show an export gate: only allow export when reviews are done.
    """
    require_user_id(user)
    supabase = get_supabase(token.credentials)

    audits_res = (
        supabase.table("run_audits")
        .select("id, review_status")
        .eq("run_id", run_id)
        .execute()
    )
    rows = audits_res.data or []

    counts = {"total": len(rows), "approved": 0, "rejected": 0, "pending": 0}
    for row in rows:
        status = (row.get("review_status") or "pending").strip().lower()
        if status in counts:
            counts[status] += 1
        else:
            counts["pending"] += 1

    counts["all_reviewed"] = counts["pending"] == 0 and counts["total"] > 0
    counts["ready_for_export"] = counts["approved"] > 0 and counts["pending"] == 0

    return counts


# ─── Phase 4: Run Comparison ─────────────────────────────────────────────────

@router.get("/{run_id}/compare/{previous_run_id}")
def compare_runs(
    run_id: str,
    previous_run_id: str,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Phase 4: Compare two runs side-by-side.
    Returns a list of question comparisons with change_type (NEW/MODIFIED/UNCHANGED).
    Both runs must belong to the same org (enforced by RLS).
    """
    require_user_id(user)
    supabase = get_supabase(token.credentials)

    # Fetch audits for both runs
    try:
        current_res = (
            supabase.table("run_audits")
            .select("id, question_text, answer_text, cell_reference, review_status, confidence_score, source_document, answer_origin, change_type")
            .eq("run_id", run_id)
            .order("id")
            .execute()
        )
    except Exception:
        # Fallback without Phase 4 columns
        current_res = (
            supabase.table("run_audits")
            .select("id, question_text, answer_text, cell_reference, review_status, confidence_score, source_document")
            .eq("run_id", run_id)
            .order("id")
            .execute()
        )
    current_audits = current_res.data or []

    try:
        previous_res = (
            supabase.table("run_audits")
            .select("id, question_text, answer_text, cell_reference, review_status, confidence_score, source_document, answer_origin, change_type")
            .eq("run_id", previous_run_id)
            .order("id")
            .execute()
        )
    except Exception:
        previous_res = (
            supabase.table("run_audits")
            .select("id, question_text, answer_text, cell_reference, review_status, confidence_score, source_document")
            .eq("run_id", previous_run_id)
            .order("id")
            .execute()
        )
    previous_audits = previous_res.data or []

    if not current_audits and not previous_audits:
        return {"comparisons": [], "summary": {"new": 0, "modified": 0, "unchanged": 0, "removed": 0}}

    # Build delta using similarity module
    from app.core.similarity import compute_delta, _normalize_question

    current_questions = [
        {"question_text": a.get("question_text", ""), "cell_reference": a.get("cell_reference", "")}
        for a in current_audits
    ]
    previous_questions = [
        {"question_text": a.get("question_text", ""), "cell_reference": a.get("cell_reference", "")}
        for a in previous_audits
    ]

    delta_map = compute_delta(current_questions, previous_questions)

    # Build previous answers lookup for side-by-side
    prev_by_norm = {}
    prev_by_cell = {}
    for a in previous_audits:
        norm = _normalize_question(a.get("question_text", ""))
        prev_by_norm[norm] = a
        cell = a.get("cell_reference", "")
        if cell:
            prev_by_cell[cell] = a

    # Build comparisons
    comparisons = []
    for audit in current_audits:
        q_text = audit.get("question_text", "")
        cell = audit.get("cell_reference", "")
        change_type = delta_map.get(q_text, "NEW")
        norm = _normalize_question(q_text)

        # Find matching previous audit
        prev_audit = prev_by_norm.get(norm) or prev_by_cell.get(cell)

        comparisons.append({
            "current": {
                "audit_id": audit.get("id"),
                "question_text": q_text,
                "answer_text": audit.get("answer_text", ""),
                "review_status": audit.get("review_status", "pending"),
                "confidence_score": audit.get("confidence_score"),
                "source_document": audit.get("source_document"),
                "answer_origin": audit.get("answer_origin", "generated"),
            },
            "previous": {
                "audit_id": prev_audit.get("id") if prev_audit else None,
                "question_text": prev_audit.get("question_text", "") if prev_audit else None,
                "answer_text": prev_audit.get("answer_text", "") if prev_audit else None,
                "review_status": prev_audit.get("review_status") if prev_audit else None,
                "confidence_score": prev_audit.get("confidence_score") if prev_audit else None,
                "source_document": prev_audit.get("source_document") if prev_audit else None,
                "answer_origin": prev_audit.get("answer_origin") if prev_audit else None,
            } if prev_audit else None,
            "change_type": change_type,
        })

    # Questions removed in current run (present in previous, absent in current)
    current_norms = {_normalize_question(a.get("question_text", "")) for a in current_audits}
    current_cells = {a.get("cell_reference", "") for a in current_audits if a.get("cell_reference")}
    for prev_a in previous_audits:
        prev_norm = _normalize_question(prev_a.get("question_text", ""))
        prev_cell = prev_a.get("cell_reference", "")
        if prev_norm not in current_norms and (not prev_cell or prev_cell not in current_cells):
            comparisons.append({
                "current": None,
                "previous": {
                    "audit_id": prev_a.get("id"),
                    "question_text": prev_a.get("question_text", ""),
                    "answer_text": prev_a.get("answer_text", ""),
                    "review_status": prev_a.get("review_status"),
                    "confidence_score": prev_a.get("confidence_score"),
                    "source_document": prev_a.get("source_document"),
                    "answer_origin": prev_a.get("answer_origin"),
                },
                "change_type": "REMOVED",
            })

    # Summary counts
    summary = {"new": 0, "modified": 0, "unchanged": 0, "removed": 0}
    for c in comparisons:
        ct = c["change_type"].lower()
        if ct in summary:
            summary[ct] += 1

    return {"comparisons": comparisons, "summary": summary}


@router.get("/{run_id}/audits/filter")
def get_run_audits_filtered(
    run_id: str,
    change_type: Optional[str] = Query(None, description="Filter by change_type: NEW, MODIFIED, UNCHANGED"),
    answer_origin: Optional[str] = Query(None, description="Filter by answer_origin: generated, reused, suggested"),
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Phase 4: Get run audits with optional filters for delta tracking and reuse.
    """
    require_user_id(user)
    supabase = get_supabase(token.credentials)

    try:
        query = supabase.table("run_audits").select("*").eq("run_id", run_id)
        if change_type:
            query = query.eq("change_type", change_type.upper())
        if answer_origin:
            query = query.eq("answer_origin", answer_origin.lower())
        response = query.order("id").execute()
        return response.data or []
    except Exception as e:
        # Graceful fallback if Phase 4 columns don't exist
        logger.warning("Filtered audit query failed (Phase 4 columns may be missing): %s", e)
        response = supabase.table("run_audits").select("*").eq("run_id", run_id).order("id").execute()
        return response.data or []


@router.patch("/{run_id}", response_model=Run)
def update_run(
    run_id: str,
    run_in: RunUpdate,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    supabase = get_supabase(token.credentials)
    data = run_in.dict(exclude_unset=True)
    
    # First get the existing run to check project_id if not in update
    existing_run_res = supabase.table("runs").select("org_id, project_id, status").eq("id", run_id).single().execute()
    if not existing_run_res.data:
         raise HTTPException(status_code=404, detail="Run not found")
    existing_run = existing_run_res.data
    
    # Enforce state machine if status is changing
    if "status" in data:
        _validate_transition(existing_run["status"], data["status"])
        data["status"] = _normalize_status(data["status"]).upper()
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        if _normalize_status(data["status"]) in TERMINAL_STATES:
            data["completed_at"] = datetime.now(timezone.utc).isoformat()
            if _normalize_status(data["status"]) == "completed":
                data["progress"] = 100

    # Clamp progress 0-100
    if "progress" in data and data["progress"] is not None:
        try:
            p = int(data["progress"])
            data["progress"] = max(0, min(100, p))
        except Exception:
            data.pop("progress", None)

    try:
        res = supabase.table("runs").update(data).eq("id", run_id).execute()
    except Exception as e:
        logger.warning("update_run full payload failed, retrying minimal payload: %s", e)
        retry = dict(data)
        for key in ("progress", "completed_at", "updated_at"):
            retry.pop(key, None)
        try:
            res = supabase.table("runs").update(retry).eq("id", run_id).execute()
        except Exception as e2:
            # Legacy DB compatibility:
            # - processing may be stored as RUNNING
            # - completed may be stored as ANALYZED
            logger.warning("update_run minimal payload failed, retrying legacy status payload: %s", e2)
            legacy_retry = dict(retry)
            if "status" in legacy_retry:
                status_raw = str(legacy_retry["status"]).strip().upper()
                if status_raw == "PROCESSING":
                    legacy_retry["status"] = "RUNNING"
                elif status_raw == "COMPLETED":
                    legacy_retry["status"] = "ANALYZED"
            try:
                res = supabase.table("runs").update(legacy_retry).eq("id", run_id).execute()
            except Exception as e3:
                logger.error("update_run failed for run %s: %s", run_id, e3)
                raise HTTPException(
                    status_code=500,
                    detail={"error": "run_update_failed", "message": "Failed to update run state"},
                )
    if not res.data:
         raise HTTPException(status_code=404, detail={"error": "run_not_found", "message": "Run not found"})
    
    updated_run = res.data[0]
    
    # Log Activity if status changed
    if "status" in data and data["status"] != existing_run["status"]:
        try:
            status_value = _normalize_status(data["status"])
            event_type = f"run_{status_value}"
            description = f"Run status updated to {status_value}"
            
            if status_value == "completed":
                description = "Run completed"
            elif status_value == "failed":
                description = "Run failed to process"
            
            activity_payload = {
                "org_id": updated_run["org_id"],
                "project_id": updated_run.get("project_id"),
                "run_id": updated_run["id"],
                "event_type": event_type,
                "description": description
            }
            supabase.table("activities").insert(activity_payload).execute()
        except Exception as e:
             logger.warning("Failed to log activity for run %s: %s", run_id, e)

    if updated_run.get("status"):
        updated_run["status"] = _normalize_status(updated_run["status"]).upper()
    return updated_run

def _compute_health_score_for_audits(audits: list) -> int:
    """Reusable: compute 0-100 health score from a list of audit rows."""
    from app.core.institutional_memory import confidence_score_to_level
    total = len(audits)
    if total == 0:
        return 0
    approved = sum(1 for a in audits if (a.get("review_status") or "") == "approved")
    total_high = sum(1 for a in audits if confidence_score_to_level(a.get("confidence_score", "MEDIUM")) == "HIGH")
    total_medium = sum(1 for a in audits if confidence_score_to_level(a.get("confidence_score", "MEDIUM")) == "MEDIUM")
    total_low = total - total_high - total_medium
    weighted = total_high * 90 + total_medium * 65 + total_low * 30
    avg_conf_pct = round(weighted / total)
    approved_ratio = approved / total
    conf_ratio = avg_conf_pct / 100
    low_penalty = (total_low / total) * 0.5
    raw = ((approved_ratio * 0.4) + (conf_ratio * 0.4) - low_penalty + 0.2) * 100
    return max(0, min(100, int(raw)))


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@router.post("/{run_id}/generate-evidence")
def generate_evidence_package(
    run_id: str,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Phase 17 Part 1+2: Generate a tamper-evident evidence package ZIP for a run.

    The ZIP contains:
      1. audit_log.json      — all audit rows with answers, confidence, review status
      2. memory_reuse.json   — audit rows that came from institutional memory
      3. activity.json       — activity_log events scoped to this run
      4. summary.json        — run metadata + health score + SHA-256 hashes
      5. export.xlsx         — original exported Excel (if available on disk)

    SHA-256 hashes of audit_log.json and export.xlsx are embedded in summary.json.
    A record is written to run_evidence_records and the run is locked.
    """
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)

    # ── 1. Fetch run ──────────────────────────────────────────────────────────
    try:
        run_res = sb.table("runs").select("*").eq("id", run_id).single().execute()
        if not run_res.data:
            raise HTTPException(status_code=404, detail="Run not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Run not found: {e}")

    run_row = run_res.data
    org_id = run_row.get("org_id", "")
    resolve_org_id_for_user(sb, user_id, org_id)  # membership check

    # Phase 19: Enforce active subscription before evidence generation
    from app.core.stripe_billing import check_subscription_active
    check_subscription_active(org_id)

    status = _normalize_status(run_row.get("status", ""))
    if status not in ("completed", "exported", "analyzed"):
        raise HTTPException(status_code=409, detail="Run must be completed before generating evidence")

    # ── 2. Fetch audits ───────────────────────────────────────────────────────
    try:
        audits_res = sb.table("run_audits").select("*").eq("run_id", run_id).order("id").execute()
        audits = audits_res.data or []
    except Exception as e:
        logger.warning("evidence: failed to fetch audits for run %s: %s", run_id, e)
        audits = []

    # ── 3. Fetch activity log entries for this run ────────────────────────────
    activity_rows: list = []
    try:
        act_res = (
            sb.table("activity_log")
            .select("*")
            .eq("org_id", org_id)
            .order("created_at")
            .execute()
        )
        # Filter client-side to entries referencing this run
        all_act = act_res.data or []
        activity_rows = [
            a for a in all_act
            if (a.get("entity_id") == run_id)
            or (isinstance(a.get("metadata"), dict) and a["metadata"].get("run_id") == run_id)
        ]
    except Exception as e:
        logger.warning("evidence: failed to fetch activity for run %s: %s", run_id, e)

    # ── 4. Compute health score ───────────────────────────────────────────────
    health_score = _compute_health_score_for_audits(audits)

    total_questions = len(audits)
    approved_count = sum(1 for a in audits if (a.get("review_status") or "") == "approved")
    rejected_count = sum(1 for a in audits if (a.get("review_status") or "") == "rejected")
    from app.core.institutional_memory import confidence_score_to_level
    low_conf_count = sum(
        1 for a in audits if confidence_score_to_level(a.get("confidence_score", "MEDIUM")) == "LOW"
    )
    reused_count = sum(1 for a in audits if a.get("reused_from_memory"))

    # ── 5. Build JSON blobs ───────────────────────────────────────────────────
    audit_log_payload = {
        "run_id": run_id,
        "project_id": run_row.get("project_id"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": user_id,
        "total_questions": total_questions,
        "approved_count": approved_count,
        "rejected_count": rejected_count,
        "low_confidence_count": low_conf_count,
        "reused_from_memory_count": reused_count,
        "health_score": health_score,
        "answers": [
            {
                "id": a.get("id"),
                "question_text": a.get("question_text"),
                "answer_text": a.get("answer_text"),
                "original_answer": a.get("original_answer"),
                "confidence_score": a.get("confidence_score"),
                "review_status": a.get("review_status"),
                "review_notes": a.get("review_notes"),
                "reviewer_id": a.get("reviewer_id"),
                "reviewed_at": a.get("reviewed_at"),
                "answer_origin": a.get("answer_origin"),
                "reused_from_memory": a.get("reused_from_memory"),
                "source_document": a.get("source_document"),
                "created_at": a.get("created_at"),
            }
            for a in audits
        ],
    }
    audit_log_bytes = _json.dumps(audit_log_payload, indent=2, default=str).encode()
    audit_log_hash = _sha256_bytes(audit_log_bytes)

    memory_reuse_payload = {
        "run_id": run_id,
        "reused_answers": [
            a for a in audit_log_payload["answers"] if a.get("reused_from_memory")
        ],
    }
    memory_reuse_bytes = _json.dumps(memory_reuse_payload, indent=2, default=str).encode()

    activity_bytes = _json.dumps(activity_rows, indent=2, default=str).encode()

    # ── 6. Load export Excel (best-effort) ────────────────────────────────────
    excel_bytes: bytes | None = None
    excel_hash: str | None = None
    excel_path = os.path.join("exports", f"{run_id}.xlsx")
    if os.path.exists(excel_path):
        try:
            with open(excel_path, "rb") as f:
                excel_bytes = f.read()
            excel_hash = _sha256_bytes(excel_bytes)
        except Exception as e:
            logger.warning("evidence: could not read Excel for run %s: %s", run_id, e)

    # ── 7. Build summary ──────────────────────────────────────────────────────
    summary_payload = {
        "evidence_package_version": "1.0",
        "run_id": run_id,
        "project_id": run_row.get("project_id"),
        "org_id": org_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": user_id,
        "total_questions": total_questions,
        "approved_count": approved_count,
        "rejected_count": rejected_count,
        "low_confidence_count": low_conf_count,
        "reused_from_memory_count": reused_count,
        "health_score": health_score,
        "integrity": {
            "audit_log_sha256": audit_log_hash,
            "export_excel_sha256": excel_hash,
        },
        "run_metadata": {
            "questionnaire_filename": run_row.get("questionnaire_filename"),
            "output_filename": run_row.get("output_filename"),
            "status": run_row.get("status"),
            "created_at": run_row.get("created_at"),
            "completed_at": run_row.get("completed_at"),
        },
    }
    summary_bytes = _json.dumps(summary_payload, indent=2, default=str).encode()

    # Combined package hash (hash of both primary artifacts)
    combined_str = audit_log_hash + (excel_hash or "")
    package_hash = _sha256_bytes(combined_str.encode())

    # ── 8. Assemble ZIP in memory ─────────────────────────────────────────────
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("audit_log.json", audit_log_bytes)
        zf.writestr("memory_reuse.json", memory_reuse_bytes)
        zf.writestr("activity.json", activity_bytes)
        zf.writestr("summary.json", summary_bytes)
        if excel_bytes:
            zf.writestr(f"export_{run_id[:8]}.xlsx", excel_bytes)
    zip_bytes = zip_buffer.getvalue()
    package_size = len(zip_bytes)

    # ── 9. Persist evidence record ────────────────────────────────────────────
    admin_sb = get_supabase_admin()
    evidence_record = {
        "run_id": run_id,
        "org_id": org_id,
        "generated_by": user_id,
        "sha256_hash": package_hash,
        "health_score": health_score,
        "package_size": package_size,
    }
    try:
        admin_sb.table("run_evidence_records").insert(evidence_record).execute()
    except Exception as e:
        logger.warning("evidence: failed to persist evidence record for run %s: %s", run_id, e)

    # ── 10. Lock run ──────────────────────────────────────────────────────────
    try:
        admin_sb.table("runs").update({"is_locked": True}).eq("id", run_id).execute()
    except Exception as e:
        logger.warning("evidence: failed to lock run %s: %s", run_id, e)

    # ── 11. Log activity ──────────────────────────────────────────────────────
    try:
        log_activity_event(
            sb, org_id=org_id, user_id=user_id,
            action_type="evidence_generated",
            entity_type="run", entity_id=run_id,
            metadata={"sha256_hash": package_hash, "health_score": health_score},
        )
    except Exception:
        pass

    # Phase 18: log evidence usage metric (fire-and-forget)
    try:
        from app.core.subscription import log_usage_metric as _log_metric
        _log_metric(org_id, "EVIDENCE_GENERATED")
    except Exception:
        pass

    # ── 12. Stream ZIP ────────────────────────────────────────────────────────
    safe_run = run_id[:8]
    zip_buffer.seek(0)
    return StreamingResponse(
        iter([zip_bytes]),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="evidence_{safe_run}.zip"',
            "X-Evidence-Hash": package_hash,
            "X-Health-Score": str(health_score),
        },
    )


# ─── Generated Answers endpoints ─────────────────────────────────────────────

@router.get("/{run_id}/answers/summary")
def get_run_answers_summary(
    run_id: str,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """Return aggregate metrics for a run's generated answers."""
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)
    try:
        run_res = sb.table("runs").select("org_id").eq("id", run_id).single().execute()
        if not run_res.data:
            raise HTTPException(status_code=404, detail="Run not found")
        org_id = run_res.data["org_id"]
        resolve_org_id_for_user(sb, user_id, org_id)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=404, detail="Run not found")

    from app.core.answer_store import get_run_answers_summary
    return get_run_answers_summary(sb, run_id)


@router.get("/{run_id}/answers")
def get_run_answers(
    run_id: str,
    needs_review: bool = Query(False, description="Filter to answers requiring review"),
    limit: int = Query(200, ge=1, le=500),
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """List generated answers for a run."""
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)
    try:
        run_res = sb.table("runs").select("org_id").eq("id", run_id).single().execute()
        if not run_res.data:
            raise HTTPException(status_code=404, detail="Run not found")
        org_id = run_res.data["org_id"]
        resolve_org_id_for_user(sb, user_id, org_id)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=404, detail="Run not found")

    from app.core.answer_store import get_run_answers
    return get_run_answers(sb, run_id, only_needs_review=needs_review, limit=limit)


@router.get("/{run_id}/evidence-records")
def list_evidence_records(
    run_id: str,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """List all evidence packages generated for a run."""
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)
    try:
        run_res = sb.table("runs").select("org_id").eq("id", run_id).single().execute()
        if not run_res.data:
            raise HTTPException(status_code=404, detail="Run not found")
        org_id = run_res.data["org_id"]
        resolve_org_id_for_user(sb, user_id, org_id)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=404, detail="Run not found")

    try:
        res = (
            sb.table("run_evidence_records")
            .select("*")
            .eq("run_id", run_id)
            .order("created_at", desc=True)
            .execute()
        )
        return res.data or []
    except Exception as e:
        logger.warning("list_evidence_records failed: %s", e)
        return []


@router.post("/{run_id}/unlock")
def unlock_run(
    run_id: str,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """Unlock a locked run — admin/owner only. Logs activity."""
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)

    try:
        run_res = sb.table("runs").select("org_id, is_locked").eq("id", run_id).single().execute()
        if not run_res.data:
            raise HTTPException(status_code=404, detail="Run not found")
        org_id = run_res.data["org_id"]
        resolve_org_id_for_user(sb, user_id, org_id)
        role = get_user_role(org_id, user_id, token.credentials)
        if role not in ("owner", "admin"):
            raise HTTPException(status_code=403, detail="Only admin/owner can unlock a run")
        if not run_res.data.get("is_locked"):
            return {"status": "already_unlocked"}
        admin_sb = get_supabase_admin()
        admin_sb.table("runs").update({"is_locked": False}).eq("id", run_id).execute()
        try:
            log_activity_event(
                sb, org_id=org_id, user_id=user_id,
                action_type="run_unlocked",
                entity_type="run", entity_id=run_id,
            )
        except Exception:
            pass
        return {"status": "unlocked"}
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("unlock_run failed: %s", e)
        raise HTTPException(status_code=500, detail="unlock_failed")
