import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


class WorkflowExecution(Base):
    __tablename__ = "workflow_executions"

    workflow_id = Column(String(64), primary_key=True)
    saga_type = Column(String(100), nullable=False, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    correlation_id = Column(String(64), nullable=False, index=True)
    status = Column(String(30), nullable=False, default="PENDING")  # PENDING, RUNNING, COMPLETED, COMPENSATED, FAILED
    current_step = Column(Integer, nullable=False, default=0)
    total_steps = Column(Integer, nullable=False, default=0)
    input_payload = Column(JSONB, nullable=False, default=dict)
    output_result = Column(JSONB, nullable=False, default=dict)
    error_summary = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)


class EventOutbox(Base):
    __tablename__ = "event_outbox"

    event_id = Column(String(64), primary_key=True)
    event_type = Column(String(100), nullable=False, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    payload = Column(JSONB, nullable=False, default=dict)
    status = Column(String(30), nullable=False, default="PENDING")  # PENDING, PUBLISHED, FAILED
    retry_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

