"""Chatlarni tozalash — barcha SUHBAT (conversation) va XABAR (message) o'chiriladi.

Inbox butunlay bo'shaydi. MIJOZLAR (customer) va BUYURTMALAR (order) SAQLANADI — faqat yozishmalar
o'chadi (ular mijoz/buyurtmaga FK bilan bog'lanmagan, xavfsiz). Yangi xabar kelsa yangi suhbat ochiladi.

XAVFSIZLIK: default DRY-RUN (faqat nechta o'chishini ko'rsatadi). Haqiqiy o'chirish uchun:
    RESET_CHATS_CONFIRM=yes  yoki  --yes

Ishga tushirish:
    docker compose exec -T api python -m app.reset_chats                      # DRY-RUN (xavfsiz)
    docker compose exec -T -e RESET_CHATS_CONFIRM=yes api python -m app.reset_chats   # HAQIQIY o'chirish
"""
import asyncio
import os
import sys

import app.core.models_registry  # noqa: F401
from sqlalchemy import text

from app.core.database import SessionLocal

# O'chiriladigan jadvallar (chat = suhbat + xabar). Tartib muhim emas — CASCADE hal qiladi.
_CHAT_TABLES = ("message", "conversation")


async def _count(db, table: str) -> int:
    res = await db.execute(text(f'SELECT count(*) FROM "{table}"'))
    return int(res.scalar_one())


async def main() -> None:
    confirm = os.getenv("RESET_CHATS_CONFIRM", "").lower() in ("yes", "1", "true") or "--yes" in sys.argv
    async with SessionLocal() as db:
        counts = {t: await _count(db, t) for t in _CHAT_TABLES}
        cust_n = await _count(db, "customer")
        order_n = await _count(db, "order")  # _count o'zi "order" ni qo'shtirnoq bilan o'raydi

        print("=" * 62)
        print("CHATLARNI TOZALASH")
        print("-" * 62)
        print("O'CHIRILADI:")
        for t in _CHAT_TABLES:
            print(f"  ✗ {t:14} {counts[t]} qator")
        print("SAQLANADI (tegilmaydi):")
        print(f"  ✔ customer       {cust_n} ta mijoz")
        print(f"  ✔ order          {order_n} ta buyurtma")
        print("=" * 62)

        if not confirm:
            print("\n[DRY-RUN] Hech narsa o'chirilmadi.")
            print("Haqiqiy o'chirish:  RESET_CHATS_CONFIRM=yes ... python -m app.reset_chats")
            return

        quoted = ", ".join(f'"{t}"' for t in _CHAT_TABLES)
        await db.execute(text(f"TRUNCATE {quoted} RESTART IDENTITY CASCADE"))
        await db.commit()
        total = sum(counts.values())
        print(f"\n✅ O'CHIRILDI: {counts['conversation']} suhbat + {counts['message']} xabar ({total} qator).")
        print("   Mijozlar va buyurtmalar saqlab qolindi. Inbox bo'sh.")


if __name__ == "__main__":
    asyncio.run(main())
