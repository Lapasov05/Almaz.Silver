"""delivery Repository qatlami."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.delivery.models import CheckoutToken, Delivery


class DeliveryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add(self, obj):
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def get(self, delivery_id: uuid.UUID) -> Delivery | None:
        return await self.db.get(Delivery, delivery_id)

    async def get_by_order(self, order_id: uuid.UUID) -> Delivery | None:
        res = await self.db.execute(select(Delivery).where(Delivery.order_id == order_id))
        return res.scalar_one_or_none()

    async def get_token_by_hash(self, token_hash: str) -> CheckoutToken | None:
        res = await self.db.execute(
            select(CheckoutToken)
            .options(selectinload(CheckoutToken.delivery))
            .where(CheckoutToken.token_hash == token_hash)
        )
        return res.scalar_one_or_none()
