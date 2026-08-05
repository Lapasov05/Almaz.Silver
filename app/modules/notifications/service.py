"""notifications Service — owner/manager botiga xabarnomalar (TZ 12 / 4-bo'lim).

Faza 5: to'lov cheki keldi → owner/manager Telegram chatiga tasdiq/rad tugmalari bilan boradi.
Chat id: `settings.payment_review_telegram_chat_id`. Sozlanmagan bo'lsa — jim (log).
"""
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.inbox.channels.base import ChannelError
from app.modules.inbox.channels.telegram import TelegramClient
from app.modules.notifications.models import Notification
from app.modules.orders.models import Order
from app.modules.payments.models import Payment
from app.modules.settings.repository import SettingsRepository

logger = logging.getLogger(__name__)


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

    async def notify_order_confirmed(self, order: Order) -> bool:
        """Tasdiqlangan (to'lov tasdiqlangan) buyurtmani Telegram GURUHiga yuboradi.

        Faqat to'lov approved bo'lganда chaqiriladi (PaymentService.approve). Guruh chat id
        `settings.orders_group_telegram_chat_id`. Sozlanmagan bo'lsa — jim. Best-effort (approve'ni buzmaydi).
        """
        setting = await SettingsRepository(self.db).get("orders_group_telegram_chat_id")
        chat_id = setting.value if setting is not None else None

        text = await self._format_confirmed_order(order)
        record = Notification(
            type="order_confirmed", channel="telegram", target=str(chat_id) if chat_id else None,
            body=text, status="pending", entity_type="order", entity_id=order.id,
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
            await TelegramClient(bot_token=token).send_text(str(chat_id), text)
            record.status = "sent"
            await self.db.commit()
            return True
        except ChannelError:
            record.status = "failed"
            logger.warning("Guruh buyurtma xabari yuborilmadi (token/chat)")
            await self.db.commit()
            return False

    async def _format_confirmed_order(self, order: Order) -> str:
        """Guruhga yuboriladigan buyurtma matni — mahsulotlar, mijoz, manzil, jami."""
        from app.modules.catalog.repository import CatalogRepository
        from app.modules.delivery.repository import DeliveryRepository
        from app.modules.inbox.models import Customer

        catalog = CatalogRepository(self.db)
        lines: list[str] = []
        for it in order.items:
            variant = await catalog.get_variant(it.variant_id)
            product = await catalog.get_product(variant.product_id) if variant else None
            seg = f"• {product.name_uz if product else '?'}"
            if it.quantity and it.quantity > 1:
                seg += f" ×{it.quantity}"
            if it.ring_size:
                seg += f", o'lcham {it.ring_size}"
            if it.box_id:
                box = await catalog.get_box(it.box_id)
                if box is not None:
                    seg += f", quti: {box.name_uz}"
            if it.engraving_text:
                seg += f", gravirovka: «{it.engraving_text}»"
            lines.append(seg)
        cust = await self.db.get(Customer, order.customer_id)
        delivery = await DeliveryRepository(self.db).get_by_order(order.id)
        addr = (delivery.address_text if delivery else None) or "—"
        zone = (delivery.location_type if delivery else None) or "—"
        return (
            f"✅ Yangi tasdiqlangan buyurtma\n"
            f"№ {order.order_no}\n\n"
            + "\n".join(lines)
            + f"\n\n👤 {cust.full_name if cust and cust.full_name else '—'}"
            + f"\n📞 {cust.phone if cust and cust.phone else '—'}"
            + f"\n📍 {addr} ({zone})"
            + f"\n💰 Jami: {int(order.grand_total or 0):,} so'm".replace(",", " ")
        )
