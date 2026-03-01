from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID


class RunBase(BaseModel):
    org_id: str
    project_id: Optional[str] = None
    questionnaire_filename: Optional[str] = None
    # State machine: queued -> processing -> completed|failed
    status: str
    progress: int = 0
    error_message: Optional[str] = None
    export_filename: Optional[str] = None

    # File metadata
    input_filename: Optional[str] = None
    output_filename: Optional[str] = None

    # Timestamps
    finished_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Counters
    docs_ingested: int = 0
    questions_total: int = 0
    questions_answered: int = 0


class RunCreate(RunBase):
    pass


class RunUpdate(BaseModel):
    status: Optional[str] = None
    progress: Optional[int] = None
    export_filename: Optional[str] = None
    output_filename: Optional[str] = None
    error_message: Optional[str] = None
    finished_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    questions_total: Optional[int] = None
    questions_answered: Optional[int] = None
    is_locked: Optional[bool] = None  # Phase 17: evidence lock


class Run(RunBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    is_locked: Optional[bool] = False  # Phase 17

    class Config:
        from_attributes = True
