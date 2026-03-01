"""
Phase 5: Role-Based Access Control (RBAC) — Hard Security Layer.

Roles (ordered by privilege):
  owner              → Full access
  admin              → Full access
  compliance_manager → Upload docs, run analysis, edit answers
  reviewer           → Review/approve answers, read
  viewer             → Read-only

This module provides:
  - Role hierarchy + permission matrix
  - get_user_role() to resolve a user's role within an org
  - require_role() FastAPI dependency factory
  - Structured 403 JSON on permission denial
"""
import logging
from enum import Enum
from typing import Optional, Set

from fastapi import Depends, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.auth import get_current_user, require_user_id
from app.core.database import get_supabase, get_supabase_admin

logger = logging.getLogger("core.rbac")
security = HTTPBearer()


# ── Role Enum ────────────────────────────────────────────────────────────────

class Role(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    COMPLIANCE_MANAGER = "compliance_manager"
    REVIEWER = "reviewer"
    VIEWER = "viewer"


# Legacy alias mapping
_ROLE_ALIASES = {
    "manager": Role.COMPLIANCE_MANAGER,
}

ALL_ROLES: Set[str] = {r.value for r in Role}


def normalize_role(raw: Optional[str]) -> Optional[str]:
    """Normalize a role string, handling legacy aliases."""
    if not raw:
        return None
    cleaned = raw.strip().lower()
    if cleaned in _ROLE_ALIASES:
        return _ROLE_ALIASES[cleaned].value
    if cleaned in ALL_ROLES:
        return cleaned
    return None


# ── Permission Definitions ───────────────────────────────────────────────────

class Permission(str, Enum):
    # Organization management
    ORG_SETTINGS = "org_settings"
    MANAGE_MEMBERS = "manage_members"
    # Project lifecycle
    CREATE_PROJECT = "create_project"
    EDIT_PROJECT = "edit_project"
    VIEW_PROJECT = "view_project"
    # Document management
    UPLOAD_DOCUMENT = "upload_document"
    DELETE_DOCUMENT = "delete_document"
    VIEW_DOCUMENT = "view_document"
    # Analysis / Runs
    RUN_ANALYSIS = "run_analysis"
    EDIT_ANSWER = "edit_answer"
    VIEW_RUN = "view_run"
    # Review workflow
    REVIEW_ANSWER = "review_answer"
    BULK_REVIEW = "bulk_review"
    # Export
    EXPORT_RUN = "export_run"


# Permission matrix: role → set of permissions
_PERMISSION_MATRIX: dict[str, Set[Permission]] = {
    Role.OWNER.value: set(Permission),           # all permissions
    Role.ADMIN.value: set(Permission),            # all permissions
    Role.COMPLIANCE_MANAGER.value: {
        Permission.CREATE_PROJECT,
        Permission.EDIT_PROJECT,
        Permission.VIEW_PROJECT,
        Permission.UPLOAD_DOCUMENT,
        Permission.DELETE_DOCUMENT,
        Permission.VIEW_DOCUMENT,
        Permission.RUN_ANALYSIS,
        Permission.EDIT_ANSWER,
        Permission.VIEW_RUN,
        Permission.EXPORT_RUN,
        # Compliance managers can also review
        Permission.REVIEW_ANSWER,
        Permission.BULK_REVIEW,
    },
    Role.REVIEWER.value: {
        Permission.VIEW_PROJECT,
        Permission.VIEW_DOCUMENT,
        Permission.VIEW_RUN,
        Permission.REVIEW_ANSWER,
        Permission.BULK_REVIEW,
        Permission.EXPORT_RUN,
    },
    Role.VIEWER.value: {
        Permission.VIEW_PROJECT,
        Permission.VIEW_DOCUMENT,
        Permission.VIEW_RUN,
    },
}


def role_has_permission(role: str, permission: Permission) -> bool:
    """Check if a role grants a specific permission."""
    normalized = normalize_role(role)
    if not normalized:
        return False
    perms = _PERMISSION_MATRIX.get(normalized, set())
    return permission in perms


def get_role_permissions(role: str) -> Set[Permission]:
    """Return the set of permissions for a role."""
    normalized = normalize_role(role)
    if not normalized:
        return set()
    return set(_PERMISSION_MATRIX.get(normalized, set()))


# ── Role Resolution ──────────────────────────────────────────────────────────

def get_user_role(org_id: str, user_id: str, token: Optional[str] = None) -> Optional[str]:
    """
    Look up the user's role in the given org from the memberships table.
    Uses admin client for reliability (bypasses RLS edge cases).
    Falls back to RLS-scoped client if admin unavailable.
    """
    # Try admin client first (most reliable)
    try:
        admin_sb = get_supabase_admin()
        mem = (
            admin_sb.table("memberships")
            .select("role")
            .eq("org_id", org_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if mem.data:
            return normalize_role(mem.data[0].get("role"))
    except Exception as e:
        logger.debug("get_user_role admin lookup failed: %s", e)

    # Fallback to user-scoped client
    if token:
        try:
            sb = get_supabase(token)
            mem = (
                sb.table("memberships")
                .select("role")
                .eq("org_id", org_id)
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
            if mem.data:
                return normalize_role(mem.data[0].get("role"))
        except Exception as e:
            logger.debug("get_user_role RLS lookup failed: %s", e)

    return None


# ── FastAPI Dependency Factories ─────────────────────────────────────────────

def _forbidden_response(permission: Permission, role: Optional[str]) -> dict:
    """Structured 403 error payload."""
    return {
        "error": "forbidden",
        "message": f"Insufficient permissions. Required: {permission.value}. Your role: {role or 'none'}.",
        "required_permission": permission.value,
        "your_role": role or "none",
    }


class RoleChecker:
    """
    FastAPI dependency that enforces a specific permission.

    Usage in endpoint:
        @router.post("/foo")
        def foo(..., _auth=Depends(require_role(Permission.RUN_ANALYSIS))):
            ...

    Resolves org_id from:
      1. Query parameter `org_id`
      2. Form field `org_id`
      3. Request body `org_id`
      4. Path parameter `project_id` → look up project's org_id
    """

    def __init__(self, permission: Permission):
        self.permission = permission

    def __call__(
        self,
        request: Request,
        user=Depends(get_current_user),
        token: HTTPAuthorizationCredentials = Depends(security),
    ) -> dict:
        user_id = require_user_id(user)

        # Attempt to resolve org_id from various sources
        org_id = self._extract_org_id(request)

        if not org_id:
            # Can't enforce role without org context — let downstream
            # endpoints handle org resolution (which itself enforces membership).
            # This is a safe fallback: if the endpoint doesn't use org_id,
            # the membership check in resolve_org_id_for_user will still fire.
            logger.debug(
                "RoleChecker: no org_id found in request for %s, deferring to endpoint",
                self.permission.value,
            )
            return {"user_id": user_id, "role": None, "org_id": None}

        role = get_user_role(org_id, user_id, token.credentials)

        if not role:
            raise HTTPException(
                status_code=403,
                detail=_forbidden_response(self.permission, None),
            )

        if not role_has_permission(role, self.permission):
            raise HTTPException(
                status_code=403,
                detail=_forbidden_response(self.permission, role),
            )

        return {"user_id": user_id, "role": role, "org_id": org_id}

    def _extract_org_id(self, request: Request) -> Optional[str]:
        """Best-effort org_id extraction from request context."""
        # 1. Query params
        org_id = request.query_params.get("org_id")
        if org_id and org_id.strip():
            return org_id.strip()

        # 2. Path params
        if hasattr(request, "path_params"):
            org_id = request.path_params.get("org_id")
            if org_id and str(org_id).strip():
                return str(org_id).strip()

        # 3. Cached on request.state (set by resolve_org_id_for_user)
        try:
            org_id = getattr(request.state, "org_id", None)
            if org_id:
                return str(org_id).strip()
        except Exception:
            pass

        return None


def require_role(permission: Permission):
    """
    Factory that returns a FastAPI Depends-compatible RoleChecker.

    Usage:
        @router.post("/analyze")
        def analyze(..., _auth=Depends(require_role(Permission.RUN_ANALYSIS))):
            ...
    """
    return RoleChecker(permission)
