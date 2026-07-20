"""inbox Service qatlami — kelgan xabarni saqlash + operator javobi + handoff (TZ 5/9)."""
import uuid
from datetime import datetime, timedelta, timezone

from app.core.exceptions import NotFoundError
from app.modules.inbox.channels.base import ChannelError, NormalizedIncoming
from app.modules.inbox.channels.factory import get_channel_client
from app.modules.inbox.models import (
    Conversation,
    Customer,
    Message,
)
from app.modules.inbox.repository import InboxRepository


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class InboxService:
    def __init__(self, repo: InboxRepository):
        self.repo = repo

    # ---------- Kelgan xabar (webhook ingestor sinxron chaqiradi) ----------
    async def ingest_incoming(self, msg: NormalizedIncoming) -> Message:
        """Customer/conversation upsert + incoming message saqlash. Hech nima yo'qolmaydi (TZ 5)."""
        customer = await self._upsert_customer(msg)
        conversation = await self._get_or_create_conversation(customer, msg.channel)

        message = Message(
            conversation_id=conversation.id,
            direction="incoming",
            sender_type="customer",
            content=msg.text,
            attachments=msg.attachments or None,
            delivery_status="delivered",  # bizga yetib keldi
            is_read=False,
            external_id=msg.external_message_id,
        )
        await self.repo.add(message)

        # Conversation metama'lumotini yangilash
        conversation.unread_count += 1
        conversation.last_message = msg.text or "[media]"
        conversation.last_activity_at = _utcnow()

        await self.repo.db.commit()
        await self.repo.db.refresh(message)
        return message

    async def _upsert_customer(self, msg: NormalizedIncoming) -> Customer:
        customer = await self.repo.get_customer(msg.channel, msg.external_user_id)
        if customer is None:
            customer = Customer(
                channel=msg.channel,
                external_id=msg.external_user_id,
                username=msg.username,
                full_name=msg.full_name,
                source=msg.channel,
            )
            await self.repo.add(customer)
        else:
            # Yangi ma'lumot kelsa yangilaymiz (takroriy so'ramaslik — TZ 7.3)
            if msg.username and customer.username != msg.username:
                customer.username = msg.username
            if msg.full_name and not customer.full_name:
                customer.full_name = msg.full_name
        return customer

    async def _get_or_create_conversation(self, customer: Customer, channel: str) -> Conversation:
        conversation = await self.repo.get_open_conversation(customer.id, channel)
        if conversation is None:
            conversation = Conversation(customer_id=customer.id, channel=channel)
            await self.repo.add(conversation)
        return conversation

    # ---------- CRM o'qish ----------
    async def list_conversations(self, **filters) -> list[Conversation]:
        return await self.repo.list_conversations(**filters)

    async def get_conversation(self, conversation_id: uuid.UUID) -> Conversation:
        conv = await self.repo.get_conversation(conversation_id)
        if conv is None:
            raise NotFoundError("Suhbat topilmadi")
        return conv

    async def list_messages(self, conversation_id: uuid.UUID, **kw) -> list[Message]:
        await self.get_conversation(conversation_id)
        return await self.repo.list_messages(conversation_id, **kw)

    async def mark_read(self, conversation_id: uuid.UUID) -> Conversation:
        conv = await self.get_conversation(conversation_id)
        await self.repo.mark_incoming_read(conversation_id)
        conv.unread_count = 0
        await self.repo.db.commit()
        return conv

    # ---------- Chiquvchi xabar (umumiy) ----------
    async def _send_outbound(
        self,
        conv: Conversation,
        text: str,
        *,
        sender_type: str,
        sender_user_id: uuid.UUID | None = None,
    ) -> Message:
        """Xabarni saqlaydi (pending) → kanalga yuboradi → delivery_status yangilaydi.

        Xabar YUBORISHDAN OLDIN saqlanadi (yuborish muvaffaqiyatsiz bo'lsa ham yo'qolmaydi).
        """
        conv.last_message = text
        conv.last_activity_at = _utcnow()

        message = Message(
            conversation_id=conv.id,
            direction="outgoing",
            sender_type=sender_type,
            sender_user_id=sender_user_id,
            content=text,
            delivery_status="pending",
        )
        await self.repo.add(message)
        await self.repo.db.commit()

        try:
            client = get_channel_client(conv.channel)
            result = await client.send_text(conv.customer.external_id, text)
            message.delivery_status = "sent"
            message.external_id = result.external_message_id
        except ChannelError:
            message.delivery_status = "failed"
        await self.repo.db.commit()
        await self.repo.db.refresh(message)
        return message

    # ---------- Operator javobi (15-daqiqa handoff) ----------
    async def operator_send(
        self, conversation_id: uuid.UUID, operator_id: uuid.UUID, text: str
    ) -> Message:
        conv = await self.get_conversation(conversation_id)
        # TZ 9: operator yozsa AI 15 daqiqa (settings) pauza qiladi
        pause_minutes = await self.repo.get_ai_pause_minutes()
        conv.ai_paused_until = _utcnow() + timedelta(minutes=pause_minutes)
        return await self._send_outbound(
            conv, text, sender_type="operator", sender_user_id=operator_id
        )

    # ---------- AI javobi (pauza QO'YMAYDI) ----------
    async def ai_send(self, conv: Conversation, text: str) -> Message:
        """AI javobini yuboradi. Operatordan farqli — ai_paused_until o'zgarmaydi."""
        return await self._send_outbound(conv, text, sender_type="ai")

    # ---------- Tizim xabari (to'lov tasdiq/rad va h.k.) ----------
    async def notify_customer(self, customer_id: uuid.UUID, channel: str, text: str) -> Message | None:
        """Mijozning ochiq suhbatiga tizim xabarini yuboradi (suhbat bo'lmasa None)."""
        conv = await self.repo.get_open_conversation(customer_id, channel)
        if conv is None:
            return None
        # customer relationship kerak (external_id) — qayta yuklaymiz
        conv = await self.repo.get_conversation(conv.id)
        return await self._send_outbound(conv, text, sender_type="system")

    # ---------- Transfer / assign ----------
    async def transfer_chat(
        self,
        conversation_id: uuid.UUID,
        target_operator_id: uuid.UUID,
        actor_id: uuid.UUID,
        reason: str | None,
    ) -> Conversation:
        conv = await self.get_conversation(conversation_id)
        conv.assigned_operator_id = target_operator_id
        note = f"Suhbat operatorga o'tkazildi (id={target_operator_id})"
        if reason:
            note += f": {reason}"
        await self.repo.add(
            Message(
                conversation_id=conv.id,
                direction="outgoing",
                sender_type="system",
                sender_user_id=actor_id,
                content=note,
                delivery_status="sent",
            )
        )
        await self.repo.db.commit()
        return conv

    async def assign(self, conversation_id: uuid.UUID, operator_id: uuid.UUID) -> Conversation:
        conv = await self.get_conversation(conversation_id)
        conv.assigned_operator_id = operator_id
        await self.repo.db.commit()
        return conv
