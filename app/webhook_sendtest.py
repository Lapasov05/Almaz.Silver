"""Jonli OUTBOUND test — TG/IG send API haqiqatan javob yuboradimi.

Ishga tushirish:
    make test-send                       # eng oxirgi real mijozga yuboradi (har kanal)
    make test-send TG=<chat_id> IG=<igsid>   # aniq oluvchiga

Nima qiladi: production yo'li bilan (build_channel_client -> DB token) haqiqiy
send_text chaqiradi va NATIJANI/XATONI to'liq bosib chiqaradi (yutmaydi).

Eslatma:
  • Telegram: oluvchi avval botga /start bosган bo'lishi kerak.
  • Instagram: oxirgi mijoz xabaridan 24 soat ичида bo'lishi kerak (Meta siyosati).
Test xabar HAQIQIY oluvchiga boradi — shuning uchun o'zingizga (yoki test akkauntга) yuboring.
"""
import asyncio
import os

from sqlalchemy import select

from app.core.database import SessionLocal
from app.modules.inbox.channels.base import ChannelError, strip_markdown
from app.modules.inbox.channels.factory import build_channel_client
from app.modules.inbox.models import Conversation, Customer

TEXT = "🔧 Almaz AI ulanish testi — bu avtomatik xabar, e'tibor bermang."


async def latest_recipient(db, channel: str):
    """Eng oxirgi REAL mijoz (sintetik selftest emas), faoliyati bo'yicha."""
    return (await db.execute(
        select(Customer.external_id, Customer.username)
        .join(Conversation, Conversation.customer_id == Customer.id)
        .where(
            Customer.channel == channel,
            Customer.external_id.notlike("selftest-%"),
            Customer.deleted_at.is_(None),
        )
        .order_by(Conversation.last_activity_at.desc())
        .limit(1)
    )).first()


async def send_one(db, channel: str, recipient: str) -> bool:
    client = await build_channel_client(db, channel)  # production yo'li (DB token)
    try:
        res = await client.send_text(recipient, strip_markdown(TEXT))
        print(f"  ✅ {channel}: YUBORILDI -> {recipient}  (msg_id={res.external_message_id})")
        return True
    except ChannelError as e:
        print(f"  ❌ {channel}: XATO -> {recipient}")
        print(f"     {e}")
        return False


async def main() -> None:
    tg_to = (os.environ.get("TG_TO") or "").strip()
    ig_to = (os.environ.get("IG_TO") or "").strip()
    print("═" * 62)
    print("  ALMAZ — jonli OUTBOUND send test (TG + IG)")
    print("═" * 62)

    results: list[bool] = []
    async with SessionLocal() as db:
        for channel, override in (("telegram", tg_to), ("instagram", ig_to)):
            print(f"\n[{channel}]")
            recipient = override
            if not recipient:
                row = await latest_recipient(db, channel)
                if not row:
                    print(f"  ⚠️  real mijoz topilmadi — {channel.upper()}=<id> bering "
                          f"yoki avval {channel}'га DM yozing")
                    continue
                recipient, uname = row
                print(f"  oxirgi real mijoz: {recipient}" + (f" (@{uname})" if uname else ""))
            results.append(await send_one(db, channel, recipient))

    print("\n" + "═" * 62)
    okc = sum(results)
    print(f"  Natija: {okc}/{len(results)} kanal javob yubordi")
    print("═" * 62)
    if okc < len(results) or not results:
        print("\n  ❌ XATO'ni yuqorида o'qing. Ko'p uchraydigan IG sabablari:")
        print("     • 24 soat oynasi tugagan (mijoz oxirgi xabaridan 24s o'tган).")
        print("     • Tokenда 'instagram_business_manage_messages' ruxsati yo'q.")
        print("     • Akkaunt/app ulanishi (Instagram Login) noto'g'ri.")
        raise SystemExit(1)
    print("\n  ✅ Send API ishlaydi — oluvchi(lar) test xabarini oldi.")


if __name__ == "__main__":
    asyncio.run(main())
