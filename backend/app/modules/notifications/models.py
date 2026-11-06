import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.core.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    recipient_id = Column(String(100), nullable=False, index=True)
    category = Column(String(50), nullable=False)  # AUTH, BILLING, SUPPORT, KNOWLEDGE, SYSTEM
    severity = Column(String(20), nullable=False, default="INFO")  # INFO, SUCCESS, WARNING, CRITICAL
    channel = Column(String(30), nullable=False, default="IN_APP")  # EMAIL, IN_APP, WEBSOCKET, WEBHOOK
    title = Column(String(255), nullable=False)
    body_text = Column(Text, nullable=False)
    action_url = Column(String(500), nullable=True)
    status = Column(String(30), nullable=False, default="DELIVERED", index=True)  # QUEUED, SENT, DELIVERED, READ
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    read_at = Column(DateTime(timezone=True), nullable=True)


class NotificationTemplate(Base):
    __tablename__ = "notification_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_code = Column(String(100), nullable=False, index=True)
    language = Column(String(10), nullable=False, default="en")
    channel = Column(String(30), nullable=False, default="EMAIL")
    subject = Column(String(255), nullable=True)
    body_template = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

