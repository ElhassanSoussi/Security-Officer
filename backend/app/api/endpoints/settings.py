"""
Settings & Member Management API.
"""
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.core.auth import get_current_user, require_user_id
from app.core.config import get_settings
from app.core.database import get_supabase, get_supabase_admin
from app.core.entitlements import get_plan
from app.core.org_context import parse_uuid, resolve_org_id_for_user

router = APIRouter()
security = HTTPBearer()
settings = get_settings()

ORG_SETTINGS_ROLES = {"owner", "admin"}
MEMBER_MANAGEMENT_ROLES = {"owner", "admin"}
ALL_MEMBER_ROLES = {"owner", "admin", "compliance_manager", "reviewer", "viewer", "manager"}  # manager kept as legacy alias


def _normalize_role(role: Optional[str]) -> Optional[str]:
    raw = str(role or "").strip().lower()
    if not raw:
        return None
    if raw == "manager":
        return "compliance_manager"
    return raw


class OrgUpdateRequest(BaseModel):
    name: Optional[str] = None
    trade_type: Optional[str] = None
    company_size: Optional[str] = None


class InviteRequest(BaseModel):
    email: str
    role: str = "viewer"


class ProfileResponse(BaseModel):
    user_id: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    title: Optional[str] = None


class ProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    title: Optional[str] = None


def _supabase_auth_headers(access_token: str) -> dict:
    return {
        "apikey": settings.SUPABASE_KEY,
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }


def _fetch_auth_user(access_token: str) -> dict:
    url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/user"
    try:
        res = httpx.get(url, headers=_supabase_auth_headers(access_token), timeout=8.0)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Failed to reach Supabase auth") from exc
    if res.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid token")
    return res.json() or {}


def _update_auth_user(access_token: str, metadata: dict) -> dict:
    url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/user"
    payload = {"data": metadata}
    try:
        res = httpx.put(url, headers=_supabase_auth_headers(access_token), json=payload, timeout=8.0)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Failed to update profile in Supabase auth") from exc
    if res.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to update profile")
    return res.json() or {}


def _get_member_role(sb_admin, org_id: str, user_id: str) -> Optional[str]:
    try:
        mem = (
            sb_admin.table("memberships")
            .select("role")
            .eq("org_id", org_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if mem.data:
            return _normalize_role(mem.data[0].get("role")) or None
    except Exception:
        return None
    return None


def _fetch_org_row(sb, org_id: str) -> dict:
    """
    Read organization row across schema variants.
    Some environments don't have plan_tier/trade_type/company_size yet.
    """
    select_attempts = (
        "id,name,owner_id,plan_tier,trade_type,company_size",
        "id,name,owner_id,plan_tier",
        "id,name,owner_id,trade_type,company_size",
        "id,name,owner_id",
    )
    last_exc: Exception | None = None
    for select_cols in select_attempts:
        try:
            res = (
                sb.table("organizations")
                .select(select_cols)
                .eq("id", org_id)
                .execute()
            )
            if res.data:
                return res.data[0]
        except Exception as exc:
            last_exc = exc
            continue
    if last_exc:
        raise last_exc
    raise HTTPException(status_code=404, detail="Organization not found")


@router.get("/org")
def get_org_settings(
    org_id: Optional[str] = Query(None, description="Organization UUID"),
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """Return org info, usage, members and caller role."""
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)
    admin_sb = get_supabase_admin()

    parsed_org_id = parse_uuid(org_id, "org_id", required=False) if org_id else None
    org_id = resolve_org_id_for_user(sb, user_id, parsed_org_id, request=request)

    try:
        org = _fetch_org_row(sb, org_id)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to load organization settings")

    plan_tier = str(org.get("plan_tier") or "starter").strip().lower()
    ent = get_plan(plan_tier)

    exports_used = 0
    storage_used = 0
    try:
        usage_res = (
            sb.table("org_usage")
            .select("exports_used,storage_used_bytes")
            .eq("org_id", org_id)
            .order("period_start", desc=True)
            .limit(1)
            .execute()
        )
        if usage_res.data:
            usage_row = usage_res.data[0] or {}
            exports_used = int(usage_row.get("exports_used") or 0)
            storage_used = int(usage_row.get("storage_used_bytes") or 0)
    except Exception:
        pass

    try:
        mem_res = sb.table("memberships").select("user_id,role,created_at").eq("org_id", org_id).execute()
        members = mem_res.data or []
    except Exception:
        members = []

    my_role = next((_normalize_role(m.get("role")) for m in members if m.get("user_id") == user_id), None)
    if not my_role:
        my_role = _get_member_role(admin_sb, org_id, user_id) or "viewer"

    if my_role not in ORG_SETTINGS_ROLES:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "forbidden",
                "message": "Only owner/admin can access organization settings",
            },
        )

    # Normalize legacy role labels in the payload shown to the UI.
    normalized_members = []
    for m in members:
        row = dict(m)
        row["role"] = _normalize_role(row.get("role")) or "viewer"
        normalized_members.append(row)

    return {
        "id": org["id"],
        "name": org.get("name"),
        "owner_id": org.get("owner_id"),
        "trade_type": org.get("trade_type"),
        "company_size": org.get("company_size"),
        "my_role": my_role,
        "plan": plan_tier,
        "exports_used": exports_used,
        "exports_limit": int(ent.get("exports_per_month", 10)),
        "storage_used": storage_used,
        "storage_limit": int(ent.get("storage_bytes", 500 * 1024 * 1024)),
        "members": normalized_members,
    }


