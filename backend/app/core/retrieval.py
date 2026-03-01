"""
Phase 3: Deterministic Retrieval Engine

Key guarantees:
1. Similarity threshold enforcement — no chunk below threshold is ever used.
2. Every retrieval returns structured metadata (scores, chunk_ids, timing).
3. Debug mode returns top-K chunks with scores (disabled in production).
4. Python fallback when match_chunks RPC is unavailable.
"""
import time
import logging
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

from app.core.config import get_settings
from app.core.database import get_supabase
from app.core.ingestion import pdf_processor  # reuse embedding function

settings = get_settings()
logger = logging.getLogger("retrieval")


@dataclass
class RetrievalChunk:
    """Structured representation of a single retrieved chunk."""
    chunk_id: Optional[str] = None
    document_id: Optional[str] = None
    filename: str = "Unknown File"
    content: str = ""
    page_number: Optional[int] = None
    chunk_index: Optional[int] = None
    similarity: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RetrievalResult:
    """Structured result of a retrieval operation with full metadata."""
    chunks: List[RetrievalChunk] = field(default_factory=list)
    query: str = ""
    threshold_used: float = 0.0
    top_k_used: int = 0
    total_candidates: int = 0          # chunks evaluated (before threshold filter)
    above_threshold: int = 0           # chunks that passed the threshold
    retrieval_time_ms: int = 0
    retrieval_method: str = "rpc"      # "rpc" or "python_fallback"
    debug_all_scores: Optional[List[Dict[str, Any]]] = None  # only populated in debug mode

    @property
    def has_results(self) -> bool:
        return len(self.chunks) > 0

    @property
    def best_score(self) -> float:
        return self.chunks[0].similarity if self.chunks else 0.0

    @property
    def context_text(self) -> str:
        return "\n\n".join(c.content for c in self.chunks if c.content)

    @property
    def source_filenames(self) -> List[str]:
        return list(dict.fromkeys(c.filename for c in self.chunks))

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "chunks_count": len(self.chunks),
            "threshold_used": self.threshold_used,
            "top_k_used": self.top_k_used,
            "total_candidates": self.total_candidates,
            "above_threshold": self.above_threshold,
            "retrieval_time_ms": self.retrieval_time_ms,
            "retrieval_method": self.retrieval_method,
            "best_score": self.best_score,
        }
        if self.debug_all_scores is not None:
            result["debug_all_scores"] = self.debug_all_scores
        return result


