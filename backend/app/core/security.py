import hmac
import hashlib
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import bcrypt
from jose import jwt, JWTError
from app.core.config import settings


def hash_password(password: str) -> str:
    """Hashes password with native bcrypt (truncated to 72 bytes)."""
    pw_bytes = password[:72].encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pw_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies plain password against bcrypt hash."""
    pw_bytes = plain_password[:72].encode("utf-8")
    hash_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(pw_bytes, hash_bytes)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Generates a signed JWT bearer access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodes and validates a JWT bearer access token."""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


def create_visitor_session_token(tenant_id: str, visitor_id: str, session_id: str) -> str:
    """Generates a signed JWT for anonymous website visitor chat sessions (valid for 24h)."""
    payload = {
        "sub": f"visitor_{visitor_id}",
        "tenant_id": tenant_id,
        "visitor_id": visitor_id,
        "session_id": session_id,
        "type": "visitor_session",
        "exp": datetime.now(timezone.utc) + timedelta(hours=24)
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_visitor_session_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodes and validates a visitor chat session JWT."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "visitor_session":
            return None
        return payload
    except JWTError:
        return None


def generate_inter_service_signature(
    secret: str,
    tenant_id: str,
    correlation_id: str,
    user_id: str = "",
    timestamp: Optional[int] = None
) -> tuple[str, int]:
    """Generates an HMAC-SHA256 signature and timestamp for inter-service communication."""
    ts = timestamp if timestamp is not None else int(time.time())
    message = f"{tenant_id}:{ts}:{correlation_id}:{user_id}".encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return signature, ts


def verify_inter_service_signature(
    signature: str,
    secret: str,
    tenant_id: str,
    correlation_id: str,
    user_id: str = "",
    timestamp: Optional[int] = None,
    max_age_seconds: int = 60
) -> bool:
    """Verifies HMAC signature with anti-replay timestamp validation."""
    if timestamp is None:
        return False
    current_time = int(time.time())
    if abs(current_time - timestamp) > max_age_seconds:
        return False
    expected_sig, _ = generate_inter_service_signature(secret, tenant_id, correlation_id, user_id, timestamp)
    return hmac.compare_digest(signature, expected_sig)

