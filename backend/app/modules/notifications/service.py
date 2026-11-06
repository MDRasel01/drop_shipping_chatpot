import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from jinja2.sandbox import SandboxedEnvironment
from jinja2 import select_autoescape

from app.modules.notifications.models import Notification

class NotificationHubService:
    """Provides sandboxed multilingual templates and in-app feed management."""

    def __init__(self):
        self.env = SandboxedEnvironment(autoescape=select_autoescape(["html", "xml"]))
        self.templates: Dict[str, Dict[str, Dict[str, str]]] = {
            "quota_warning_80": {
                "en": {
                    "subject": "⚠️ Quota Warning: 80% Monthly Messages Used",
                    "body": "Your company has utilized 80% of its monthly message limit."
                },
                "bn": {
                    "subject": "⚠️ কোটা সতর্কতা: ৮০% মেসেজ ব্যবহৃত হয়েছে",
                    "body": "আপনার কোম্পানি চলতি মাসের ৮০% মেসেজ ব্যবহার করেছে।"
                }
            },
            "unanswered_question_alert": {
                "en": {
                    "subject": "❓ New Unknown Customer Question Detected",
                    "body": "A visitor asked: '{{ question_text }}'. Please submit an approved answer in Knowledge Engine."
                },
                "bn": {
                    "subject": "❓ নতুন অজানা প্রশ্ন শনাক্ত হয়েছে",
                    "body": "ভিজিটর প্রশ্ন করেছেন: '{{ question_text }}'। নলেজ ইঞ্জিনে অনুমোদিত উত্তর যোগ করুন।"
                }
            }
        }

    def render(self, code: str, language: str = "en", ctx: Optional[dict] = None) -> Tuple[str, str]:
        c = ctx or {}
        tmpl = self.templates.get(code, {}).get(language) or self.templates.get(code, {}).get("en")
        if not tmpl:
            return f"Alert: {code}", f"Event {code} with {c}"
        return self.env.from_string(tmpl["subject"]).render(**c), self.env.from_string(tmpl["body"]).render(**c)

    async def create_in_app_notification(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        recipient_id: str,
        category: str,
        title: str,
        body_text: str,
        severity: str = "INFO",
        action_url: Optional[str] = None
    ) -> Notification:
        notif = Notification(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            recipient_id=recipient_id,
            category=category,
            severity=severity,
            channel="IN_APP",
            title=title,
            body_text=body_text,
            action_url=action_url,
            status="DELIVERED"
        )
        db.add(notif)
        await db.flush()
        return notif


notification_service = NotificationHubService()

