from fastapi import APIRouter, HTTPException, Query, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List
import logging

from app.core.auth import get_current_user, require_user_id
from app.core.database import get_supabase
from app.core.org_context import parse_uuid, resolve_org_id_for_user
from app.core.rbac import get_user_role, role_has_permission, Permission
from app.core.audit_events import log_audit_event

router = APIRouter()
security = HTTPBearer()
logger = logging.getLogger("api.knowledge_memory")


class SaveMemoryPayload(BaseModel):
    audit_id: str
    org_id: Optional[str] = None


class UpdateMemoryPayload(BaseModel):
    answer_text: Optional[str] = None
    question_text: Optional[str] = None


@router.post("/save")
def save_memory_entry(
    payload: SaveMemoryPayload,
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """Embed an approved audit answer and store it in knowledge_memory."""
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)

    try:
        audit_res = sb.table("run_audits").select("*").eq("id", payload.audit_id).single().execute()
        if not audit_res.data:
            raise HTTPException(status_code=404, detail="Audit entry not found")
        audit = audit_res.data
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Audit entry not found: {exc}")

    org_id = audit.get("org_id") or payload.org_id
    if org_id:
        org_id = parse_uuid(org_id, "org_id")
    org_id = resolve_org_id_for_user(sb, user_id, org_id, request=request)
    if not org_id:
        raise HTTPException(status_code=400, detail="org_id required")

    role = get_user_role(org_id, user_id, token.credentials)
    if not role_has_permission(role or "", Permission.REVIEW_ANSWER):
        raise HTTPException(status_code=403, detail="Insufficient permissions to save to memory")

    question_text = audit.get("question_text", "")
    answer_text = audit.get("answer_text", "")
    run_id = audit.get("run_id")

    from app.core.answer_store import _parse_confidence
    confidence = _parse_confidence(audit.get("confidence_score") or audit.get("confidence"))

    from app.core.knowledge_memory import save_to_memory
    new_id = save_to_memory(
        organization_id=org_id,
        question_text=question_text,
        answer_text=answer_text,
        confidence=confidence,
        source_run_id=run_id,
        approved_by=user_id,
        sb=sb,
    )

    if not new_id:
        raise HTTPException(status_code=500, detail="Failed to save to knowledge memory")

    try:
        log_audit_event(
            sb, org_id=org_id, user_id=user_id,
            event_type="memory_saved",
            metadata={"audit_id": payload.audit_id, "memory_id": new_id},
        )
    except Exception:
        pass

    return {"status": "saved", "id": new_id}


@router.get("")
def list_memory_entries(
    org_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """List all knowledge_memory entries for the caller's organization."""
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)
    if org_id:
        org_id = parse_uuid(org_id, "org_id")
    org_id = resolve_org_id_for_user(sb, user_id, org_id, request=request)
    if not org_id:
        raise HTTPException(status_code=400, detail="org_id required")

    try:
        res = (
            sb.table("knowledge_memory")
            .select(
                "id, organization_id, question_text, answer_text, "
                "confidence, source_run_id, approved_by, created_at, updated_at"
            )
            .eq("organization_id", org_id)
            .order("created_at", desc=True)
            .limit(limit)
            .offset(offset)
            .execute()
        )
        return res.data or []
    except Exception as exc:
        logger.warning("list_memory_entries failed: %s", exc)
        return []


@router.patch("/{memory_id}")
def update_memory_entry(
    memory_id: str,
    payload: UpdateMemoryPayload,
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """Edit the answer_text or question_text of a knowledge_memory entry."""
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)

    try:
        existing = sb.table("knowledge_memory").select("organization_id").eq("id", memory_id).single().execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Memory entry not found")
        org_id = existing.data["organization_id"]
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=404, detail="Memory entry not found")

    org_id = resolve_org_id_for_user(sb, user_id, org_id, request=request)
    if not org_id:
        raise HTTPException(status_code=403, detail="forbidden")

    update: dict = {}
    if payload.answer_text is not None:
        update["answer_text"] = payload.answer_text.strip()[:8000]
    if payload.question_text is not None:
        update["question_text"] = payload.question_text.strip()[:4000]
    if not update:
        return {"updated": 0}

    from datetime import datetime, timezone
    update["updated_at"] = datetime.now(timezone.utc).isoformat()

    try:
        res = sb.table("knowledge_memory").update(update).eq("id", memory_id).execute()
        return {"updated": len(res.data) if res.data else 0}
    except Exception as exc:
        logger.warning("update_memory_entry failed: %s", exc)
        raise HTTPException(status_code=500, detail="update_failed")


@router.delete("/{memory_id}")
def delete_memory_entry(
    memory_id: str,
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """Hard-delete a knowledge_memory entry. Requires admin/owner role."""
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)

    try:
        existing = sb.table("knowledge_memory").select("organization_id").eq("id", memory_id).single().execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Memory entry not found")
        org_id = existing.data["organization_id"]
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=404, detail="Memory entry not found")

    org_id = resolve_org_id_for_user(sb, user_id, org_id, request=request)
    if not org_id:
        raise HTTPException(status_code=403, detail="forbidden")

    role = get_user_role(org_id, user_id, token.credentials)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only admin/owner can delete memory entries")

    try:
        sb.table("knowledge_memory").delete().eq("id", memory_id).execute()
        try:
            log_audit_event(
                sb, org_id=org_id, user_id=user_id,
                event_type="memory_deleted",
                metadata={"memory_id": memory_id},
            )
        except Exception:
            pass
        return {"status": "deleted"}
    except Exception as exc:
        logger.warning("delete_memory_entry failed: %s", exc)
        raise HTTPException(status_code=500, detail="delete_failed")


@router.get("/matches")
def list_memory_matches(
    org_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """List recent memory_matches for the caller's organization."""
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)
    if org_id:
        org_id = parse_uuid(org_id, "org_id")
    org_id = resolve_org_id_for_user(sb, user_id, org_id, request=request)
    if not org_id:
        raise HTTPException(status_code=400, detail="org_id required")

    try:
        km_res = (
            sb.table("knowledge_memory")
            .select("id")
            .eq("organization_id", org_id)
            .execute()
        )
        km_ids = [r["id"] for r in (km_res.data or [])]
        if not km_ids:
            return []

        res = (
            sb.table("memory_matches")
            .select(
                "id, question_text, matched_memory_id, "
                "similarity_score, used_in_run, created_at"
            )
            .in_("matched_memory_id", km_ids)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []
    except Exception as exc:
        logger.warning("list_memory_matches failed: %s", exc)
        return []


@router.get("/search")
def search_memory_entries(
    q: str = Query(..., min_length=3, description="Question text to search"),
    org_id: Optional[str] = Query(None),
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Vector-search knowledge_memory for the closest matching entries.
    Used by the Assistant to answer memory-related queries.
    """
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)
    if org_id:
        org_id = parse_uuid(org_id, "org_id")
    org_id = resolve_org_id_for_user(sb, user_id, org_id, request=request)
    if not org_id:
        raise HTTPException(status_code=400, detail="org_id required")

    from app.core.knowledge_memory import search_memory, MEMORY_SIMILARITY_THRESHOLD
    try:
        from app.core.similarity import get_embedding_cached
        embedding = get_embedding_cached(q)
        result = sb.rpc(
            "match_knowledge_memory",
            {
                "query_embedding": embedding,
                "match_threshold": max(0.60, MEMORY_SIMILARITY_THRESHOLD - 0.20),
                "match_count": 5,
                "filter_org_id": org_id,
            },
        ).execute()
        return result.data or []
    except Exception as exc:
        logger.warning("search_memory_entries failed: %s", exc)
        return []
