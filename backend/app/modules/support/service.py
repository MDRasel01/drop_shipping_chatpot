import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.core.config import settings
from app.core.security import create_visitor_session_token
from app.modules.support.models import AIAgent, WidgetInstallation, Conversation, Message
from app.modules.support.schemas import SessionTokenResponse, ChatMessageResponse
from app.modules.knowledge.service import knowledge_service
from app.modules.saas.service import saas_service
from app.modules.saas.models import Tenant, TenantSetting

logger = logging.getLogger("support_service")


class SupportEngineService:
    """Manages chat widget gateways, signed visitor sessions, and grounded Gemini AI inference."""

    async def get_or_create_widget(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID
    ) -> WidgetInstallation:
        """Retrieves or creates the widget keys and configuration for a tenant."""
        stmt = select(WidgetInstallation).where(WidgetInstallation.tenant_id == tenant_id)
        widget = (await db.execute(stmt)).scalar_one_or_none()

        if not widget:
            widget = WidgetInstallation(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                public_key=f"pk_live_{uuid.uuid4().hex[:16]}",
                secret_key=f"sk_live_{uuid.uuid4().hex}",
                theme_color="#2563eb",
                allowed_origins=[]
            )
            db.add(widget)
            await db.flush()

        return widget

    async def get_or_create_default_agent(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID
    ) -> AIAgent:
        """Ensures at least one logical AI agent exists for the tenant."""
        stmt = select(AIAgent).where(AIAgent.tenant_id == tenant_id).order_by(AIAgent.active_chats.asc())
        agent = (await db.execute(stmt)).scalars().first()

        if not agent:
            agent = AIAgent(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                name="Support Assistant",
                role="Customer Support Representative",
                status="online",
                active_chats=0,
                max_concurrency=25,
                system_instructions="You are a professional, helpful, and concise customer support representative. Answer only using the verified knowledge provided in <context>."
            )
            db.add(agent)
            await db.flush()

        return agent

    async def initialize_visitor_session(
        self,
        db: AsyncSession,
        public_key: str,
        origin: str,
        visitor_fingerprint: Optional[str] = None
    ) -> SessionTokenResponse:
        """Validates widget key and issues a signed visitor chat JWT token."""
        stmt = select(WidgetInstallation).where(WidgetInstallation.public_key == public_key)
        widget = (await db.execute(stmt)).scalar_one_or_none()
        if not widget:
            raise ValueError("Invalid widget public key")

        # Validate origin if allowed_origins configured
        if widget.allowed_origins and origin not in widget.allowed_origins:
            raise ValueError(f"Origin '{origin}' not authorized for this widget")

        visitor_id = visitor_fingerprint or f"vis_{uuid.uuid4().hex[:12]}"
        agent = await self.get_or_create_default_agent(db, widget.tenant_id)

        # Create active conversation
        conversation = Conversation(
            id=uuid.uuid4(),
            tenant_id=widget.tenant_id,
            visitor_id=visitor_id,
            agent_id=agent.id,
            status="active"
        )
        db.add(conversation)

        # Increment active chat counter on agent
        agent.active_chats += 1
        await db.flush()

        # Fetch tenant settings welcome message
        setting_stmt = select(TenantSetting).where(TenantSetting.tenant_id == widget.tenant_id)
        setting = (await db.execute(setting_stmt)).scalar_one_or_none()
        welcome_msg = setting.welcome_message if setting else "Hello! How can I assist you today?"

        token = create_visitor_session_token(
            tenant_id=str(widget.tenant_id),
            visitor_id=visitor_id,
            session_id=str(conversation.id)
        )

        return SessionTokenResponse(
            session_token=token,
            session_id=conversation.id,
            tenant_id=widget.tenant_id,
            visitor_id=visitor_id,
            welcome_message=welcome_msg
        )

    async def generate_gemini_response(
        self,
        query: str,
        context_chunks: list
    ) -> Tuple[str, int]:
        """Calls Google Gemini API or formats grounded response from context."""
        context_text = "\n---\n".join([c.content for c in context_chunks])

        if settings.GEMINI_API_KEY:
            try:
                from google import genai
                client = genai.Client(api_key=settings.GEMINI_API_KEY)
                prompt = (
                    "You are a professional customer support assistant. Answer the customer's question using ONLY the facts present in the <context> tags.\n"
                    "If the information is not present in the context, reply exactly: 'UNKNOWN_QUESTION'.\n\n"
                    f"<context>\n{context_text}\n</context>\n\n"
                    f"<customer_question>\n{query}\n</customer_question>"
                )
                res = client.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=prompt
                )
                if res.text and res.text.strip():
                    ans = res.text.strip()
                    tokens = len(prompt.split()) + len(ans.split())
                    return ans, tokens
            except Exception as e:
                logger.warning(f"Live Gemini generation failed ({e}). Using grounded extractor.")

        # Grounded extraction fallback
        best_chunk = context_chunks[0].content
        reply = f"Based on our documentation: {best_chunk}"
        return reply, 120

    async def process_chat_message(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        conversation_id: uuid.UUID,
        message_text: str
    ) -> ChatMessageResponse:
        """Processes customer message through RAG retrieval, Gemini inference, unknown escalation, and usage recording."""
        # 1. Validate quota
        quota = await saas_service.validate_quota(db, tenant_id)
        if not quota.allowed:
            return ChatMessageResponse(
                message_id=uuid.uuid4(),
                conversation_id=conversation_id,
                sender_type="agent",
                content="Our support chat is currently at full monthly capacity. Please email support directly.",
                is_escalated=True,
                tokens_consumed=0,
                created_at=datetime.now()
            )

        # 2. Record visitor message
        visitor_msg = Message(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            sender_type="visitor",
            content=message_text,
            tokens_consumed=len(message_text.split()),
            created_at=datetime.now(timezone.utc)
        )
        db.add(visitor_msg)
        await db.flush()

        # 3. Retrieve Knowledge Chunks
        chunks = await knowledge_service.retrieve_chunks(db, tenant_id, message_text, top_k=3)

        # 4. Check confidence / knowledge presence
        is_unknown = False
        if not chunks or (chunks and chunks[0].similarity_score < settings.SIMILARITY_THRESHOLD):
            is_unknown = True

        if is_unknown:
            # Escalate: record in custom_questions table and notify
            await knowledge_service.record_unanswered_question(db, tenant_id, message_text)
            reply_text = "I do not have enough verified information to answer this question. I have forwarded your query to our support team."
            tokens = 45
            is_escalated = True
        else:
            # Generate grounded response
            reply_text, tokens = await self.generate_gemini_response(message_text, chunks)
            if "UNKNOWN_QUESTION" in reply_text:
                await knowledge_service.record_unanswered_question(db, tenant_id, message_text)
                reply_text = "I do not have enough verified information to answer this question. I have forwarded your query to our support team."
                is_escalated = True
            else:
                is_escalated = False

        # 5. Record Assistant Message
        agent_msg = Message(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            sender_type="agent",
            content=reply_text,
            tokens_consumed=tokens,
            created_at=datetime.now(timezone.utc)
        )
        db.add(agent_msg)

        # 6. Record usage quota
        await saas_service.record_usage(db, tenant_id, tokens)
        await db.flush()

        return ChatMessageResponse(
            message_id=agent_msg.id,
            conversation_id=conversation_id,
            sender_type="agent",
            content=reply_text,
            is_escalated=is_escalated,
            tokens_consumed=tokens,
            created_at=agent_msg.created_at
        )


support_service = SupportEngineService()
