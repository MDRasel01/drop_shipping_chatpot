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
    AIAgentResponse
)
from app.modules.support.models import AIAgent, WidgetInstallation
from app.modules.support.service import support_service
from app.modules.saas.models import Tenant, TenantSetting

router = APIRouter(tags=["AI Support & Public Chat Widget"])


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
    """Lists company logical AI agents and their live chat concurrency."""
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

