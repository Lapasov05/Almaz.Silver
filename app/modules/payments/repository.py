"""payments Repository qatlami."""
# `list` metodi sinf ichida builtin `list`ni soyalaydi — annotatsiyalarni kechiktiramiz
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payments.models import Payment, PaymentCard


class PaymentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add(self, obj):
        self.db.add(obj)
        await self.db.flush()
        return obj

    # ---------- Payment ----------
    async def get(self, payment_id: uuid.UUID) -> Payment | None:
        return await self.db.get(Payment, payment_id)

    async def get_by_order(self, order_id: uuid.UUID) -> Payment | None:
        res = await self.db.execute(select(Payment).where(Payment.order_id == order_id))
        return res.scalar_one_or_none()

    async def list(self, *, status: str | None = None, limit: int = 50, offset: int = 0) -> list[Payment]:
        stmt = select(Payment)
        if status is not None:
            stmt = stmt.where(Payment.status == status)
        stmt = stmt.order_by(Payment.created_at.desc()).limit(limit).offset(offset)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    # ---------- Payment Card ----------
    async def get_card(self, card_id: uuid.UUID) -> PaymentCard | None:
        return await self.db.get(PaymentCard, card_id)

    async def list_cards(self) -> list[PaymentCard]:
        res = await self.db.execute(select(PaymentCard).order_by(PaymentCard.is_primary.desc()))
        return list(res.scalars().all())

    async def get_primary_card(self) -> PaymentCard | None:
        res = await self.db.execute(
            select(PaymentCard).where(
                PaymentCard.is_primary.is_(True), PaymentCard.is_active.is_(True)
            )
        )
        return res.scalars().first()

    async def clear_primary(self) -> None:
        """Barcha kartalardan is_primary ni olib tashlaydi (bitta primary bo'lishi uchun)."""
        for card in await self.list_cards():
            if card.is_primary:
                card.is_primary = False
