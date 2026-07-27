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

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.modules.integrations.models import IntegrationConfig

settings = get_settings()

# (provider, key, .env fallback, placeholder/izoh)
DEMO_INTEGRATIONS = [
    ("telegram", "bot_token", settings.telegram_bot_token, "123456:ABC-DEF-bot-token-bu-yerga"),
    ("telegram", "webhook_secret", settings.telegram_webhook_secret, "webhook-maxfiy-kalit"),
    ("instagram", "access_token", settings.instagram_page_access_token, "IGAAxxxxxxxx-access-token"),
    ("instagram", "verify_token", settings.instagram_verify_token, "verify-token-meta-konsolда-bir-xil"),
    ("instagram", "app_secret", settings.instagram_app_secret, "meta-app-secret-hmac-uchun"),
    ("openai", "api_key", settings.openai_api_key, "sk-...-openai-api-key"),
]


async def main() -> None:
    force = "--force" in sys.argv
    created, updated, skipped = 0, 0, 0

    async with SessionLocal() as db:
        for provider, key, env_value, placeholder in DEMO_INTEGRATIONS:
            value = env_value or placeholder            # .env bo'lsa o'sha, aks holda placeholder
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
