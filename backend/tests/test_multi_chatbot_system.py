import uuid
import asyncio
import pytest
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import select

from app.core.database import Base
from app.modules.support.models import (
    Chatbot,
    ChatbotCapacity,
    ChatbotURL,
    ChatbotWidget,
    Conversation
)
from app.modules.support.schemas import (
    ChatbotCreateRequest,
    ChatbotUpdateRequest,
    ChatbotURLUpdateRequest
)
from app.modules.support.service import support_service
from app.modules.support.scheduler import chatbot_scheduler
from app.modules.saas.models import Tenant, Subscription, SubscriptionPlan


async def setup_test_context():
    engine = create_async_engine(
        f"sqlite+aiosqlite:///:memory:?cache=shared",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    session = session_factory()

    # Create base subscription plan and tenant
    plan = SubscriptionPlan(
        id=uuid.uuid4(),
        code="Starter",
        name="Starter Plan",
        max_messages_monthly=10000,
        max_ai_agents=3,  # Limit is 3 chatbots
        price_cents=0,
        is_active=True
    )
    session.add(plan)

    tenant = Tenant(
        id=uuid.uuid4(),
        name="Test Corp",
        slug="test-corp",
        status="active",
        subscription_tier="Starter"
    )
    session.add(tenant)

    sub = Subscription(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        plan_code="Starter",
        status="active"
    )
    session.add(sub)
    await session.commit()

    return engine, session, tenant.id


def test_acceptance_02_04_create_multiple_chatbots_default_inactive():
    """Verifies Admin can create multiple chatbots and they are INACTIVE by default (Acceptance 02 & 04)."""
    async def _test():
        engine, db, tenant_id = await setup_test_context()
        try:
            bot1 = await support_service.create_chatbot(
                db,
                tenant_id,
                ChatbotCreateRequest(name="Maya - Support", max_capacity=5, slug="maya-support")
            )
            assert bot1.name == "Maya - Support"
            assert bot1.is_active is False
            assert bot1.status == "inactive"
            assert bot1.max_capacity == 5
            assert bot1.slug == "maya-support"

            bot2 = await support_service.create_chatbot(
                db,
                tenant_id,
                ChatbotCreateRequest(name="Alex - Sales", max_capacity=3, slug="alex-sales")
            )
            assert bot2.name == "Alex - Sales"
            assert bot2.is_active is False
            assert bot2.status == "inactive"
        finally:
            await db.close()
            await engine.dispose()

    asyncio.run(_test())


def test_acceptance_03_profile_and_avatar_customization():
    """Verifies Chatbot name, avatar, instructions, and capacity can be updated (Acceptance 03)."""
    async def _test():
        engine, db, tenant_id = await setup_test_context()
        try:
            bot = await support_service.create_chatbot(
                db,
                tenant_id,
                ChatbotCreateRequest(name="Bot 01", max_capacity=5)
            )

            updated = await support_service.update_chatbot(
                db,
                tenant_id,
                bot.id,
                ChatbotUpdateRequest(
                    name="Elena - Senior Specialist",
                    avatar_url="https://example.com/elena.png",
                    welcome_message="Welcome! I am Elena.",
                    max_capacity=10
                )
            )
            assert updated.name == "Elena - Senior Specialist"
            assert updated.avatar_url == "https://example.com/elena.png"
            assert updated.welcome_message == "Welcome! I am Elena."
            assert updated.max_capacity == 10
        finally:
            await db.close()
            await engine.dispose()

    asyncio.run(_test())


def test_acceptance_05_06_on_off_toggle_lifecycle():
    """Verifies ON activates into pool and OFF removes from pool (Acceptance 05 & 06)."""
    async def _test():
        engine, db, tenant_id = await setup_test_context()
        try:
            bot = await support_service.create_chatbot(
                db,
                tenant_id,
                ChatbotCreateRequest(name="Support Bot", max_capacity=5)
            )
            assert bot.is_active is False

            # Turn ON
            activated = await support_service.activate_chatbot(db, tenant_id, bot.id)
            assert activated.is_active is True
            assert activated.status == "active"

            # Turn OFF (immediate)
            deactivated = await support_service.deactivate_chatbot(db, tenant_id, bot.id, mode="immediate")
            assert deactivated.is_active is False
            assert deactivated.status == "inactive"

            # Turn OFF (drain mode)
            draining = await support_service.deactivate_chatbot(db, tenant_id, bot.id, mode="drain")
            assert draining.is_active is False
            assert draining.status == "draining"
        finally:
            await db.close()
            await engine.dispose()

    asyncio.run(_test())


def test_acceptance_07_08_standalone_live_url_and_slug_edit():
    """Verifies Standalone Live URL generation and unique slug updates (Acceptance 07 & 08)."""
    async def _test():
        engine, db, tenant_id = await setup_test_context()
        try:
            bot = await support_service.create_chatbot(
                db,
                tenant_id,
                ChatbotCreateRequest(name="Help Bot", slug="help-bot-1")
            )
            assert bot.slug == "help-bot-1"

            # Update slug
            url_resp = await support_service.update_chatbot_url(
                db,
                tenant_id,
                bot.id,
                "customer-care"
            )
            assert url_resp.slug == "customer-care"
            assert "/live/customer-care" in url_resp.full_url
        finally:
            await db.close()
            await engine.dispose()

    asyncio.run(_test())


def test_acceptance_09_public_live_chat_resolution():
    """Verifies public live URL resolves anonymous info without exposing tenant secrets (Acceptance 09)."""
    async def _test():
        engine, db, tenant_id = await setup_test_context()
        try:
            bot = await support_service.create_chatbot(
                db,
                tenant_id,
                ChatbotCreateRequest(
                    name="Public Assistant",
                    slug="public-assistant",
                    welcome_message="Welcome to public support!"
                )
            )
            await support_service.activate_chatbot(db, tenant_id, bot.id)

            public_info = await support_service.get_public_live_info(db, "public-assistant")
            assert public_info.chatbot_name == "Public Assistant"
            assert public_info.welcome_message == "Welcome to public support!"
            assert public_info.status == "online"
            assert public_info.slug == "public-assistant"
        finally:
            await db.close()
            await engine.dispose()

    asyncio.run(_test())


def test_acceptance_11_least_loaded_scheduler_selection():
    """Verifies Scheduler picks the least-loaded available chatbot from active pool (Acceptance 11)."""
    async def _test():
        engine, db, tenant_id = await setup_test_context()
        try:
            # Create Bot A (Busy: 4/5 load)
            botA = await support_service.create_chatbot(db, tenant_id, ChatbotCreateRequest(name="Bot A", max_capacity=5))
            await support_service.activate_chatbot(db, tenant_id, botA.id)

            # Create Bot B (Light: 1/5 load)
            botB = await support_service.create_chatbot(db, tenant_id, ChatbotCreateRequest(name="Bot B", max_capacity=5))
            await support_service.activate_chatbot(db, tenant_id, botB.id)

            # Artificially simulate load
            capA = (await db.execute(select(ChatbotCapacity).where(ChatbotCapacity.chatbot_id == botA.id))).scalar_one()
            capA.active_conversations = 4

            capB = (await db.execute(select(ChatbotCapacity).where(ChatbotCapacity.chatbot_id == botB.id))).scalar_one()
            capB.active_conversations = 1
            await db.commit()

            # Scheduler should select Bot B (least loaded)
            selected, token, status = await chatbot_scheduler.find_and_reserve_chatbot(db, tenant_id)
            assert status == "ASSIGNED"
            assert selected.id == botB.id
            assert selected.name == "Bot B"
            assert token is not None
        finally:
            await db.close()
            await engine.dispose()

    asyncio.run(_test())


def test_acceptance_13_all_chatbots_busy_waiting_queue():
    """Verifies Scheduler returns ALL_CHATBOTS_BUSY when all active chatbots reach max capacity (Acceptance 13)."""
    async def _test():
        engine, db, tenant_id = await setup_test_context()
        try:
            bot = await support_service.create_chatbot(db, tenant_id, ChatbotCreateRequest(name="Solo Bot", max_capacity=2))
            await support_service.activate_chatbot(db, tenant_id, bot.id)

            # Fill capacity
            cap = (await db.execute(select(ChatbotCapacity).where(ChatbotCapacity.chatbot_id == bot.id))).scalar_one()
            cap.active_conversations = 2
            bot.status = "busy"
            await db.commit()

            selected, token, status = await chatbot_scheduler.find_and_reserve_chatbot(db, tenant_id)
            assert selected is None
            assert token is None
            assert status == "ALL_CHATBOTS_BUSY"
        finally:
            await db.close()
            await engine.dispose()

    asyncio.run(_test())


def test_acceptance_14_conversation_continuity_sticky_assignment():
    """Verifies that subsequent messages maintain the same assigned chatbot (Acceptance 14)."""
    async def _test():
        engine, db, tenant_id = await setup_test_context()
        try:
            bot = await support_service.create_chatbot(db, tenant_id, ChatbotCreateRequest(name="Sticky Bot", max_capacity=5))
            await support_service.activate_chatbot(db, tenant_id, bot.id)

            conv_id = uuid.uuid4()
            conv = Conversation(
                id=conv_id,
                tenant_id=tenant_id,
                visitor_id="visitor_test_001",
                chatbot_id=None,
                status="active"
            )
            db.add(conv)
            await db.commit()

            # 1. First message assignment
            selected, token, status = await chatbot_scheduler.find_and_reserve_chatbot(db, tenant_id, conv_id)
            await chatbot_scheduler.commit_assignment(db, tenant_id, conv_id, selected.id, token)

            # 2. Subsequent message continuity check
            sticky = await chatbot_scheduler.get_assigned_chatbot(db, conv_id)
            assert sticky is not None
            assert sticky.id == bot.id
            assert sticky.name == "Sticky Bot"
        finally:
            await db.close()
            await engine.dispose()

    asyncio.run(_test())


def test_acceptance_15_atomic_capacity_release():
    """Verifies conversation capacity is atomically reserved and released upon completion (Acceptance 15)."""
    async def _test():
        engine, db, tenant_id = await setup_test_context()
        try:
            bot = await support_service.create_chatbot(db, tenant_id, ChatbotCreateRequest(name="Cap Bot", max_capacity=5))
            await support_service.activate_chatbot(db, tenant_id, bot.id)

            conv_id = uuid.uuid4()
            conv = Conversation(
                id=conv_id,
                tenant_id=tenant_id,
                visitor_id="vis_cap_test",
                status="active"
            )
            db.add(conv)
            await db.commit()

            selected, token, status = await chatbot_scheduler.find_and_reserve_chatbot(db, tenant_id, conv_id)
            await chatbot_scheduler.commit_assignment(db, tenant_id, conv_id, selected.id, token)

            cap = (await db.execute(select(ChatbotCapacity).where(ChatbotCapacity.chatbot_id == bot.id))).scalar_one()
            assert cap.active_conversations == 1

            # Release
            released = await chatbot_scheduler.release_capacity(db, tenant_id, conv_id)
            assert released is True
            assert cap.active_conversations == 0
        finally:
            await db.close()
            await engine.dispose()

    asyncio.run(_test())


def test_acceptance_16_subscription_limit_enforcement():
    """Verifies backend rejects chatbot creation when exceeding subscription plan limit (Acceptance 16)."""
    async def _test():
        engine, db, tenant_id = await setup_test_context()
        try:
            # Plan limit is 3
            await support_service.create_chatbot(db, tenant_id, ChatbotCreateRequest(name="Bot 1"))
            await support_service.create_chatbot(db, tenant_id, ChatbotCreateRequest(name="Bot 2"))
            await support_service.create_chatbot(db, tenant_id, ChatbotCreateRequest(name="Bot 3"))

            # 4th should be rejected
            with pytest.raises(ValueError) as exc:
                await support_service.create_chatbot(db, tenant_id, ChatbotCreateRequest(name="Bot 4"))
            assert "limit" in str(exc.value).lower()
        finally:
            await db.close()
            await engine.dispose()

    asyncio.run(_test())
