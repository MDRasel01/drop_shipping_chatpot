import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Uuid, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base


class AIAgent(Base):
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


class WidgetInstallation(Base):
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
    __tablename__ = "conversations"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id = Column(Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    visitor_id = Column(String(100), nullable=False, index=True)
    agent_id = Column(Uuid, ForeignKey("ai_agents.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(30), nullable=False, default="active", index=True)  # active, closed, escalated
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    conversation_id = Column(Uuid, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_type = Column(String(30), nullable=False)  # visitor, agent, admin
    content = Column(Text, nullable=False)
    tokens_consumed = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    conversation = relationship("Conversation", back_populates="messages")

