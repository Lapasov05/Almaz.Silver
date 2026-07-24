"""inbox Repository qatlami — DB kirish."""
import uuid

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.pagination import PageParams, paginate
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
        pp: PageParams,
        status: str | None = None,
        channel: str | None = None,
        ai_state: str | None = None,
        assigned_operator_id: uuid.UUID | None = None,
        unread_only: bool | None = None,
        q: str | None = None,
    ):
        stmt = select(Conversation)
        if status is not None:
            stmt = stmt.where(Conversation.status == status)
        if channel is not None:
            stmt = stmt.where(Conversation.channel == channel)
        if ai_state is not None:
            stmt = stmt.where(Conversation.ai_state == ai_state)
        if assigned_operator_id is not None:
            stmt = stmt.where(Conversation.assigned_operator_id == assigned_operator_id)
        if unread_only:
            stmt = stmt.where(Conversation.unread_count > 0)
        if q:
            like = f"%{q}%"
            stmt = stmt.join(Customer, Customer.id == Conversation.customer_id).where(
                or_(Customer.full_name.ilike(like), Customer.username.ilike(like), Customer.external_id.ilike(like))
            )
        return await paginate(
            self.db, stmt, [Conversation.last_activity_at.desc()], pp,
            loaders=(selectinload(Conversation.customer),),
        )

    # ---------- Message ----------
    async def get_message(self, message_id: uuid.UUID) -> Message | None:
        return await self.db.get(Message, message_id)

    async def list_messages(
        self,
        conversation_id: uuid.UUID,
        *,
        pp: PageParams,
        direction: str | None = None,
        sender_type: str | None = None,
    ):
        stmt = select(Message).where(Message.conversation_id == conversation_id)
        if direction is not None:
            stmt = stmt.where(Message.direction == direction)
        if sender_type is not None:
            stmt = stmt.where(Message.sender_type == sender_type)
        return await paginate(self.db, stmt, [Message.created_at.asc()], pp)

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
