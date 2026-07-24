"""Umumiy pagination — barcha ro'yxat (GET) endpointlari uchun.

Javob shakli: {items, total, limit, offset}. `paginate()` bir xil filtrlangan
`select()` bo'yicha ham sahifani, ham umumiy sonni (total) qaytaradi.
"""
from typing import Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class PageParams:
    """FastAPI dependency — limit/offset (`Depends(page_params)`)."""

    def __init__(self, limit: int, offset: int):
        self.limit = limit
        self.offset = offset


def page_params(
    limit: int = Query(default=50, ge=1, le=200, description="Sahifa hajmi"),
    offset: int = Query(default=0, ge=0, description="Boshlanish (siljish)"),
) -> PageParams:
    return PageParams(limit=limit, offset=offset)


# Lug'at/dropdown endpointlar uchun kattaroq default (frontend hammasini bir marta oladi)
def page_params_ref(
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> PageParams:
    return PageParams(limit=limit, offset=offset)


async def paginate(
    db: AsyncSession,
    base_stmt,
    order_by,
    pp: PageParams,
    *,
    loaders: tuple = (),
) -> tuple[list, int]:
    """(rows, total) qaytaradi.

    base_stmt: `select(Model).where(...)` (loader/order/limitsiz).
    order_by: tartib ustunlari ro'yxati. loaders: selectinload'lar (faqat items uchun).
    """
    total = (
        await db.execute(select(func.count()).select_from(base_stmt.order_by(None).subquery()))
    ).scalar_one()

    stmt = base_stmt
    for loader in loaders:
        stmt = stmt.options(loader)
    stmt = stmt.order_by(*order_by).limit(pp.limit).offset(pp.offset)
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows), int(total)
