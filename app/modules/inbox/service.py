"""inbox Service qatlami — kelgan xabarni saqlash + operator javobi + handoff (TZ 5/9)."""
import uuid
from datetime import datetime, timedelta, timezone

import structlog

from app.core.exceptions import AppError, NotFoundError
from app.modules.inbox.channels.base import ChannelError, NormalizedIncoming
from app.modules.inbox.channels.factory import build_channel_client
from app.modules.inbox.models import (
    Conversation,
    Customer,
    Message,
)
from app.modules.inbox.repository import InboxRepository


logger = structlog.get_logger(__name__)


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

    # ---------- Mijoz / suhbat CRUD (operator qo'lda tahrirlash/o'chirish) ----------
    async def get_customer(self, customer_id: uuid.UUID) -> Customer:
        customer = await self.repo.get_customer_by_id(customer_id)
        if customer is None:
            raise NotFoundError("Mijoz topilmadi")
        return customer

    async def update_customer(self, customer_id: uuid.UUID, data) -> Customer:
        """Mijoz ism/telefonini qo'lda yozadi (partial). Berilmagan maydon o'zgarmaydi."""
        customer = await self.get_customer(customer_id)
        fields = data.model_dump(exclude_unset=True)
        if "full_name" in fields:
            customer.full_name = (fields["full_name"] or None)
        if "phone" in fields:
            customer.phone = (fields["phone"] or None)
        await self.repo.db.commit()
        return customer

    async def delete_conversation(self, conversation_id: uuid.UUID) -> None:
        """Suhbatni (va xabarlarini — CASCADE) o'chiradi. Mijoz saqlanadi."""
        conv = await self.get_conversation(conversation_id)
        await self.repo.db.delete(conv)
        await self.repo.db.commit()

    async def delete_customer(self, customer_id: uuid.UUID) -> None:
        """Mijozni to'liq o'chiradi (suhbat+xabar+lokatsiya bilan). Buyurtmasi bo'lsa RAD etiladi."""
        from sqlalchemy import delete, func, select

        from app.modules.delivery.models import CustomerLocation
        from app.modules.inbox.models import Conversation
        from app.modules.orders.models import Order

        customer = await self.get_customer(customer_id)
        order_cnt = await self.repo.db.scalar(
            select(func.count()).select_from(Order).where(Order.customer_id == customer_id)
        )
        if order_cnt:
            raise AppError(
                f"Bu mijozning {order_cnt} ta buyurtmasi bor — o'chirib bo'lmaydi. "
                "Avval buyurtmalarni bekor qiling yoki faqat suhbatni o'chiring."
            )
        # suhbatlar (xabarlar CASCADE) + lokatsiyalar, so'ng mijoz
        for conv in await self.repo.db.scalars(
            select(Conversation).where(Conversation.customer_id == customer_id)
        ):
            await self.repo.db.delete(conv)
        await self.repo.db.execute(delete(CustomerLocation).where(CustomerLocation.customer_id == customer_id))
        await self.repo.db.delete(customer)
        await self.repo.db.commit()

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
            # Token DB (IntegrationConfig) → .env; markdown tozalanadi
            client = await build_channel_client(self.repo.db, conv.channel)
            result = await client.send_text(conv.customer.external_id, text)
            message.delivery_status = "sent"
            message.external_id = result.external_message_id
        except ChannelError as e:
            # Yuborish yiqildi — sababни log'ga chiqaramiz (aks holда jim "failed" bo'lardi)
            message.delivery_status = "failed"
            logger.error(
                "outbound_send_failed",
                channel=conv.channel,
                conversation_id=str(conv.id),
                recipient=conv.customer.external_id,
                error=str(e),
            )
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

    async def send_typing(self, conv: Conversation) -> None:
        """Suhbat kanalига "yozyapti..." indikatorini yuboradi (best-effort)."""
        try:
            client = await build_channel_client(self.repo.db, conv.channel)
            await client.send_typing(conv.customer.external_id)
        except Exception:  # noqa: BLE001 — indikator muhim emas
            logger.debug("typing indikatori yuborilmadi (conv=%s)", conv.id, exc_info=True)

    async def send_media(self, conv: Conversation, image_url: str, caption: str | None = None) -> Message:
        """AI mahsulot rasmini yuboradi — chiquvchi xabar sifatida saqlanadi (delivery_status bilan)."""
        # Rasm URL'ini tashqi (public) bazaga keltiramiz — aks holda IG/TG serveri localhost/ichki
        # hostни ololmaydi va rasm "urli ketib" ko'rinmaydi (bug fix).
        from app.core.media_url import public_media_url

        image_url = public_media_url(image_url)
        conv.last_message = caption or "[rasm]"
        conv.last_activity_at = _utcnow()
        message = Message(
            conversation_id=conv.id,
            direction="outgoing",
            sender_type="ai",
            content=caption,
            attachments=[{"type": "image", "url": image_url}],
            delivery_status="pending",
        )
        await self.repo.add(message)
        await self.repo.db.commit()
        try:
            client = await build_channel_client(self.repo.db, conv.channel)
            result = await client.send_image(conv.customer.external_id, image_url, caption=caption)
            message.delivery_status = "sent"
            message.external_id = result.external_message_id
        except ChannelError as e:
            message.delivery_status = "failed"
            logger.error(
                "outbound_image_failed",
                channel=conv.channel, conversation_id=str(conv.id), error=str(e),
            )
        await self.repo.db.commit()
        await self.repo.db.refresh(message)
        return message

    async def send_media_group(
        self,
        conv: Conversation,
        items: list[dict],
        *,
        tool_name: str,
    ) -> Message:
        from app.core.media_url import public_media_url

        normalized = []
        for position, item in enumerate(items, start=1):
            normalized.append({**item, "position": position, "image_url": public_media_url(item["image_url"])})
        conv.last_message = f"[{len(normalized)} ta rasm]"
        conv.last_activity_at = _utcnow()
        attachments = [
            {
                "type": "image",
                "url": item["image_url"],
                "position": item["position"],
                "product_id": item.get("product_id"),
                "variant_id": item.get("variant_id"),
                "name": item.get("name"),
            }
            for item in normalized
        ]
        products = [
            {
                "position": item["position"],
                "product_id": item["product_id"],
                "variant_id": item["variant_id"],
                "name": item["name"],
            }
            for item in normalized
            if item.get("product_id") and item.get("variant_id") and item.get("name")
        ]
        message = Message(
            conversation_id=conv.id,
            direction="outgoing",
            sender_type="ai",
            content=None,
            attachments=attachments,
            tool_call={"name": tool_name, "products": products},
            delivery_status="pending",
        )
        await self.repo.add(message)
        await self.repo.db.commit()
        try:
            client = await build_channel_client(self.repo.db, conv.channel)
            result = await client.send_images(conv.customer.external_id, normalized)
            message.delivery_status = "sent"
            message.external_id = result.external_message_id
        except ChannelError as error:
            message.delivery_status = "failed"
            logger.error(
                "outbound_media_group_failed",
                channel=conv.channel,
                conversation_id=str(conv.id),
                error=str(error),
            )
        await self.repo.db.commit()
        await self.repo.db.refresh(message)
        return message

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

    # ---------- Shu suhbatда AI'ni qo'lda boshqarish ----------
    async def set_ai_control(
        self, conversation_id: uuid.UUID, *, mode: str, minutes: int | None, until: datetime | None
    ) -> Conversation:
        conv = await self.get_conversation(conversation_id)
        now = _utcnow()
        if mode == "off":              # butunlay o'chir (mijoz keyin yozsa ham AI jim)
            conv.ai_enabled = False
        elif mode == "on":             # yoq (pauzani ham tozala)
            conv.ai_enabled = True
            conv.ai_paused_until = None
        elif mode == "pause_minutes":  # N daqiqaga
            if not minutes:
                raise AppError("`minutes` ko'rsatilishi kerak")
            conv.ai_enabled = True
            conv.ai_paused_until = now + timedelta(minutes=minutes)
        elif mode == "pause_until":    # aniq sana-vaqtgacha
            if until is None:
                raise AppError("`until` ko'rsatilishi kerak")
            if until.tzinfo is None:
                until = until.replace(tzinfo=timezone.utc)
            if until <= now:
                raise AppError("`until` kelajakдаgi vaqt bo'lishi kerak")
            conv.ai_enabled = True
            conv.ai_paused_until = until
        await self.repo.db.commit()
        return conv