class RetrievalEngine:
    """Deterministic retrieval engine with threshold enforcement and metadata tracking."""

    def retrieve(
        self,
        query: str,
        org_id: str,
        project_id: Optional[str] = None,
        token: Optional[str] = None,
        # Per-call overrides (fall back to settings if not provided)
        similarity_threshold: Optional[float] = None,
        top_k: Optional[int] = None,
        debug: Optional[bool] = None,
    ) -> RetrievalResult:
        threshold = similarity_threshold if similarity_threshold is not None else settings.RETRIEVAL_SIMILARITY_THRESHOLD
        limit = top_k if top_k is not None else settings.RETRIEVAL_TOP_K
        is_debug = debug if debug is not None else settings.RETRIEVAL_DEBUG

        start = time.monotonic()

        # Use per-request client so RLS evaluates with the caller's JWT.
        sb = get_supabase(token) if token else get_supabase()

        # 1. Generate query embedding
        query_embedding = pdf_processor.get_embedding(query)

        # 2. Construct filter
        filter_criteria = {"org_id": org_id}
        if project_id:
            filter_criteria["project_id"] = project_id

        # 3. Try RPC first, fallback to Python vector search
        chunks: List[RetrievalChunk] = []
        total_candidates = 0
        method = "rpc"
        debug_scores: Optional[List[Dict[str, Any]]] = None

        try:
            params = {
                "query_embedding": query_embedding,
                "match_threshold": threshold,
                "match_count": limit,
                "filter": filter_criteria,
            }
            result = sb.rpc("match_chunks", params).execute()
            rows = result.data or []

            for r in rows:
                sim = float(r.get("similarity", 0))
                if sim >= threshold:
                    chunks.append(RetrievalChunk(
                        chunk_id=r.get("chunk_id"),
                        document_id=r.get("document_id"),
                        filename=r.get("document_filename") or r.get("filename", "Unknown File"),
                        content=r.get("content", ""),
                        page_number=r.get("page_number"),
                        chunk_index=r.get("chunk_index"),
                        similarity=sim,
                    ))

            total_candidates = len(rows)

            if is_debug:
                # For debug: query with threshold=0 to see all candidates
                try:
                    debug_params = {
                        "query_embedding": query_embedding,
                        "match_threshold": 0.0,
                        "match_count": 5,
                        "filter": filter_criteria,
                    }
                    debug_result = sb.rpc("match_chunks", debug_params).execute()
                    debug_rows = debug_result.data or []
                    debug_scores = [
                        {
                            "chunk_id": dr.get("chunk_id"),
                            "document_id": dr.get("document_id"),
                            "filename": dr.get("document_filename") or dr.get("filename"),
                            "similarity": round(float(dr.get("similarity", 0)), 4),
                            "content_preview": (dr.get("content", "")[:200] + "...") if dr.get("content") else "",
                            "above_threshold": float(dr.get("similarity", 0)) >= threshold,
                        }
                        for dr in debug_rows
                    ]
                except Exception as debug_err:
                    logger.warning(f"Debug retrieval failed (non-fatal): {debug_err}")
                    debug_scores = []

        except Exception as rpc_err:
            logger.warning(f"RPC retrieval failed, falling back to Python: {rpc_err}")
            method = "python_fallback"
            chunks, total_candidates, debug_scores = self._python_vector_search(
                sb, query_embedding, org_id, project_id, limit, threshold, is_debug
            )

        # Sort by similarity descending and cap at limit
        chunks.sort(key=lambda c: c.similarity, reverse=True)
        above_threshold = len(chunks)
        chunks = chunks[:limit]

        elapsed_ms = int((time.monotonic() - start) * 1000)

        return RetrievalResult(
            chunks=chunks,
            query=query,
            threshold_used=threshold,
            top_k_used=limit,
            total_candidates=total_candidates,
            above_threshold=above_threshold,
            retrieval_time_ms=elapsed_ms,
            retrieval_method=method,
            debug_all_scores=debug_scores if is_debug else None,
        )

    def _python_vector_search(
        self,
        sb,
        query_vector: List[float],
        org_id: str,
        project_id: Optional[str],
        limit: int,
        threshold: float,
        is_debug: bool,
    ) -> tuple:
        """Fallback: fetch all org chunks and compute cosine similarity in Python."""
        try:
            import numpy as np

            # 1. Get document IDs for org
            doc_query = sb.table("documents").select("id, filename").eq("org_id", org_id)
            if project_id:
                doc_query = doc_query.eq("project_id", project_id)
            docs = doc_query.execute()
            doc_data = docs.data or []
            doc_ids = [d["id"] for d in doc_data]
            filename_map = {d["id"]: d["filename"] for d in doc_data}

            if not doc_ids:
                return [], 0, [] if is_debug else None

            # 2. Get all chunks for these docs
            all_chunks = sb.table("chunks").select("*").in_("document_id", doc_ids).execute()
            if not all_chunks.data:
                return [], 0, [] if is_debug else None

            # 3. Compute cosine similarity
            query_vec = np.array(query_vector)
            scored: List[RetrievalChunk] = []
            debug_scores_list = [] if is_debug else None
            total_candidates = len(all_chunks.data)

            for chunk in all_chunks.data:
                vec = np.array(chunk["embedding"])
                # OpenAI embeddings are normalized — dot product = cosine similarity
                score = float(np.dot(query_vec, vec))

                if is_debug and debug_scores_list is not None:
                    debug_scores_list.append({
                        "chunk_id": chunk.get("id"),
                        "document_id": chunk.get("document_id"),
                        "filename": filename_map.get(chunk.get("document_id"), "Unknown"),
                        "similarity": round(score, 4),
                        "content_preview": (chunk.get("content", "")[:200] + "...") if chunk.get("content") else "",
                        "above_threshold": score >= threshold,
                    })

                if score >= threshold:
                    scored.append(RetrievalChunk(
                        chunk_id=chunk.get("id"),
                        document_id=chunk.get("document_id"),
                        filename=filename_map.get(chunk.get("document_id"), "Unknown File"),
                        content=chunk.get("content", ""),
                        page_number=chunk.get("page_number"),
                        chunk_index=chunk.get("chunk_index"),
                        similarity=score,
                    ))

            # Sort debug scores by similarity for readability
            if debug_scores_list:
                debug_scores_list.sort(key=lambda x: x["similarity"], reverse=True)
                debug_scores_list = debug_scores_list[:5]  # Top 5 for debug

            return scored, total_candidates, debug_scores_list

        except Exception as e:
            logger.error(f"Python vector search failed: {e}")
            return [], 0, [] if is_debug else None


retrieval_engine = RetrievalEngine()
