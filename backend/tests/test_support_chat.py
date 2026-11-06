import uuid
import pytest
from app.core.security import create_visitor_session_token, decode_visitor_session_token
from app.modules.support.schemas import SessionInitRequest, ChatMessageRequest


def test_visitor_session_token_lifecycle():
    tenant_id = str(uuid.uuid4())
    visitor_id = "vis_test_123"
    session_id = str(uuid.uuid4())

    token = create_visitor_session_token(tenant_id, visitor_id, session_id)
    claims = decode_visitor_session_token(token)

    assert claims is not None
    assert claims["tenant_id"] == tenant_id
    assert claims["visitor_id"] == visitor_id
    assert claims["session_id"] == session_id
    assert claims["type"] == "visitor_session"


def test_visitor_token_rejects_arbitrary_jwt():
    from app.core.security import create_access_token
    # Regular user token should fail decode_visitor_session_token
    user_token = create_access_token({"sub": "admin", "type": "user_auth"})
    assert decode_visitor_session_token(user_token) is None


def test_chat_message_schema():
    req = ChatMessageRequest(message="What is the price of the starter plan?")
    assert req.message == "What is the price of the starter plan?"

