"""
Audit Log API — Phase 5 Part 4: Hardened.

Endpoints:
  GET /audit/log     → paginated run_audits with filters
  GET /audit/exports → export events (who exported what, when)
  GET /audit/events  → paginated audit_events with event_type + date range filters
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import logging

from app.core.auth import get_current_user, require_user_id
from app.core.database import get_supabase
from app.core.org_context import parse_uuid, resolve_org_id_for_user

router = APIRouter()
security = HTTPBearer()
logger = logging.getLogger("api.audit")

def _normalize_confidence_score(value) -> Optional[float]:
    """
    Normalize confidence to a 0..1 ratio. Returns None for invalid/unparseable
    values (including legacy string labels like "HIGH"/"LOW").
    """
    try:
        if value is None:
            return None
        # Pass through numeric
        if isinstance(value, (int, float)):
            v = float(value)
        elif isinstance(value, str):
            s = value.strip()
            if not s:
                return None
            v = float(s)
        else:
            return None

        if v != v:  # NaN
            return None
        if v < 0:
            return None
        if v <= 1:
            return v
        if v <= 100:
            return v / 100.0
        return None
    except Exception:
        return None


@router.get("/log")
def get_audit_log(
    org_id: Optional[str] = Query(None, description="Organization UUID"),
    project_id: Optional[str] = Query(None, description="Filter by project"),
    date_from: Optional[str] = Query(None, description="ISO date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="ISO date (YYYY-MM-DD)"),
    min_confidence: Optional[float] = Query(None, description="Min confidence 0-1"),
    source: Optional[str] = Query(None, description="Filter by source document"),
    review_status: Optional[str] = Query(None, description="Filter by review status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Paginated audit log from run_audits table.
    Supports filters: project, date range, confidence, source document.
    """
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)

    if not org_id or not str(org_id).strip():
        raise HTTPException(status_code=400, detail="org_id is required")

    # Verify membership
    org_id = resolve_org_id_for_user(sb, user_id, org_id, request=request)

    # Build query
    query = (
        sb.table("run_audits")
        .select("*", count="exact")
        .eq("org_id", org_id)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
    )

    if project_id:
        query = query.eq("project_id", parse_uuid(project_id, "project_id"))

    if date_from:
        query = query.gte("created_at", f"{date_from}T00:00:00")

    if date_to:
        query = query.lte("created_at", f"{date_to}T23:59:59")

    # NOTE: some legacy deployments stored confidence_score as text; applying a
    # numeric gte filter would fail. We attempt server-side filtering; if it
    # errors, we fall back to client-side filtering after normalization.
    apply_min_confidence_in_query = min_confidence is not None
    if apply_min_confidence_in_query:
        query = query.gte("confidence_score", min_confidence)

    if source:
        query = query.ilike("source_document", f"%{source}%")

    if review_status:
        query = query.eq("review_status", review_status)

    try:
        res = query.execute()
    except Exception as err:
        # Retry without min_confidence filter for legacy schemas.
        if apply_min_confidence_in_query:
            try:
                retry_query = (
                    sb.table("run_audits")
                    .select("*", count="exact")
                    .eq("org_id", org_id)
                    .order("created_at", desc=True)
                    .range(offset, offset + limit - 1)
                )
                if project_id:
                    retry_query = retry_query.eq("project_id", parse_uuid(project_id, "project_id"))
                if date_from:
                    retry_query = retry_query.gte("created_at", f"{date_from}T00:00:00")
                if date_to:
                    retry_query = retry_query.lte("created_at", f"{date_to}T23:59:59")
                if source:
                    retry_query = retry_query.ilike("source_document", f"%{source}%")
                if review_status:
                    retry_query = retry_query.eq("review_status", review_status)
                res = retry_query.execute()
            except Exception:
                # Table may not exist in partial setups
                return {"items": [], "total": 0, "limit": limit, "offset": offset}
        else:
            return {"items": [], "total": 0, "limit": limit, "offset": offset}

    # Normalize confidence_score to number|null (never NaN) for frontend.
    items = res.data or []
    for row in items:
        row["confidence_score"] = _normalize_confidence_score(row.get("confidence_score"))

    if min_confidence is not None:
        items = [r for r in items if (r.get("confidence_score") is not None and r["confidence_score"] >= min_confidence)]

    return {
        "items": items,
        "total": res.count if res.count is not None else len(res.data or []),
        "limit": limit,
        "offset": offset,
    }


