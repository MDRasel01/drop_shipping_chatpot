import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field


class TenantRegisterRequest(BaseModel):
    company_name: str = Field(..., min_length=2, max_length=255)
    admin_name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8)
    slug: Optional[str] = None


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    company_name: str


class QuotaCheckResponse(BaseModel):
    allowed: bool
    current_used: int
    max_limit: int
    remaining: int
    warning_level: str  # ok, warning_80, warning_90, blocked_100


class TenantDashboardResponse(BaseModel):
    tenant_id: uuid.UUID
    name: str
    slug: str
    subscription_tier: str
    messages_used: int
    messages_limit: int
    usage_percentage: float
    total_tokens: int
    active_agents: int
    status: str

