"""notifications Service — owner/manager botiga va operator GURUHiga xabarnomalar (TZ 12 / 4-bo'lim).

Ikki oqim:
- To'lov cheki → `payment_review_telegram_chat_id` chatiga ✅/❌ tugmalar bilan (TZ 12).
- Yangi buyurtma va operator so'rovi → `orders_group_telegram_chat_id` guruhiga (markdown, rasm havolasi bilan).
"""
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.media_url import public_media_url
from app.modules.inbox.channels.base import ChannelError
from app.modules.inbox.channels.telegram import TelegramClient
from app.modules.notifications.models import Notification
from app.modules.orders.models import Order
from app.modules.payments.models import Payment
from app.modules.settings.repository import SettingsRepository

logger = logging.getLogger(__name__)

# Telegram "Markdown" (legacy) rejimida shu belgilar formatlash deb o'qiladi —
# mijoz ismi/savolida uchrasa xabar 400 bilan qaytadi, shuning uchun qalqon qo'yamiz.
_MD_SPECIAL = ("_", "*", "`", "[")


def _md(value) -> str:
    """Markdown uchun xavfsiz matn."""
    text = str(value or "")
    for ch in _MD_SPECIAL:
        text = text.replace(ch, "\\" + ch)
    return text


def _md_image(url: str | None, label: str) -> str:
    """Rasm havolasi — Telegram uni preview qilib ko'rsatadi (fayl saqlanmaydi)."""
    url = public_media_url(url) if url else ""
    # Havola ichida ")" bo'lsa markdown buziladi — bunday havolani tashlab ketamiz
    return f"[{label}]({url})\n" if url and ")" not in url else ""


def _sum(value) -> str:
    return f"{int(value or 0):,}".replace(",", " ")


class NotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def notify_payment_review(self, payment: Payment, order: Order) -> bool:
        """To'lov chekini tasdiqlash uchun owner/manager botiga yuboradi."""
        setting = await SettingsRepository(self.db).get("payment_review_telegram_chat_id")
        chat_id = setting.value if setting is not None else None

        text = (
            f"🧾 Yangi to'lov cheki\n"
            f"Buyurtma: {order.order_no}\n"
            f"Summa: {order.grand_total} so'm (mahsulot {order.items_total} + yetkazish {order.delivery_fee})\n"
            f"To'lovchi: {payment.payer_name or '—'}\n"
            f"Chek: {payment.receipt_url or '—'}"
        )
        record = Notification(
            type="payment_review", channel="telegram", target=str(chat_id) if chat_id else None,
            body=text, status="pending", entity_type="payment", entity_id=payment.id,
        )
        self.db.add(record)

        if not chat_id:
            record.status = "skipped"
            logger.info("payment_review_telegram_chat_id sozlanmagan — owner xabarnomasi o'tkazib yuborildi")
            await self.db.commit()
            return False

        keyboard = {
            "inline_keyboard": [[
                {"text": "✅ Tasdiqlash", "callback_data": f"pay:approve:{payment.id}"},
                {"text": "❌ Rad etish", "callback_data": f"pay:reject:{payment.id}"},
            ]]
        }
        try:
            from app.modules.integrations.service import get_config_value

            token = await get_config_value(self.db, "telegram", "bot_token")
            await TelegramClient(bot_token=token).send_text(str(chat_id), text, reply_markup=keyboard)
            record.status = "sent"
            await self.db.commit()
            return True
        except ChannelError:
            record.status = "failed"
            logger.warning("Owner to'lov xabarnomasi yuborilmadi (token/chat)")
            await self.db.commit()
            return False

    # ---------- Operator guruhi ----------
    async def notify_new_order(self, order: Order, superseded: list[str] | None = None) -> bool:
        """YANGI buyurtma (yaratilishi bilan) — operator guruhiga tasdiqlash uchun.

        To'lov tasdiqlangandan keyin guruhga xabar YUBORILMAYDI: operator buyurtmani
        aynan tushgan paytda ko'rishi kerak. Best-effort — buyurtma yaratishni buzmaydi.
        `superseded` — mijoz fikrini o'zgartirib, bekor bo'lgan oldingi buyurtma raqamlari
        (guruhdagi eski xabar endi kuchda emasligini operator bilib tursin).
        """
        text = await self._format_new_order(order, superseded)
        return await self._send_to_group(
            type_="order_created", text=text, entity_type="order", entity_id=order.id
        )

    async def notify_operator_request(
        self, customer, question: str | None, image_url: str | None = None
    ) -> bool:
        """Mijoz rasm yuborib «shunga o'xshagani bormi» desa — operator aloqaga chiqishi uchun.

        Mijoz ismi, telefoni, so'rovi va yuborgan rasmi havolasi guruhga boradi.
        Rasm YUKLAB OLINMAYDI — havola markdown ko'rinishida beriladi.
        """
        parts = ["🔔 *Operator kerak*", "Mijoz rasm yuborib mahsulot so'radi.", ""]
        image_line = _md_image(image_url, "🖼 Mijoz rasmi")
        if image_line:
            parts.append(image_line)
        parts.append(f"👤 {_md(getattr(customer, 'full_name', None) or '—')}")
        parts.append(f"📞 {_md(getattr(customer, 'phone', None) or '—')}")
        if question:
            parts.append(f"❓ {_md(question)}")
        channel = getattr(customer, "channel", None)
        username = getattr(customer, "username", None)
        if channel:
            parts.append(f"💬 {_md(channel)}" + (f" @{_md(username)}" if username else ""))
        return await self._send_to_group(
            type_="operator_request", text="\n".join(parts),
            entity_type="customer", entity_id=getattr(customer, "id", None),
        )

    async def _send_to_group(self, *, type_: str, text: str, entity_type: str, entity_id) -> bool:
        """Operator guruhiga markdown xabar (umumiy oqim + notification qaydi)."""
        setting = await SettingsRepository(self.db).get("orders_group_telegram_chat_id")
        chat_id = setting.value if setting is not None else None
        record = Notification(
            type=type_, channel="telegram", target=str(chat_id) if chat_id else None,
            body=text, status="pending", entity_type=entity_type, entity_id=entity_id,
        )
        self.db.add(record)
        if not chat_id:
            record.status = "skipped"
            logger.info("orders_group_telegram_chat_id sozlanmagan — guruh xabari o'tkazib yuborildi")
            await self.db.commit()
            return False
        try:
            from app.modules.integrations.service import get_config_value

            token = await get_config_value(self.db, "telegram", "bot_token")
            await TelegramClient(bot_token=token).send_text(str(chat_id), text, parse_mode="Markdown")
            record.status = "sent"
            await self.db.commit()
            return True
        except ChannelError:
            record.status = "failed"
            logger.warning("Guruh xabari yuborilmadi (%s): token/chat/format", type_)
            await self.db.commit()
            return False

    async def _format_new_order(self, order: Order, superseded: list[str] | None = None) -> str:
        """Guruhga yuboriladigan buyurtma matni — mahsulot rasmi, tarkib, mijoz, manzil, jami."""
        from app.modules.catalog.repository import CatalogRepository
        from app.modules.delivery.repository import DeliveryRepository
        from app.modules.inbox.models import Customer

        catalog = CatalogRepository(self.db)
        lines: list[str] = []
        first_image: str | None = None
        for it in order.items:
            variant = await catalog.get_variant(it.variant_id)
            product = await catalog.get_product(variant.product_id) if variant else None
            if product is not None and first_image is None:
                media = [m for m in product.media if m.image_url]
                if media:
                    first_image = media[0].image_url
            seg = f"• {_md(product.name_uz if product else '?')}"
            if it.quantity and it.quantity > 1:
                seg += f" ×{it.quantity}"
            if it.ring_size:
                seg += f", o'lcham {_md(it.ring_size)}"
            if it.box_id:
                box = await catalog.get_box(it.box_id)
                if box is not None:
                    seg += f", quti: {_md(box.name_uz)}"
            if it.engraving_text:
                seg += f", gravirovka: «{_md(it.engraving_text)}»"
            lines.append(seg)

        cust = await self.db.get(Customer, order.customer_id)
        delivery = await DeliveryRepository(self.db).get_by_order(order.id)
        addr = (delivery.address_text if delivery else None) or "—"
        zone = (delivery.location_type if delivery else None) or "—"
        return (
            f"🆕 *Yangi buyurtma*\n"
            f"№ {_md(order.order_no)}\n\n"
            + _md_image(first_image, "🖼 Mahsulot rasmi")
            + "\n".join(lines)
            + f"\n\n👤 {_md(cust.full_name if cust and cust.full_name else '—')}"
            + f"\n📞 {_md(cust.phone if cust and cust.phone else '—')}"
            + f"\n📍 {_md(addr)} ({_md(zone)})"
            + f"\n💰 Jami: {_sum(order.grand_total)} so'm"
            + (f"\n\n♻️ Mijoz o'zgartirdi — bekor bo'ldi: {_md(', '.join(superseded))}"
               if superseded else "")
        )
