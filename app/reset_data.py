"""Ma'lumotlarni tozalash — user/role/config/reference'dan tashqari HAMMA jadval bo'shatiladi.

SAQLANADI (o'chirilmaydi):
  - RBAC/identity : user, role, permission, role_permission, user_role
  - Konfiguratsiya: setting, payment_card, integration_config (IG/TG kanal kalitlari)
  - Reference     : material, gender, stone
  - (alembic_version — migratsiya holati — baribir tegilmaydi)

O'CHIRILADI (bo'shatiladi): mahsulot/variant/media/kategoriya/box/combo, mijoz/suhbat/xabar,
  buyurtma/yetkazish/checkout, to'lov (payment), knowledge_base, audit_log, notification,
  bts_branch, customer_location, integration_event — qisqasi qolgan hammasi.

XAVFSIZLIK: default DRY-RUN (faqat nechta qator o'chishini ko'rsatadi). Haqiqiy o'chirish uchun:
    RESET_CONFIRM=yes  yoki  --yes

Ishga tushirish:
    docker compose exec -T api python -m app.reset_data            # DRY-RUN (xavfsiz)
    docker compose exec -T -e RESET_CONFIRM=yes api python -m app.reset_data   # HAQIQIY o'chirish
"""
import asyncio
import os
import sys

import app.core.models_registry  # noqa: F401 — barcha modelni metadata'ga yuklaydi
from sqlalchemy import text

from app.core.base_model import Base
from app.core.database import SessionLocal

# Saqlanadigan jadvallar (o'chirilmaydi). Qolgan hamma metadata jadvali bo'shatiladi.
PRESERVE: set[str] = {
    # --- RBAC / identity ---
    "user", "role", "permission", "role_permission", "user_role",
    # --- Konfiguratsiya (tizim ishlab turishi uchun) ---
    "setting", "payment_card", "integration_config",
    # --- Reference (mahsulot uchun katalog atamalari) ---
    "material", "gender", "stone",
}


def _wipe_tables() -> list[str]:
    """O'chiriladigan jadvallar = metadata'dagi hammasi − PRESERVE (yangi jadval ham avtomatik kiradi)."""
    return sorted(set(Base.metadata.tables) - PRESERVE)


async def _count(db, table: str) -> int:
    res = await db.execute(text(f'SELECT count(*) FROM "{table}"'))
    return int(res.scalar_one())


async def main() -> None:
    confirm = os.getenv("RESET_CONFIRM", "").lower() in ("yes", "1", "true") or "--yes" in sys.argv
    wipe = _wipe_tables()
    preserve = sorted(PRESERVE)

    async with SessionLocal() as db:
        print("=" * 66)
        print("SAQLANADI (tegilmaydi):")
        for t in preserve:
            n = await _count(db, t) if t in Base.metadata.tables else "?"
            print(f"  ✔ {t:22} {n} qator")

        print("\nO'CHIRILADI (bo'shatiladi):")
        total = 0
        for t in wipe:
            n = await _count(db, t)
            total += n
            print(f"  ✗ {t:22} {n} qator")
        print("-" * 66)
        print(f"  Jami o'chiriladigan qatorlar: {total}  ({len(wipe)} jadval)")
        print("=" * 66)

        if not confirm:
            print("\n[DRY-RUN] Hech narsa o'chirilmadi.")
            print("Haqiqiy o'chirish:  RESET_CONFIRM=yes ... python -m app.reset_data")
            return

        # Bir TRUNCATE ... CASCADE — jadvallararo FK'larni o'zi hal qiladi, PK ketma-ketligi qayta boshlanadi.
        quoted = ", ".join(f'"{t}"' for t in wipe)
        await db.execute(text(f"TRUNCATE {quoted} RESTART IDENTITY CASCADE"))
        await db.commit()
        print(f"\n✅ O'CHIRILDI: {total} qator, {len(wipe)} jadval bo'shatildi.")
        print("   user/role/config/reference saqlab qolindi. Tizim ishlab turadi.")


if __name__ == "__main__":
    asyncio.run(main())
