import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
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
    assigned_chatbot_name: Optional[str] = None
    assigned_chatbot_avatar: Optional[str] = None


class AIAgentResponse(BaseModel):
    id: uuid.UUID
    name: str
    role: str
    status: str
    active_chats: int
    max_concurrency: int


# --- Multi-Chatbot Management Schemas ---

class ChatbotCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    avatar_url: Optional[str] = None
    description: Optional[str] = None
    welcome_message: str = Field("Hello! How can I assist you today?", max_length=1000)
    system_instructions: Optional[str] = None
    max_capacity: int = Field(5, ge=1, le=100)
    slug: Optional[str] = None
    ai_config: Optional[Dict[str, Any]] = None


class ChatbotUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    avatar_url: Optional[str] = None
    description: Optional[str] = None
    welcome_message: Optional[str] = None
    system_instructions: Optional[str] = None
    max_capacity: Optional[int] = Field(None, ge=1, le=100)
    slug: Optional[str] = None
    ai_config: Optional[Dict[str, Any]] = None


class ChatbotResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    avatar_url: Optional[str] = None
    description: Optional[str] = None
    welcome_message: str
    system_instructions: Optional[str] = None
    status: str
    is_active: bool
    max_capacity: int
    active_conversations: int
    available_capacity: int
    slug: Optional[str] = None
    live_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ChatbotURLResponse(BaseModel):
    chatbot_id: uuid.UUID
    slug: str
    full_url: str
    is_published: bool
    status: str


class ChatbotURLUpdateRequest(BaseModel):
    slug: str = Field(..., min_length=3, max_length=64)


# --- Standalone Public Live Chat Schemas ---

class PublicChatbotInfoResponse(BaseModel):
    chatbot_name: str
    avatar_url: Optional[str] = None
    welcome_message: str
    status: str  # online, busy, offline
    theme_color: str = "#2563eb"
    slug: str


class PublicLiveSessionRequest(BaseModel):
    visitor_fingerprint: Optional[str] = None
    origin: Optional[str] = None


class PublicLiveSessionResponse(BaseModel):
    session_token: str
    conversation_id: uuid.UUID
    chatbot_name: str
    avatar_url: Optional[str] = None
    welcome_message: str
    status: str


class PublicLiveMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


class PublicLiveMessageResponse(BaseModel):
    message_id: uuid.UUID
    conversation_id: uuid.UUID
    sender_type: str
    content: str
    assigned_chatbot_name: Optional[str] = None
    assigned_chatbot_avatar: Optional[str] = None
    is_escalated: bool = False
    tokens_consumed: int = 0
    created_at: datetime
    status: str = "DELIVERED"  # DELIVERED, WAITING_IN_QUEUE, FALLBACK
