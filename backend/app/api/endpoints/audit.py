"""
Audit Log API — Activity Timeline + Compliance Review.

Endpoints:
  GET /audit/log     → paginated run_audits with filters (compliance review)
  GET /audit/exports → export events (who exported what, when)
  GET /audit/events  → paginated activity timeline with rich filters
  GET /audit/export  → CSV download of filtered activity events
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Any, Dict, List, Optional
import csv
import io
import json
import logging

from app.core.auth import get_current_user, require_user_id
from app.core.database import get_supabase
from app.core.org_context import parse_uuid, resolve_org_id_for_user
from app.core.audit_events import sanitize_metadata

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


# ── Shared helpers ───────────────────────────────────────────────────────────

def _validate_iso_date(value: Optional[str], field_name: str) -> Optional[str]:
    """Validate an ISO date string (YYYY-MM-DD). Returns None if empty/None."""
    if not value or not str(value).strip():
        return None
    import re
    from datetime import datetime as _dt
    s = str(value).strip()
    date_part = s[:10]
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_part):
        raise HTTPException(status_code=400, detail=f"{field_name} must be ISO format YYYY-MM-DD")
    try:
        _dt.strptime(date_part, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{field_name} is not a valid date")
    return date_part


# Keys whose names contain these fragments are stripped from response metadata.
_SENSITIVE_FRAGS = ("password", "token", "secret", "api_key", "apikey",
                    "credential", "private_key", "access_key", "auth", "bearer", "jwt")


def _safe_meta(raw: Any) -> Dict[str, Any]:
    """Return a sanitized copy of a metadata dict (or {} if unparseable)."""
    if not raw:
        return {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return {}
    if not isinstance(raw, dict):
        return {}
    return sanitize_metadata(raw)


def _build_events_query(
    sb,
    org_id: str,
    *,
    user_id_filter: Optional[str],
    action_type: Optional[str],
    project_id: Optional[str],
    validated_from: Optional[str],
    validated_to: Optional[str],
    limit: int,
    offset: int,
):
    """Build the audit_events query with all optional filters applied."""
    query = (
        sb.table("audit_events")
        .select("*", count="exact")
        .eq("org_id", org_id)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
    )
    if user_id_filter and user_id_filter.strip():
        query = query.eq("user_id", user_id_filter.strip())
    if action_type and action_type.strip():
        query = query.eq("event_type", action_type.strip())
    if validated_from:
        query = query.gte("created_at", f"{validated_from}T00:00:00")
    if validated_to:
        query = query.lte("created_at", f"{validated_to}T23:59:59")
    return query


def _normalize_event_row(row: Dict[str, Any], project_id_filter: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Map a raw audit_events DB row to the canonical API shape.
    Returns None if project_id_filter is set and the row doesn't match.
    """
    meta = _safe_meta(row.get("metadata"))

    # Server-side project_id filter via metadata (client-side fallback)
    if project_id_filter and meta.get("project_id") != project_id_filter:
        return None

    return {
        "id": row.get("id"),
        "timestamp": row.get("created_at"),
        "user_id": row.get("user_id"),
        "user_email": meta.pop("user_email", None),
        "action_type": row.get("event_type"),
        "entity_type": row.get("entity_type") or meta.pop("entity_type", None) or "",
        "entity_id": row.get("entity_id") or meta.pop("entity_id", None) or "",
        "metadata": meta,
    }


# ── GET /events ───────────────────────────────────────────────────────────────