@router.get("/exports")
def get_export_events(
    org_id: str = Query(..., description="Organization UUID"),
    date_from: Optional[str] = Query(None, description="ISO date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="ISO date (YYYY-MM-DD)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Export events from the exports table.
    Shows who exported what and when.
    """
    user_id = require_user_id(user)

    sb = get_supabase(token.credentials)

    # Verify membership
    org_id = resolve_org_id_for_user(sb, user_id, org_id, request=request)

    query = (
        sb.table("exports")
        .select("*", count="exact")
        .eq("org_id", org_id)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
    )

    if date_from:
        query = query.gte("created_at", f"{date_from}T00:00:00")

    if date_to:
        query = query.lte("created_at", f"{date_to}T23:59:59")

    try:
        res = query.execute()
    except Exception as err:
        return {"items": [], "total": 0, "limit": limit, "offset": offset}

    return {
        "items": res.data or [],
        "total": res.count if res.count is not None else len(res.data or []),
        "limit": limit,
        "offset": offset,
    }


# ── Phase 5 Part 4: Hardened Audit Events Endpoint ──────────────────────────

def _validate_iso_date(value: Optional[str], field_name: str) -> Optional[str]:
    """Validate an ISO date string (YYYY-MM-DD). Returns None if empty/None."""
    if not value or not str(value).strip():
        return None
    s = str(value).strip()
    if len(s) < 10:
        raise HTTPException(status_code=400, detail=f"{field_name} must be ISO format YYYY-MM-DD")
    # Accept YYYY-MM-DD prefix
    date_part = s[:10]
    import re
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_part):
        raise HTTPException(status_code=400, detail=f"{field_name} must be ISO format YYYY-MM-DD")
    # Validate it's a real date
    from datetime import datetime as _dt
    try:
        _dt.strptime(date_part, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{field_name} is not a valid date")
    return date_part


@router.get("/events")
def get_audit_events(
    org_id: Optional[str] = Query(None, description="Organization UUID (required)"),
    event_type: Optional[str] = Query(None, alias="event", description="Filter by event_type"),
    date_from: Optional[str] = Query(None, alias="from", description="Start date YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, alias="to", description="End date YYYY-MM-DD"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Paginated audit_events log with filters.
    Phase 5 Part 4: Never returns 500 — always returns valid JSON.
    Supports filtering by event_type and date range.
    """
    user_id = require_user_id(user)

    if not org_id or not str(org_id).strip():
        raise HTTPException(status_code=400, detail="org_id is required")

    # Validate date params (raises 400 on bad format, never 500)
    validated_from = _validate_iso_date(date_from, "from")
    validated_to = _validate_iso_date(date_to, "to")

    try:
        sb = get_supabase(token.credentials)
    except Exception:
        logger.warning("audit_events: failed to get supabase client")
        return {"items": [], "total": 0, "limit": limit, "offset": offset}

    # Verify membership
    try:
        org_id = resolve_org_id_for_user(sb, user_id, org_id, request=request)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=403, detail="Organization access denied")

    # Build query
    try:
        query = (
            sb.table("audit_events")
            .select("*", count="exact")
            .eq("org_id", org_id)
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
        )

        if event_type and event_type.strip():
            query = query.eq("event_type", event_type.strip())

        if validated_from:
            query = query.gte("created_at", f"{validated_from}T00:00:00")

        if validated_to:
            query = query.lte("created_at", f"{validated_to}T23:59:59")

        res = query.execute()
    except Exception as e:
        # Never 500: if table missing or query fails, return empty
        logger.warning("audit_events query failed: %s", str(e)[:200])
        return {"items": [], "total": 0, "limit": limit, "offset": offset}

    items = res.data or []
    total = res.count if res.count is not None else len(items)

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }
