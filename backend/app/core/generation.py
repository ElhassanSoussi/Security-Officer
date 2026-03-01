"""
Phase 3: Deterministic Answer Generation Engine

Key guarantees:
1. Threshold-enforced retrieval — no generation without sufficient context.
2. Strict mode — model MUST quote from source, no synthesis allowed.
3. Structured confidence scoring (0-1) with confidence_reason.
4. Full retrieval metadata captured per answer (timing, model, tokens, scores).
5. Timeout protection on LLM calls.
"""
import time
import logging
from typing import Dict, Any, Optional

try:
    from openai import OpenAI, APIConnectionError, RateLimitError, APITimeoutError
except ImportError:
    class OpenAI:
        def __init__(self, api_key=None):
            pass
        chat = type("obj", (), {
            "completions": type("obj", (), {
                "create": lambda **k: type("obj", (), {
                    "choices": [type("obj", (), {
                        "message": type("obj", (), {"content": "Mock response"})
                    })],
                    "usage": type("obj", (), {"total_tokens": 0})
                })
            })
        })
    class APIConnectionError(Exception):
        pass
    class RateLimitError(Exception):
        pass
    class APITimeoutError(Exception):
        pass

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger("generation")

# ─── Confidence Scoring ─────────────────────────────────────────────────────

def compute_confidence(
    best_similarity: float,
    num_supporting_chunks: int,
    excerpt_length: int,
    is_direct_quote: bool,
    answer_text: str,
) -> tuple:
    """
    Compute a normalized 0-1 confidence score with a human-readable reason.

    Factors:
    - similarity score (40% weight)
    - number of supporting chunks (20% weight)
    - length of source excerpt (15% weight)
    - direct quote vs inference (25% weight)
    """
    # Factor 1: Similarity (0-1, already normalized)
    sim_score = min(max(best_similarity, 0.0), 1.0)

    # Factor 2: Supporting chunks (more = better, cap at 5)
    chunk_score = min(num_supporting_chunks / 5.0, 1.0)

    # Factor 3: Excerpt length (longer context = more reliable, cap at 500 chars)
    excerpt_score = min(excerpt_length / 500.0, 1.0)

    # Factor 4: Direct quote vs inference
    quote_score = 1.0 if is_direct_quote else 0.4

    # Weighted combination
    raw = (
        0.40 * sim_score
        + 0.20 * chunk_score
        + 0.15 * excerpt_score
        + 0.25 * quote_score
    )
    confidence_score = round(min(max(raw, 0.0), 1.0), 3)

    # Build reason
    reasons = []
    if sim_score >= 0.8:
        reasons.append("high similarity match")
    elif sim_score >= 0.6:
        reasons.append("moderate similarity match")
    else:
        reasons.append("low similarity match")

    if num_supporting_chunks >= 3:
        reasons.append(f"{num_supporting_chunks} supporting chunks")
    elif num_supporting_chunks == 1:
        reasons.append("single source chunk")

    if is_direct_quote:
        reasons.append("direct quote from source")
    else:
        reasons.append("inferred from context")

    confidence_reason = "; ".join(reasons)

    return confidence_score, confidence_reason


def _classify_confidence_label(score: float) -> str:
    """Map numeric confidence to categorical label for backward compatibility."""
    if score >= 0.7:
        return "HIGH"
    elif score >= 0.4:
        return "MEDIUM"
    return "LOW"


def _detect_direct_quote(answer: str, context: str) -> bool:
    """Check if the answer appears to be a direct quote from the context."""
    if not answer or not context:
        return False
    # Check if a significant substring of the answer appears verbatim in context
    # Use sliding window of 40+ chars
    answer_clean = answer.strip().lower()
    context_clean = context.lower()
    window = 40
    if len(answer_clean) < window:
        return answer_clean in context_clean
    for i in range(0, len(answer_clean) - window + 1, 10):
        fragment = answer_clean[i:i + window]
        if fragment in context_clean:
            return True
    return False


# ─── System Prompts ──────────────────────────────────────────────────────────

STANDARD_SYSTEM_PROMPT = (
    "You are an expert NYC Compliance Officer. "
    "Answer the question strictly based on the provided context. "
    "If the answer is not in the context, say 'NOT FOUND IN LOCKER'. "
    "Do not hallucinate. "
    "Cite your sources in the format: [Filename, pg. X]."
)

STRICT_MODE_SYSTEM_PROMPT = (
    "You are an expert NYC Compliance Officer operating in STRICT MODE. "
    "You MUST answer by directly quoting from the provided context. "
    "Do NOT paraphrase, synthesize, or infer beyond what is explicitly stated. "
    "Every claim must include a verbatim excerpt from the source. "
    "If the answer is not clearly and explicitly stated in the context, "
    "respond with exactly: 'NOT FOUND IN LOCKER'. "
    "Cite your sources in the format: [Filename, pg. X]."
)


