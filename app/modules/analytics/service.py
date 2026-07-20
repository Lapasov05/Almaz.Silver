"""analytics Service — KPI dashboard (TZ 1).

AI KPI'lari: Sales Conversion, Lead Conversion, AI yaratgan buyurtmalar, operator yukini
kamaytirish (AI mustaqil hal qilgan suhbatlar ulushi). Barchasi CRM ma'lumotidan hisoblanadi.
"""
from decimal import Decimal

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.inbox.models import Conversation, Message
from app.modules.orders.models import Order, OrderStatus
from app.modules.payments.models import Payment, PaymentStatus

# To'langan/bajarilgan deb hisoblanadigan buyurtma holatlari (daromad uchun)
_PAID_STATUSES = [
    OrderStatus.confirmed.value,
    OrderStatus.preparing.value,
    OrderStatus.packed.value,
    OrderStatus.shipping.value,
    OrderStatus.delivered.value,
    OrderStatus.completed.value,
]


class AnalyticsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _scalar(self, stmt) -> int:
        return int((await self.db.execute(stmt)).scalar_one() or 0)

    async def dashboard(self) -> dict:
        conversations_total = await self._scalar(select(func.count(Conversation.id)))

        # AI mustaqil hal qilgan suhbatlar: operator xabari YO'Q, lekin AI xabari BOR suhbatlar
        convs_with_operator = select(distinct(Message.conversation_id)).where(Message.sender_type == "operator")
        convs_with_ai = select(distinct(Message.conversation_id)).where(Message.sender_type == "ai")
        ai_handled = await self._scalar(
            select(func.count()).select_from(
                convs_with_ai.except_(convs_with_operator).subquery()
            )
        )

        orders_total = await self._scalar(select(func.count(Order.id)))
        ai_orders = await self._scalar(select(func.count(Order.id)).where(Order.created_by_ai.is_(True)))

        # Buyurtmalar holat bo'yicha
        status_rows = (
            await self.db.execute(select(Order.status, func.count(Order.id)).group_by(Order.status))
        ).all()
        orders_by_status = {row[0]: int(row[1]) for row in status_rows}

        # Daromad (to'langan buyurtmalar grand_total yig'indisi)
        revenue = (
            await self.db.execute(
                select(func.coalesce(func.sum(Order.grand_total), 0)).where(Order.status.in_(_PAID_STATUSES))
            )
        ).scalar_one()

        payments_total = await self._scalar(select(func.count(Payment.id)))
        payments_approved = await self._scalar(
            select(func.count(Payment.id)).where(Payment.status == PaymentStatus.approved.value)
        )

        # Lead: xabar yozgan mijozlar (conversations_total ~ leadlar); malakali lead — buyurtma bergan
        customers_with_orders = await self._scalar(select(func.count(distinct(Order.customer_id))))

        return {
            "conversations_total": conversations_total,
            "orders_total": orders_total,
            "ai_created_orders": ai_orders,                       # KPI 3
            "revenue": _num(revenue),
            "orders_by_status": orders_by_status,
            "payments": {
                "total": payments_total,
                "approved": payments_approved,
                "approval_rate": _ratio(payments_approved, payments_total),
            },
            "kpi": {
                # KPI 1 — Sales Conversion (suhbatdan buyurtmaga)
                "sales_conversion": _ratio(orders_total, conversations_total),
                # KPI 2 — Lead Conversion (malakali lead = buyurtma bergan)
                "lead_conversion": _ratio(customers_with_orders, conversations_total),
                # KPI 4 — Operator yukini kamaytirish (AI mustaqil hal qilgan suhbatlar ulushi)
                "ai_handled_share": _ratio(ai_handled, conversations_total),
            },
        }


def _num(value) -> float:
    return float(value) if value is not None else 0.0


def _ratio(part: int, whole: int) -> float:
    return round(part / whole, 4) if whole else 0.0
