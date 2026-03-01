from supabase import create_client, Client
from app.core.config import get_settings
import os
import base64
from typing import Optional, Any

try:
    import jwt  # PyJWT
except Exception:  # pragma: no cover
    jwt = None  # type: ignore

settings = get_settings()

def get_supabase(token: str = None) -> Client:
    """
    Create a Supabase client that respects Row Level Security (RLS).

    When a user JWT is provided, we forward it as the Authorization bearer
    while still sending the project's anon/service key as the `apikey` header.
    This ensures PostgREST evaluates policies with the caller's identity.
    """

    url = settings.SUPABASE_URL
    key = settings.SUPABASE_KEY

    client = create_client(url, key)

    # Important: keep Supabase anon/service key as `apikey`, and only override
    # the PostgREST auth bearer token for RLS evaluation.
    if token:
        client.postgrest.auth(token.strip())

    return client


def _iter_jwt_secrets(raw_secret: str):
    """Yield candidate secrets for HS256 verification/signing.

    Supabase "JWT Secret" is sometimes stored as a base64-encoded string.
    """
    secret = (raw_secret or "").strip()
    if not secret:
        return
    yield secret
    try:
        decoded = base64.b64decode(secret)
        if decoded:
            yield decoded
    except Exception:
        return


def _can_verify_jwt(token: str, secret: Any) -> bool:
    if not jwt:
        return False
    try:
        jwt.decode(token, secret, algorithms=["HS256"], options={"verify_aud": False})
        return True
    except Exception:
        return False


def _generate_service_role_key(url: str, anon_key: str, jwt_secret: str) -> Optional[str]:
    """Re-sign a stable 'service_role' API key using the project's JWT secret.

    Why: Some setups end up with a corrupted/invalid service_role key in env.
    We can deterministically regenerate a valid one by:
      - decoding the *anon* key (which is a HS256 JWT API key)
      - copying its payload (iss/ref/iat/exp) and setting role=service_role
      - signing with SUPABASE_JWT_SECRET

    This does NOT print or persist secrets; it only returns the token string.
    """
    if not jwt:
        return None
    anon_key = (anon_key or "").strip()
    jwt_secret = (jwt_secret or "").strip()
    if not anon_key or not jwt_secret or not anon_key.startswith("eyJ"):
        return None

    # Decode the anon payload WITHOUT trusting it blindly: verify with secret first.
    payload = None
    for s in _iter_jwt_secrets(jwt_secret):
        try:
            payload = jwt.decode(anon_key, s, algorithms=["HS256"], options={"verify_aud": False})
            signing_secret = s
            break
        except Exception:
            payload = None
            signing_secret = None  # type: ignore
    if not payload:
        return None

    svc_payload = dict(payload)
    svc_payload["role"] = "service_role"

    try:
        token = jwt.encode(svc_payload, signing_secret, algorithm="HS256")
        # PyJWT may return bytes in older versions
        if isinstance(token, bytes):
            token = token.decode("utf-8")
        return token
    except Exception:
        return None


def get_supabase_admin() -> Client:
    """
    Create a Supabase client using the service_role key (bypasses RLS).
    Use ONLY for privileged backend operations like org/membership creation.
    Falls back to normal anon key if service_role key is not available.
    """
    url = (settings.SUPABASE_URL or "").strip()
    anon_key = (settings.SUPABASE_KEY or "").strip()

    # Prefer explicit server-side keys, but tolerate partially-configured envs.
    # Some local setups may contain an invalid/truncated `SUPABASE_SECRET_KEY`;
    # in that case we gracefully fall back to service-role JWT generation.
    raw_secret_key = (
        getattr(settings, "SUPABASE_SECRET_KEY", "")
        or os.getenv("SUPABASE_SECRET_KEY", "")
    ).strip()
    raw_service_role_key = (
        getattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    ).strip()
    jwt_secret = (getattr(settings, "SUPABASE_JWT_SECRET", "") or os.getenv("SUPABASE_JWT_SECRET", "")).strip()

    candidate_keys: list[str] = []
    if raw_secret_key:
        candidate_keys.append(raw_secret_key)

    service_key = raw_service_role_key
    if service_key and service_key.startswith("eyJ") and jwt_secret:
        valid = any(_can_verify_jwt(service_key, s) for s in _iter_jwt_secrets(jwt_secret))
        if not valid:
            regenerated = _generate_service_role_key(url, anon_key, jwt_secret)
            if regenerated:
                service_key = regenerated
    if service_key:
        candidate_keys.append(service_key)

    # Try each privileged candidate key; if one is invalid for this project,
    # continue to the next before falling back to anon.
    for key in candidate_keys:
        try:
            return create_client(url, key)
        except Exception:
            continue

    # Fallback: use anon key (will be subject to RLS)
    return create_client(url, anon_key)
