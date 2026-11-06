import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db, set_tenant_context
from app.modules.knowledge.schemas import (
    InstructionCreateRequest,
    InstructionResponse,
    RetrievalRequest,
    RetrievalResponse,
    CustomQuestionResponse,
    ApproveAnswerRequest
)
from app.modules.knowledge.models import Instruction, CustomQuestion
from app.modules.knowledge.service import knowledge_service

router = APIRouter(prefix="/knowledge", tags=["Knowledge Engine"])


@router.post("/instructions", response_model=InstructionResponse, status_code=status.HTTP_201_CREATED)
async def create_instruction(
    request: InstructionCreateRequest,
    tenant_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Creates a business instruction draft with automatic version 1 snapshot."""
    await set_tenant_context(db, tenant_id)
    inst = await knowledge_service.create_instruction(db, tenant_id, request)
    return InstructionResponse(
        id=inst.id,
        tenant_id=inst.tenant_id,
        title=inst.title,
        content=inst.content,
        status=inst.status,
        version=inst.version,
        created_at=inst.created_at,
        updated_at=inst.updated_at
    )


@router.post("/instructions/{instruction_id}/publish", response_model=InstructionResponse)
async def publish_instruction(
    instruction_id: uuid.UUID,
    tenant_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Chunks instruction content, computes 768d vector embeddings, and marks published."""
    await set_tenant_context(db, tenant_id)
    try:
        inst = await knowledge_service.publish_instruction(db, tenant_id, instruction_id)
        return InstructionResponse(
            id=inst.id,
            tenant_id=inst.tenant_id,
            title=inst.title,
            content=inst.content,
            status=inst.status,
            version=inst.version,
            created_at=inst.created_at,
            updated_at=inst.updated_at
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/retrieval", response_model=RetrievalResponse)
async def retrieve_knowledge(
    request: RetrievalRequest,
    tenant_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Performs hybrid vector/semantic search for RAG context retrieval."""
    await set_tenant_context(db, tenant_id)
    chunks = await knowledge_service.retrieve_chunks(db, tenant_id, request.query, request.top_k)
    return RetrievalResponse(chunks=chunks, query=request.query)


@router.get("/questions", response_model=List[CustomQuestionResponse])
async def list_unanswered_questions(
    tenant_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Lists unanswered customer queries detected during live conversations."""
    await set_tenant_context(db, tenant_id)
    stmt = (
        select(CustomQuestion)
        .options(selectinload(CustomQuestion.approved_answer))
        .where(CustomQuestion.tenant_id == tenant_id)
        .order_by(CustomQuestion.frequency.desc(), CustomQuestion.created_at.desc())
    )
    res = await db.execute(stmt)
    records = res.scalars().all()

    return [
        CustomQuestionResponse(
            id=r.id,
            tenant_id=r.tenant_id,
            question_text=r.question_text,
            status=r.status,
            frequency=r.frequency,
            created_at=r.created_at,
            approved_answer=r.approved_answer.answer_text if r.approved_answer else None
        )
        for r in records
    ]


@router.post("/questions/{question_id}/answer")
async def approve_question_answer(
    question_id: uuid.UUID,
    request: ApproveAnswerRequest,
    tenant_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Approves an answer to an unknown question, auto-vectorizing it for future customer queries."""
    await set_tenant_context(db, tenant_id)
    try:
        ans = await knowledge_service.approve_answer(
            db=db,
            tenant_id=tenant_id,
            question_id=question_id,
            answer_text=request.answer_text,
            approved_by=request.approved_by or "Admin"
        )
        return {
            "status": "SUCCESS",
            "message": "Answer approved and vector knowledge index updated.",
            "answer_id": ans.id,
            "question_id": ans.question_id
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

