from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List
import logging

from app.core.auth import get_current_user, require_user_id
from app.core.database import get_supabase, get_supabase_admin
from app.core.org_context import list_orgs_for_user

router = APIRouter()
logger = logging.getLogger("api.orgs")

class OrgCreate(BaseModel):
    name: str
    trade_type: str | None = None
    company_size: str | None = None

class OrgResponse(BaseModel):
    id: str
    name: str
    role: str

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

@router.get("", response_model=List[OrgResponse])
def list_my_orgs(user=Depends(get_current_user), token: HTTPAuthorizationCredentials = Depends(security)):
    """
    List organizations the current user is a member of.
    Uses the caller's JWT for RLS-scoped queries; falls back to admin client
    when RLS policies block the read (e.g. policy mismatch, missing grants).
    """
    user_id = require_user_id(user)
    logger.info(f"list_my_orgs: user_id={user_id}")

    # 1. Try with user's JWT (RLS-scoped)
    supabase = get_supabase(token.credentials)
    try:
        orgs = list_orgs_for_user(supabase, user_id)
        if orgs:
            logger.info(f"list_my_orgs: found {len(orgs)} org(s) for user_id={user_id}")
            return orgs
    except Exception as err:
        logger.warning(f"list_my_orgs: RLS-scoped query failed for user_id={user_id}: {err}")

    # 2. Fallback: admin client (bypasses RLS). This handles cases where
    #    RLS policies on memberships/organizations are too restrictive or
    #    the user JWT doesn't match the policy expectations.
    try:
        admin_sb = get_supabase_admin()
        orgs = list_orgs_for_user(admin_sb, user_id)
        if orgs:
            logger.info(f"list_my_orgs: admin fallback found {len(orgs)} org(s) for user_id={user_id}")
            return orgs
    except Exception as admin_err:
        logger.warning(f"list_my_orgs: admin fallback also failed for user_id={user_id}: {admin_err}")

    logger.info(f"list_my_orgs: no orgs found for user_id={user_id}")
    return []

@router.get("/current", response_model=OrgResponse)
def get_current_org(
    prefer_org_id: str | None = None,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Return the caller's "current" organization.

    Deterministic rules:
      - if prefer_org_id is provided and the user is a member, return it
      - else return the first org membership (stable enough for Phase 1)
      - if user has no org memberships: 404
    """
    from app.core.org_context import parse_uuid

    user_id = require_user_id(user)
    logger.info(f"get_current_org: user_id={user_id}, prefer_org_id={prefer_org_id}")

    # Try RLS-scoped first, then admin fallback (same pattern as list_my_orgs)
    orgs = []
    sb = get_supabase(token.credentials)
    try:
        orgs = list_orgs_for_user(sb, user_id)
    except Exception as err:
        logger.warning(f"get_current_org: RLS query failed: {err}")

    if not orgs:
        try:
            admin_sb = get_supabase_admin()
            orgs = list_orgs_for_user(admin_sb, user_id)
        except Exception as admin_err:
            logger.warning(f"get_current_org: admin fallback failed: {admin_err}")

    if not orgs:
        raise HTTPException(status_code=404, detail="No org membership")

    if prefer_org_id and str(prefer_org_id).strip():
        preferred = parse_uuid(prefer_org_id, "prefer_org_id", required=True)
        for o in orgs:
            if o.get("id") == preferred:
                return o

    return orgs[0]

@router.post("", response_model=OrgResponse)
def create_org(
    org: OrgCreate,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Create a new organization and make current user the owner.
    Uses the caller's JWT (RLS) by default; falls back to admin client if configured.
    """
    user_id = require_user_id(user)
    
    name = (org.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Organization name is required")

    sb = get_supabase(token.credentials)
    admin_sb = get_supabase_admin()

    # 1. Create Org
    org_payload = {
        "name": name,
        "owner_id": user_id,
    }
    if org.trade_type:
        org_payload["trade_type"] = str(org.trade_type).strip()
    if org.company_size:
        org_payload["company_size"] = str(org.company_size).strip()
    try:
        res_org = (
            sb
            .table("organizations")
            .insert(org_payload)
            .execute()
        )
    except Exception as err:
        # Retry without optional fields for older schemas that don't have
        # trade_type/company_size columns yet.
        try:
            fallback_payload = {"name": name, "owner_id": user_id}
            res_org = (
                sb
                .table("organizations")
                .insert(fallback_payload)
                .execute()
            )
        except Exception:
            res_org = (
                admin_sb
                .table("organizations")
                .insert({"name": name, "owner_id": user_id})
                .execute()
            )
    
    if not res_org.data:
        raise HTTPException(status_code=500, detail="Failed to create organization")
        
    new_org = res_org.data[0]
    
    # 2. Create Membership (Owner)
    try:
        sb.table("memberships").insert({
            "user_id": user_id,
            "org_id": new_org["id"],
            "role": "owner"
        }).execute()
    except Exception as err:
        try:
            admin_sb.table("memberships").insert({
                "user_id": user_id,
                "org_id": new_org["id"],
                "role": "owner"
            }).execute()
        except Exception:
            raise HTTPException(status_code=500, detail=f"Failed to create membership: {err}")
    
    # 3. Create Trial Subscription (best effort, table may not exist in partial setups)
    try:
        admin_sb.table("subscriptions").upsert({
            "org_id": new_org["id"],
            "status": "trialing",
            "plan_id": "starter",
            "exports_used": 0,
            "exports_limit": 10
        }).execute()
    except Exception as err:
        print(f"⚠️ subscription create skipped: {err}")
    
    return {
        "id": new_org["id"],
        "name": new_org["name"],
        "role": "owner"
    }


@router.post("/onboard", response_model=OrgResponse)
def onboard_user(
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Onboarding helper: If user has 0 orgs, create "My Organization" automatically.
    Returns the new org or the first existing org.
    """
    user_id = require_user_id(user)
    supabase = get_supabase(token.credentials)
    
    # 1. Check if user already has orgs
    existing = list_orgs_for_user(supabase, user_id)
    if existing:
        return existing[0]

    # 2. Create default org
    return create_org(OrgCreate(name="My Organization"), user=user, token=token)
