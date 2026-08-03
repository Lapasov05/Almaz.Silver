"""Rangli qutilar (box) seed — PROD uchun. Har kategoriyaga standart rang palitrasi.

Sabab: jonli tizimда kategoriyalarда quti yo'q edi -> AI "quti mavjud emas" derdi va mijozlar
so'ragan "pushti quti"ni bera olmasdik (sotuv yo'qolardi). Bu seed shuni to'g'rilaydi.

- IDEMPOTENT: qutilari BOR kategoriya o'tkazib yuboriladi (`--force` bilan ular ham to'ldiriladi).
- Standart: hamma rang TEKIN (price=0) — quti mahsulotга bepul beriladi. Narx/zaxira/rangni keyin
  CRM'дан (kategoriya bo'limi) tahrirlash mumkin.
- `boxes_enabled=true` qilib qo'yadi.

Ishga tushirish:
    docker compose exec api python -m app.seed_boxes
    docker compose exec api python -m app.seed_boxes --force   # mavjud qutili kategoriyalarni ham
"""
import asyncio
import sys
from decimal import Decimal

import app.core.models_registry  # noqa: F401 — barcha model registratsiyasi
from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.modules.catalog.models import Box, Category
from app.modules.settings.models import Setting

# (rang nomi uz, rang nomi ru, hex, narx, zaxira). Hammasi TEKIN — do'kon bepul quti beradi.
# "Pushti" mijozlar eng ko'p so'ragan rang (chat tahlili) — birinchi qo'yildi.
PALETTE: list[tuple[str, str, str, str, int]] = [
    ("Pushti", "Розовый", "#FF6FA5", "0", 50),
    ("Oq", "Белый", "#FFFFFF", "0", 50),
    ("Qora", "Чёрный", "#111111", "0", 50),
    ("Qizil", "Красный", "#E53935", "0", 40),
    ("Ko'k", "Синий", "#1E88E5", "0", 40),
    ("Tilla", "Золотой", "#D4AF37", "0", 30),
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
            print("⚠️  Kategoriya yo'q — avval katalogni to'ldiring.")
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
            for i, (name_uz, name_ru, hex_, price, stock) in enumerate(PALETTE):
                db.add(Box(
                    category_id=cat.id,
                    name_uz=name_uz,
                    name_ru=name_ru,
                    color_hex=hex_,
                    price=Decimal(price),
                    stock_qty=stock,
                    sort_order=i,
                ))
                boxes_added += 1
            filled += 1

        await db.commit()

    print(f"✅ Box seed: {filled} kategoriya to'ldirildi ({boxes_added} rang), "
          f"{skipped} o'tkazib yuborildi (qutilari bor). Tekin, zaxira bilan.")
    print("   Rang/narx/zaxirani CRM (kategoriya bo'limi)dan tahrirlang.")


if __name__ == "__main__":
    asyncio.run(main())
