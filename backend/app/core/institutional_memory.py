"""
Phase 15: Institutional Answer Memory Engine

Responsibilities:
1. Normalize + hash question text (sha256).
2. Look up canonical answers in institutional_answers table BEFORE generation.
3. On approved review, upsert the Q&A into institutional_answers.
4. Return reuse metadata so the audit record can flag reused_from_memory=True.
"""

import hashlib
import logging
import re
import time
from typing import Optional, Tuple

from app.core.config import get_settings
from app.core.database import get_supabase

settings = get_settings()
logger = logging.getLogger("institutional_memory")


# ─── Normalization ────────────────────────────────────────────────────────────

def normalize_question(text: str) -> str:
    """Lowercase, strip whitespace, remove punctuation for canonical hashing."""
    text = text.strip().lower()
    text = re.sub(r"[^\w\s]", "", text)   # remove punctuation
    text = re.sub(r"\s+", " ", text)      # collapse whitespace
    return text.strip()


def hash_question(text: str) -> str:
    """SHA-256 hex digest of the normalized question text."""
    normalized = normalize_question(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


# ─── Lookup ───────────────────────────────────────────────────────────────────

def lookup_institutional_answer(
    question_text: str,
    org_id: str,
    token: Optional[str] = None,
) -> Optional[dict]:
    """
    Look up a canonical answer by question hash.

    Returns the institutional_answers row if found (with use_count bumped),
    or None if no match exists.

    Response dict keys:
      id, canonical_answer, confidence_level, source_doc_ids,
      canonical_question_text, use_count, last_used_at
    """
    q_hash = hash_question(question_text)

    try:
        sb = get_supabase(token) if token else get_supabase()
        res = (
            sb.table("institutional_answers")
            .select(
                "id, canonical_question_text, canonical_answer, "
                "confidence_level, source_doc_ids, use_count, last_used_at"
            )
            .eq("org_id", org_id)
            .eq("normalized_question_hash", q_hash)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            return None

        row = rows[0]

        # Bump use_count + last_used_at (best-effort, non-blocking)
        try:
            from datetime import datetime, timezone
            sb.table("institutional_answers").update(
                {
                    "use_count": row["use_count"] + 1,
                    "last_used_at": datetime.now(timezone.utc).isoformat(),
                }
            ).eq("id", row["id"]).execute()
        except Exception as bump_err:
            logger.debug("Non-fatal: failed to bump use_count for %s: %s", row["id"], bump_err)

        return row

    except Exception as e:
        logger.warning("Institutional memory lookup failed (non-fatal): %s", e)
        return None


# ─── Store / Upsert ──────────────────────────────────────────────────────────

def store_institutional_answer(
    question_text: str,
    answer_text: str,
    org_id: str,
    confidence_level: str = "MEDIUM",
    source_doc_ids: Optional[list] = None,
    token: Optional[str] = None,
) -> Optional[str]:
    """
    Upsert an approved Q&A pair into the institutional_answers table.

    Uses INSERT … ON CONFLICT DO UPDATE so existing records are refreshed
    rather than duplicated. Returns the row id or None on failure.
    """
    if not question_text or not answer_text:
        return None

    q_hash = hash_question(question_text)
    conf = confidence_level.upper() if confidence_level else "MEDIUM"
    if conf not in ("HIGH", "MEDIUM", "LOW"):
        conf = "MEDIUM"

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    row = {
        "org_id": org_id,
        "normalized_question_hash": q_hash,
        "canonical_question_text": question_text.strip(),
        "canonical_answer": answer_text.strip(),
        "confidence_level": conf,
        "source_doc_ids": source_doc_ids or [],
        "last_used_at": now,
    }

    try:
        sb = get_supabase(token) if token else get_supabase()

        # Try upsert (requires unique index on org_id + hash)
        res = (
            sb.table("institutional_answers")
            .upsert(row, on_conflict="org_id,normalized_question_hash")
            .execute()
        )
        if res.data:
            stored_id = res.data[0].get("id")
            logger.info(
                "Stored institutional answer: id=%s org=%s hash=%s",
                stored_id, org_id, q_hash[:12],
            )
            return stored_id
        return None

    except Exception as e:
        logger.warning("Failed to store institutional answer (non-fatal): %s", e)
        return None


# ─── Confidence Mapping ───────────────────────────────────────────────────────

def confidence_score_to_level(score) -> str:
    """Convert numeric confidence score or string label to HIGH/MEDIUM/LOW."""
    if isinstance(score, str):
        upper = score.strip().upper()
        if upper in ("HIGH", "MEDIUM", "LOW"):
            return upper
        try:
            score = float(score)
        except ValueError:
            return "MEDIUM"
    if isinstance(score, (int, float)):
        if score > 1:
            score = score / 100.0
        if score >= 0.8:
            return "HIGH"
        if score >= 0.5:
            return "MEDIUM"
        return "LOW"
    return "MEDIUM"
