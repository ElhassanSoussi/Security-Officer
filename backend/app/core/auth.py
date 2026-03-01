import os
import base64
import binascii
import jwt
import httpx
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from app.core.config import get_settings

# Supabase JWT Secret (Ensure this is in .env)
settings = get_settings()
# Prefer configured settings (.env via pydantic settings), fallback to process env.
JWT_SECRET = (settings.SUPABASE_JWT_SECRET or os.getenv("SUPABASE_JWT_SECRET", "")).strip()
SUPABASE_URL = (settings.SUPABASE_URL or os.getenv("SUPABASE_URL", "")).strip()
SUPABASE_KEY = (settings.SUPABASE_KEY or os.getenv("SUPABASE_KEY", "")).strip()
# If using Supabase, the JWT secret is usually the same as the "Anon" key for signing,
# but for verification of access tokens, we need the PROJECT JWT SECRET.

security = HTTPBearer()


def extract_user_id(payload: dict) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    for key in ("sub", "id", "user_id"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def require_user_id(payload: dict) -> str:
    user_id = extract_user_id(payload)
    if user_id:
        return user_id
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token payload",
        headers={"WWW-Authenticate": "Bearer"},
    )

def _enforce_authenticated_audience(payload: dict) -> dict:
    """
    Supabase access tokens should target the authenticated audience.
    Accept both str and list forms for compatibility.
    """
    aud = payload.get("aud")
    if aud is None:
        return payload
    if isinstance(aud, str) and aud == "authenticated":
        return payload
    if isinstance(aud, list) and "authenticated" in aud:
        return payload
    raise jwt.InvalidTokenError("Invalid audience")

def _decode_hs256(token: str, secret: str) -> dict:
    payload = jwt.decode(
        token,
        secret,
        algorithms=["HS256"],
        options={"verify_aud": False},
    )
    return _enforce_authenticated_audience(payload)

def _decode_with_local_secrets(token: str) -> Optional[dict]:
    """
    Try local signature verification with:
    1) raw secret string
    2) base64-decoded secret (some envs store it encoded)
    """
    if not JWT_SECRET:
        return None

    # 1) Raw secret
    try:
        return _decode_hs256(token, JWT_SECRET)
    except Exception:
        pass

    # 2) Base64 decoded secret
    try:
        decoded = base64.b64decode(JWT_SECRET)
        if decoded:
            return _decode_hs256(token, decoded)
    except (binascii.Error, ValueError, TypeError):
        pass
    except Exception:
        pass

    return None

def _validate_with_supabase_auth(token: str) -> Optional[dict]:
    """
    Fallback to Supabase Auth validation for projects using non-HS256 signing
    modes (or when local secret differs).
    """
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            # Direct HTTP fallback is the most robust path across supabase-py versions.
            resp = httpx.get(
                f"{SUPABASE_URL.rstrip('/')}/auth/v1/user",
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {token}",
                },
                timeout=8.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                user_id = extract_user_id(data)
                if user_id:
                    return {"sub": user_id, "email": data.get("email")}
        except Exception:
            pass

    # Keep sdk-based fallback for compatibility with existing environments.
    try:
        from app.core.database import get_supabase
        sb = get_supabase()
        user_resp = sb.auth.get_user(token)

        user_obj = getattr(user_resp, "user", None)
        if user_obj is None and isinstance(user_resp, dict):
            user_obj = user_resp.get("user")
        if user_obj is None:
            return None

        user_id = getattr(user_obj, "id", None)
        user_email = getattr(user_obj, "email", None)
        if isinstance(user_obj, dict):
            user_id = user_id or extract_user_id(user_obj)
            user_email = user_email or user_obj.get("email")

        if not user_id:
            return None

        return {"sub": user_id, "email": user_email}
    except Exception:
        return None

def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Validates Supabase JWT and returns user payload (sub/uid).
    """
    token = credentials.credentials
    payload = _decode_with_local_secrets(token)
    if payload:
        user_id = extract_user_id(payload)
        if user_id:
            try:
                request.state.user_id = user_id
            except Exception:
                pass
        return payload

    payload = _validate_with_supabase_auth(token)
    if payload:
        user_id = extract_user_id(payload)
        if user_id:
            try:
                request.state.user_id = user_id
            except Exception:
                pass
        return payload

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token",
        headers={"WWW-Authenticate": "Bearer"},
    )

def get_current_org(org_id: str, user=Depends(get_current_user)):
    """
    Dependency to verify user access to the requested Organization.
    (Requires lookup in subscriptions/memberships table - simplified here for MVP logic)
    """
    # In a real impl, we query the DB to check if user.sub is in memberships for org_id
    # For MVP, we pass the user payload through and let the endpoint/RLS handle the specific check,
    # or we implement the DB check here.
    return org_id
