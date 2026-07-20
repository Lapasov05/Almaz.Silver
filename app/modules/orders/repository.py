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

    async def list(
        self,
        *,
        status: str | None = None,
        customer_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Order]:
        stmt = select(Order).options(*_ORDER_LOADERS)
        if status is not None:
            stmt = stmt.where(Order.status == status)
        if customer_id is not None:
            stmt = stmt.where(Order.customer_id == customer_id)
        stmt = stmt.order_by(Order.created_at.desc()).limit(limit).offset(offset)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())
