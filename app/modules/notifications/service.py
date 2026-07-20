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
            await TelegramClient().send_text(str(chat_id), text, reply_markup=keyboard)
            record.status = "sent"
            await self.db.commit()
            return True
        except ChannelError:
            record.status = "failed"
            logger.warning("Owner to'lov xabarnomasi yuborilmadi (token/chat)")
            await self.db.commit()
            return False
