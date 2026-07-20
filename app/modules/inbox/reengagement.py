"""Proaktiv qayta jalb (TZ 17) — jim qolgan mijozlarni IG 24-soat oynasi ichida qayta jalb.

Nomzod: ochiq suhbat, AI pauzada emas, oxirgi xabar MIJOZDAN (biz javob bermaganmiz),
`inactivity_minutes`dan jim, lekin `window_hours` (IG 24h) ichida (hali yozsa bo'ladi).
Bir marta jalb qilgach oxirgi xabar chiquvchi bo'ladi — takroran spam qilinmaydi.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.inbox.models import Conversation
from app.modules.inbox.repository import InboxRepository
from app.modules.inbox.service import InboxService

settings = get_settings()

REENGAGE_TEXT = (
    "Assalomu alaykum! 😊 Sizga tanlovда yordam kerak bo'lsa, shu yerдамiz — "
    "savolingizni yozing yoki qaysi model yoqqanini ayting."
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ReengagementService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = InboxRepository(db)

    async def find_candidates(self, limit: int = 50) -> list[Conversation]:
        now = _utcnow()
        inactive_before = now - timedelta(minutes=settings.reengagement_inactivity_minutes)
        window_after = now - timedelta(hours=settings.reengagement_window_hours)

        stmt = (
            select(Conversation)
            .where(
                Conversation.status == "open",
                (Conversation.ai_paused_until.is_(None)) | (Conversation.ai_paused_until < now),
                Conversation.last_activity_at < inactive_before,
                Conversation.last_activity_at > window_after,  # IG 24h oynasi
            )
            .order_by(Conversation.last_activity_at.asc())
            .limit(limit)
        )
        convs = list((await self.db.execute(stmt)).scalars().all())

        # Faqat oxirgi xabar mijozdan bo'lgan suhbatlar (biz javob bermaganmiz)
        result: list[Conversation] = []
        for conv in convs:
            recent = await self.repo.list_recent_messages(conv.id, 1)
            if recent and recent[-1].direction == "incoming":
                result.append(conv)
        return result

    async def run(self) -> int:
        """Nomzodlarni topib, har biriga qayta jalb xabari yuboradi. Yuborilgan sonini qaytaradi."""
        if not settings.reengagement_enabled:
            return 0
        candidates = await self.find_candidates()
        inbox = InboxService(self.repo)
        sent = 0
        for conv in candidates:
            full = await self.repo.get_conversation(conv.id)  # customer bilan
            await inbox.ai_send(full, REENGAGE_TEXT)
            sent += 1
        return sent
