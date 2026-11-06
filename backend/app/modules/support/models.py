import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Boolean, Text, DateTime, ForeignKey, Uuid, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base


class AIAgent(Base):
    """Legacy single agent model for backward compatibility."""
    __tablename__ = "ai_agents"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id = Column(Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    role = Column(String(100), nullable=False, default="Customer Support Representative")
    status = Column(String(30), nullable=False, default="online", index=True)  # online, busy, offline
    active_chats = Column(Integer, nullable=False, default=0)
    max_concurrency = Column(Integer, nullable=False, default=20)
    system_instructions = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Chatbot(Base):
    """Primary Multi-Chatbot identity, persona, instructions, and lifecycle state."""
    __tablename__ = "chatbots"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id = Column(Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    avatar_url = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    welcome_message = Column(Text, nullable=False, default="Hello! How can I assist you today?")
    system_instructions = Column(Text, nullable=True)
    ai_config = Column(JSON, nullable=False, default=lambda: {"model": "gemini-1.5-flash", "temperature": 0.7})
    status = Column(String(30), nullable=False, default="inactive", index=True)  # draft, inactive, active, busy, draining, degraded, error
    is_active = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Child relationships
    capacity = relationship("ChatbotCapacity", back_populates="chatbot", uselist=False, cascade="all, delete-orphan")
    live_url = relationship("ChatbotURL", back_populates="chatbot", uselist=False, cascade="all, delete-orphan")
    widget = relationship("ChatbotWidget", back_populates="chatbot", uselist=False, cascade="all, delete-orphan")
    assignments = relationship("ChatbotAssignment", back_populates="chatbot", cascade="all, delete-orphan")


class ChatbotCapacity(Base):
    """Tracks real-time conversation capacity, concurrency, and worker health."""
    __tablename__ = "chatbot_capacity"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    chatbot_id = Column(Uuid, ForeignKey("chatbots.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    tenant_id = Column(Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    max_capacity = Column(Integer, nullable=False, default=5)
    active_conversations = Column(Integer, nullable=False, default=0)
    reserved_capacity = Column(Integer, nullable=False, default=0)
    last_heartbeat = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    chatbot = relationship("Chatbot", back_populates="capacity")


class ChatbotURL(Base):
    """Standalone Live Chat URL configuration with global or tenant-scoped uniqueness."""
    __tablename__ = "chatbot_urls"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    chatbot_id = Column(Uuid, ForeignKey("chatbots.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    tenant_id = Column(Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    is_published = Column(Boolean, nullable=False, default=False, index=True)
    status = Column(String(30), nullable=False, default="published")
    redirect_slug = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    chatbot = relationship("Chatbot", back_populates="live_url")


class ChatbotWidget(Base):
    """Dedicated embeddable widget credentials for a specific chatbot instance."""
    __tablename__ = "chatbot_widgets"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    chatbot_id = Column(Uuid, ForeignKey("chatbots.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    tenant_id = Column(Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    public_key = Column(String(64), unique=True, nullable=False, index=True)
    secret_key = Column(String(64), nullable=False)
    theme_color = Column(String(20), nullable=False, default="#2563eb")
    allowed_origins = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    chatbot = relationship("Chatbot", back_populates="widget")


class ChatbotKnowledgeSource(Base):
    """Maps custom knowledge instructions or collections to a specific chatbot."""
    __tablename__ = "chatbot_knowledge_sources"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    chatbot_id = Column(Uuid, ForeignKey("chatbots.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    source_type = Column(String(50), nullable=False, default="ALL_TENANT_KNOWLEDGE")
    source_reference_id = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class ChatbotStatusLog(Base):
    """Audit log for ON/OFF activation, deactivation, and capacity state changes."""
    __tablename__ = "chatbot_status_logs"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    chatbot_id = Column(Uuid, ForeignKey("chatbots.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    old_status = Column(String(30), nullable=False)
    new_status = Column(String(30), nullable=False)
    changed_by_user_id = Column(Uuid, nullable=True)
    reason = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class ChatbotAssignment(Base):
    """Binds an ongoing conversation to a specific chatbot instance with lifecycle tracking."""
    __tablename__ = "chatbot_assignments"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    conversation_id = Column(Uuid, ForeignKey("conversations.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    chatbot_id = Column(Uuid, ForeignKey("chatbots.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(30), nullable=False, default="active")  # active, completed, transferred, drained
    assigned_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    released_at = Column(DateTime(timezone=True), nullable=True)

    chatbot = relationship("Chatbot", back_populates="assignments")


class ChatbotReservation(Base):
    """Atomic concurrency reservation lock preventing race conditions during assignment."""
    __tablename__ = "chatbot_reservations"

    reservation_token = Column(String(64), primary_key=True)
    chatbot_id = Column(Uuid, ForeignKey("chatbots.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(Uuid, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(20), nullable=False, default="PENDING")  # PENDING, COMMITTED, EXPIRED


class ChatbotSession(Base):
    """Signed anonymous visitor live chat session tokens."""
    __tablename__ = "chatbot_sessions"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    session_token = Column(String(255), unique=True, nullable=False, index=True)
    chatbot_id = Column(Uuid, ForeignKey("chatbots.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    visitor_fingerprint = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), nullable=False)


class WidgetInstallation(Base):
    """Global tenant-level widget configuration for backward compatibility."""
    __tablename__ = "widget_installations"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id = Column(Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    public_key = Column(String(64), unique=True, nullable=False, index=True)
    secret_key = Column(String(64), nullable=False)
    theme_color = Column(String(20), nullable=False, default="#2563eb")
    allowed_origins = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Conversation(Base):
    """Ongoing customer interaction thread."""
    __tablename__ = "conversations"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id = Column(Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    visitor_id = Column(String(100), nullable=False, index=True)
    agent_id = Column(Uuid, ForeignKey("ai_agents.id", ondelete="SET NULL"), nullable=True)
    chatbot_id = Column(Uuid, ForeignKey("chatbots.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(30), nullable=False, default="active", index=True)  # active, closed, escalated
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")


class Message(Base):
    """Individual visitor or chatbot message turn."""
    __tablename__ = "messages"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    conversation_id = Column(Uuid, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_type = Column(String(30), nullable=False)  # visitor, agent, admin
    content = Column(Text, nullable=False)
    tokens_consumed = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    conversation = relationship("Conversation", back_populates="messages")
