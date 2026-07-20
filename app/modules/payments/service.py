"""payments Service qatlami — prepaid oqim: submit → approve/reject (TZ 12).

Idempotentlik: bir payment bir marta approve bo'ladi. Approve: stock_qty--/reserved_qty--,
order → confirmed (operatorga tushadi). Reject: sabab (settings'ga qarab), mijozga xabar.
"""
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, NotFoundError
from app.modules.audit.service import AuditService
from app.modules.catalog.repository import CatalogRepository
from app.modules.inbox.models import Customer
from app.modules.inbox.repository import InboxRepository
from app.modules.inbox.service import InboxService
from app.modules.notifications.service import NotificationService
from app.modules.orders.models import OrderStatus, OrderStatusHistory
from app.modules.orders.repository import OrdersRepository
from app.modules.payments.models import Payment, PaymentStatus
from app.modules.payments.repository import PaymentRepository
from app.modules.settings.repository import SettingsRepository

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PaymentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = PaymentRepository(db)
        self.orders = OrdersRepository(db)
        self.catalog = CatalogRepository(db)
        self.settings_repo = SettingsRepository(db)

    async def _setting(self, key: str, default=None):
        s = await self.settings_repo.get(key)
        return s.value if s is not None else default

    # ---------- Submit (AI/mijoz oqimi) ----------
    async def submit_payment(
        self, order_id: uuid.UUID, receipt_url: str, payer_name: str, *, card_id: uuid.UUID | None = None
    ) -> Payment:
        order = await self.orders.get(order_id)
        if order is None:
            raise NotFoundError("Buyurtma topilmadi")

        payment = await self.repo.get_by_order(order_id)
        if payment is not None and payment.status == PaymentStatus.approved.value:
            raise AppError("Bu buyurtma allaqachon to'langan")

        if payment is None:
            payment = Payment(order_id=order_id)
            await self.repo.add(payment)
        # rad etilgan bo'lsa qayta yuborish — yangilaymiz
        if card_id is None:
            primary = await self.repo.get_primary_card()
            card_id = primary.id if primary is not None else None
        payment.status = PaymentStatus.pending.value
        payment.receipt_url = receipt_url
        payment.payer_name = payer_name
        payment.card_id = card_id
        payment.reject_reason = None
        payment.reviewed_by = None
        payment.reviewed_at = None

        # Order: waiting_payment → payment_review (chek ko'rib chiqilmoqda)
        if order.status in (OrderStatus.waiting_payment.value, OrderStatus.pending.value):
            order.history.append(
                OrderStatusHistory(
                    from_status=order.status, to_status=OrderStatus.payment_review.value, changed_by=None
                )
            )
            order.status = OrderStatus.payment_review.value

        await self.db.commit()

        # Owner/manager botiga xabar (best-effort)
        await NotificationService(self.db).notify_payment_review(payment, order)
        return await self.get(payment.id)

    # ---------- Approve (idempotent) ----------
    async def approve(self, payment_id: uuid.UUID, reviewer_id: uuid.UUID | None) -> Payment:
        payment = await self.get(payment_id)
        if payment.status == PaymentStatus.approved.value:
            return payment  # idempotent — takroriy bosishда o'zgarmaydi

        order = await self.orders.get(payment.order_id)
        if order is None:
            raise NotFoundError("Buyurtma topilmadi")

        payment.status = PaymentStatus.approved.value
        payment.reviewed_by = reviewer_id
        payment.reviewed_at = _utcnow()

        # TZ 10: approved → stock_qty--, reserved_qty--
        for item in order.items:
            variant = await self.catalog.get_variant(item.variant_id)
            if variant is not None:
                variant.stock_qty = max(0, variant.stock_qty - item.quantity)
                variant.reserved_qty = max(0, variant.reserved_qty - item.quantity)

        # Order: → confirmed (operatorga tushadi)
        order.history.append(
            OrderStatusHistory(from_status=order.status, to_status=OrderStatus.confirmed.value, changed_by=reviewer_id)
        )
        order.status = OrderStatus.confirmed.value

        await AuditService(self.db).record(
            action="payment.approve", entity_type="payment", entity_id=payment.id,
            actor_id=reviewer_id, after={"status": "approved", "order_id": str(order.id)},
        )
        await self.db.commit()
        await self._notify_customer(order.customer_id, "To'lovingiz tasdiqlandi! ✅ Buyurtmangiz tayyorlanmoqda.")
        return await self.get(payment_id)

    # ---------- Reject ----------
    async def reject(
        self, payment_id: uuid.UUID, reviewer_id: uuid.UUID | None, reason: str | None
    ) -> Payment:
        payment = await self.get(payment_id)
        if payment.status == PaymentStatus.approved.value:
            raise AppError("Tasdiqlangan to'lovni rad etib bo'lmaydi")

        if bool(await self._setting("reject_reason_required", False)) and not reason:
            raise AppError("Rad etish sababi ko'rsatilishi shart")

        payment.status = PaymentStatus.rejected.value
        payment.reject_reason = reason
        payment.reviewed_by = reviewer_id
        payment.reviewed_at = _utcnow()

        # TZ 10: to'lov rejected → reserved_qty-- (band bo'shaydi)
        order = await self.orders.get(payment.order_id)
        if order is not None:
            for item in order.items:
                variant = await self.catalog.get_variant(item.variant_id)
                if variant is not None:
                    variant.reserved_qty = max(0, variant.reserved_qty - item.quantity)

        await AuditService(self.db).record(
            action="payment.reject", entity_type="payment", entity_id=payment.id,
            actor_id=reviewer_id, after={"status": "rejected", "reason": reason},
        )
        await self.db.commit()
        msg = "To'lovingiz tasdiqlanmadi."
        if reason:
            msg += f" Sabab: {reason}"
        msg += " Iltimos, qayta urinib ko'ring."
        await self._notify_customer(order.customer_id, msg)
        return await self.get(payment_id)

    async def _notify_customer(self, customer_id: uuid.UUID, text: str) -> None:
        customer = await self.db.get(Customer, customer_id)
        if customer is None:
            return
        inbox = InboxService(InboxRepository(self.db))
        await inbox.notify_customer(customer_id, customer.channel, text)

    # ---------- O'qish ----------
    async def get(self, payment_id: uuid.UUID) -> Payment:
        payment = await self.repo.get(payment_id)
        if payment is None:
            raise NotFoundError("To'lov topilmadi")
        return payment

    async def list(self, **filters) -> list[Payment]:
        return await self.repo.list(**filters)


