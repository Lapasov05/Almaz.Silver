"""orders Repository qatlami."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.orders.models import Order

_ORDER_LOADERS = (selectinload(Order.items), selectinload(Order.history))


class OrdersRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add(self, obj):
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def get(self, order_id: uuid.UUID) -> Order | None:
        res = await self.db.execute(
            select(Order).options(*_ORDER_LOADERS).where(Order.id == order_id)
        )
        return res.scalar_one_or_none()

    async def order_no_exists(self, order_no: str) -> bool:
        res = await self.db.execute(select(Order.id).where(Order.order_no == order_no))
        return res.scalar_one_or_none() is not None

    # Double-order himoyasi: mijozning faol (hali to'lanmagan/yakunlanmagan) buyurtmasi.
    # Bu holatlar zaxirани band qilib turadi — AI yangi buyurtма yaratmasin, shuni davom ettirsin.
    _ACTIVE_STATUSES = ("draft", "pending", "waiting_payment", "payment_review")

    async def get_active_order(self, customer_id: uuid.UUID) -> Order | None:
        """Mijozning eng so'nggi faol (to'lanmagan) buyurtmasi; yo'q bo'lsa None."""
        res = await self.db.execute(
            select(Order)
            .options(*_ORDER_LOADERS)
            .where(Order.customer_id == customer_id, Order.status.in_(self._ACTIVE_STATUSES))
            .order_by(Order.created_at.desc())
            .limit(1)
        )
        return res.scalar_one_or_none()

    async def list_active_orders(self, customer_id: uuid.UUID) -> list[Order]:
        """Mijozning barcha faol (to'lanmagan) buyurtmalari — supersede uchun."""
        res = await self.db.execute(
            select(Order)
            .options(*_ORDER_LOADERS)
            .where(Order.customer_id == customer_id, Order.status.in_(self._ACTIVE_STATUSES))
            .order_by(Order.created_at.desc())
        )
        return list(res.scalars().all())

    async def get_latest_order(self, customer_id: uuid.UUID) -> Order | None:
        """Mijozning eng so'nggi buyurtmasi (har qanday statusда) — status so'rovi uchun."""
        res = await self.db.execute(
            select(Order)
            .options(*_ORDER_LOADERS)
            .where(Order.customer_id == customer_id)
            .order_by(Order.created_at.desc())
            .limit(1)
        )
        return res.scalar_one_or_none()

    async def list(
        self,
        *,
        pp=None,
        status: str | None = None,
        customer_id: uuid.UUID | None = None,
        assigned_operator_id: uuid.UUID | None = None,
        created_by_ai: bool | None = None,
        order_no: str | None = None,
        date_from=None,
        date_to=None,
    ):
        from app.core.pagination import paginate

        stmt = select(Order)
        if status is not None:
            stmt = stmt.where(Order.status == status)
        if customer_id is not None:
            stmt = stmt.where(Order.customer_id == customer_id)
        if assigned_operator_id is not None:
            stmt = stmt.where(Order.assigned_operator_id == assigned_operator_id)
        if created_by_ai is not None:
            stmt = stmt.where(Order.created_by_ai.is_(created_by_ai))
        if order_no:
            stmt = stmt.where(Order.order_no.ilike(f"%{order_no}%"))
        if date_from is not None:
            stmt = stmt.where(Order.created_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(Order.created_at <= date_to)
        return await paginate(self.db, stmt, [Order.created_at.desc()], pp, loaders=_ORDER_LOADERS)
