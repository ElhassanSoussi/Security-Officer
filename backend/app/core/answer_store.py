"""
answer_store — persist generated answers and expose summary queries.

Writes to `generated_answers` after each run. Marks answers with
confidence < LOW_CONFIDENCE_THRESHOLD as needing review.
All writes are best-effort and never block the main run response.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("answer_store")

# Answers below this score are flagged for human review.
LOW_CONFIDENCE_THRESHOLD = 0.5


def _parse_confidence(raw: Any) -> float:
    """Coerce confidence to a 0–1 float regardless of source format."""
    if raw is None:
        return 0.0
    if isinstance(raw, float):
        return raw if raw <= 1.0 else raw / 100.0
    if isinstance(raw, int):
        return raw / 100.0 if raw > 1 else float(raw)
    s = str(raw).strip().upper()
    if s == "HIGH":
        return 0.85
    if s == "MEDIUM":
        return 0.60
    if s == "LOW":
        return 0.25
    try:
        v = float(s)
        return v if v <= 1.0 else v / 100.0
    except ValueError:
        return 0.0


def store_generated_answers(
    sb,
    run_id: str,
    org_id: str,
    items: List[Any],
) -> int:
    """
    Persist answer items to `generated_answers`.

    Accepts QuestionItem model instances or plain dicts.
    Returns the number of rows written.
    """
    if not items:
        return 0

    rows: List[Dict[str, Any]] = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for item in items:
        if hasattr(item, "__dict__"):
            d = item.__dict__
        elif hasattr(item, "dict"):
            d = item.dict()
        else:
            d = dict(item)

        confidence = _parse_confidence(
            d.get("confidence_score") or d.get("confidence")
        )

        rows.append({
            "run_id":          run_id,
            "org_id":          org_id,
            "question_text":   (d.get("question") or d.get("question_text") or "")[:2000],
            "answer_text":     (d.get("final_answer") or d.get("answer_text") or d.get("ai_answer") or "")[:8000],
            "confidence":      confidence,
            "source_document": d.get("source_document") or (d.get("sources") or [None])[0],
            "page_number":     d.get("source_page") or d.get("page_number"),
            "source_excerpt":  (d.get("source_excerpt") or "")[:500] or None,
            "needs_review":    confidence < LOW_CONFIDENCE_THRESHOLD,
            "created_at":      now_iso,
        })

    written = 0
    batch_size = 50
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        try:
            sb.table("generated_answers").insert(batch).execute()
            written += len(batch)
        except Exception as exc:
            logger.warning(
                "answer_store: failed to insert batch [%d:%d] for run %s: %s",
                i, i + len(batch), run_id, exc,
            )

    logger.info("answer_store: wrote %d/%d rows for run %s", written, len(rows), run_id)
    return written


def get_run_answers_summary(sb, run_id: str) -> Dict[str, Any]:
    """
    Return aggregate metrics for a run's generated answers.
    Falls back to zero-values if the table is not yet populated.
    """
    try:
        res = sb.table("generated_answers").select("confidence, needs_review").eq("run_id", run_id).execute()
        rows = res.data or []
        if not rows:
            return {"total": 0, "needs_review_count": 0, "avg_confidence": 0.0}

        total = len(rows)
        needs_review = sum(1 for r in rows if r.get("needs_review"))
        avg_conf = round(sum(r.get("confidence", 0.0) for r in rows) / total, 3)
        return {
            "total":               total,
            "needs_review_count":  needs_review,
            "avg_confidence":      avg_conf,
        }
    except Exception as exc:
        logger.warning("answer_store: summary query failed for run %s: %s", run_id, exc)
        return {"total": 0, "needs_review_count": 0, "avg_confidence": 0.0}


def get_run_answers(
    sb,
    run_id: str,
    only_needs_review: bool = False,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    """Return generated answer rows for a run, optionally filtered to review-needed."""
    try:
        q = (
            sb.table("generated_answers")
            .select("*")
            .eq("run_id", run_id)
            .order("created_at")
            .limit(limit)
        )
        if only_needs_review:
            q = q.eq("needs_review", True)
        res = q.execute()
        return res.data or []
    except Exception as exc:
        logger.warning("answer_store: get_run_answers failed for run %s: %s", run_id, exc)
        return []
