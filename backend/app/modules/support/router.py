import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db, set_tenant_context
from app.core.security import decode_visitor_session_token
from app.modules.support.schemas import (
    WidgetConfigResponse,
    SessionInitRequest,
    SessionTokenResponse,
    ChatMessageRequest,
    ChatMessageResponse,
    AIAgentResponse,
    ChatbotCreateRequest,
    ChatbotUpdateRequest,
    ChatbotResponse,
    ChatbotURLResponse,
    ChatbotURLUpdateRequest,
    PublicChatbotInfoResponse,
    PublicLiveSessionRequest,
    PublicLiveSessionResponse,
    PublicLiveMessageRequest,
    PublicLiveMessageResponse
)
from app.modules.support.models import AIAgent, WidgetInstallation, Conversation, Message
from app.modules.support.service import support_service
from app.modules.saas.models import Tenant, TenantSetting

router = APIRouter(tags=["Multi-Chatbot Management & Live Chat"])


# ==========================================
# Multi-Chatbot Administration (Dashboard)
# ==========================================

@router.get("/dashboard/chatbots", response_model=List[ChatbotResponse])
async def list_chatbots(
    tenant_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Lists all tenant chatbots with live capacity meters and state badges."""
    await set_tenant_context(db, tenant_id)
    return await support_service.get_chatbots(db, tenant_id)


@router.post("/dashboard/chatbots", response_model=ChatbotResponse, status_code=status.HTTP_201_CREATED)
async def create_chatbot(
    request: ChatbotCreateRequest,
    tenant_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Creates a new custom chatbot instance (default: Inactive) within subscription limits."""
    await set_tenant_context(db, tenant_id)
    try:
        return await support_service.create_chatbot(db, tenant_id, request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/dashboard/chatbots/{chatbot_id}", response_model=ChatbotResponse)
async def get_chatbot(
    chatbot_id: uuid.UUID,
    tenant_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Retrieves full configuration and capacity details of a specific chatbot."""
    await set_tenant_context(db, tenant_id)
    bot = await support_service.get_chatbot_by_id(db, tenant_id, chatbot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Chatbot not found")
    return bot


@router.patch("/dashboard/chatbots/{chatbot_id}", response_model=ChatbotResponse)
async def update_chatbot(
    chatbot_id: uuid.UUID,
    request: ChatbotUpdateRequest,
    tenant_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Updates chatbot profile, persona, instructions, capacity, or slug."""
    await set_tenant_context(db, tenant_id)
    try:
        return await support_service.update_chatbot(db, tenant_id, chatbot_id, request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/dashboard/chatbots/{chatbot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chatbot(
    chatbot_id: uuid.UUID,
    tenant_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Removes a chatbot instance."""
    await set_tenant_context(db, tenant_id)
    deleted = await support_service.delete_chatbot(db, tenant_id, chatbot_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Chatbot not found")


@router.post("/dashboard/chatbots/{chatbot_id}/activate", response_model=ChatbotResponse)
async def activate_chatbot(
    chatbot_id: uuid.UUID,
    tenant_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Activates chatbot into the live customer auto-assignment pool (ON)."""
    await set_tenant_context(db, tenant_id)
    try:
        return await support_service.activate_chatbot(db, tenant_id, chatbot_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/dashboard/chatbots/{chatbot_id}/deactivate", response_model=ChatbotResponse)
async def deactivate_chatbot(
    chatbot_id: uuid.UUID,
    mode: str = Query("immediate", pattern="^(immediate|drain)$"),
    tenant_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Deactivates chatbot from receiving new conversation assignments (OFF)."""
    await set_tenant_context(db, tenant_id)
    try:
        return await support_service.deactivate_chatbot(db, tenant_id, chatbot_id, mode=mode)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/dashboard/chatbots/{chatbot_id}/live-url", response_model=ChatbotURLResponse)
async def update_chatbot_url(
    chatbot_id: uuid.UUID,
    request: ChatbotURLUpdateRequest,
    tenant_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Updates standalone live chat URL slug."""
    await set_tenant_context(db, tenant_id)
    try:
        return await support_service.update_chatbot_url(db, tenant_id, chatbot_id, request.slug)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==========================================
# Standalone Public Live Chat Gateway
# ==========================================

@router.get("/public/live/{slug}", response_model=PublicChatbotInfoResponse)
async def get_public_live_info(
    slug: str,
    db: AsyncSession = Depends(get_db)
):
    """Resolves public chatbot branding and status for visitor rendering."""
    try:
        return await support_service.get_public_live_info(db, slug)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/public/live/{slug}/session", response_model=PublicLiveSessionResponse)
async def init_public_live_session(
    slug: str,
    request: PublicLiveSessionRequest,
    db: AsyncSession = Depends(get_db)
):
    """Creates an anonymous visitor session token for standalone live chat."""
    try:
        return await support_service.initialize_public_live_session(
            db=db,
            slug=slug,
            visitor_fingerprint=request.visitor_fingerprint
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/public/live/{slug}/messages", response_model=PublicLiveMessageResponse)
async def send_public_live_message(
    slug: str,
    request: PublicLiveMessageRequest,
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db)
):
    """Processes customer turn: auto-assignment scheduler, sticky context, RAG & Gemini inference."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid session bearer token")

    token = authorization.split(" ", 1)[1]
    claims = decode_visitor_session_token(token)
    if not claims:
        raise HTTPException(status_code=401, detail="Session expired or invalid")

    tenant_id = uuid.UUID(claims["tenant_id"])
    conversation_id = uuid.UUID(claims["session_id"])
    await set_tenant_context(db, tenant_id)

    try:
        return await support_service.process_live_chat_turn(
            db=db,
            slug=slug,
            conversation_id=conversation_id,
            message_text=request.message
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/public/live/{slug}/messages", response_model=List[ChatMessageResponse])
async def get_public_live_messages(
    slug: str,
    conversation_id: uuid.UUID = Query(...),
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db)
):
    """Retrieves message history for the active visitor session."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid session bearer token")

    stmt = select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.asc())
    msgs = (await db.execute(stmt)).scalars().all()

    return [
        ChatMessageResponse(
            message_id=m.id,
            conversation_id=m.conversation_id,
            sender_type=m.sender_type,
            content=m.content,
            is_escalated=False,
            tokens_consumed=m.tokens_consumed,
            created_at=m.created_at
        )
        for m in msgs
    ]


# ==========================================
# Legacy Widget & Embed Endpoints
# ==========================================

@router.get("/support/widget/config", response_model=WidgetConfigResponse)
async def get_widget_config(
    public_key: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Fetches widget branding and welcome message for embed script mounting."""
    stmt = select(WidgetInstallation).where(WidgetInstallation.public_key == public_key)
    widget = (await db.execute(stmt)).scalar_one_or_none()
    if not widget:
        raise HTTPException(status_code=404, detail="Widget not found")

    tenant_stmt = select(Tenant).where(Tenant.id == widget.tenant_id)
    tenant = (await db.execute(tenant_stmt)).scalar_one()

    setting_stmt = select(TenantSetting).where(TenantSetting.tenant_id == widget.tenant_id)
    setting = (await db.execute(setting_stmt)).scalar_one_or_none()

    return WidgetConfigResponse(
        public_key=widget.public_key,
        tenant_name=tenant.name,
        theme_color=widget.theme_color,
        allowed_origins=widget.allowed_origins or [],
        welcome_message=setting.welcome_message if setting else "Hello! How can I assist you?"
    )


@router.get("/support/widget/tenant")
async def get_tenant_widget(
    tenant_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Retrieves or provisions the widget installation and keys for a tenant."""
    widget = await support_service.get_or_create_widget(db, tenant_id)
    return {
        "tenant_id": str(widget.tenant_id),
        "public_key": widget.public_key,
        "theme_color": widget.theme_color,
        "allowed_origins": widget.allowed_origins
    }


@router.post("/chat/session", response_model=SessionTokenResponse)
async def init_chat_session(
    request: SessionInitRequest,
    x_widget_key: str = Header(...),
    db: AsyncSession = Depends(get_db)
):
    """Public gateway endpoint issuing signed visitor chat session JWTs."""
    try:
        return await support_service.initialize_visitor_session(
            db=db,
            public_key=x_widget_key,
            origin=request.origin,
            visitor_fingerprint=request.visitor_fingerprint
        )
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/chat/message", response_model=ChatMessageResponse)
async def send_customer_message(
    request: ChatMessageRequest,
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db)
):
    """Processes customer turn: hybrid RAG retrieval, Gemini inference, unknown escalation, and usage recording."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid session bearer token")

    token = authorization.split(" ", 1)[1]
    claims = decode_visitor_session_token(token)
    if not claims:
        raise HTTPException(status_code=401, detail="Session expired or invalid")

    tenant_id = uuid.UUID(claims["tenant_id"])
    conversation_id = uuid.UUID(claims["session_id"])

    await set_tenant_context(db, tenant_id)

    return await support_service.process_chat_message(
        db=db,
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        message_text=request.message
    )


@router.get("/support/agents", response_model=List[AIAgentResponse])
async def list_agents(
    tenant_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Lists legacy company logical AI agents."""
    await set_tenant_context(db, tenant_id)
    stmt = select(AIAgent).where(AIAgent.tenant_id == tenant_id)
    agents = (await db.execute(stmt)).scalars().all()

    return [
        AIAgentResponse(
            id=a.id,
            name=a.name,
            role=a.role,
            status=a.status,
            active_chats=a.active_chats,
            max_concurrency=a.max_concurrency
        )
        for a in agents
    ]
