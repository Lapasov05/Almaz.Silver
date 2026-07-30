"""AI promtlarni DB'ga (settings) yozadi — prodda bir marta ishga tushiriladi.

Registrdagi (app/modules/ai/prompt_registry.py) HAR bir AI matnini settings jadvaliga qo'yadi:
shundan keyin barcha AI promtlar DB'dan boshqariladi (settings API orqali tahrirlanadi), kod emas.

IDEMPOTENT: mavjud kalitni O'ZGARTIRMAYDI (prodda tahrirlaganingiz saqlanadi).
    --force  : mavjudlarni ham registr standart qiymati bilan QAYTA yozadi (tahrirlar yo'qoladi).

Har kalit uchun MAQSAD va QAYERDA ishlatilishi ekranga chiqadi — nima nima uchun ekani ko'rinib turadi.

Ishga tushirish:
    docker compose exec -T api python -m app.seed_ai_prompts
    docker compose exec -T -e FORCE=1 api python -m app.seed_ai_prompts   # qayta yozish
"""
import asyncio
import os
import sys

import app.core.models_registry  # noqa: F401
from app.core.database import SessionLocal
from app.modules.ai.prompt_registry import AI_PROMPTS
from app.modules.settings.repository import SettingsRepository


async def main() -> None:
    force = "--force" in sys.argv or os.getenv("FORCE", "").lower() in ("1", "true", "yes")
    added, updated, skipped = 0, 0, 0
    async with SessionLocal() as db:
        repo = SettingsRepository(db)
        print("=" * 78)
        print(f"AI PROMTLAR -> DB (settings). Jami: {len(AI_PROMPTS)} ta. force={force}")
        print("=" * 78)
        for p in AI_PROMPTS:
            key = p["key"]
            existing = await repo.get(key)
            ph = f"  [o'rinlar: {p['placeholders']}]" if p.get("placeholders") else ""
            if existing is None:
                await repo.upsert(key, p["value"])
                added += 1
                state = "➕ QO'SHILDI"
            elif force:
                await repo.upsert(key, p["value"])
                updated += 1
                state = "♻️  QAYTA YOZILDI"
            else:
                skipped += 1
                state = "⏭  BOR (o'zgarmadi)"
            print(f"\n{state}  {key}{ph}")
            print(f"   MAQSAD : {p['purpose']}")
            print(f"   QAYERDA: {p['used_in']}")
        await db.commit()
    print("\n" + "=" * 78)
    print(f"Natija: qo'shildi={added}, qayta yozildi={updated}, o'zgarmadi={skipped}")
    print("Endi barcha AI promtlar DB'da — settings API orqali tahrirlang (kalit = yuqoridagi nom).")
    print("=" * 78)


if __name__ == "__main__":
    asyncio.run(main())
