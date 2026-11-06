import pytest
from app.modules.notifications.service import NotificationHubService


def test_notification_template_rendering_english():
    hub = NotificationHubService()
    subj, body = hub.render(
        code="quota_warning_80",
        language="en",
        ctx={"tenant_name": "Apex Support"}
    )
    assert "80% Monthly Messages Used" in subj
    assert "utilized 80% of its monthly message limit" in body


def test_notification_template_rendering_bengali():
    hub = NotificationHubService()
    subj, body = hub.render(
        code="quota_warning_80",
        language="bn",
        ctx={"tenant_name": "শীর্ষ আইটি"}
    )
    assert "৮০% মেসেজ ব্যবহৃত হয়েছে" in subj
    assert "৮০% মেসেজ ব্যবহার করেছে" in body


def test_template_sandboxed_xss_protection():
    hub = NotificationHubService()
    subj, body = hub.render(
        code="unanswered_question_alert",
        language="en",
        ctx={"question_text": "<script>alert('xss')</script>"}
    )
    assert "<script>" not in body
    assert "&lt;script&gt;" in body

