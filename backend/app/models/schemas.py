from pydantic import BaseModel
from typing import List, Optional

class QuestionItem(BaseModel):
    sheet_name: str
    cell_coordinate: str  # e.g. "B5"
    question: str
    ai_answer: str
    final_answer: str
    confidence: str       # "HIGH", "MEDIUM", "LOW"
    sources: List[str]
    source_id: Optional[str] = None
    source_page: Optional[int] = None
    source_excerpt: Optional[str] = None  # Chunk text used to generate the answer
    # When we can't produce a grounded answer, the UI should prompt for more info.
    status: Optional[str] = None  # "ok" | "needs_info" | "ai_unavailable"
    status_reason: Optional[str] = None
    is_verified: bool = False
    edited_by_user: bool = False
    # Review workflow: "pending" | "approved" | "rejected"
    review_status: Optional[str] = None
    # Phase 3: Structured confidence
    confidence_score: Optional[float] = None     # 0.0 - 1.0 normalized
    confidence_reason: Optional[str] = None      # Human-readable explanation
    # Phase 3: Retrieval metadata
    embedding_similarity_score: Optional[float] = None
    chunk_id: Optional[str] = None
    token_count_used: Optional[int] = None
    model_used: Optional[str] = None
    generation_time_ms: Optional[int] = None
    retrieval_mode: Optional[str] = None         # "standard" | "strict"
    # Phase 3: Retrieval debug (only in debug mode)
    retrieval_debug: Optional[dict] = None
    # Phase 4: Answer reuse / institutional memory
    answer_origin: Optional[str] = None          # "generated" | "reused" | "suggested"
    reused_from_question_id: Optional[str] = None  # question_embeddings.id
    reuse_similarity_score: Optional[float] = None # similarity to matched approved Q&A
    # Phase 4: Delta tracking between runs
    change_type: Optional[str] = None            # "NEW" | "MODIFIED" | "UNCHANGED"
