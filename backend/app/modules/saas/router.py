import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db, set_tenant_context
from app.modules.saas.schemas import (
    TenantRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    QuotaCheckResponse,
    TenantDashboardResponse
)
from app.modules.saas.models import Tenant, UsageCounter
from app.modules.saas.service import saas_service

router = APIRouter(tags=["Auth & Tenant Lifecycle"])


@router.post("/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(request: TenantRegisterRequest, db: AsyncSession = Depends(get_db)):
    """Registers a new company, provisions Starter subscription, usage counter, and issues JWT."""
    try:
        tenant, user, token = await saas_service.register_company(db, request)
        return TokenResponse(
            access_token=token,
            tenant_id=tenant.id,
            user_id=user.id,
            role=user.role,
            company_name=tenant.name
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/auth/token", response_model=TokenResponse)
async def login(request: UserLoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticates admin or staff user and returns JWT bearer token."""
    res = await saas_service.authenticate_user(db, request.email, request.password)
    if not res:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    user, tenant, token = res
    return TokenResponse(
        access_token=token,
        tenant_id=tenant.id,
        user_id=user.id,
        role=user.role,
        company_name=tenant.name
    )


@router.get("/saas/usage/quota", response_model=QuotaCheckResponse)
async def check_quota(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Validates message quota and returns threshold alerts (80%, 90%, 100%)."""
    await set_tenant_context(db, tenant_id)
    return await saas_service.validate_quota(db, tenant_id)


@router.get("/saas/dashboard", response_model=TenantDashboardResponse)
async def get_dashboard(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Returns overview statistics for the company dashboard."""
    await set_tenant_context(db, tenant_id)
    stmt = select(Tenant).where(Tenant.id == tenant_id)
    tenant = (await db.execute(stmt)).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    quota = await saas_service.validate_quota(db, tenant_id)
    usage_pct = round((quota.current_used / max(1, quota.max_limit)) * 100, 2)

    return TenantDashboardResponse(
        tenant_id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        subscription_tier=tenant.subscription_tier,
        messages_used=quota.current_used,
        messages_limit=quota.max_limit,
        usage_percentage=usage_pct,
        total_tokens=quota.current_used * 150,
        active_agents=1,
        status=tenant.status
    )

