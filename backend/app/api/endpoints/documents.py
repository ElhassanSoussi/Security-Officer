"""
Project Documents API — Phase 2 Knowledge Vault + Phase 5 Extensions.

Endpoints:
  GET  /projects/{project_id}/documents  → list documents in project vault
  POST /projects/{project_id}/documents  → upload document into project vault
  DELETE /projects/{project_id}/documents/{document_id}  → remove from vault
  GET  /projects/{project_id}/expirations  → document expiration status (Phase 5 Part 2)
  POST /projects/{project_id}/compliance-pack  → bundle docs into zip (Phase 5 Part 3)
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import logging
import io
import zipfile
import uuid
from datetime import datetime, timezone

from app.core.auth import get_current_user, require_user_id
from app.core.database import get_supabase, get_supabase_admin
from app.core.audit_events import log_audit_event, log_activity_event
from app.core.org_context import parse_uuid, resolve_org_id_for_user
from app.core.ingestion import pdf_processor
from app.core.rbac import get_user_role, role_has_permission, Permission
from app.core.expiration import classify_documents, summarize_expirations
from app.core.rate_limit import export_limiter
from app.core.subscription import check_plan_limit, log_usage_metric

router = APIRouter()
security = HTTPBearer()
logger = logging.getLogger("api.documents")


def _file_extension(filename: str) -> str:
    """Extract lowercase file extension without dot."""
    if "." in filename:
        return filename.rsplit(".", 1)[-1].lower()
    return ""


@router.get("/{project_id}/documents", response_model=List[Dict[str, Any]])
def list_project_documents(
    project_id: str,
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """List all documents uploaded to a project's Knowledge Vault."""
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)
    project_id = parse_uuid(project_id, "project_id", required=True)

    # Verify project exists and caller has access
    try:
        proj = (
            sb.table("projects")
            .select("id, org_id")
            .eq("id", project_id)
            .single()
            .execute()
        )
    except Exception:
        raise HTTPException(status_code=404, detail="Project not found")

    if not proj.data:
        raise HTTPException(status_code=404, detail="Project not found")

    org_id = proj.data["org_id"]
    resolve_org_id_for_user(sb, user_id, org_id, request=request)

    # Query documents table for this project
    res = (
        sb.table("documents")
        .select("id, filename, scope, created_at, metadata, project_id")
        .eq("org_id", org_id)
        .eq("project_id", project_id)
        .order("created_at", desc=True)
        .execute()
    )

    rows = res.data or []

    # Also try to join project_documents for richer metadata (uploaded_by, file_type, etc.)
    pd_map: Dict[str, Dict] = {}
    try:
        pd_res = (
            sb.table("project_documents")
            .select("document_id, uploaded_by, display_name, file_type, file_size_bytes, created_at")
            .eq("project_id", project_id)
            .execute()
        )
        for pd_row in (pd_res.data or []):
            pd_map[pd_row["document_id"]] = pd_row
    except Exception:
        # project_documents table may not exist yet (pre-migration)
        pass

    result = []
    for row in rows:
        doc_id = row["id"]
        pd_meta = pd_map.get(doc_id, {})
        result.append({
            "id": doc_id,
            "filename": pd_meta.get("display_name") or row["filename"],
            "file_type": pd_meta.get("file_type") or _file_extension(row["filename"]),
            "file_size_bytes": pd_meta.get("file_size_bytes"),
            "scope": row.get("scope", "PROJECT"),
            "uploaded_by": pd_meta.get("uploaded_by"),
            "created_at": pd_meta.get("created_at") or row["created_at"],
            "project_id": project_id,
        })

    return result


