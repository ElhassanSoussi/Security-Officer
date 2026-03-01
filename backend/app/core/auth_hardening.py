"""
Phase 21 Part 5: Password & Auth Hardening.

SOC2-aligned authentication controls:
- Minimum password length enforcement (AUTH_MIN_PASSWORD_LENGTH)
- Email verification requirement (AUTH_REQUIRE_EMAIL_VERIFICATION)
- Inactive user blocking logic

These are declarative checks used by endpoints and middleware.
"""
import logging
from typing import Any, Dict, Optional

from app.core.config import get_settings

logger = logging.getLogger("core.auth_hardening")


def validate_password_strength(password: str) -> Dict[str, Any]:
    """
    Validate password against SOC2-aligned minimum requirements.

    Returns:
        {"valid": bool, "errors": [...], "min_length": int}
    """
    settings = get_settings()
    min_length = settings.AUTH_MIN_PASSWORD_LENGTH
    errors = []

    if not password or len(password) < min_length:
        errors.append(f"Password must be at least {min_length} characters")

    # SOC2 recommends mixed characters
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)

    if not has_upper:
        errors.append("Password must contain at least one uppercase letter")
    if not has_lower:
        errors.append("Password must contain at least one lowercase letter")
    if not has_digit:
        errors.append("Password must contain at least one digit")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "min_length": min_length,
    }


def check_email_verification(user_metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Check whether a user's email is verified.

    Args:
        user_metadata: The user object or metadata dict from Supabase auth.

    Returns:
        {"verified": bool, "enforcement_enabled": bool}
    """
    settings = get_settings()
    enforcement = settings.AUTH_REQUIRE_EMAIL_VERIFICATION

    if not user_metadata:
        return {"verified": False, "enforcement_enabled": enforcement}

    # Supabase stores email_confirmed_at on the user object
    email_confirmed = user_metadata.get("email_confirmed_at")
    is_verified = bool(email_confirmed)

    return {
        "verified": is_verified,
        "enforcement_enabled": enforcement,
    }


def is_user_active(user_metadata: Optional[Dict[str, Any]]) -> bool:
    """
    Check if user account is active (not banned/disabled).

    Supabase uses `banned_until` field; if set and in future, user is inactive.
    """
    if not user_metadata:
        return False

    banned_until = user_metadata.get("banned_until")
    if banned_until:
        from datetime import datetime, timezone
        try:
            ban_dt = datetime.fromisoformat(str(banned_until).replace("Z", "+00:00"))
            if ban_dt > datetime.now(timezone.utc):
                return False
        except (ValueError, TypeError):
            pass

    return True