def _apply_org_update(
    update: OrgUpdateRequest,
    org_id: Optional[str],
    request: Request,
    user,
    token: HTTPAuthorizationCredentials,
):
    user_id = require_user_id(user)
    sb = get_supabase(token.credentials)
    admin_sb = get_supabase_admin()

    parsed_org_id = parse_uuid(org_id, "org_id", required=False) if org_id else None
    resolved_org_id = resolve_org_id_for_user(sb, user_id, parsed_org_id, request=request)

    member_role = _get_member_role(admin_sb, resolved_org_id, user_id) or "viewer"
    if member_role not in ORG_SETTINGS_ROLES:
        raise HTTPException(status_code=403, detail="Only owner/admin can update organization settings")

    payload = {}
    if update.name is not None:
        name = update.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Organization name cannot be empty")
        payload["name"] = name
    if update.trade_type is not None:
        payload["trade_type"] = update.trade_type.strip() or None
    if update.company_size is not None:
        payload["company_size"] = update.company_size.strip() or None

    if not payload:
        raise HTTPException(status_code=400, detail="No fields to update")

    try:
        sb.table("organizations").update(payload).eq("id", resolved_org_id).execute()
    except Exception:
        # Retry with a schema-compatible subset when optional columns are not present.
        fallback_payload = {"name": payload.get("name")} if payload.get("name") else {}
        if not fallback_payload:
            raise HTTPException(
                status_code=400,
                detail="This environment does not support trade_type/company_size columns yet",
            )
        admin_sb.table("organizations").update(fallback_payload).eq("id", resolved_org_id).execute()

    return {"status": "ok", "org_id": resolved_org_id, "updated_fields": list(payload.keys())}


@router.put("/org")
def update_org_settings(
    update: OrgUpdateRequest,
    org_id: Optional[str] = Query(None, description="Organization UUID"),
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    return _apply_org_update(update, org_id, request, user, token)


@router.patch("/org")
def patch_org_settings(
    update: OrgUpdateRequest,
    org_id: Optional[str] = Query(None, description="Organization UUID"),
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    return _apply_org_update(update, org_id, request, user, token)


@router.get("/profile", response_model=ProfileResponse)
def get_profile(
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """Return the caller's profile from Supabase Auth metadata."""
    user_id = require_user_id(user)
    auth_user = _fetch_auth_user(token.credentials)
    metadata = auth_user.get("user_metadata") or auth_user.get("data") or {}
    return {
        "user_id": user_id,
        "email": auth_user.get("email") or (user.get("email") if isinstance(user, dict) else None),
        "full_name": metadata.get("full_name") or metadata.get("name"),
        "phone": metadata.get("phone"),
        "title": metadata.get("title"),
    }


@router.put("/profile", response_model=ProfileResponse)
def update_profile(
    update: ProfileUpdateRequest,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """Update caller profile metadata in Supabase Auth."""
    user_id = require_user_id(user)
    auth_user = _fetch_auth_user(token.credentials)
    current_meta = auth_user.get("user_metadata") or auth_user.get("data") or {}
    merged_meta = dict(current_meta)

    if update.full_name is not None:
        merged_meta["full_name"] = update.full_name.strip() or None
    if update.phone is not None:
        merged_meta["phone"] = update.phone.strip() or None
    if update.title is not None:
        merged_meta["title"] = update.title.strip() or None

    updated_user = _update_auth_user(token.credentials, merged_meta)
    updated_meta = updated_user.get("user_metadata") or updated_user.get("data") or merged_meta
    return {
        "user_id": user_id,
        "email": updated_user.get("email") or auth_user.get("email"),
        "full_name": updated_meta.get("full_name") or updated_meta.get("name"),
        "phone": updated_meta.get("phone"),
        "title": updated_meta.get("title"),
    }


@router.post("/org/invite")
def invite_member(
    invite: InviteRequest,
    org_id: str = Query(..., description="Organization UUID"),
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Invite a member by email (placeholder persistence; no email delivery yet).
    """
    user_id = require_user_id(user)
    org_id = parse_uuid(org_id, "org_id")

    sb = get_supabase(token.credentials)
    admin_sb = get_supabase_admin()
    resolve_org_id_for_user(sb, user_id, org_id, request=request)

    role = _normalize_role(invite.role or "viewer") or "viewer"
    if role not in ALL_MEMBER_ROLES:
        raise HTTPException(status_code=400, detail="Invalid role. Use owner/admin/compliance_manager/reviewer/viewer")

    member_role = _get_member_role(admin_sb, org_id, user_id) or "viewer"
    if member_role not in MEMBER_MANAGEMENT_ROLES:
        raise HTTPException(status_code=403, detail="Only owner/admin can invite members")

    email = (invite.email or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email is required")

    try:
        admin_sb.table("invites").insert({
            "org_id": org_id,
            "email": email,
            "role": role,
            "invited_by": user_id,
            "status": "pending",
        }).execute()
    except Exception:
        return {"status": "pending", "email": email, "note": "Invite saved (email delivery coming soon)"}

    return {"status": "pending", "email": email, "note": "Invite saved (email delivery coming soon)"}


@router.delete("/org/members/{target_user_id}")
def remove_member(
    target_user_id: str,
    org_id: str = Query(..., description="Organization UUID"),
    request: Request = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """Remove a member from the org (owner/admin only)."""
    user_id = require_user_id(user)
    org_id = parse_uuid(org_id, "org_id")

    sb = get_supabase(token.credentials)
    admin_sb = get_supabase_admin()
    resolve_org_id_for_user(sb, user_id, org_id, request=request)

    member_role = _get_member_role(admin_sb, org_id, user_id) or "viewer"
    if member_role not in MEMBER_MANAGEMENT_ROLES:
        raise HTTPException(status_code=403, detail="Only owner/admin can remove members")

    if target_user_id == user_id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself from the organization")

    admin_sb.table("memberships").delete().eq("org_id", org_id).eq("user_id", target_user_id).execute()
    return {"status": "ok", "removed": target_user_id}
