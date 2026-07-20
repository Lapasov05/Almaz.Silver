"""inbox Repository qatlami — DB kirish."""
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.inbox.models import Conversation, Customer, Message
from app.modules.settings.models import Setting


class InboxRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add(self, obj):
        self.db.add(obj)
        await self.db.flush()
        return obj

    # ---------- Customer ----------
    async def get_customer(self, channel: str, external_id: str) -> Customer | None:
        res = await self.db.execute(
            select(Customer).where(
                Customer.channel == channel,
                Customer.external_id == external_id,
                Customer.deleted_at.is_(None),
            )
        )
        return res.scalar_one_or_none()

    # ---------- Conversation ----------
    async def get_open_conversation(self, customer_id: uuid.UUID, channel: str) -> Conversation | None:
        res = await self.db.execute(
            select(Conversation)
            .where(
                Conversation.customer_id == customer_id,
                Conversation.channel == channel,
                Conversation.status == "open",
            )
            .order_by(Conversation.last_activity_at.desc())
        )
        return res.scalars().first()

    async def get_conversation(self, conversation_id: uuid.UUID) -> Conversation | None:
        res = await self.db.execute(
            select(Conversation)
            .options(selectinload(Conversation.customer))
            .where(Conversation.id == conversation_id)
        )
        return res.scalar_one_or_none()

    async def list_conversations(
        self,
        *,
        status: str | None = None,
        channel: str | None = None,
        assigned_operator_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Conversation]:
        stmt = select(Conversation).options(selectinload(Conversation.customer))
        if status is not None:
            stmt = stmt.where(Conversation.status == status)
        if channel is not None:
            stmt = stmt.where(Conversation.channel == channel)
        if assigned_operator_id is not None:
            stmt = stmt.where(Conversation.assigned_operator_id == assigned_operator_id)
        stmt = stmt.order_by(Conversation.last_activity_at.desc()).limit(limit).offset(offset)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    # ---------- Message ----------
    async def get_message(self, message_id: uuid.UUID) -> Message | None:
        return await self.db.get(Message, message_id)

    async def list_messages(
        self, conversation_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> list[Message]:
        res = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(res.scalars().all())

    async def list_recent_messages(self, conversation_id: uuid.UUID, limit: int) -> list[Message]:
        """Oxirgi N xabar (AI xotirasi uchun), xronologik tartibда (TZ 7.3)."""
        res = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        return list(reversed(res.scalars().all()))

    async def mark_incoming_read(self, conversation_id: uuid.UUID) -> None:
        await self.db.execute(
            update(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.direction == "incoming",
                Message.is_read.is_(False),
            )
            .values(is_read=True)
        )

    # ---------- Settings (cross-modul read) ----------
    async def get_ai_pause_minutes(self, default: int = 15) -> int:
        res = await self.db.execute(select(Setting.value).where(Setting.key == "ai_pause_minutes"))
        value = res.scalar_one_or_none()
        try:
            return int(value) if value is not None else default
        except (TypeError, ValueError):
            return default
