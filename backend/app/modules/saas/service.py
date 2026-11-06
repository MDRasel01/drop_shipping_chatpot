import re
import uuid
from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.core.security import hash_password, verify_password, create_access_token
from app.modules.saas.models import Tenant, TenantSetting, User, Subscription, UsageCounter
from app.modules.saas.schemas import TenantRegisterRequest, TokenResponse, QuotaCheckResponse, TenantDashboardResponse


class SaaSManagementService:
    """Manages company registration, user auth, subscriptions, and atomic usage quotas."""

    def _generate_slug(self, company_name: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", company_name.strip().lower()).strip("-")
        return f"{slug}-{uuid.uuid4().hex[:6]}"

    async def register_company(
        self,
        db: AsyncSession,
        req: TenantRegisterRequest
    ) -> Tuple[Tenant, User, str]:
        """Atomically registers a new company tenant, admin user, settings, starter subscription, and usage counter."""
        # 1. Check existing email
        stmt = select(User).where(User.email == req.email)
        existing_user = (await db.execute(stmt)).scalar_one_or_none()
        if existing_user:
            raise ValueError("Email already registered")

        slug = req.slug or self._generate_slug(req.company_name)

        # 2. Create Tenant
        tenant = Tenant(
            id=uuid.uuid4(),
            name=req.company_name,
            slug=slug,
            status="active",
            subscription_tier="Starter",
            monthly_message_limit=10000
        )
        db.add(tenant)

        # 3. Create Tenant Settings
        setting = TenantSetting(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            primary_color="#2563eb",
            welcome_message=f"Welcome to {tenant.name}! How can we assist you?",
            allowed_domains=[]
        )
        db.add(setting)

        # 4. Create Admin User
        user = User(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            email=req.email,
            hashed_password=hash_password(req.password),
            full_name=req.admin_name,
            role="Company Admin",
            is_active=True
        )
        db.add(user)

        # 5. Create Starter Subscription
        sub = Subscription(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            plan_code="Starter",
            status="active"
        )
        db.add(sub)

        # 6. Create Usage Counter
        usage = UsageCounter(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            current_messages_used=0,
            max_messages_limit=10000,
            total_tokens_consumed=0
        )
        db.add(usage)

        await db.flush()

        # 7. Generate JWT
        token = create_access_token({
            "sub": str(user.id),
            "tenant_id": str(tenant.id),
            "role": user.role,
            "company_name": tenant.name
        })

        return tenant, user, token

    async def authenticate_user(
        self,
        db: AsyncSession,
        email: str,
        password: str
    ) -> Optional[Tuple[User, Tenant, str]]:
        """Verifies credentials and issues a JWT token."""
        stmt = select(User).where(User.email == email)
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()
        if not user or not verify_password(password, user.hashed_password):
            return None

        # Fetch Tenant
        tenant_stmt = select(Tenant).where(Tenant.id == user.tenant_id)
        tenant = (await db.execute(tenant_stmt)).scalar_one_or_none()
        if not tenant or tenant.status != "active":
            return None

        token = create_access_token({
            "sub": str(user.id),
            "tenant_id": str(tenant.id),
            "role": user.role,
            "company_name": tenant.name
        })

        return user, tenant, token

    async def validate_quota(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID
    ) -> QuotaCheckResponse:
        """Validates current usage against limit, calculating warning tiers."""
        stmt = select(UsageCounter).where(UsageCounter.tenant_id == tenant_id)
        usage = (await db.execute(stmt)).scalar_one_or_none()

        if not usage:
            return QuotaCheckResponse(
                allowed=True,
                current_used=0,
                max_limit=10000,
                remaining=10000,
                warning_level="ok"
            )

        used = usage.current_messages_used
        limit = usage.max_messages_limit
        remaining = max(0, limit - used)

        if used >= limit:
            warning_level = "blocked_100"
            allowed = False
        elif used >= int(limit * 0.90):
            warning_level = "warning_90"
            allowed = True
        elif used >= int(limit * 0.80):
            warning_level = "warning_80"
            allowed = True
        else:
            warning_level = "ok"
            allowed = True

        return QuotaCheckResponse(
            allowed=allowed,
            current_used=used,
            max_limit=limit,
            remaining=remaining,
            warning_level=warning_level
        )

    async def record_usage(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        tokens: int = 150
    ) -> None:
        """Atomically increments message count and tokens consumed."""
        stmt = (
            update(UsageCounter)
            .where(UsageCounter.tenant_id == tenant_id)
            .values(
                current_messages_used=UsageCounter.current_messages_used + 1,
                total_tokens_consumed=UsageCounter.total_tokens_consumed + tokens
            )
        )
        await db.execute(stmt)
        await db.flush()


saas_service = SaaSManagementService()

