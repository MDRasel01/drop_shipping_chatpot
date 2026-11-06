import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

from app.modules.support.models import (
    Chatbot,
    ChatbotCapacity,
    ChatbotReservation,
    ChatbotAssignment,
    Conversation
)

logger = logging.getLogger("chatbot_scheduler")


class ChatbotSchedulerService:
    """Least-Loaded Multi-Chatbot Scheduler with Atomic Concurrency Reservations."""

    async def get_assigned_chatbot(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID
    ) -> Optional[Chatbot]:
        """Checks for existing sticky chatbot assignment for conversation continuity."""
        conv_stmt = select(Conversation).where(Conversation.id == conversation_id)
        conv = (await db.execute(conv_stmt)).scalar_one_or_none()
        if not conv or not conv.chatbot_id:
            return None

        bot_stmt = select(Chatbot).where(Chatbot.id == conv.chatbot_id)
        return (await db.execute(bot_stmt)).scalar_one_or_none()

    async def find_and_reserve_chatbot(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        conversation_id: Optional[uuid.UUID] = None
    ) -> Tuple[Optional[Chatbot], Optional[str], str]:
        """
        Selects the least-loaded eligible chatbot for the tenant and places an atomic 30s reservation.
        Returns: (chatbot, reservation_token, status_code)
        Status codes:
          - ASSIGNED: Eligible chatbot found and reservation placed.
          - NO_ACTIVE_CHATBOTS: No chatbots currently turned ON by admin.
          - ALL_CHATBOTS_BUSY: Active chatbots exist, but all are at full capacity.
        """
        # First reconcile any stale expired reservations
        await self.reconcile_expired_reservations(db, tenant_id)

        # 1. Fetch all active chatbots for tenant
        stmt = (
            select(Chatbot, ChatbotCapacity)
            .join(ChatbotCapacity, Chatbot.id == ChatbotCapacity.chatbot_id)
            .where(
                Chatbot.tenant_id == tenant_id,
                Chatbot.is_active == True,
                Chatbot.status.in_(["active", "busy"])
            )
        )
        results = (await db.execute(stmt)).all()

        if not results:
            logger.info(f"Tenant {tenant_id} has no active chatbots in pool.")
            return None, None, "NO_ACTIVE_CHATBOTS"

        # 2. Filter eligible candidates where (active + reserved) < max_capacity
        candidates = []
        for bot, cap in results:
            current_load = cap.active_conversations + cap.reserved_capacity
            if current_load < cap.max_capacity and bot.status != "draining":
                ratio = current_load / max(1, cap.max_capacity)
                candidates.append((ratio, cap.active_conversations, bot.created_at, bot, cap))

        if not candidates:
            logger.info(f"All active chatbots for tenant {tenant_id} are currently at max capacity.")
            return None, None, "ALL_CHATBOTS_BUSY"

        # 3. Least-Loaded selection with deterministic tie-breaker
        # Sort by: ratio ASC, active_conversations ASC, created_at ASC
        candidates.sort(key=lambda c: (c[0], c[1], c[2]))
        best_candidate = candidates[0]
        selected_bot = best_candidate[3]
        selected_cap = best_candidate[4]

        # 4. Atomic reservation lock
        res_token = f"res_{uuid.uuid4().hex}"
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=30)

        reservation = ChatbotReservation(
            reservation_token=res_token,
            chatbot_id=selected_bot.id,
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            expires_at=expires_at,
            status="PENDING"
        )
        db.add(reservation)

        # Increment reserved capacity
        selected_cap.reserved_capacity += 1
        if (selected_cap.active_conversations + selected_cap.reserved_capacity) >= selected_cap.max_capacity:
            selected_bot.status = "busy"

        await db.flush()
        logger.info(f"Reserved slot on chatbot '{selected_bot.name}' (Token: {res_token})")
        return selected_bot, res_token, "ASSIGNED"

    async def commit_assignment(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        conversation_id: uuid.UUID,
        chatbot_id: uuid.UUID,
        reservation_token: Optional[str] = None
    ) -> ChatbotAssignment:
        """Commits reservation into a permanent sticky conversation assignment."""
        # 1. Clear reservation token if provided
        if reservation_token:
            res_stmt = select(ChatbotReservation).where(
                ChatbotReservation.reservation_token == reservation_token
            )
            res = (await db.execute(res_stmt)).scalar_one_or_none()
            if res:
                res.status = "COMMITTED"

        # 2. Adjust capacity
        cap_stmt = select(ChatbotCapacity).where(ChatbotCapacity.chatbot_id == chatbot_id)
        cap = (await db.execute(cap_stmt)).scalar_one_or_none()
        if cap:
            if reservation_token and cap.reserved_capacity > 0:
                cap.reserved_capacity -= 1
            cap.active_conversations += 1

            bot_stmt = select(Chatbot).where(Chatbot.id == chatbot_id)
            bot = (await db.execute(bot_stmt)).scalar_one_or_none()
            if bot and (cap.active_conversations + cap.reserved_capacity) >= cap.max_capacity:
                bot.status = "busy"

        # 3. Create assignment record
        assignment = ChatbotAssignment(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            chatbot_id=chatbot_id,
            tenant_id=tenant_id,
            status="active",
            assigned_at=datetime.now(timezone.utc)
        )
        db.add(assignment)

        # 4. Update Conversation pointer
        conv_stmt = select(Conversation).where(Conversation.id == conversation_id)
        conv = (await db.execute(conv_stmt)).scalar_one_or_none()
        if conv:
            conv.chatbot_id = chatbot_id

        await db.flush()
        logger.info(f"Committed assignment: Conversation {conversation_id} -> Chatbot {chatbot_id}")
        return assignment

    async def release_capacity(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        conversation_id: uuid.UUID
    ) -> bool:
        """Releases chatbot conversation capacity on conversation completion."""
        stmt = select(ChatbotAssignment).where(
            ChatbotAssignment.conversation_id == conversation_id,
            ChatbotAssignment.status == "active"
        )
        assignment = (await db.execute(stmt)).scalar_one_or_none()
        if not assignment:
            return False

        assignment.status = "completed"
        assignment.released_at = datetime.now(timezone.utc)

        # Decrement capacity
        cap_stmt = select(ChatbotCapacity).where(ChatbotCapacity.chatbot_id == assignment.chatbot_id)
        cap = (await db.execute(cap_stmt)).scalar_one_or_none()
        if cap:
            cap.active_conversations = max(0, cap.active_conversations - 1)

            # Check if chatbot can return from 'busy' to 'active'
            bot_stmt = select(Chatbot).where(Chatbot.id == assignment.chatbot_id)
            bot = (await db.execute(bot_stmt)).scalar_one_or_none()
            if bot and bot.is_active and bot.status == "busy":
                if (cap.active_conversations + cap.reserved_capacity) < cap.max_capacity:
                    bot.status = "active"

        await db.flush()
        logger.info(f"Released capacity for conversation {conversation_id} on chatbot {assignment.chatbot_id}")
        return True

    async def reconcile_expired_reservations(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID
    ) -> int:
        """Recovers capacity from abandoned or expired reservation locks."""
        now = datetime.now(timezone.utc)
        stmt = select(ChatbotReservation).where(
            ChatbotReservation.tenant_id == tenant_id,
            ChatbotReservation.status == "PENDING",
            ChatbotReservation.expires_at < now
        )
        expired = (await db.execute(stmt)).scalars().all()
        count = 0

        for r in expired:
            r.status = "EXPIRED"
            cap_stmt = select(ChatbotCapacity).where(ChatbotCapacity.chatbot_id == r.chatbot_id)
            cap = (await db.execute(cap_stmt)).scalar_one_or_none()
            if cap and cap.reserved_capacity > 0:
                cap.reserved_capacity -= 1
            count += 1

        if count > 0:
            await db.flush()
            logger.info(f"Reconciled {count} expired reservation locks for tenant {tenant_id}")
        return count


chatbot_scheduler = ChatbotSchedulerService()