# ─── Answer Engine ───────────────────────────────────────────────────────────

class AnswerEngine:
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        if not self.api_key:
            logger.warning("OPENAI_API_KEY is missing. Answer generation will fail.")
            self.client = None
        else:
            self.client = OpenAI(api_key=self.api_key)

    def generate_answer(
        self,
        query: str,
        org_id: str,
        project_id: str = None,
        token: Optional[str] = None,
        strict_mode: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Generate a grounded answer using deterministic retrieval.

        Phase 4: Before retrieval, check institutional memory for similar
        previously-approved answers. If similarity ≥ 0.90, reuse directly.

        Returns a structured dict with answer, metadata, confidence, and retrieval debug info.
        """
        if not self.client:
            return self._error_response("ai_unavailable", "AI is unavailable (missing API key).")

        is_strict = strict_mode if strict_mode is not None else settings.STRICT_MODE
        model = settings.LLM_MODEL

        try:
            # ── Phase 4: Similarity Search (before retrieval) ─────────────
            similarity_result = None
            try:
                from app.core.similarity import similarity_engine
                similarity_result = similarity_engine.search_similar(
                    question=query,
                    org_id=org_id,
                    project_id=project_id,
                    token=token,
                )

                if similarity_result.has_reusable:
                    # Direct reuse — skip retrieval + LLM entirely
                    match = similarity_result.best_match
                    logger.info(
                        f"Phase 4 REUSE: similarity={match.similarity:.3f} "
                        f"from question_embedding={match.question_embedding_id}"
                    )
                    return {
                        "status": "ok",
                        "answer": match.answer_text,
                        "sources": [match.source_document] if match.source_document else [],
                        "source_id": None,
                        "source_page": None,
                        "source_excerpt": match.source_excerpt,
                        "confidence": "HIGH",
                        "confidence_score": match.confidence_score or 0.9,
                        "confidence_reason": f"reused from approved answer (similarity {match.similarity:.3f})",
                        "embedding_similarity_score": round(match.similarity, 4),
                        "chunk_id": None,
                        "token_count_used": 0,
                        "model_used": "reused",
                        "generation_time_ms": similarity_result.search_time_ms,
                        "retrieval_mode": "strict" if is_strict else "standard",
                        "retrieval_debug": None,
                        # Phase 4 fields
                        "answer_origin": "reused",
                        "reused_from_question_id": match.question_embedding_id,
                        "reuse_similarity_score": round(match.similarity, 4),
                    }
            except Exception as sim_err:
                logger.warning(f"Phase 4 similarity search failed (non-fatal): {sim_err}")

            # ── 1. Retrieval ──────────────────────────────────────────────
            from app.core.retrieval import retrieval_engine

            retrieval_start = time.monotonic()
            retrieval_result = retrieval_engine.retrieve(
                query=query,
                org_id=org_id,
                project_id=project_id,
                token=token,
            )
            retrieval_ms = int((time.monotonic() - retrieval_start) * 1000)

            logger.info(
                f"Retrieval: {retrieval_result.above_threshold}/{retrieval_result.total_candidates} "
                f"chunks above threshold {retrieval_result.threshold_used} in {retrieval_ms}ms"
            )

            # ── 2. Threshold Gate ─────────────────────────────────────────
            if not retrieval_result.has_results:
                return self._not_found_response(
                    retrieval_result=retrieval_result,
                    model=model,
                    is_strict=is_strict,
                )

            context_text = retrieval_result.context_text
            sources = retrieval_result.source_filenames
            top_chunk = retrieval_result.chunks[0]

            # ── 3. LLM Generation ────────────────────────────────────────
            system_prompt = STRICT_MODE_SYSTEM_PROMPT if is_strict else STANDARD_SYSTEM_PROMPT
            user_prompt = f"Context:\n{context_text}\n\nQuestion: {query}"

            gen_start = time.monotonic()
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0,
                timeout=settings.LLM_TIMEOUT_SECONDS,
            )
            gen_ms = int((time.monotonic() - gen_start) * 1000)

            answer = response.choices[0].message.content.strip()
            token_count = getattr(response.usage, "total_tokens", 0) if response.usage else 0

            # ── 4. NOT FOUND gate ────────────────────────────────────────
            if "NOT FOUND" in answer.upper():
                return self._not_found_response(
                    retrieval_result=retrieval_result,
                    model=model,
                    is_strict=is_strict,
                    generation_time_ms=gen_ms,
                    token_count=token_count,
                )

            # ── 5. Confidence Scoring ────────────────────────────────────
            source_excerpt = top_chunk.content[:500].strip() if top_chunk.content else ""
            is_direct_quote = _detect_direct_quote(answer, context_text)

            confidence_score, confidence_reason = compute_confidence(
                best_similarity=top_chunk.similarity,
                num_supporting_chunks=len(retrieval_result.chunks),
                excerpt_length=len(source_excerpt),
                is_direct_quote=is_direct_quote,
                answer_text=answer,
            )
            confidence_label = _classify_confidence_label(confidence_score)

            total_time_ms = retrieval_ms + gen_ms

            # Phase 4: Determine answer_origin based on similarity search
            answer_origin = "generated"
            reused_from_question_id = None
            reuse_similarity_score = None
            if similarity_result and similarity_result.has_suggestion:
                answer_origin = "suggested"
                reused_from_question_id = similarity_result.best_match.question_embedding_id
                reuse_similarity_score = round(similarity_result.best_match.similarity, 4)

            result = {
                "status": "ok",
                "answer": answer,
                "sources": sources,
                "source_id": top_chunk.document_id,
                "source_page": top_chunk.page_number,
                "source_excerpt": source_excerpt,
                "confidence": confidence_label,
                # Phase 3: Structured confidence
                "confidence_score": confidence_score,
                "confidence_reason": confidence_reason,
                # Phase 3: Retrieval metadata
                "embedding_similarity_score": round(top_chunk.similarity, 4),
                "chunk_id": top_chunk.chunk_id,
                "token_count_used": token_count,
                "model_used": model,
                "generation_time_ms": total_time_ms,
                "retrieval_mode": "strict" if is_strict else "standard",
                # Phase 3: Retrieval debug (only when enabled)
                "retrieval_debug": retrieval_result.to_dict() if settings.RETRIEVAL_DEBUG else None,
                # Phase 4: Answer reuse metadata
                "answer_origin": answer_origin,
                "reused_from_question_id": reused_from_question_id,
                "reuse_similarity_score": reuse_similarity_score,
            }

            return result

        except (APIConnectionError, RateLimitError) as e:
            logger.error(f"OpenAI API error: {e}")
            return self._error_response("ai_unavailable", "AI is unavailable (network/API error).")
        except APITimeoutError:
            logger.error(f"OpenAI API timeout after {settings.LLM_TIMEOUT_SECONDS}s")
            return self._error_response("ai_timeout", f"AI timed out after {settings.LLM_TIMEOUT_SECONDS}s. Try again.")
        except Exception as e:
            logger.error(f"Unexpected generation error: {e}", exc_info=True)
            return self._error_response("ai_unavailable", f"AI is unavailable (system error).")

    def _not_found_response(
        self,
        retrieval_result=None,
        model: str = "",
        is_strict: bool = False,
        generation_time_ms: int = 0,
        token_count: int = 0,
    ) -> Dict[str, Any]:
        """Deterministic fallback when context is insufficient."""
        top_score = retrieval_result.best_score if retrieval_result else 0.0
        return {
            "status": "needs_info",
            "reason": "NOT FOUND IN LOCKER — no supporting context above confidence threshold.",
            "answer": "",
            "sources": [],
            "source_id": None,
            "source_page": None,
            "source_excerpt": None,
            "confidence": "LOW",
            "confidence_score": 0.0,
            "confidence_reason": f"no chunks above threshold ({retrieval_result.threshold_used if retrieval_result else 'N/A'}); best score {round(top_score, 3)}",
            "embedding_similarity_score": round(top_score, 4) if top_score else None,
            "chunk_id": None,
            "token_count_used": token_count,
            "model_used": model,
            "generation_time_ms": generation_time_ms,
            "retrieval_mode": "strict" if is_strict else "standard",
            "retrieval_debug": retrieval_result.to_dict() if retrieval_result and settings.RETRIEVAL_DEBUG else None,
            # Phase 4
            "answer_origin": "generated",
            "reused_from_question_id": None,
            "reuse_similarity_score": None,
        }

    @staticmethod
    def _error_response(status: str, reason: str) -> Dict[str, Any]:
        return {
            "status": status,
            "reason": reason,
            "answer": "",
            "sources": [],
            "source_id": None,
            "source_page": None,
            "source_excerpt": None,
            "confidence": "LOW",
            "confidence_score": 0.0,
            "confidence_reason": reason,
            "embedding_similarity_score": None,
            "chunk_id": None,
            "token_count_used": 0,
            "model_used": "",
            "generation_time_ms": 0,
            "retrieval_mode": "standard",
            "retrieval_debug": None,
            # Phase 4
            "answer_origin": "generated",
            "reused_from_question_id": None,
            "reuse_similarity_score": None,
        }


answer_engine = AnswerEngine()
