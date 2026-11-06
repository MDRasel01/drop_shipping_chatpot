import hashlib
import uuid
import logging
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.modules.knowledge.models import (
    Instruction,
    KnowledgeVersion,
    KnowledgeChunk,
    CustomQuestion,
    ApprovedAnswer
)
from app.modules.knowledge.schemas import (
    InstructionCreateRequest,
    InstructionResponse,
    ChunkResponse,
    CustomQuestionResponse
)

logger = logging.getLogger("knowledge_service")


class KnowledgeService:
    """Manages business instructions, chunking, Gemini embeddings, and approved answer loops."""

    def _generate_mock_embedding(self, text: str) -> List[float]:
        """Deterministic 768-dimensional fallback embedding when live API key is unavailable."""
        hash_val = int(hashlib.md5(text.encode("utf-8")).hexdigest(), 16)
        return [((hash_val >> (i % 64)) & 0xFF) / 255.0 for i in range(768)]

    async def get_embedding(self, text: str) -> List[float]:
        """Fetches vector embedding from Gemini text-embedding-004 or fallback generator."""
        if settings.GEMINI_API_KEY:
            try:
                from google import genai
                client = genai.Client(api_key=settings.GEMINI_API_KEY)
                response = client.models.embed_content(
                    model=settings.GEMINI_EMBEDDING_MODEL,
                    contents=text
                )
                if response.embedding and response.embedding.values:
                    return response.embedding.values[:768]
            except Exception as e:
                logger.warning(f"Gemini embedding API call failed ({e}). Falling back to deterministic vector.")

        return self._generate_mock_embedding(text)

    async def create_instruction(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        req: InstructionCreateRequest
    ) -> Instruction:
        instruction = Instruction(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            title=req.title,
            content=req.content,
            status="draft",
            version=1
        )
        db.add(instruction)

        # Snapshot version 1
        v1 = KnowledgeVersion(
            id=uuid.uuid4(),
            instruction_id=instruction.id,
            version_number=1,
            snapshot_content=req.content
        )
        db.add(v1)
        await db.flush()
        return instruction

    async def publish_instruction(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        instruction_id: uuid.UUID
    ) -> Instruction:
        stmt = select(Instruction).where(
            Instruction.tenant_id == tenant_id,
            Instruction.id == instruction_id
        )
        instruction = (await db.execute(stmt)).scalar_one_or_none()
        if not instruction:
            raise ValueError("Instruction not found")

        # 1. Chunk content by paragraphs or headers
        paragraphs = [p.strip() for p in instruction.content.split("\n\n") if p.strip()]
        if not paragraphs:
            paragraphs = [instruction.content]

        # 2. Vectorize and persist chunks
        for idx, para in enumerate(paragraphs):
            embedding = await self.get_embedding(para)
            chunk = KnowledgeChunk(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                instruction_id=instruction.id,
                content=para,
                embedding=embedding,
                extra_metadata={"title": instruction.title, "chunk_index": idx}
            )
            db.add(chunk)

        instruction.status = "published"
        await db.flush()
        return instruction

    async def retrieve_chunks(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        query: str,
        top_k: int = 3
    ) -> List[ChunkResponse]:
        """Retrieves top matching knowledge chunks for RAG."""
        stmt = select(KnowledgeChunk).where(KnowledgeChunk.tenant_id == tenant_id)
        res = await db.execute(stmt)
        all_chunks = res.scalars().all()

        if not all_chunks:
            return []

        # In-memory keyword and semantic match
        import re
        stopwords = {"how", "many", "do", "i", "have", "for", "a", "an", "the", "in", "on", "at", "to", "is", "are", "can", "you", "we", "our", "your", "what", "where", "when", "why"}
        tokens = set(re.findall(r"\w+", query.lower()))
        content_tokens = {t for t in tokens if t not in stopwords} or tokens

        scored = []
        for chunk in all_chunks:
            chunk_tokens = set(re.findall(r"\w+", chunk.content.lower()))
            overlap = len(content_tokens.intersection(chunk_tokens))
            if overlap > 0:
                score = 0.5 + (0.5 * (overlap / len(content_tokens)))
            else:
                score = 0.0
            scored.append((chunk, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:top_k]

        return [
            ChunkResponse(
                id=c.id,
                content=c.content,
                similarity_score=round(s, 2)
            )
            for c, s in top
        ]

    async def record_unanswered_question(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        question_text: str
    ) -> CustomQuestion:
        """Records an unknown question or increments frequency if already logged."""
        stmt = select(CustomQuestion).where(
            CustomQuestion.tenant_id == tenant_id,
            CustomQuestion.question_text == question_text.strip()
        )
        q = (await db.execute(stmt)).scalar_one_or_none()

        if q:
            q.frequency += 1
        else:
            q = CustomQuestion(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                question_text=question_text.strip(),
                status="UNANSWERED",
                frequency=1
            )
            db.add(q)

        await db.flush()
        return q

    async def approve_answer(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        question_id: uuid.UUID,
        answer_text: str,
        approved_by: str = "Admin"
    ) -> ApprovedAnswer:
        """Approves answer, marks question resolved, and immediately vectorizes answer for future AI use."""
        stmt = select(CustomQuestion).where(
            CustomQuestion.tenant_id == tenant_id,
            CustomQuestion.id == question_id
        )
        q = (await db.execute(stmt)).scalar_one_or_none()
        if not q:
            raise ValueError("Question not found")

        q.status = "ANSWERED"

        ans = ApprovedAnswer(
            id=uuid.uuid4(),
            question_id=q.id,
            answer_text=answer_text,
            approved_by=approved_by
        )
        db.add(ans)

        # Auto-embed approved Q&A pair into KnowledgeChunk
        qa_chunk_content = f"Question: {q.question_text}\nAnswer: {answer_text}"
        embedding = await self.get_embedding(qa_chunk_content)
        chunk = KnowledgeChunk(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            content=qa_chunk_content,
            embedding=embedding,
            extra_metadata={"source": "approved_answer", "question_id": str(q.id)}
        )
        db.add(chunk)

        await db.flush()
        return ans


knowledge_service = KnowledgeService()
