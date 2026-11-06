import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class InstructionCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    content: str = Field(..., min_length=5)


class InstructionResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    title: str
    content: str
    status: str
    version: int
    created_at: datetime
    updated_at: datetime


class ChunkResponse(BaseModel):
    id: uuid.UUID
    content: str
    similarity_score: float = 1.0


class RetrievalRequest(BaseModel):
    query: str = Field(..., min_length=2)
    top_k: int = 3


class RetrievalResponse(BaseModel):
    chunks: List[ChunkResponse]
    query: str


class CustomQuestionResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    question_text: str
    status: str
    frequency: int
    created_at: datetime
    approved_answer: Optional[str] = None


class ApproveAnswerRequest(BaseModel):
    answer_text: str = Field(..., min_length=2)
    approved_by: Optional[str] = "Admin"

