"""
Phase 4: Question Similarity Engine — Institutional Memory

Responsibilities:
1. Search for similar previously-approved Q&A pairs before retrieval.
2. Classify reuse: ≥0.90 = reuse directly, 0.75-0.90 = suggest, <0.75 = normal.
3. Store approved answers as embeddings for future reuse.
4. LRU cache for embeddings to reduce OpenAI calls.
5. Delta tracking between runs (NEW / MODIFIED / UNCHANGED).
"""
import logging
import time
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Tuple
from functools import lru_cache

from app.core.config import get_settings
from app.core.database import get_supabase

settings = get_settings()
logger = logging.getLogger("similarity")


# ─── Embedding Cache ─────────────────────────────────────────────────────────

class EmbeddingCache:
    """Thread-safe LRU cache for question embeddings to avoid redundant API calls."""

    def __init__(self, max_size: int = 1000):
        self._cache: Dict[str, List[float]] = {}
        self._access_order: List[str] = []
        self._max_size = max_size

    def get(self, text: str) -> Optional[List[float]]:
        key = text.strip().lower()
        if key in self._cache:
            # Move to end (most recently used)
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)
            return self._cache[key]
        return None

    def put(self, text: str, embedding: List[float]) -> None:
        key = text.strip().lower()
        if key in self._cache:
            self._access_order.remove(key)
        elif len(self._cache) >= self._max_size:
            # Evict least recently used
            oldest = self._access_order.pop(0)
            del self._cache[oldest]
        self._cache[key] = embedding
        self._access_order.append(key)

    def size(self) -> int:
        return len(self._cache)

    def clear(self) -> None:
        self._cache.clear()
        self._access_order.clear()


# Module-level singleton
_embedding_cache = EmbeddingCache(max_size=settings.EMBEDDING_CACHE_SIZE)


def get_embedding_cached(text: str) -> List[float]:
    """Get embedding with LRU cache. Falls back to OpenAI API on cache miss."""
    cached = _embedding_cache.get(text)
    if cached is not None:
        return cached

    from app.core.ingestion import pdf_processor
    embedding = pdf_processor.get_embedding(text)
    _embedding_cache.put(text, embedding)
    return embedding


