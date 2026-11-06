import uuid
import pytest
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token
from app.modules.saas.schemas import TenantRegisterRequest, QuotaCheckResponse


def test_password_hashing_and_verification():
    password = "SuperSecretPassword123!"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_password_truncation_safety():
    # Long password > 72 bytes should hash cleanly without raising ValueError in bcrypt
    long_password = "A" * 150
    hashed = hash_password(long_password)
    assert verify_password(long_password, hashed) is True


def test_jwt_access_token_creation_and_decoding():
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    token = create_access_token({
        "sub": user_id,
        "tenant_id": tenant_id,
        "role": "Company Admin",
        "company_name": "Apex Support"
    })

    claims = decode_access_token(token)
    assert claims is not None
    assert claims["sub"] == user_id
    assert claims["tenant_id"] == tenant_id
    assert claims["role"] == "Company Admin"
    assert claims["company_name"] == "Apex Support"


def test_tenant_register_request_schema():
    req = TenantRegisterRequest(
        company_name="Acme Corporation",
        admin_name="John Doe",
        email="john@acme.com",
        password="ValidPassword123!"
    )
    assert req.company_name == "Acme Corporation"
    assert req.email == "john@acme.com"


def test_quota_threshold_tiers():
    # OK tier
    q1 = QuotaCheckResponse(allowed=True, current_used=5000, max_limit=10000, remaining=5000, warning_level="ok")
    assert q1.warning_level == "ok"
    assert q1.allowed is True

    # 80% Warning tier
    q2 = QuotaCheckResponse(allowed=True, current_used=8200, max_limit=10000, remaining=1800, warning_level="warning_80")
    assert q2.warning_level == "warning_80"
    assert q2.allowed is True

    # 90% Warning tier
    q3 = QuotaCheckResponse(allowed=True, current_used=9100, max_limit=10000, remaining=900, warning_level="warning_90")
    assert q3.warning_level == "warning_90"
    assert q3.allowed is True

    # 100% Blocked tier
    q4 = QuotaCheckResponse(allowed=False, current_used=10000, max_limit=10000, remaining=0, warning_level="blocked_100")
    assert q4.warning_level == "blocked_100"
    assert q4.allowed is False

