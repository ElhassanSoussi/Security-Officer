"""
Account Profile & Appearance API.
Allows authenticated users to manage their own profile and avatar.
"""
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, field_validator

from app.core.auth import get_current_user, require_user_id
from app.core.config import get_settings
from app.core.database import get_supabase_admin

router = APIRouter()
security = HTTPBearer()
settings = get_settings()

ALLOWED_THEMES = {"light", "dark", "system"}
AVATAR_MAX_BYTES = 2 * 1024 * 1024  # 2 MB
AVATAR_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
AVATAR_BUCKET = "avatars"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ProfileResponse(BaseModel):
    user_id: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    public_email: Optional[str] = None
    avatar_url: Optional[str] = None
    theme_preference: str = "system"


class ProfilePatchRequest(BaseModel):
    display_name: Optional[str] = None
    public_email: Optional[str] = None
    theme_preference: Optional[str] = None

    @field_validator("theme_preference")
    @classmethod
    def validate_theme(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ALLOWED_THEMES:
            raise ValueError(f"theme_preference must be one of {sorted(ALLOWED_THEMES)}")
        return v


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_or_create_profile(user_id: str, email: Optional[str] = None) -> dict:
    """Fetch the user_profiles row, creating a default if absent."""
    sb = get_supabase_admin()
    res = sb.table("user_profiles").select("*").eq("user_id", user_id).limit(1).execute()
    if res.data:
        row = res.data[0]
        row.setdefault("email", email)
        return row

    # First access — insert default row
    new_row = {
        "user_id": user_id,
        "display_name": None,
        "avatar_url": None,
        "public_email": None,
        "theme_preference": "system",
    }
    try:
        ins = sb.table("user_profiles").insert(new_row).execute()
        row = ins.data[0] if ins.data else new_row
    except Exception:
        # Race condition: another request inserted first — re-fetch
        res2 = sb.table("user_profiles").select("*").eq("user_id", user_id).limit(1).execute()
        row = res2.data[0] if res2.data else new_row

    row.setdefault("email", email)
    return row


def _ensure_avatar_bucket() -> None:
    """Create the avatars storage bucket if it doesn't exist."""
    sb = get_supabase_admin()
    try:
        sb.storage.get_bucket(AVATAR_BUCKET)
    except Exception:
        try:
            sb.storage.create_bucket(
                AVATAR_BUCKET,
                options={"public": True, "file_size_limit": AVATAR_MAX_BYTES},
            )
        except Exception:
            pass  # bucket may already exist from another concurrent request


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/account/profile", response_model=ProfileResponse)
def get_account_profile(
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """Return the caller's profile and appearance preferences."""
    user_id = require_user_id(user)
    email = user.get("email") if isinstance(user, dict) else None
    row = _get_or_create_profile(user_id, email)
    return ProfileResponse(
        user_id=user_id,
        email=email or row.get("email"),
        display_name=row.get("display_name"),
        public_email=row.get("public_email"),
        avatar_url=row.get("avatar_url"),
        theme_preference=row.get("theme_preference", "system"),
    )


@router.patch("/account/profile", response_model=ProfileResponse)
def patch_account_profile(
    update: ProfilePatchRequest,
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """Update the caller's profile fields (display name, public email, theme)."""
    user_id = require_user_id(user)
    email = user.get("email") if isinstance(user, dict) else None

    # Build update payload — only include non-None fields
    changes: dict = {}
    if update.display_name is not None:
        changes["display_name"] = update.display_name.strip() or None
    if update.public_email is not None:
        changes["public_email"] = update.public_email.strip() or None
    if update.theme_preference is not None:
        changes["theme_preference"] = update.theme_preference

    if not changes:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Ensure row exists
    _get_or_create_profile(user_id, email)

    sb = get_supabase_admin()
    res = sb.table("user_profiles").update(changes).eq("user_id", user_id).execute()
    row = res.data[0] if res.data else _get_or_create_profile(user_id, email)

    return ProfileResponse(
        user_id=user_id,
        email=email or row.get("email"),
        display_name=row.get("display_name"),
        public_email=row.get("public_email"),
        avatar_url=row.get("avatar_url"),
        theme_preference=row.get("theme_preference", "system"),
    )


@router.patch("/account/avatar", response_model=ProfileResponse)
async def patch_account_avatar(
    file: UploadFile = File(...),
    user=Depends(get_current_user),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """Upload or replace the caller's avatar image (max 2 MB, image/* only)."""
    user_id = require_user_id(user)
    email = user.get("email") if isinstance(user, dict) else None

    # Validate content type
    ct = (file.content_type or "").lower()
    if ct not in AVATAR_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type '{ct}'. Allowed: {sorted(AVATAR_CONTENT_TYPES)}",
        )

    # Read and validate size
    data = await file.read()
    if len(data) > AVATAR_MAX_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({len(data)} bytes). Maximum is {AVATAR_MAX_BYTES // (1024*1024)} MB.",
        )

    # Determine file extension
    ext_map = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif"}
    ext = ext_map.get(ct, "png")
    object_path = f"{user_id}/avatar.{ext}"

    _ensure_avatar_bucket()

    sb = get_supabase_admin()
    # Remove old avatar files for this user (any extension)
    try:
        existing = sb.storage.from_(AVATAR_BUCKET).list(user_id)
        if existing:
            paths = [f"{user_id}/{f['name']}" for f in existing if isinstance(f, dict) and f.get("name")]
            if paths:
                sb.storage.from_(AVATAR_BUCKET).remove(paths)
    except Exception:
        pass  # non-fatal — overwrite will handle it

    # Upload new file
    try:
        sb.storage.from_(AVATAR_BUCKET).upload(
            object_path,
            data,
            file_options={"content-type": ct, "upsert": "true"},
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Avatar upload failed: {str(exc)[:200]}") from exc

    # Build public URL
    public_url = f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/object/public/{AVATAR_BUCKET}/{object_path}"

    # Persist in user_profiles
    _get_or_create_profile(user_id, email)
    res = sb.table("user_profiles").update({"avatar_url": public_url}).eq("user_id", user_id).execute()
    row = res.data[0] if res.data else _get_or_create_profile(user_id, email)

    return ProfileResponse(
        user_id=user_id,
        email=email or row.get("email"),
        display_name=row.get("display_name"),
        public_email=row.get("public_email"),
        avatar_url=public_url,
        theme_preference=row.get("theme_preference", "system"),
    )
