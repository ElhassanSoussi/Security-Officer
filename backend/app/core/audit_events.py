import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("audit.events")
_missing_table_warned = False
_missing_activity_table_warned = False

# Phase 12 Part 5: Audit entries are append-only / immutable.
# The audit_events table should have no UPDATE or DELETE policies.
AUDIT_IMMUTABLE = True

# Keys containing these substrings are stripped from metadata before storage/return.
_SENSITIVE_KEY_FRAGMENTS = (
    "password", "token", "secret", "api_key", "apikey",
    "credential", "private_key", "privatekey", "access_key",
    "auth", "bearer", "jwt",
)


def sanitize_metadata(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Strip any metadata keys that look like secrets.
    Safe to call on None (returns {}).
    """
    if not metadata:
        return {}
    cleaned: Dict[str, Any] = {}
    for k, v in metadata.items():
        lower_k = str(k).lower()
        if any(frag in lower_k for frag in _SENSITIVE_KEY_FRAGMENTS):
            continue
        cleaned[k] = v
    return cleaned


def log_audit_event(
    supabase,
    *,
    org_id: str,
    user_id: str,
    event_type: str,
    metadata: Optional[Dict[str, Any]] = None,
    immutable: bool = True,
) -> None:
    """
    Best-effort audit event logger.

    Uses the caller's Supabase client (RLS-scoped). If the table/policies are not
    deployed yet, this should never break core flows.

    Phase 12: entries are marked immutable — no update/delete permitted.
    """
    if not supabase or not org_id or not user_id or not event_type:
        return

    payload: Dict[str, Any] = {
        "org_id": org_id,
        "user_id": user_id,
        "event_type": event_type,
        "metadata": sanitize_metadata(metadata) or {},
    }

    try:
        supabase.table("audit_events").insert(payload).execute()
    except Exception as e:
        global _missing_table_warned
        err = str(e)
        if "Could not find the table 'public.audit_events'" in err:
            if not _missing_table_warned:
                _missing_table_warned = True
                logger.warning("audit_events table missing; audit event writes are skipped until migration is applied")
            return
        # Do not leak metadata; keep logs terse.
        logger.warning("audit_event_failed event_type=%s error=%s", event_type, err[:200])


def log_activity_event(
    supabase,
    *,
    org_id: str,
    user_id: Optional[str],
    action_type: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Phase 16: Best-effort compliance activity timeline logger.

    Writes to the `activity_log` table which backs the /app/activity UI.
    Schema: id, org_id, user_id, action_type, entity_type, entity_id, metadata, created_at.

    This is intentionally non-blocking — never raises.
    """
    if not supabase or not org_id or not action_type:
        return

    payload: Dict[str, Any] = {
        "org_id": org_id,
        "user_id": user_id or "",
        "action_type": action_type,
        "entity_type": entity_type or "",
        "entity_id": entity_id or "",
        "metadata": sanitize_metadata(metadata) or {},
    }

    try:
        supabase.table("activity_log").insert(payload).execute()
    except Exception as e:
        global _missing_activity_table_warned
        err = str(e)
        if "Could not find the table 'public.activity_log'" in err:
            if not _missing_activity_table_warned:
                _missing_activity_table_warned = True
                logger.warning(
                    "activity_log table missing; apply 010_institutional_memory_governance.sql"
                )
            return
        logger.warning("activity_log_failed action_type=%s error=%s", action_type, err[:200])