@router.post("/{project_id}/documents")
async def upload_project_document(
    project_id: str,
    file: UploadFile = File(...),
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Upload a document into a project's Knowledge Vault.
    Supported formats: PDF, DOCX, TXT.
    The document is chunked + embedded and linked to the project for scoped retrieval.
    """
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)
    project_id = parse_uuid(project_id, "project_id", required=True)

    # Verify project exists and get org_id
    try:
        proj = (
            sb.table("projects")
            .select("id, org_id")
            .eq("id", project_id)
            .single()
            .execute()
        )
    except Exception:
        raise HTTPException(status_code=404, detail="Project not found")

    if not proj.data:
        raise HTTPException(status_code=404, detail="Project not found")

    org_id = proj.data["org_id"]
    resolve_org_id_for_user(sb, user_id, org_id, request=request)

    # Subscription tier enforcement — document limit
    from app.core.plan_service import PlanService
    PlanService.enforce_documents_limit(org_id)

    # Existing subscription.check_plan_limit for backward compat
    check_plan_limit(org_id, "documents")

    # Phase 5: Role enforcement — viewer/reviewer cannot upload documents
    _role = get_user_role(org_id, user_id, token.credentials)
    if not role_has_permission(_role or "", Permission.UPLOAD_DOCUMENT):
        raise HTTPException(status_code=403, detail={
            "error": "forbidden",
            "message": f"Insufficient permissions. Required: {Permission.UPLOAD_DOCUMENT.value}. Your role: {_role or 'none'}.",
            "required_permission": Permission.UPLOAD_DOCUMENT.value,
            "your_role": _role or "none",
        })

    # Validate file type
    filename = file.filename or "unknown"
    ext = _file_extension(filename)
    if ext not in ("pdf", "docx", "txt"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '.{ext}'. Allowed: PDF, DOCX, TXT.",
        )

    # Read content
    MAX_SIZE = 10 * 1024 * 1024  # 10MB
    content = await file.read()
    await file.close()
    file_size = len(content)

    if file_size > MAX_SIZE:
        raise HTTPException(status_code=413, detail="File too large. Maximum size is 10MB.")

    if file_size == 0:
        raise HTTPException(status_code=400, detail="File is empty.")

    # Magic byte validation
    if ext == "pdf" and not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="Invalid PDF file signature.")
    elif ext == "docx" and not content.startswith(b"PK\x03\x04"):
        raise HTTPException(status_code=400, detail="Invalid DOCX file signature.")

    # Process: chunk + embed + store in documents/chunks tables
    try:
        result = pdf_processor.process_and_store_document(
            file_content=content,
            filename=filename,
            org_id=org_id,
            project_id=project_id,
            scope="PROJECT",
            token=token.credentials,
        )
        document_id = result["document_id"]
    except Exception as e:
        logger.error("Document ingestion failed for project %s: %s", project_id, e)
        raise HTTPException(status_code=500, detail=f"Document processing failed: {str(e)}")

    # Register in project_documents for richer metadata (best-effort)
    try:
        pd_row = {
            "project_id": project_id,
            "document_id": document_id,
            "org_id": org_id,
            "uploaded_by": user_id,
            "display_name": filename,
            "file_type": ext,
            "file_size_bytes": file_size,
        }
        sb.table("project_documents").insert(pd_row).execute()
    except Exception as e:
        # Table may not exist pre-migration; non-fatal
        logger.warning("project_documents insert failed (non-fatal): %s", e)

    # Audit trail
    log_audit_event(
        sb,
        org_id=org_id,
        user_id=user_id,
        event_type="document_uploaded",
        metadata={
            "project_id": project_id,
            "document_id": document_id,
            "filename": filename,
            "chunks_count": result.get("chunks_count", 0),
        },
    )

    # Activity timeline
    log_activity_event(
        sb,
        org_id=org_id,
        user_id=user_id,
        action_type="document_uploaded",
        entity_type="document",
        entity_id=document_id,
        metadata={"project_id": project_id, "filename": filename},
    )

    # Activity feed
    try:
        sb.table("activities").insert({
            "org_id": org_id,
            "project_id": project_id,
            "event_type": "document_uploaded",
            "description": f"Uploaded {filename}",
            "user_id": user_id,
        }).execute()
    except Exception:
        pass

    # Phase 18: log usage metric (fire-and-forget)
    try:
        log_usage_metric(org_id, "DOCUMENT_UPLOADED")
    except Exception:
        pass

    # Compliance Intelligence — extract metadata and persist (best-effort)
    try:
        from app.core.compliance_engine import extract_document_metadata, upsert_document_metadata
        from app.core.database import get_supabase_admin
        text_preview = ""
        if ext == "txt":
            text_preview = content.decode("utf-8", errors="ignore")[:5000]
        meta = extract_document_metadata(filename, text_preview)
        admin_sb = get_supabase_admin()
        upsert_document_metadata(
            admin_sb,
            org_id=org_id,
            document_id=document_id,
            document_type=meta["document_type"],
            expiration_date=meta["expiration_date"],
            risk_level=meta["risk_level"],
        )
    except Exception as _ce:
        logger.debug("Compliance metadata extraction skipped: %s", _ce)

    return {
        "status": "success",
        "document_id": document_id,
        "filename": filename,
        "chunks_count": result.get("chunks_count", 0),
        "file_size_bytes": file_size,
    }


@router.delete("/{project_id}/documents/{document_id}")
def delete_project_document(
    project_id: str,
    document_id: str,
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """Remove a document from a project's Knowledge Vault."""
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)
    project_id = parse_uuid(project_id, "project_id", required=True)
    document_id = parse_uuid(document_id, "document_id", required=True)

    # Verify project + org
    try:
        proj = (
            sb.table("projects")
            .select("id, org_id")
            .eq("id", project_id)
            .single()
            .execute()
        )
    except Exception:
        raise HTTPException(status_code=404, detail="Project not found")

    if not proj.data:
        raise HTTPException(status_code=404, detail="Project not found")

    org_id = proj.data["org_id"]
    resolve_org_id_for_user(sb, user_id, org_id, request=request)

    # Phase 5: Role enforcement — viewer/reviewer cannot delete documents
    _role = get_user_role(org_id, user_id, token.credentials)
    if not role_has_permission(_role or "", Permission.DELETE_DOCUMENT):
        raise HTTPException(status_code=403, detail={
            "error": "forbidden",
            "message": f"Insufficient permissions. Required: {Permission.DELETE_DOCUMENT.value}. Your role: {_role or 'none'}.",
            "required_permission": Permission.DELETE_DOCUMENT.value,
            "your_role": _role or "none",
        })

    # Delete from project_documents registry
    try:
        sb.table("project_documents").delete().eq("document_id", document_id).eq("project_id", project_id).execute()
    except Exception:
        pass

    # Delete the document (cascades to chunks via FK)
    try:
        sb.table("documents").delete().eq("id", document_id).eq("project_id", project_id).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {e}")

    log_audit_event(
        sb,
        org_id=org_id,
        user_id=user_id,
        event_type="document_deleted",
        metadata={"project_id": project_id, "document_id": document_id},
    )
    log_activity_event(
        sb,
        org_id=org_id,
        user_id=user_id,
        action_type="document_deleted",
        entity_type="document",
        entity_id=document_id,
        metadata={"project_id": project_id},
    )

    return {"status": "deleted", "document_id": document_id}


