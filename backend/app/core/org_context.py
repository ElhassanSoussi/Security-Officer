from typing import Dict, List, Optional, Any
from uuid import UUID
import logging

from fastapi import HTTPException

logger = logging.getLogger("core.org_context")


def parse_uuid(value: Optional[str], field_name: str = "id", required: bool = True) -> Optional[str]:
    """
    Validate UUID inputs consistently across endpoints.
    """
    if value is None or str(value).strip() == "":
        if required:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field_name}")
        return None

    try:
        return str(UUID(str(value).strip()))
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{field_name} must be a UUID")


def list_orgs_for_user(supabase, user_id: str) -> List[Dict[str, str]]:
    """
    Return user's org memberships.  No auto-bootstrap — org creation is
    always explicit via POST /orgs.
    """
    try:
        mems = (
            supabase
            .table("memberships")
            .select("org_id, role")
            .eq("user_id", user_id)
            .execute()
        )
        memberships = mems.data or []
        logger.debug(f"list_orgs_for_user: user_id={user_id} memberships_count={len(memberships)}")
    except Exception as err:
        logger.warning(f"list_orgs_for_user: memberships query failed for user_id={user_id}: {err}")
        memberships = []

    if not memberships:
        return []

    org_ids = [m["org_id"] for m in memberships if m.get("org_id")]
    org_map: Dict[str, Dict[str, str]] = {}
    if org_ids:
        try:
            orgs = supabase.table("organizations").select("id,name").in_("id", org_ids).execute()
            org_map = {o["id"]: o for o in (orgs.data or [])}
        except Exception as err:
            logger.warning(f"list_orgs_for_user: organizations lookup failed for user_id={user_id}: {err}")

    return [
        {
            "id": str(m["org_id"]),
            "name": org_map.get(m["org_id"], {}).get("name", str(m["org_id"])),
            "role": m.get("role", "member"),
        }
        for m in memberships
        if m.get("org_id")
    ]


def _list_orgs_with_admin_fallback(supabase, user_id: str) -> List[Dict[str, str]]:
    """Try RLS-scoped query first, fall back to admin client on failure/empty."""
    orgs = list_orgs_for_user(supabase, user_id)
    if orgs:
        return orgs
    # Admin fallback — handles RLS policy mismatches without breaking the flow.
    try:
        from app.core.database import get_supabase_admin
        admin_sb = get_supabase_admin()
        orgs = list_orgs_for_user(admin_sb, user_id)
    except Exception as err:
        logger.debug(f"_list_orgs_with_admin_fallback: admin also failed: {err}")
    return orgs


def resolve_org_id_for_user(
    supabase,
    user_id: str,
    requested_org_id: Optional[str],
    request: Optional[Any] = None,
) -> Optional[str]:
    """
    Resolve org context — org_id is REQUIRED.  If missing, raise 403.
    If the user is not a member, raise 403.
    """
    endpoint = ""
    if request is not None:
        try:
            endpoint = getattr(request, "url", {})
            endpoint = str(getattr(endpoint, "path", ""))
        except Exception:
            endpoint = ""

    # If org_id is provided, validate it
    if requested_org_id and str(requested_org_id).strip():
        org_id = parse_uuid(requested_org_id, "org_id", required=True)
        # Check membership (with admin fallback for RLS edge cases)
        orgs = _list_orgs_with_admin_fallback(supabase, user_id)
        if not any(o["id"] == org_id for o in orgs):
            logger.warning(
                f"resolve_org_id: ACCESS DENIED user_id={user_id} "
                f"requested_org={org_id} endpoint={endpoint} "
                f"user_orgs={[o['id'] for o in orgs]}"
            )
            raise HTTPException(status_code=403, detail="Organization access denied")
        logger.debug(f"resolve_org_id: user_id={user_id} org_id={org_id} endpoint={endpoint}")
        if request is not None:
            try:
                request.state.org_id = org_id
            except Exception:
                pass
        return org_id

    # If no org_id, try to resolve a default (with admin fallback)
    orgs = _list_orgs_with_admin_fallback(supabase, user_id)
    if orgs:
        logger.debug(f"resolve_org_id: defaulting to first org={orgs[0]['id']} for user_id={user_id}")
        if request is not None:
            try:
                request.state.org_id = orgs[0]["id"]
            except Exception:
                pass
        return orgs[0]["id"]
    
    # If no orgs at all, raise 403 (caller should handle enrollment)
    logger.warning(f"resolve_org_id: NO ORGS for user_id={user_id} endpoint={endpoint}")
    raise HTTPException(
        status_code=403,
        detail="No organization found. Please create or join an organization."
    )