@router.get("/events")
def get_audit_events(
    org_id: Optional[str] = Query(None, description="Organization UUID (required)"),
    user_id: Optional[str] = Query(None, description="Filter by user UUID"),
    action_type: Optional[str] = Query(None, description="Filter by action/event type"),
    project_id: Optional[str] = Query(None, description="Filter by project UUID (metadata match)"),
    start_date: Optional[str] = Query(None, alias="from", description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, alias="to", description="End date YYYY-MM-DD"),
    page: int = Query(1, ge=1, description="1-based page number"),
    page_size: int = Query(25, ge=1, le=200, description="Rows per page"),
    request: Request = None,
    current_user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Paginated activity timeline from audit_events.
    Filters: user_id, action_type, project_id, date range.
    Response shape: {total, page, page_size, events: [...]}
    Never returns 500 — always valid JSON.
    """
    caller_id = require_user_id(current_user)

    if not org_id or not str(org_id).strip():
        raise HTTPException(status_code=400, detail="org_id is required")

    validated_from = _validate_iso_date(start_date, "from")
    validated_to = _validate_iso_date(end_date, "to")

    try:
        sb = get_supabase(token.credentials)
    except Exception:
        logger.warning("audit_events: failed to get supabase client")
        return {"events": [], "total": 0, "page": page, "page_size": page_size}

    try:
        org_id = resolve_org_id_for_user(sb, caller_id, org_id, request=request)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=403, detail="Organization access denied")

    offset = (page - 1) * page_size

    try:
        query = _build_events_query(
            sb, org_id,
            user_id_filter=user_id,
            action_type=action_type,
            project_id=project_id,
            validated_from=validated_from,
            validated_to=validated_to,
            limit=page_size,
            offset=offset,
        )
        res = query.execute()
    except Exception as exc:
        logger.warning("audit_events query failed: %s", str(exc)[:200])
        return {"events": [], "total": 0, "page": page, "page_size": page_size}

    raw_rows: List[Dict[str, Any]] = res.data or []
    total = res.count if res.count is not None else len(raw_rows)

    events = []
    for row in raw_rows:
        normalized = _normalize_event_row(row, project_id)
        if normalized is not None:
            events.append(normalized)

    return {
        "events": events,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ── GET /export (CSV download) ────────────────────────────────────────────────

@router.get("/export")
def export_audit_csv(
    org_id: Optional[str] = Query(None, description="Organization UUID (required)"),
    user_id: Optional[str] = Query(None, description="Filter by user UUID"),
    action_type: Optional[str] = Query(None, description="Filter by action/event type"),
    project_id: Optional[str] = Query(None, description="Filter by project UUID"),
    start_date: Optional[str] = Query(None, alias="from", description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, alias="to", description="End date YYYY-MM-DD"),
    request: Request = None,
    current_user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """
    CSV export of filtered audit_events — org-scoped, metadata sanitized.
    Hard cap: 5 000 rows. Content-Disposition triggers browser download.
    """
    caller_id = require_user_id(current_user)

    if not org_id or not str(org_id).strip():
        raise HTTPException(status_code=400, detail="org_id is required")

    validated_from = _validate_iso_date(start_date, "from")
    validated_to = _validate_iso_date(end_date, "to")

    try:
        sb = get_supabase(token.credentials)
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable")

    try:
        org_id = resolve_org_id_for_user(sb, caller_id, org_id, request=request)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=403, detail="Organization access denied")

    MAX_EXPORT_ROWS = 5000
    try:
        query = _build_events_query(
            sb, org_id,
            user_id_filter=user_id,
            action_type=action_type,
            project_id=project_id,
            validated_from=validated_from,
            validated_to=validated_to,
            limit=MAX_EXPORT_ROWS,
            offset=0,
        )
        res = query.execute()
    except Exception as exc:
        logger.warning("audit_export query failed: %s", str(exc)[:200])
        raise HTTPException(status_code=500, detail="Export query failed")

    raw_rows: List[Dict[str, Any]] = res.data or []

    # Build CSV in-memory
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(["id", "timestamp", "user_id", "action_type", "entity_type", "entity_id", "metadata"])

    for row in raw_rows:
        normalized = _normalize_event_row(row, project_id)
        if normalized is None:
            continue
        writer.writerow([
            normalized.get("id", ""),
            normalized.get("timestamp", ""),
            normalized.get("user_id", ""),
            normalized.get("action_type", ""),
            normalized.get("entity_type", ""),
            normalized.get("entity_id", ""),
            json.dumps(normalized.get("metadata", {}), ensure_ascii=False),
        ])

    output.seek(0)

    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"audit_events_{ts}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
