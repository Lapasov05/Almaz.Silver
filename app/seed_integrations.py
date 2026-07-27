"""Integration configlarni (tokenlarni) DB'ga kiritish skripti — misol/boshlang'ich.

Har `(provider, key)` uchun bitta qator yaratadi. Qiymat: `.env`da bo'lsa o'shandan olinadi,
aks holda placeholder qoldiriladi (admin API orqali to'ldiradi). IDEMPOTENT — mavjud (bo'sh
bo'lmagan) qiymatlarni O'ZGARTIRMAYDI.

Ishga tushirish:
    docker compose exec api python -m app.seed_integrations
Majburan qayta yozish (mavjudlarni ham):
    docker compose exec api python -m app.seed_integrations --force
"""
import asyncio
import sys

from sqlalchemy import select

from app.core.database import SessionLocal
from app.modules.integrations.models import IntegrationConfig

# (provider, key, placeholder) — tokenlar FAQAT DB'да; bu placeholder'larni API orqali almashtiring
DEMO_INTEGRATIONS = [
    ("telegram", "bot_token", "123456:ABC-DEF-bot-token-bu-yerga"),
    ("telegram", "webhook_secret", "webhook-maxfiy-kalit"),
    ("instagram", "access_token", "IGAAxxxxxxxx-access-token"),
    ("instagram", "verify_token", "verify-token-meta-konsolда-bir-xil"),
    ("instagram", "app_secret", "meta-app-secret-hmac-uchun"),
    ("openai", "api_key", "sk-...-openai-api-key"),
    ("openai", "base_url", ""),  # ixtiyoriy (Azure/proxy uchun)
]


async def main() -> None:
    force = "--force" in sys.argv
    created, updated, skipped = 0, 0, 0

    async with SessionLocal() as db:
        for provider, key, placeholder in DEMO_INTEGRATIONS:
            value = placeholder
            row = (
                await db.execute(
                    select(IntegrationConfig).where(
                        IntegrationConfig.provider == provider, IntegrationConfig.key == key
                    )
                )
            ).scalar_one_or_none()

            if row is None:
                db.add(IntegrationConfig(provider=provider, key=key, value=value, is_active=True))
                created += 1
            elif force:
                row.value = value
                updated += 1
            else:
                skipped += 1  # mavjud — tegilmaydi
        await db.commit()

    print(f"✅ Integration configlar: {created} yaratildi, {updated} yangilandi, {skipped} o'tkazib yuborildi.")
    print("   Ko'rish/o'zgartirish (admin token bilan):")
    print("     GET   /integrations/configs")
    print('     PATCH /integrations/configs/{id}  {"value": "<haqiqiy-token>"}')
    print("   Yoki:")
    print('     POST  /integrations/configs  {"provider":"telegram","key":"bot_token","value":"<token>"}')


if __name__ == "__main__":
    asyncio.run(main())
