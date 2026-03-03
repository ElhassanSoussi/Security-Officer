from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging

from app.core.auth import get_current_user, require_user_id
from app.core.database import get_supabase
from app.core.org_context import resolve_org_id_for_user

router = APIRouter()
security = HTTPBearer()
logger = logging.getLogger("api.onboarding")


class OnboardingStateResponse(BaseModel):
    onboarding_completed: bool
    onboarding_step: int


class OnboardingStatePatch(BaseModel):
    onboarding_completed: Optional[bool] = None
    onboarding_step: Optional[int] = None


def _clamp_step(value: int) -> int:
    if value < 1 or value > 5:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_onboarding_step",
                "message": "onboarding_step must be between 1 and 5",
                "min": 1,
                "max": 5,
            },
        )
    return value


@router.get("/org/onboarding", response_model=OnboardingStateResponse)
def get_onboarding_state(
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """Return onboarding state for the caller's current org."""
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)

    # Resolve org using existing membership logic (defaults to first org if none provided).
    org_id = resolve_org_id_for_user(sb, user_id, None, request=request)

    try:
        res = (
            sb.table("organizations")
            .select("id, onboarding_completed, onboarding_step")
            .eq("id", org_id)
            .single()
            .execute()
        )
    except HTTPException:
        raise
    except Exception as err:
        logger.warning("get_onboarding_state failed: %s", err)
        # Never 500 for onboarding reads; return safe defaults.
        return {"onboarding_completed": False, "onboarding_step": 1}

    if not res.data:
        raise HTTPException(status_code=404, detail={"error": "org_not_found", "message": "Organization not found"})

    row = res.data
    completed = bool(row.get("onboarding_completed") or False)
    step = int(row.get("onboarding_step") or 1)
    if step < 1 or step > 5:
        step = 1

    return {"onboarding_completed": completed, "onboarding_step": step}


@router.patch("/org/onboarding", response_model=OnboardingStateResponse)
def patch_onboarding_state(
    payload: OnboardingStatePatch,
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """Update onboarding state for the caller's current org."""
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)

    org_id = resolve_org_id_for_user(sb, user_id, None, request=request)

    update: Dict[str, Any] = {}
    if payload.onboarding_completed is not None:
        update["onboarding_completed"] = bool(payload.onboarding_completed)
    if payload.onboarding_step is not None:
        update["onboarding_step"] = _clamp_step(int(payload.onboarding_step))

    if not update:
        raise HTTPException(status_code=400, detail={"error": "empty_patch", "message": "No fields to update"})

    # If marking completed=true, force step to 5 (consistent UI state).
    if update.get("onboarding_completed") is True:
        update["onboarding_step"] = 5

    try:
        res = sb.table("organizations").update(update).eq("id", org_id).execute()
    except HTTPException:
        raise
    except Exception as err:
        logger.warning("patch_onboarding_state failed: %s", err)
        raise HTTPException(status_code=500, detail={"error": "onboarding_update_failed", "message": "Failed to update onboarding state"})

    # Supabase update may return [] when nothing changed; re-read to return canonical.
    return get_onboarding_state(request=request, user=user, token=token)


@router.get("/org/metrics")
def get_org_metrics(
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """Minimal onboarding metrics for step completion. Never creates new tables."""
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)

    org_id = resolve_org_id_for_user(sb, user_id, None, request=request)

    def _safe_count(table: str, filters: Dict[str, Any]) -> int:
        try:
            q = sb.table(table).select("id", count="exact")
            for k, v in filters.items():
                q = q.eq(k, v)
            r = q.execute()
            if getattr(r, "count", None) is None:
                return len(r.data or [])
            return int(r.count or 0)
        except Exception:
            return 0

    documents_count = _safe_count("documents", {"org_id": org_id})
    projects_count = _safe_count("projects", {"org_id": org_id})
    runs_count = _safe_count("runs", {"org_id": org_id})

    # reviewed_count: at least one run_audits row with review_status approved/rejected
    reviewed_count = 0
    try:
        res = (
            sb.table("run_audits")
            .select("id", count="exact")
            .eq("org_id", org_id)
            .in_("review_status", ["approved", "rejected"])
            .execute()
        )
        reviewed_count = int(res.count or 0) if getattr(res, "count", None) is not None else len(res.data or [])
    except Exception:
        reviewed_count = 0

    exports_count = _safe_count("exports", {"org_id": org_id})

    return {
        "documents_count": int(documents_count),
        "projects_count": int(projects_count),
        "runs_count": int(runs_count),
        "reviewed_count": int(reviewed_count),
        "exports_count": int(exports_count),
    }