class PaymentCardService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = PaymentRepository(db)

    async def list_cards(self):
        return await self.repo.list_cards()

    async def create(self, data: dict):
        from app.modules.payments.models import PaymentCard

        if data.get("is_primary"):
            await self.repo.clear_primary()  # bitta primary bo'lishi uchun
        card = PaymentCard(**data)
        await self.repo.add(card)
        await self.db.commit()
        return card

    async def update(self, card_id: uuid.UUID, data: dict):
        card = await self.repo.get_card(card_id)
        if card is None:
            raise NotFoundError("Karta topilmadi")
        if data.get("is_primary"):
            await self.repo.clear_primary()
        for field, value in data.items():
            setattr(card, field, value)
        await self.db.commit()
        return card


async def handle_payment_callback(db: AsyncSession, data: str) -> str:
    """Telegram inline tugma (pay:approve:<id> / pay:reject:<id>) ni qayta ishlaydi.

    Tasdiqlovchi xodim — `settings.payment_reviewer_user_id` (bo'lsa), aks holda NULL.
    """
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "pay":
        return "Noma'lum buyruq"
    action, payment_id = parts[1], parts[2]

    reviewer_setting = await SettingsRepository(db).get("payment_reviewer_user_id")
    reviewer_id = None
    if reviewer_setting and reviewer_setting.value:
        try:
            reviewer_id = uuid.UUID(str(reviewer_setting.value))
        except (TypeError, ValueError):
            reviewer_id = None

    service = PaymentService(db)
    try:
        if action == "approve":
            await service.approve(uuid.UUID(payment_id), reviewer_id)
            return "✅ To'lov tasdiqlandi, buyurtma tayyorlanmoqda"
        if action == "reject":
            await service.reject(uuid.UUID(payment_id), reviewer_id, reason=None)
            return "❌ To'lov rad etildi"
    except AppError as exc:
        return exc.message
    return "Noma'lum amal"
