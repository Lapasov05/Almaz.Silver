"""Jonli typing_on test — IG/TG "yozyapti..." indikatori API'da ishlaydimi.

Ishga tushirish:
    make test-typing                       # oxirgi real mijozga
    make test-typing IG=<igsid> TG=<chatid>

Production yo'li (DB token) bilan haqiqiy typing so'rovini yuboradi va API javobini
(status + tana) TO'LIQ chiqaradi. Instagram qabul qilmasa — aniq xato ko'rinadi.
"""
import asyncio
import os

import httpx
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.modules.inbox.models import Conversation, Customer
from app.modules.integrations.service import get_config_value

settings = get_settings()


async def _latest(db, channel: str):
    return (await db.execute(
        select(Customer.external_id)
        .join(Conversation, Conversation.customer_id == Customer.id)
        .where(
            Customer.channel == channel,
            Customer.external_id.notlike("selftest-%"),
            Customer.deleted_at.is_(None),
        )
        .order_by(Conversation.last_activity_at.desc())
        .limit(1)
    )).scalar_one_or_none()


async def _test_instagram(db, rid: str) -> None:
    token = await get_config_value(db, "instagram", "access_token")
    if not token:
        print("  ⚠️  instagram access_token yo'q")
        return
    biz = (await get_config_value(db, "instagram", "business_id")).strip() or "me"
    base = settings.instagram_graph_base_url.rstrip("/")
    url = f"{base}/{settings.instagram_graph_version}/{biz}/messages"
    body = {"recipient": {"id": rid}, "sender_action": "typing_on"}
    print(f"  URL: {url}")
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(url, params={"access_token": token}, json=body)
    ok = r.status_code < 400
    print(f"  {'✅' if ok else '❌'} typing_on -> {r.status_code}: {r.text[:300]}")
    if not ok:
        print("     -> Instagram typing_on'ni rad etdi. Xato matnini o'qing (qo'llab-quvvatlash/token/oyna).")


async def _test_telegram(db, rid: str) -> None:
    token = await get_config_value(db, "telegram", "bot_token")
    if not token:
        print("  ⚠️  telegram bot_token yo'q")
        return
    base = settings.telegram_api_base_url.rstrip("/")
    url = f"{base}/bot{token}/sendChatAction"
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(url, json={"chat_id": rid, "action": "typing"})
    ok = r.status_code == 200 and r.json().get("ok")
    print(f"  {'✅' if ok else '❌'} sendChatAction(typing) -> {r.status_code}: {r.text[:200]}")


async def main() -> None:
    ig_to = (os.environ.get("IG_TO") or "").strip()
    tg_to = (os.environ.get("TG_TO") or "").strip()
    print("═" * 60)
    print("  Jonli typing_on test (IG + TG)")
    print("═" * 60)
    async with SessionLocal() as db:
        print("\n[instagram]")
        rid = ig_to or await _latest(db, "instagram")
        if not rid:
            print("  ⚠️  real IG mijoz topilmadi — IG=<igsid> bering yoki DM yozdiring")
        else:
            print(f"  oluvchi: {rid}")
            await _test_instagram(db, rid)

        print("\n[telegram]")
        rid2 = tg_to or await _latest(db, "telegram")
        if not rid2:
            print("  ⚠️  real TG mijoz topilmadi — TG=<chatid> bering yoki botga /start bosing")
        else:
            print(f"  oluvchi: {rid2}")
            await _test_telegram(db, rid2)
    print("\n" + "═" * 60)


if __name__ == "__main__":
    asyncio.run(main())
