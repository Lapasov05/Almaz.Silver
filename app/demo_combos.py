"""Demo combo (to'plam) ma'lumotlari — mavjud mahsulotlardan combolar yaratadi.

Har combo TURLI kategoriyadan 2-3 mahsulot + qo'lda narx. IDEMPOTENT: combo bo'lsa o'tkazadi.
Talab: avval `python -m app.demo_seed` (mahsulotlar bo'lishi kerak).

Ishga tushirish:
    docker compose exec api python -m app.demo_combos
"""
import asyncio
from decimal import Decimal

import app.core.models_registry  # noqa: F401
from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.modules.catalog.models import Product, Variant
from app.modules.catalog.repository import CatalogRepository
from app.modules.catalog.schemas import ComboCreate, ComboItemIn
from app.modules.catalog.service import CatalogService

DEMO_COMBOS = [
    ("Sevgi to'plami", Decimal("450000")),
    ("Sovg'a to'plami", Decimal("650000")),
]


async def _default_variant(db, product_id):
    return (await db.execute(
        select(Variant)
        .where(Variant.product_id == product_id, Variant.deleted_at.is_(None), Variant.is_active.is_(True))
        .order_by(Variant.created_at)
        .limit(1)
    )).scalar_one_or_none()


async def main() -> None:
    async with SessionLocal() as db:
        existing = (await db.execute(
            select(func.count()).select_from(Product).where(
                Product.is_combo.is_(True), Product.deleted_at.is_(None)
            )
        )).scalar() or 0
        if existing:
            print(f"⚠️  {existing} combo allaqachon bor — o'tkazib yuborildi.")
            return

        prods = (await db.execute(
            select(Product)
            .where(Product.is_combo.is_(False), Product.deleted_at.is_(None), Product.status == "active")
            .order_by(Product.category_id, Product.created_at)
        )).scalars().all()

        by_cat: dict = {}
        for p in prods:
            if p.category_id is not None:
                by_cat.setdefault(p.category_id, []).append(p)
        cats = list(by_cat.keys())
        if len(cats) < 2:
            print("⚠️  Combo uchun kamida 2 xil kategoriyada mahsulot kerak — avval `python -m app.demo_seed`.")
            return

        svc = CatalogService(CatalogRepository(db))
        created = 0
        for idx, (name, price) in enumerate(DEMO_COMBOS):
            picks: list[ComboItemIn] = []
            for cat in cats[:3]:  # 3 xil kategoriyadan 1 mahsulot
                lst = by_cat[cat]
                p = lst[idx % len(lst)]
                v = await _default_variant(db, p.id)
                if v is not None:
                    picks.append(ComboItemIn(variant_id=v.id, quantity=1))
            if len(picks) < 2:
                continue
            await svc.create_combo(ComboCreate(name_uz=name, price=price, status="active", items=picks))
            created += 1

        print(f"✅ Demo combo: {created} ta yaratildi (turli kategoriyadan mahsulotlar bilan).")
        print("   Ko'rish: GET /catalog/combos")


if __name__ == "__main__":
    asyncio.run(main())
