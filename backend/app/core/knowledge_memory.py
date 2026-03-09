"""
knowledge_memory — vector-similarity institutional memory service.

Workflow per questionnaire question:
  1. Embed the question text (cached).
  2. Search knowledge_memory via cosine similarity using match_knowledge_memory RPC.
  3. If best match >= MEMORY_SIMILARITY_THRESHOLD (0.85): reuse stored answer.
  4. Record the match in memory_matches (best-effort, non-blocking).
  5. Fallback to evidence-based answer engine when no memory hit.

Saving approved answers:
  - save_to_memory() embeds the question and inserts a new knowledge_memory row.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("knowledge_memory")

MEMORY_SIMILARITY_THRESHOLD = 0.85
MEMORY_SEARCH_LIMIT = 3


def _get_embedding(text: str) -> List[float]:
    from app.core.similarity import get_embedding_cached
    return get_embedding_cached(text)


def search_memory(
    question_text: str,
    organization_id: str,
    sb,
) -> Optional[Dict[str, Any]]:
    """
    Search knowledge_memory for a semantically similar question.

    Returns the highest-similarity row dict (keys: id, question_text,
    answer_text, confidence, source_run_id, approved_by, similarity,
    created_at) when similarity >= MEMORY_SIMILARITY_THRESHOLD, else None.
    Non-fatal: returns None on any error.
    """
    try:
        embedding = _get_embedding(question_text)
        result = sb.rpc(
            "match_knowledge_memory",
            {
                "query_embedding": embedding,
                "match_threshold": MEMORY_SIMILARITY_THRESHOLD,
                "match_count": MEMORY_SEARCH_LIMIT,
                "filter_org_id": organization_id,
            },
        ).execute()
        rows = result.data or []
        if not rows:
            return None
        return rows[0]
    except Exception as exc:
        logger.warning("knowledge_memory search failed (non-fatal): %s", exc)
        return None


def record_memory_match(
    question_text: str,
    matched_memory_id: str,
    similarity_score: float,
    run_id: Optional[str],
    sb,
) -> None:
    """Best-effort: insert a row into memory_matches to track reuse."""
    try:
        sb.table("memory_matches").insert({
            "question_text": question_text[:2000],
            "matched_memory_id": matched_memory_id,
            "similarity_score": round(similarity_score, 4),
            "used_in_run": run_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception as exc:
        logger.debug("memory_matches insert failed (non-fatal): %s", exc)


def save_to_memory(
    organization_id: str,
    question_text: str,
    answer_text: str,
    confidence: float,
    source_run_id: Optional[str],
    approved_by: str,
    sb,
) -> Optional[str]:
    """
    Embed question_text and insert a new row into knowledge_memory.
    Returns the new row UUID on success, None on failure.
    """
    if not question_text or not answer_text:
        return None
    try:
        embedding = _get_embedding(question_text)
        now = datetime.now(timezone.utc).isoformat()
        row: Dict[str, Any] = {
            "organization_id": organization_id,
            "question_text": question_text.strip()[:4000],
            "answer_text": answer_text.strip()[:8000],
            "embedding": embedding,
            "confidence": round(float(confidence), 4),
            "source_run_id": source_run_id,
            "approved_by": approved_by,
            "created_at": now,
            "updated_at": now,
        }
        res = sb.table("knowledge_memory").insert(row).execute()
        if res.data:
            new_id = res.data[0].get("id")
            logger.info(
                "knowledge_memory: saved entry %s for org %s (confidence=%.3f)",
                new_id, organization_id, confidence,
            )
            return new_id
        return None
    except Exception as exc:
        logger.warning("knowledge_memory save failed (non-fatal): %s", exc)
        return None