# ── Phase 5 Part 2: Expiration Tracking ──────────────────────────────────────

@router.get("/{project_id}/expirations")
def get_project_expirations(
    project_id: str,
    reminder_days: int = Query(30, ge=0, le=365, description="Days before expiry to flag as 'expiring'"),
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Get expiration status for all documents in a project.
    Each document is classified as: valid, expiring, expired, or no_expiration.
    """
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)
    project_id = parse_uuid(project_id, "project_id", required=True)

    # Verify project + membership
    try:
        proj = (
            sb.table("projects")
            .select("id, org_id")
            .eq("id", project_id)
            .single()
            .execute()
        )
    except Exception:
        raise HTTPException(status_code=404, detail="Project not found")

    if not proj.data:
        raise HTTPException(status_code=404, detail="Project not found")

    org_id = proj.data["org_id"]
    resolve_org_id_for_user(sb, user_id, org_id, request=request)

    # RBAC: VIEW_DOCUMENT is sufficient
    _role = get_user_role(org_id, user_id, token.credentials)
    if not role_has_permission(_role or "", Permission.VIEW_DOCUMENT):
        raise HTTPException(status_code=403, detail={
            "error": "forbidden",
            "message": f"Insufficient permissions. Required: {Permission.VIEW_DOCUMENT.value}. Your role: {_role or 'none'}.",
            "required_permission": Permission.VIEW_DOCUMENT.value,
            "your_role": _role or "none",
        })

    # Fetch project_documents with expiration fields
    docs = []
    try:
        pd_res = (
            sb.table("project_documents")
            .select("document_id, display_name, file_type, expiration_date, reminder_days_before, created_at")
            .eq("project_id", project_id)
            .execute()
        )
        docs = pd_res.data or []
    except Exception:
        # Table may not have expiration columns yet — return empty gracefully
        pass

    summary = summarize_expirations(docs, reminder_days_before=reminder_days)
    summary["project_id"] = project_id
    return summary


# ── Phase 5 Part 3: Compliance Pack Builder ──────────────────────────────────

class CompliancePackRequest(BaseModel):
    document_ids: List[str]


@router.post("/{project_id}/compliance-pack")
def build_compliance_pack(
    project_id: str,
    body: CompliancePackRequest,
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Bundle selected documents into a compliance pack (zip).
    Requires EXPORT_RUN permission. Logs an audit event.
    """
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)
    project_id = parse_uuid(project_id, "project_id", required=True)

    # Phase 6: Rate limiting for export/pack endpoint
    export_limiter.check(user_id)

    # Validate non-empty selection
    if not body.document_ids:
        raise HTTPException(status_code=400, detail="document_ids must not be empty")

    # Deduplicate and validate UUIDs
    doc_ids = []
    seen = set()
    for raw_id in body.document_ids:
        did = parse_uuid(raw_id, "document_id", required=True)
        if did not in seen:
            doc_ids.append(did)
            seen.add(did)

    # Verify project + membership
    try:
        proj = (
            sb.table("projects")
            .select("id, org_id")
            .eq("id", project_id)
            .single()
            .execute()
        )
    except Exception:
        raise HTTPException(status_code=404, detail="Project not found")

    if not proj.data:
        raise HTTPException(status_code=404, detail="Project not found")

    org_id = proj.data["org_id"]
    resolve_org_id_for_user(sb, user_id, org_id, request=request)

    # RBAC: requires EXPORT_RUN
    _role = get_user_role(org_id, user_id, token.credentials)
    if not role_has_permission(_role or "", Permission.EXPORT_RUN):
        raise HTTPException(status_code=403, detail={
            "error": "forbidden",
            "message": f"Insufficient permissions. Required: {Permission.EXPORT_RUN.value}. Your role: {_role or 'none'}.",
            "required_permission": Permission.EXPORT_RUN.value,
            "your_role": _role or "none",
        })

    # Fetch the requested documents — verify they belong to this project
    try:
        docs_res = (
            sb.table("documents")
            .select("id, filename, project_id, org_id")
            .eq("project_id", project_id)
            .in_("id", doc_ids)
            .execute()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to query documents")

    found_docs = docs_res.data or []
    found_ids = {d["id"] for d in found_docs}
    missing_ids = [did for did in doc_ids if did not in found_ids]

    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Documents not found in project: {missing_ids}",
        )

    # Cross-org protection
    for doc in found_docs:
        if doc.get("org_id") and doc["org_id"] != org_id:
            raise HTTPException(status_code=403, detail="Cross-organization access denied")

    # Build zip in memory
    pack_id = str(uuid.uuid4())
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for doc in found_docs:
            filename = doc.get("filename", f"document_{doc['id']}.txt")
            # Try to fetch content from storage; include a manifest entry regardless
            content = _fetch_document_content(sb, org_id, project_id, doc["id"], filename)
            zf.writestr(filename, content)

        # Add manifest
        manifest_lines = [
            f"Compliance Pack: {pack_id}",
            f"Project: {project_id}",
            f"Generated: {datetime.now(timezone.utc).isoformat()}",
            f"Generated by: {user_id}",
            f"Documents ({len(found_docs)}):",
        ]
        for doc in found_docs:
            manifest_lines.append(f"  - {doc.get('filename', doc['id'])}")
        zf.writestr("_manifest.txt", "\n".join(manifest_lines))

    zip_buffer.seek(0)
    zip_bytes = zip_buffer.getvalue()

    # Record pack (best-effort)
    try:
        sb.table("compliance_packs").insert({
            "id": pack_id,
            "project_id": project_id,
            "org_id": org_id,
            "created_by": user_id,
            "document_ids": doc_ids,
            "file_count": len(found_docs),
            "size_bytes": len(zip_bytes),
        }).execute()
    except Exception:
        # Table may not exist yet — non-fatal
        pass

    # Audit event
    log_audit_event(
        sb,
        org_id=org_id,
        user_id=user_id,
        event_type="compliance_pack_created",
        metadata={
            "pack_id": pack_id,
            "project_id": project_id,
            "document_ids": doc_ids,
            "document_count": len(found_docs),
        },
    )
    log_activity_event(
        sb,
        org_id=org_id,
        user_id=user_id,
        action_type="compliance_pack_created",
        entity_type="compliance_pack",
        entity_id=pack_id,
        metadata={"project_id": project_id, "document_count": len(found_docs)},
    )

    # Return zip as streaming response
    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="compliance-pack-{pack_id[:8]}.zip"',
            "X-Pack-Id": pack_id,
        },
    )


def _fetch_document_content(sb, org_id: str, project_id: str, doc_id: str, filename: str) -> bytes:
    """
    Best-effort fetch of document content from storage or chunks.
    Falls back to a placeholder if storage is unavailable.
    """
    # Try storage first
    try:
        storage_path = f"org/{org_id}/projects/{project_id}/{filename}"
        data = sb.storage.from_("documents").download(storage_path)
        if data:
            return data
    except Exception:
        pass

    # Fallback: concatenate chunk texts
    try:
        chunks_res = (
            sb.table("chunks")
            .select("content")
            .eq("document_id", doc_id)
            .order("chunk_index")
            .execute()
        )
        if chunks_res.data:
            return "\n".join(c["content"] for c in chunks_res.data).encode("utf-8")
    except Exception:
        pass

    return f"[Content unavailable for {filename}]".encode("utf-8")
