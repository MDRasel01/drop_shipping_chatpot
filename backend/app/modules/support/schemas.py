import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class WidgetConfigResponse(BaseModel):
    public_key: str
    tenant_name: str
    theme_color: str
    allowed_origins: List[str]
    welcome_message: str


class SessionInitRequest(BaseModel):
    origin: str
    visitor_fingerprint: Optional[str] = None


class SessionTokenResponse(BaseModel):
    session_token: str
    session_id: uuid.UUID
    tenant_id: uuid.UUID
    visitor_id: str
    welcome_message: str


class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


class ChatMessageResponse(BaseModel):
    message_id: uuid.UUID
    conversation_id: uuid.UUID
    sender_type: str
    content: str
    is_escalated: bool = False
    tokens_consumed: int = 0
    created_at: datetime


class AIAgentResponse(BaseModel):
    id: uuid.UUID
    name: str
    role: str
    status: str
    active_chats: int
    max_concurrency: int

