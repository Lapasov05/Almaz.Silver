"""Demo box (rangli quti) ma'lumotlari — mavjud kategoriyalarga ranglar qo'shadi.

Har kategoriyaga 6 xil rang (2 tekin + 4 pulli), turli count bilan. `boxes_enabled=true` qiladi.
IDEMPOTENT: boxlari bor kategoriyalar o'tkazib yuboriladi (--force bilan ular ham to'ldiriladi).

Ishga tushirish:
    docker compose exec api python -m app.demo_boxes
    docker compose exec api python -m app.demo_boxes --force
"""
import asyncio
import sys
from decimal import Decimal

import app.core.models_registry  # noqa: F401 — barcha model
from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.modules.catalog.models import Box, BoxMedia, Category
from app.modules.settings.models import Setting

# (rang nomi, hex, narx, count) — 2 tekin (0) + 4 pulli
DEMO_COLORS = [
    ("Qora", "#111111", "0", 20),
    ("Oq", "#FFFFFF", "0", 15),
    ("Qizil", "#E53935", "5000", 10),
    ("Ko'k", "#1E88E5", "5000", 8),
    ("Yashil", "#43A047", "8000", 5),
    ("Tilla", "#D4AF37", "12000", 3),
]


async def _ensure_boxes_enabled(db) -> None:
    row = (await db.execute(select(Setting).where(Setting.key == "boxes_enabled"))).scalar_one_or_none()
    if row is None:
        db.add(Setting(key="boxes_enabled", value=True))
    elif not row.value:
        row.value = True


async def main() -> None:
    force = "--force" in sys.argv
    filled, skipped, boxes_added = 0, 0, 0

    async with SessionLocal() as db:
        await _ensure_boxes_enabled(db)

        cats = (await db.execute(select(Category).order_by(Category.name_uz))).scalars().all()
        if not cats:
            print("⚠️  Kategoriya yo'q — avval `python -m app.demo_seed` ni ishga tushiring.")
            return

        for cat in cats:
            existing = (await db.execute(
                select(func.count()).select_from(Box).where(
                    Box.category_id == cat.id, Box.deleted_at.is_(None)
                )
            )).scalar() or 0
            if existing > 0 and not force:
                skipped += 1
                continue
            for i, (name, hex_, price, stock) in enumerate(DEMO_COLORS):
                box = Box(
                    category_id=cat.id,
                    name_uz=name,
                    color_hex=hex_,
                    price=Decimal(price),
                    stock_qty=stock,
                    sort_order=i,
                )
                # Demo galereya rasmi (placeholder — rangga mos)
                box.media.append(BoxMedia(
                    image_url=f"https://placehold.co/600x600/{hex_.lstrip('#')}/ffffff.png",
                    sort_order=0,
                ))
                db.add(box)
                boxes_added += 1
            filled += 1

        await db.commit()

    print(f"✅ Demo box: {filled} kategoriya to'ldirildi ({boxes_added} rang), "
          f"{skipped} o'tkazib yuborildi (boxlari bor).")
    print("   Ko'rish: GET /catalog/categories/{id}/boxes")


if __name__ == "__main__":
    asyncio.run(main())
