"""payments Repository qatlami."""
# `list` metodi sinf ichida builtin `list`ni soyalaydi — annotatsiyalarni kechiktiramiz
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PageParams, paginate
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

    async def list(
        self,
        *,
        pp: PageParams,
        status: str | None = None,
        order_id: uuid.UUID | None = None,
        reviewed_by: uuid.UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ):
        stmt = select(Payment)
        if status is not None:
            stmt = stmt.where(Payment.status == status)
        if order_id is not None:
            stmt = stmt.where(Payment.order_id == order_id)
        if reviewed_by is not None:
            stmt = stmt.where(Payment.reviewed_by == reviewed_by)
        if date_from is not None:
            stmt = stmt.where(Payment.created_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(Payment.created_at <= date_to)
        return await paginate(self.db, stmt, [Payment.created_at.desc()], pp)

    # ---------- Payment Card ----------
    async def get_card(self, card_id: uuid.UUID) -> PaymentCard | None:
        return await self.db.get(PaymentCard, card_id)

    async def list_cards(self, *, is_active: bool | None, pp: PageParams):
        stmt = select(PaymentCard)
        if is_active is not None:
            stmt = stmt.where(PaymentCard.is_active.is_(is_active))
        return await paginate(self.db, stmt, [PaymentCard.is_primary.desc(), PaymentCard.created_at.desc()], pp)

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