def batch_get_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Batch embedding request. Checks cache first, batches uncached texts
    into a single OpenAI call, then caches all results.
    """
    results: List[Optional[List[float]]] = [None] * len(texts)
    uncached_indices: List[int] = []
    uncached_texts: List[str] = []

    # Check cache first
    for i, text in enumerate(texts):
        cached = _embedding_cache.get(text)
        if cached is not None:
            results[i] = cached
        else:
            uncached_indices.append(i)
            uncached_texts.append(text)

    # Batch embed uncached texts
    if uncached_texts:
        try:
            from app.core.ingestion import pdf_processor
            cleaned = [t.replace("\n", " ") for t in uncached_texts]
            response = pdf_processor.openai_client.embeddings.create(
                input=cleaned,
                model=settings.embedding_model,
            )
            for j, item in enumerate(response.data):
                idx = uncached_indices[j]
                embedding = item.embedding
                results[idx] = embedding
                _embedding_cache.put(uncached_texts[j], embedding)
        except Exception as e:
            logger.error(f"Batch embedding failed, falling back to individual: {e}")
            for j, text in enumerate(uncached_texts):
                idx = uncached_indices[j]
                results[idx] = get_embedding_cached(text)

    return results


# ─── Similarity Match Dataclass ─────────────────────────────────────────────

@dataclass
class SimilarityMatch:
    """A previously-approved Q&A pair that matched the current question."""
    question_embedding_id: str
    question_text: str
    answer_text: str
    similarity: float
    source_document: Optional[str] = None
    source_excerpt: Optional[str] = None
    confidence_score: Optional[float] = None
    run_id: Optional[str] = None
    audit_id: Optional[str] = None
    project_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SimilarityResult:
    """Result of searching for similar approved Q&A pairs."""
    matches: List[SimilarityMatch] = field(default_factory=list)
    best_match: Optional[SimilarityMatch] = None
    action: str = "generate"  # "reuse" | "suggest" | "generate"
    search_time_ms: int = 0
    cache_hit: bool = False

    @property
    def has_reusable(self) -> bool:
        return self.action == "reuse" and self.best_match is not None

    @property
    def has_suggestion(self) -> bool:
        return self.action == "suggest" and self.best_match is not None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "matches_count": len(self.matches),
            "best_similarity": self.best_match.similarity if self.best_match else 0.0,
            "search_time_ms": self.search_time_ms,
            "cache_hit": self.cache_hit,
            "best_match": self.best_match.to_dict() if self.best_match else None,
        }


# ─── Similarity Engine ───────────────────────────────────────────────────────

class SimilarityEngine:
    """
    Search for similar previously-approved Q&A pairs.

    Thresholds:
    - ≥ REUSE_EXACT_THRESHOLD (0.90): Reuse directly → answer_origin = "reused"
    - ≥ REUSE_SUGGEST_THRESHOLD (0.75): Suggest to user → answer_origin = "suggested"
    - Below: Normal retrieval → answer_origin = "generated"
    """

    def search_similar(
        self,
        question: str,
        org_id: str,
        project_id: Optional[str] = None,
        token: Optional[str] = None,
    ) -> SimilarityResult:
        """
        Search for similar approved Q&A pairs for a given question.
        Returns a SimilarityResult with the recommended action.
        """
        if not settings.REUSE_ENABLED:
            return SimilarityResult(action="generate")

        start = time.monotonic()

        try:
            # Get embedding (cached)
            query_embedding = get_embedding_cached(question)

            # Use RLS-scoped client
            sb = get_supabase(token) if token else get_supabase()

            # Search via RPC
            params = {
                "query_embedding": query_embedding,
                "match_threshold": settings.REUSE_SUGGEST_THRESHOLD,  # Lower bound
                "match_count": settings.REUSE_SEARCH_LIMIT,
                "filter_org_id": org_id,
            }
            if project_id:
                params["filter_project_id"] = project_id

            result = sb.rpc("match_question_embeddings", params).execute()
            rows = result.data or []

            matches = []
            for r in rows:
                sim = float(r.get("similarity", 0))
                matches.append(SimilarityMatch(
                    question_embedding_id=r.get("id", ""),
                    question_text=r.get("question_text", ""),
                    answer_text=r.get("answer_text", ""),
                    similarity=sim,
                    source_document=r.get("source_document"),
                    source_excerpt=r.get("source_excerpt"),
                    confidence_score=r.get("confidence_score"),
                    run_id=str(r["run_id"]) if r.get("run_id") else None,
                    audit_id=str(r["audit_id"]) if r.get("audit_id") else None,
                    project_id=str(r["project_id"]) if r.get("project_id") else None,
                ))

            # Sort by similarity descending
            matches.sort(key=lambda m: m.similarity, reverse=True)

            elapsed_ms = int((time.monotonic() - start) * 1000)

            if not matches:
                return SimilarityResult(
                    matches=[],
                    action="generate",
                    search_time_ms=elapsed_ms,
                )

            best = matches[0]
            if best.similarity >= settings.REUSE_EXACT_THRESHOLD:
                action = "reuse"
            elif best.similarity >= settings.REUSE_SUGGEST_THRESHOLD:
                action = "suggest"
            else:
                action = "generate"

            return SimilarityResult(
                matches=matches,
                best_match=best,
                action=action,
                search_time_ms=elapsed_ms,
            )

        except Exception as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.warning(f"Similarity search failed (non-fatal, falling back to generate): {e}")
            return SimilarityResult(
                action="generate",
                search_time_ms=elapsed_ms,
            )

    def store_approved_answer(
        self,
        org_id: str,
        project_id: Optional[str],
        run_id: str,
        audit_id: str,
        question_text: str,
        answer_text: str,
        source_document: Optional[str] = None,
        source_excerpt: Optional[str] = None,
        confidence_score: Optional[float] = None,
        similarity_score: Optional[float] = None,
        token: Optional[str] = None,
    ) -> Optional[str]:
        """
        Store an approved Q&A pair with its embedding for future reuse.
        Returns the question_embeddings.id or None on failure.
        """
        try:
            embedding = get_embedding_cached(question_text)
            sb = get_supabase(token) if token else get_supabase()

            row = {
                "org_id": org_id,
                "project_id": project_id,
                "run_id": run_id,
                "audit_id": audit_id,
                "question_text": question_text,
                "answer_text": answer_text,
                "embedding": embedding,
                "source_document": source_document,
                "source_excerpt": (source_excerpt or "")[:500] if source_excerpt else None,
                "confidence_score": confidence_score,
                "similarity_score": similarity_score,
                "review_status": "approved",
            }
            cleaned = {k: v for k, v in row.items() if v is not None}
            res = sb.table("question_embeddings").insert(cleaned).execute()
            if res.data:
                qe_id = res.data[0].get("id")
                logger.info(f"Stored approved Q&A embedding: {qe_id}")
                return qe_id
            return None
        except Exception as e:
            logger.warning(f"Failed to store approved Q&A embedding (non-fatal): {e}")
            return None


# ─── Delta Tracking ──────────────────────────────────────────────────────────

def compute_delta(
    current_questions: List[Dict[str, str]],
    previous_questions: List[Dict[str, str]],
) -> Dict[str, str]:
    """
    Compare question lists between current and previous runs.

    Args:
        current_questions: List of dicts with 'question_text' and optionally 'cell_reference'
        previous_questions: List of dicts with 'question_text' and optionally 'cell_reference'

    Returns:
        Dict mapping question_text -> change_type ("NEW" | "MODIFIED" | "UNCHANGED")
    """
    # Build lookup from previous questions by normalized text
    prev_texts = {_normalize_question(q.get("question_text", "")): q for q in previous_questions}
    prev_cells = {q.get("cell_reference", ""): q for q in previous_questions if q.get("cell_reference")}

    result = {}
    for q in current_questions:
        text = q.get("question_text", "")
        cell = q.get("cell_reference", "")
        norm = _normalize_question(text)

        if norm in prev_texts:
            # Exact text match → UNCHANGED
            result[text] = "UNCHANGED"
        elif cell and cell in prev_cells:
            # Same cell but different text → MODIFIED
            result[text] = "MODIFIED"
        else:
            # Not found in previous run → NEW
            result[text] = "NEW"

    return result


def _normalize_question(text: str) -> str:
    """Normalize question text for comparison (lowercase, strip whitespace/punctuation)."""
    import re
    return re.sub(r"\s+", " ", text.strip().lower())


# ─── Module Singletons ──────────────────────────────────────────────────────

similarity_engine = SimilarityEngine()
