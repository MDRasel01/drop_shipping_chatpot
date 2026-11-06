import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.core.database import get_db, set_tenant_context
from app.modules.notifications.models import Notification

router = APIRouter(prefix="/notifications", tags=["In-App Notifications"])


@router.get("/inbox")
async def get_inbox(
    tenant_id: uuid.UUID = Query(...),
    recipient_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Retrieves in-app notification feed and unread badge count."""
    await set_tenant_context(db, tenant_id)
    stmt = (
        select(Notification)
        .where(Notification.tenant_id == tenant_id, Notification.recipient_id == recipient_id)
        .order_by(Notification.created_at.desc())
        .limit(50)
    )
    records = (await db.execute(stmt)).scalars().all()
    unread_count = sum(1 for r in records if r.read_at is None)

    return {
        "items": [
            {
                "id": r.id,
                "category": r.category,
                "severity": r.severity,
                "title": r.title,
                "body_text": r.body_text,
                "action_url": r.action_url,
                "created_at": r.created_at,
                "read_at": r.read_at
            }
            for r in records
        ],
        "unread_count": unread_count
    }


@router.patch("/{notification_id}/read")
async def mark_as_read(
    notification_id: uuid.UUID,
    tenant_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Marks an in-app notification as read."""
    await set_tenant_context(db, tenant_id)
    stmt = (
        update(Notification)
        .where(Notification.tenant_id == tenant_id, Notification.id == notification_id)
        .values(read_at=datetime.now())
    )
    await db.execute(stmt)
    await db.flush()
    return {"status": "SUCCESS"}
