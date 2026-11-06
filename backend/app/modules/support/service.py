import uuid
import re
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func

from app.core.config import settings
from app.core.security import create_visitor_session_token
from app.modules.support.models import (
    AIAgent,
    WidgetInstallation,
    Conversation,
    Message,
    Chatbot,
    ChatbotCapacity,
    ChatbotURL,
    ChatbotWidget,
    ChatbotKnowledgeSource,
    ChatbotStatusLog,
    ChatbotAssignment,
    ChatbotSession
)
from app.modules.support.schemas import (
    SessionTokenResponse,
    ChatMessageResponse,
    ChatbotCreateRequest,
    ChatbotUpdateRequest,
    ChatbotResponse,
    ChatbotURLResponse,
    PublicChatbotInfoResponse,
    PublicLiveSessionResponse,
    PublicLiveMessageResponse
)
from app.modules.support.scheduler import chatbot_scheduler
from app.modules.knowledge.service import knowledge_service
from app.modules.saas.service import saas_service
from app.modules.saas.models import Tenant, TenantSetting, Subscription, SubscriptionPlan

logger = logging.getLogger("support_service")


class SupportEngineService:
    """Manages multi-chatbot lifecycle, scheduler auto-assignments, public live chat, and Gemini AI inference."""

    # ==========================================
    # Multi-Chatbot Lifecycle & Administration
    # ==========================================

    async def create_chatbot(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        req: ChatbotCreateRequest
    ) -> ChatbotResponse:
        """Creates a new inactive custom chatbot instance within tenant subscription limits."""
        # 1. Enforce Subscription Plan Limit
        sub_stmt = select(Subscription).where(Subscription.tenant_id == tenant_id)
        subscription = (await db.execute(sub_stmt)).scalar_one_or_none()
        plan_code = subscription.plan_code if subscription else "Starter"

        plan_stmt = select(SubscriptionPlan).where(SubscriptionPlan.code == plan_code)
        plan = (await db.execute(plan_stmt)).scalar_one_or_none()
        max_allowed_bots = plan.max_ai_agents if plan else 5

        current_bots_count = (
            await db.execute(
                select(func.count(Chatbot.id)).where(Chatbot.tenant_id == tenant_id)
            )
        ).scalar() or 0

        if current_bots_count >= max_allowed_bots:
            raise ValueError(
                f"Chatbot limit of {max_allowed_bots} reached for your {plan_code} plan. Please upgrade your subscription."
            )

        # 2. Slug Generation & Validation
        raw_slug = req.slug or req.name
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", raw_slug).strip("-").lower()
        if not slug:
            slug = f"bot-{uuid.uuid4().hex[:8]}"

        # Ensure slug uniqueness
        existing_slug = (
            await db.execute(select(ChatbotURL).where(ChatbotURL.slug == slug))
        ).scalar_one_or_none()
        if existing_slug:
            slug = f"{slug}-{uuid.uuid4().hex[:4]}"

        # 3. Create Chatbot Model (Default: Inactive)
        chatbot = Chatbot(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            name=req.name,
            avatar_url=req.avatar_url,
            description=req.description,
            welcome_message=req.welcome_message,
            system_instructions=req.system_instructions or "You are a professional, helpful, and concise customer support representative.",
            ai_config=req.ai_config or {"model": "gemini-1.5-flash", "temperature": 0.7},
            status="inactive",
            is_active=False
        )
        db.add(chatbot)

        # 4. Create Capacity Tracker
        capacity = ChatbotCapacity(
            id=uuid.uuid4(),
            chatbot_id=chatbot.id,
            tenant_id=tenant_id,
            max_capacity=req.max_capacity,
            active_conversations=0,
            reserved_capacity=0
        )
        db.add(capacity)

        # 5. Create Standalone Live URL Configuration
        live_url = ChatbotURL(
            id=uuid.uuid4(),
            chatbot_id=chatbot.id,
            tenant_id=tenant_id,
            slug=slug,
            is_published=False,
            status="published"
        )
        db.add(live_url)

        # 6. Create Dedicated Widget Credentials
        widget = ChatbotWidget(
            id=uuid.uuid4(),
            chatbot_id=chatbot.id,
            tenant_id=tenant_id,
            public_key=f"pk_bot_{uuid.uuid4().hex[:16]}",
            secret_key=f"sk_bot_{uuid.uuid4().hex}",
            theme_color="#2563eb",
            allowed_origins=[]
        )
        db.add(widget)

        # 7. Record Status Log
        log = ChatbotStatusLog(
            id=uuid.uuid4(),
            chatbot_id=chatbot.id,
            tenant_id=tenant_id,
            old_status="none",
            new_status="inactive",
            reason="Initial chatbot instance created"
        )
        db.add(log)

        await db.flush()
        return self._format_chatbot_response(chatbot, capacity, live_url)

    async def get_chatbots(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID
    ) -> List[ChatbotResponse]:
        """Lists all tenant chatbots with live capacity and standalone URLs."""
        stmt = (
            select(Chatbot, ChatbotCapacity, ChatbotURL)
            .outerjoin(ChatbotCapacity, Chatbot.id == ChatbotCapacity.chatbot_id)
            .outerjoin(ChatbotURL, Chatbot.id == ChatbotURL.chatbot_id)
            .where(Chatbot.tenant_id == tenant_id)
            .order_by(Chatbot.created_at.desc())
        )
        results = (await db.execute(stmt)).all()

        return [
            self._format_chatbot_response(bot, cap, url)
            for bot, cap, url in results
        ]

    async def get_chatbot_by_id(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        chatbot_id: uuid.UUID
    ) -> Optional[ChatbotResponse]:
        """Retrieves a single chatbot configuration."""
        stmt = (
            select(Chatbot, ChatbotCapacity, ChatbotURL)
            .outerjoin(ChatbotCapacity, Chatbot.id == ChatbotCapacity.chatbot_id)
            .outerjoin(ChatbotURL, Chatbot.id == ChatbotURL.chatbot_id)
            .where(Chatbot.id == chatbot_id, Chatbot.tenant_id == tenant_id)
        )
        res = (await db.execute(stmt)).first()
        if not res:
            return None
        bot, cap, url = res
        return self._format_chatbot_response(bot, cap, url)

    async def update_chatbot(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        chatbot_id: uuid.UUID,
        req: ChatbotUpdateRequest
    ) -> ChatbotResponse:
        """Updates chatbot profile, persona, instructions, capacity, or slug while preserving conversation history."""
        bot_stmt = select(Chatbot).where(Chatbot.id == chatbot_id, Chatbot.tenant_id == tenant_id)
        bot = (await db.execute(bot_stmt)).scalar_one_or_none()
        if not bot:
            raise ValueError("Chatbot not found")

        if req.name is not None:
            bot.name = req.name
        if req.avatar_url is not None:
            bot.avatar_url = req.avatar_url
        if req.description is not None:
            bot.description = req.description
        if req.welcome_message is not None:
            bot.welcome_message = req.welcome_message
        if req.system_instructions is not None:
            bot.system_instructions = req.system_instructions
        if req.ai_config is not None:
            bot.ai_config = req.ai_config

        # Update Capacity if specified
        cap_stmt = select(ChatbotCapacity).where(ChatbotCapacity.chatbot_id == chatbot_id)
        cap = (await db.execute(cap_stmt)).scalar_one_or_none()
        if cap and req.max_capacity is not None:
            cap.max_capacity = req.max_capacity

        # Update Slug if specified
        url_stmt = select(ChatbotURL).where(ChatbotURL.chatbot_id == chatbot_id)
        url = (await db.execute(url_stmt)).scalar_one_or_none()
        if url and req.slug is not None:
            clean_slug = re.sub(r"[^a-zA-Z0-9]+", "-", req.slug).strip("-").lower()
            if clean_slug != url.slug:
                # Check uniqueness
                dup = (
                    await db.execute(
                        select(ChatbotURL).where(ChatbotURL.slug == clean_slug, ChatbotURL.id != url.id)
                    )
                ).scalar_one_or_none()
                if dup:
                    raise ValueError(f"The URL slug '{clean_slug}' is already taken.")
                url.redirect_slug = url.slug
                url.slug = clean_slug

        await db.flush()
        return self._format_chatbot_response(bot, cap, url)

    async def delete_chatbot(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        chatbot_id: uuid.UUID
    ) -> bool:
        """Removes a chatbot instance."""
        stmt = select(Chatbot).where(Chatbot.id == chatbot_id, Chatbot.tenant_id == tenant_id)
        bot = (await db.execute(stmt)).scalar_one_or_none()
        if not bot:
            return False
        await db.delete(bot)
        await db.flush()
        return True

    async def activate_chatbot(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        chatbot_id: uuid.UUID
    ) -> ChatbotResponse:
        """Enables chatbot for live customer auto-assignment (ON)."""
        bot_stmt = select(Chatbot).where(Chatbot.id == chatbot_id, Chatbot.tenant_id == tenant_id)
        bot = (await db.execute(bot_stmt)).scalar_one_or_none()
        if not bot:
            raise ValueError("Chatbot not found")

        old_status = bot.status
        bot.is_active = True
        bot.status = "active"

        # Publish Standalone Live URL automatically on activation
        url_stmt = select(ChatbotURL).where(ChatbotURL.chatbot_id == chatbot_id)
        url = (await db.execute(url_stmt)).scalar_one_or_none()
        if url:
            url.is_published = True

        log = ChatbotStatusLog(
            id=uuid.uuid4(),
            chatbot_id=chatbot_id,
            tenant_id=tenant_id,
            old_status=old_status,
            new_status="active",
            reason="Admin activated chatbot into live pool (ON)"
        )
        db.add(log)

        cap_stmt = select(ChatbotCapacity).where(ChatbotCapacity.chatbot_id == chatbot_id)
        cap = (await db.execute(cap_stmt)).scalar_one_or_none()

        await db.flush()
        return self._format_chatbot_response(bot, cap, url)

    async def deactivate_chatbot(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        chatbot_id: uuid.UUID,
        mode: str = "immediate"
    ) -> ChatbotResponse:
        """Disables chatbot from receiving new conversation assignments (OFF)."""
        bot_stmt = select(Chatbot).where(Chatbot.id == chatbot_id, Chatbot.tenant_id == tenant_id)
        bot = (await db.execute(bot_stmt)).scalar_one_or_none()
        if not bot:
            raise ValueError("Chatbot not found")

        old_status = bot.status
        bot.is_active = False

        if mode == "drain":
            bot.status = "draining"
            reason = "Admin initiated graceful drain of active conversations"
        else:
            bot.status = "inactive"
            reason = "Admin immediately stopped chatbot (OFF)"

        log = ChatbotStatusLog(
            id=uuid.uuid4(),
            chatbot_id=chatbot_id,
            tenant_id=tenant_id,
            old_status=old_status,
            new_status=bot.status,
            reason=reason
        )
        db.add(log)

        cap_stmt = select(ChatbotCapacity).where(ChatbotCapacity.chatbot_id == chatbot_id)
        cap = (await db.execute(cap_stmt)).scalar_one_or_none()

        url_stmt = select(ChatbotURL).where(ChatbotURL.chatbot_id == chatbot_id)
        url = (await db.execute(url_stmt)).scalar_one_or_none()

        await db.flush()
        return self._format_chatbot_response(bot, cap, url)

    async def update_chatbot_url(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        chatbot_id: uuid.UUID,
        new_slug: str
    ) -> ChatbotURLResponse:
        """Updates and validates custom live URL slug."""
        clean_slug = re.sub(r"[^a-zA-Z0-9]+", "-", new_slug).strip("-").lower()
        if len(clean_slug) < 3:
            raise ValueError("Slug must be at least 3 characters long.")

        url_stmt = select(ChatbotURL).where(ChatbotURL.chatbot_id == chatbot_id, ChatbotURL.tenant_id == tenant_id)
        url = (await db.execute(url_stmt)).scalar_one_or_none()
        if not url:
            raise ValueError("Chatbot URL configuration not found")

        # Uniqueness check
        dup = (
            await db.execute(
                select(ChatbotURL).where(ChatbotURL.slug == clean_slug, ChatbotURL.id != url.id)
            )
        ).scalar_one_or_none()
        if dup:
            raise ValueError(f"Slug '{clean_slug}' is already registered on the platform.")

        url.redirect_slug = url.slug
        url.slug = clean_slug
        await db.flush()

        base_domain = "http://localhost:3000/live"
        return ChatbotURLResponse(
            chatbot_id=chatbot_id,
            slug=url.slug,
            full_url=f"{base_domain}/{url.slug}",
            is_published=url.is_published,
            status=url.status
        )

    # ==========================================
    # Standalone Public Live Chat Gateway
    # ==========================================

    async def get_public_live_info(
        self,
        db: AsyncSession,
        slug: str
    ) -> PublicChatbotInfoResponse:
        """Resolves public chatbot metadata from URL slug without exposing sensitive tenant data."""
        clean_slug = slug.strip().lower()
        stmt = (
            select(Chatbot, ChatbotURL, ChatbotCapacity)
            .join(ChatbotURL, Chatbot.id == ChatbotURL.chatbot_id)
            .outerjoin(ChatbotCapacity, Chatbot.id == ChatbotCapacity.chatbot_id)
            .where(ChatbotURL.slug == clean_slug)
        )
        res = (await db.execute(stmt)).first()
        if not res:
            raise ValueError("Chatbot not found for this live URL")

        bot, url, cap = res

        # Derive live status for public visitor
        if not bot.is_active or bot.status in ["inactive", "draining"]:
            pub_status = "offline"
        elif bot.status == "busy" or (cap and (cap.active_conversations + cap.reserved_capacity) >= cap.max_capacity):
            pub_status = "busy"
        else:
            pub_status = "online"

        return PublicChatbotInfoResponse(
            chatbot_name=bot.name,
            avatar_url=bot.avatar_url,
            welcome_message=bot.welcome_message,
            status=pub_status,
            theme_color="#2563eb",
            slug=url.slug
        )

    async def initialize_public_live_session(
        self,
        db: AsyncSession,
        slug: str,
        visitor_fingerprint: Optional[str] = None
    ) -> PublicLiveSessionResponse:
        """Initializes an anonymous visitor session on the standalone live chat page."""
        clean_slug = slug.strip().lower()
        stmt = (
            select(Chatbot, ChatbotURL)
            .join(ChatbotURL, Chatbot.id == ChatbotURL.chatbot_id)
            .where(ChatbotURL.slug == clean_slug)
        )
        res = (await db.execute(stmt)).first()
        if not res:
            raise ValueError("Chatbot not found for this live URL")

        bot, url = res
        visitor_id = visitor_fingerprint or f"vis_live_{uuid.uuid4().hex[:12]}"

        # Create active conversation record
        conv = Conversation(
            id=uuid.uuid4(),
            tenant_id=bot.tenant_id,
            visitor_id=visitor_id,
            chatbot_id=None,  # Will be assigned on first customer message via Scheduler!
            status="active"
        )
        db.add(conv)
        await db.flush()

        # Sign JWT visitor token
        token = create_visitor_session_token(
            tenant_id=str(bot.tenant_id),
            visitor_id=visitor_id,
            session_id=str(conv.id)
        )

        return PublicLiveSessionResponse(
            session_token=token,
            conversation_id=conv.id,
            chatbot_name=bot.name,
            avatar_url=bot.avatar_url,
            welcome_message=bot.welcome_message,
            status=bot.status
        )

    async def process_live_chat_turn(
        self,
        db: AsyncSession,
        slug: str,
        conversation_id: uuid.UUID,
        message_text: str
    ) -> PublicLiveMessageResponse:
        """
        Processes customer message turn with multi-chatbot auto-assignment:
        1. Checks conversation continuity (sticky assignment).
        2. On first turn: Least-loaded candidate selection and atomic reservation.
        3. If all busy or OFF: Returns waiting queue or fallback status.
        4. Injects assigned chatbot instructions into Gemini RAG pipeline.
        """
        # Resolve target tenant from slug
        info = await self.get_public_live_info(db, slug)

        url_stmt = select(ChatbotURL).where(ChatbotURL.slug == slug)
        url = (await db.execute(url_stmt)).scalar_one_or_none()
        if not url:
            raise ValueError("Invalid live chat slug")
        tenant_id = url.tenant_id

        # 1. Conversation Continuity Check
        assigned_bot = await chatbot_scheduler.get_assigned_chatbot(db, conversation_id)

        # 2. First turn: Auto-Assignment Scheduler
        if not assigned_bot:
            selected_bot, res_token, sched_status = await chatbot_scheduler.find_and_reserve_chatbot(
                db=db,
                tenant_id=tenant_id,
                conversation_id=conversation_id
            )

            if sched_status == "NO_ACTIVE_CHATBOTS":
                return PublicLiveMessageResponse(
                    message_id=uuid.uuid4(),
                    conversation_id=conversation_id,
                    sender_type="agent",
                    content="Our AI assistants are currently offline. Please leave your email or contact support directly.",
                    assigned_chatbot_name=info.chatbot_name,
                    assigned_chatbot_avatar=info.avatar_url,
                    is_escalated=True,
                    tokens_consumed=0,
                    created_at=datetime.now(timezone.utc),
                    status="FALLBACK"
                )

            if sched_status == "ALL_CHATBOTS_BUSY":
                return PublicLiveMessageResponse(
                    message_id=uuid.uuid4(),
                    conversation_id=conversation_id,
                    sender_type="agent",
                    content="All our AI support assistants are currently busy assisting customers. Please wait a moment while we connect you...",
                    assigned_chatbot_name=info.chatbot_name,
                    assigned_chatbot_avatar=info.avatar_url,
                    is_escalated=False,
                    tokens_consumed=0,
                    created_at=datetime.now(timezone.utc),
                    status="WAITING_IN_QUEUE"
                )

            # Commit the assignment
            await chatbot_scheduler.commit_assignment(
                db=db,
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                chatbot_id=selected_bot.id,
                reservation_token=res_token
            )
            assigned_bot = selected_bot

        # 3. Record visitor message turn
        vis_msg = Message(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            sender_type="visitor",
            content=message_text,
            tokens_consumed=len(message_text.split()),
            created_at=datetime.now(timezone.utc)
        )
        db.add(vis_msg)
        await db.flush()

        # 4. RAG Knowledge Retrieval
        chunks = await knowledge_service.retrieve_chunks(db, tenant_id, message_text, top_k=3)
        is_unknown = not chunks or chunks[0].similarity_score < settings.SIMILARITY_THRESHOLD

        if is_unknown:
            await knowledge_service.record_unanswered_question(db, tenant_id, message_text)
            reply_text = f"I do not have enough verified information to answer this question. I have forwarded your query to our {assigned_bot.name} escalation queue."
            tokens = 45
            is_escalated = True
        else:
            # Generate grounded response using assigned chatbot's instructions
            reply_text, tokens = await self.generate_gemini_response(
                query=message_text,
                context_chunks=chunks,
                system_instructions=assigned_bot.system_instructions
            )
            if "UNKNOWN_QUESTION" in reply_text:
                await knowledge_service.record_unanswered_question(db, tenant_id, message_text)
                reply_text = f"I do not have enough verified information to answer this question. I have forwarded your query to our {assigned_bot.name} escalation queue."
                is_escalated = True
            else:
                is_escalated = False

        # 5. Record Assistant Message Turn
        agent_msg = Message(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            sender_type="agent",
            content=reply_text,
            tokens_consumed=tokens,
            created_at=datetime.now(timezone.utc)
        )
        db.add(agent_msg)

        # 6. Usage Quota Tracking
        await saas_service.record_usage(db, tenant_id, tokens)
        await db.flush()

        return PublicLiveMessageResponse(
            message_id=agent_msg.id,
            conversation_id=conversation_id,
            sender_type="agent",
            content=reply_text,
            assigned_chatbot_name=assigned_bot.name,
            assigned_chatbot_avatar=assigned_bot.avatar_url,
            is_escalated=is_escalated,
            tokens_consumed=tokens,
            created_at=agent_msg.created_at,
            status="DELIVERED"
        )

    # ==========================================
    # Gemini Provider & Grounded Inference
    # ==========================================

    async def generate_gemini_response(
        self,
        query: str,
        context_chunks: list,
        system_instructions: Optional[str] = None
    ) -> Tuple[str, int]:
        """Calls Google Gemini API or formats grounded response using contextual facts."""
        context_text = "\n---\n".join([c.content for c in context_chunks])
        persona = system_instructions or "You are a professional customer support assistant."

        if settings.GEMINI_API_KEY:
            try:
                from google import genai
                client = genai.Client(api_key=settings.GEMINI_API_KEY)
                prompt = (
                    f"{persona}\n\n"
                    "Answer the customer's question using ONLY the facts present in the <context> tags.\n"
                    "If the information is not present in the context, reply exactly: 'UNKNOWN_QUESTION'.\n\n"
                    f"<context>\n{context_text}\n</context>\n\n"
                    f"<customer_question>\n{query}\n</customer_question>"
                )
                response = client.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=prompt
                )
                text = response.text.strip()
                tokens = len(text.split()) + len(prompt.split())
                return text, tokens
            except Exception as e:
                logger.error(f"Gemini API generation failed: {e}")

        # Local deterministic fallback
        best = context_chunks[0]
        tokens = len(best.content.split()) + 20
        return f"Based on our documentation: {best.content}", tokens

    # ==========================================
    # Helper & Legacy Functions (Backward Compatibility)
    # ==========================================

    def _format_chatbot_response(
        self,
        bot: Chatbot,
        cap: Optional[ChatbotCapacity],
        url: Optional[ChatbotURL]
    ) -> ChatbotResponse:
        max_cap = cap.max_capacity if cap else 5
        act_conv = cap.active_conversations if cap else 0
        res_cap = cap.reserved_capacity if cap else 0
        avail_cap = max(0, max_cap - act_conv - res_cap)

        slug = url.slug if url else None
        live_url = f"http://localhost:3000/live/{slug}" if slug else None

        return ChatbotResponse(
            id=bot.id,
            tenant_id=bot.tenant_id,
            name=bot.name,
            avatar_url=bot.avatar_url,
            description=bot.description,
            welcome_message=bot.welcome_message,
            system_instructions=bot.system_instructions,
            status=bot.status,
            is_active=bot.is_active,
            max_capacity=max_cap,
            active_conversations=act_conv,
            available_capacity=avail_cap,
            slug=slug,
            live_url=live_url,
            created_at=bot.created_at,
            updated_at=bot.updated_at
        )

    async def get_or_create_widget(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID
    ) -> WidgetInstallation:
        """Legacy helper for tenant widget installation."""
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
        """Legacy helper for single agent fallback."""
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
                system_instructions="You are a professional customer support representative."
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
        """Legacy visitor session for widget embedding."""
        stmt = select(WidgetInstallation).where(WidgetInstallation.public_key == public_key)
        widget = (await db.execute(stmt)).scalar_one_or_none()
        if not widget:
            raise ValueError("Invalid widget public key")

        visitor_id = visitor_fingerprint or f"vis_{uuid.uuid4().hex[:12]}"
        agent = await self.get_or_create_default_agent(db, widget.tenant_id)

        conversation = Conversation(
            id=uuid.uuid4(),
            tenant_id=widget.tenant_id,
            visitor_id=visitor_id,
            agent_id=agent.id,
            status="active"
        )
        db.add(conversation)
        agent.active_chats += 1
        await db.flush()

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

    async def process_chat_message(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        conversation_id: uuid.UUID,
        message_text: str
    ) -> ChatMessageResponse:
        """Legacy message processing for existing tests and widget."""
        quota = await saas_service.validate_quota(db, tenant_id)
        if not quota.allowed:
            return ChatMessageResponse(
                message_id=uuid.uuid4(),
                conversation_id=conversation_id,
                sender_type="agent",
                content="Our support chat is currently at full monthly capacity. Please email support directly.",
                is_escalated=True,
                tokens_consumed=0,
                created_at=datetime.now(timezone.utc)
            )

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

        chunks = await knowledge_service.retrieve_chunks(db, tenant_id, message_text, top_k=3)
        is_unknown = not chunks or (chunks and chunks[0].similarity_score < settings.SIMILARITY_THRESHOLD)

        if is_unknown:
            await knowledge_service.record_unanswered_question(db, tenant_id, message_text)
            reply_text = "I do not have enough verified information to answer this question. I have forwarded your query to our support team."
            tokens = 45
            is_escalated = True
        else:
            reply_text, tokens = await self.generate_gemini_response(message_text, chunks)
            if "UNKNOWN_QUESTION" in reply_text:
                await knowledge_service.record_unanswered_question(db, tenant_id, message_text)
                reply_text = "I do not have enough verified information to answer this question. I have forwarded your query to our support team."
                is_escalated = True
            else:
                is_escalated = False

        agent_msg = Message(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            sender_type="agent",
            content=reply_text,
            tokens_consumed=tokens,
            created_at=datetime.now(timezone.utc)
        )
        db.add(agent_msg)

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
