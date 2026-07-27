"""TG + IG webhook to'liq self-test (diagnostika).

Ishga tushirish (konteyner ichida):
    docker compose exec api python -m app.webhook_selftest
yoki:  make test-webhooks

Nima tekshiradi:
  A) Config    — DB'да tokenlar bormi (integration_config).
  B) Ulanish   — Telegram getWebhookInfo/getMe, Instagram me + me/subscribed_apps
                 (Meta/Telegram tomonда webhook ulanганmi, xatolar bormi).
  C) Pipeline  — IMZOLANGAN webhook POST -> localhost:8000 -> xabar DB'га saqlandimi.
                 + noto'g'ri imzo -> 401 (himoya ishlaydimi).

C o'tsa: ichki kod (webhook->parse->ingest) TO'LIQ ishlaydi. Real xabar kelmasa —
muammo FAQAT Meta/Telegram yetkazishида (app rejimi, field obuna, akkaunt roli), kodда emas.

Sintetik ma'lumot test oxirida o'chiriladi. Real foydalanuvchiga xabar bormaydi (soxta id).
"""
import asyncio
import hashlib
import hmac
import json

import httpx
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.modules.inbox.models import Conversation, Customer, Message
from app.modules.integrations.service import get_config_value

settings = get_settings()
APP = "http://localhost:8000"

# Soxta (hech qachon real bo'lmaydigan) test id'lari — cleanup shu bo'yicha
TG_ID = "selftest-tg-000000"
IG_ID = "selftest-ig-000000"
TG_TEXT = "SELF-TEST telegram xabari"
IG_TEXT = "SELF-TEST instagram xabari"

PASS: list[str] = []
FAIL: list[str] = []
WARN: list[str] = []


def ok(name: str, cond: bool, detail: str = "") -> bool:
    (PASS if cond else FAIL).append(name)
    print(f"    {'✅' if cond else '❌'} {name}" + (f" — {detail}" if detail else ""))
    return cond


def info(name: str, detail: str = "") -> None:
    print(f"    •  {name}" + (f": {detail}" if detail else ""))


def warn(name: str) -> None:
    WARN.append(name)
    print(f"    ⚠️  {name}")


# ==================== A) Config ====================
async def check_config(db) -> None:
    print("\n[A] Config (integration_config) ─────────────────────────")
    for prov, keys in (("telegram", ("bot_token", "webhook_secret")),
                       ("instagram", ("access_token", "verify_token", "app_secret"))):
        for key in keys:
            val = await get_config_value(db, prov, key)
            ok(f"{prov}/{key} sozlangan", bool(val), (val[:10] + "…") if val else "BO'SH")


# ==================== B) Real ulanish ====================
async def check_telegram_connectivity(db) -> None:
    print("\n[B1] Telegram ulanish (getWebhookInfo/getMe) ────────────")
    token = await get_config_value(db, "telegram", "bot_token")
    if not token:
        warn("telegram bot_token yo'q — o'tkazib yuborildi")
        return
    base = settings.telegram_api_base_url.rstrip("/")
    async with httpx.AsyncClient(timeout=15) as c:
        me = (await c.get(f"{base}/bot{token}/getMe")).json()
        ok("bot token yaroqli (getMe)", me.get("ok"), (me.get("result") or {}).get("username", me))
        wh = (await c.get(f"{base}/bot{token}/getWebhookInfo")).json()
    r = wh.get("result") or {}
    url = r.get("url") or ""
    ok("webhook URL o'rnatilgan", bool(url), url or "BO'SH — make tg-set-webhook URL=...")
    info("pending_update_count", str(r.get("pending_update_count")))
    if r.get("last_error_message"):
        warn(f"oxirgi yetkazish XATOSI: {r.get('last_error_message')}")
    else:
        info("oxirgi xato", "yo'q ✅")
    if r.get("ip_address"):
        info("ip_address", r.get("ip_address"))


async def check_instagram_connectivity(db) -> None:
    print("\n[B2] Instagram ulanish (me + subscribed_apps) ───────────")
    token = await get_config_value(db, "instagram", "access_token")
    if not token:
        warn("instagram access_token yo'q — o'tkazib yuborildi")
        return
    base = settings.instagram_graph_base_url.rstrip("/")
    ver = settings.instagram_graph_version
    info("graph base", f"{base}/{ver}  (IGAA token -> graph.instagram.com bo'lishi kerak)")
    async with httpx.AsyncClient(timeout=15) as c:
        me = (await c.get(f"{base}/{ver}/me",
                          params={"fields": "id,username", "access_token": token})).json()
        if "error" in me:
            ok("access_token yaroqli (me)", False, me["error"].get("message"))
        else:
            ok("access_token yaroqli (me)", bool(me.get("id")),
               f"@{me.get('username')} (id={me.get('id')})")
        sub = (await c.get(f"{base}/{ver}/me/subscribed_apps",
                           params={"access_token": token})).json()
    if "error" in sub:
        ok("me/subscribed_apps o'qildi", False, sub["error"].get("message"))
        return
    apps = sub.get("data") or []
    fields: list[str] = []
    for a in apps:
        fields += a.get("subscribed_fields") or []
    ok("akkaunt obuna qilingan (subscribed_apps)", bool(apps), f"apps={len(apps)}")
    ok("'messages' fieldга obuna", "messages" in fields, ", ".join(fields) or "yo'q")


# ==================== C) Lokal end-to-end pipeline ====================
async def _customer_message(db, channel: str, external_id: str) -> tuple[Customer | None, Message | None]:
    """Sintetik mijoz + oxirgi kiruvchi xabarni topadi (tekshiruv uchun)."""
    cust = (await db.execute(
        select(Customer).where(Customer.channel == channel, Customer.external_id == external_id)
    )).scalar_one_or_none()
    if not cust:
        return None, None
    msg = (await db.execute(
        select(Message).join(Conversation, Message.conversation_id == Conversation.id)
        .where(Conversation.customer_id == cust.id, Message.direction == "incoming")
        .order_by(Message.created_at.desc()).limit(1)
    )).scalar_one_or_none()
    return cust, msg


async def _cleanup(db, channel: str, external_id: str) -> None:
    """Sintetik mijozni o'chiradi (conversation/message CASCADE bilan ketadi)."""
    await db.execute(delete(Customer).where(
        Customer.channel == channel, Customer.external_id == external_id))
    await db.commit()


async def test_telegram_pipeline(db) -> None:
    print("\n[C1] Telegram pipeline (imzolangan POST -> ingest) ──────")
    secret = await get_config_value(db, "telegram", "webhook_secret")
    update = {
        "update_id": 999_000_001,
        "message": {
            "message_id": 900001,
            "from": {"id": TG_ID, "is_bot": False, "first_name": "SelfTest",
                     "username": "selftest_user"},
            "chat": {"id": TG_ID, "type": "private"},
            "date": 0, "text": TG_TEXT, "selftest": True,
        },
    }
    raw = json.dumps(update).encode()
    hdr = {"Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=15) as c:
        # 1) Noto'g'ri secret -> 401 (secret sozlangan bo'lsa)
        if secret:
            r_bad = await c.post(f"{APP}/webhooks/telegram", content=raw,
                                 headers={**hdr, "X-Telegram-Bot-Api-Secret-Token": "WRONG"})
            ok("noto'g'ri secret -> 401", r_bad.status_code == 401, f"status={r_bad.status_code}")
        else:
            warn("webhook_secret yo'q — imzo tekshiruvi o'chiq (dev)")
        # 2) To'g'ri secret -> 200
        good_hdr = {**hdr}
        if secret:
            good_hdr["X-Telegram-Bot-Api-Secret-Token"] = secret
        r = await c.post(f"{APP}/webhooks/telegram", content=raw, headers=good_hdr)
    ok("to'g'ri secret -> 200", r.status_code == 200, f"status={r.status_code}")
    # 3) Xabar DB'га saqlandimi
    cust, msg = await _customer_message(db, "telegram", TG_ID)
    ok("mijoz yaratildi", cust is not None)
    ok("kiruvchi xabar saqlandi", msg is not None and (msg.content or "") == TG_TEXT,
       (msg.content if msg else "yo'q"))
    await _cleanup(db, "telegram", TG_ID)
    info("cleanup", "sintetik telegram mijoz o'chirildi")


async def test_instagram_pipeline(db) -> None:
    print("\n[C2] Instagram pipeline (imzolangan POST -> ingest) ─────")
    app_secret = await get_config_value(db, "instagram", "app_secret")
    payload = {
        "object": "instagram",
        "entry": [{
            "id": "selftest-page", "time": 0,
            "messaging": [{
                "sender": {"id": IG_ID}, "recipient": {"id": "selftest-page"}, "timestamp": 0,
                "message": {"mid": "selftest-mid-1", "text": IG_TEXT},
            }],
        }],
    }
    raw = json.dumps(payload).encode()
    hdr = {"Content-Type": "application/json"}

    def sign(secret: str) -> str:
        return "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()

    async with httpx.AsyncClient(timeout=15) as c:
        # 1) Noto'g'ri imzo -> 401 (app_secret sozlangan bo'lsa)
        if app_secret:
            r_bad = await c.post(f"{APP}/webhooks/instagram", content=raw,
                                 headers={**hdr, "X-Hub-Signature-256": "sha256=deadbeef"})
            ok("noto'g'ri imzo -> 401", r_bad.status_code == 401, f"status={r_bad.status_code}")
        else:
            warn("app_secret yo'q — imzo tekshiruvi o'chiq (dev)")
        # 2) To'g'ri imzo -> 200
        good_hdr = {**hdr}
        if app_secret:
            good_hdr["X-Hub-Signature-256"] = sign(app_secret)
        r = await c.post(f"{APP}/webhooks/instagram", content=raw, headers=good_hdr)
    ok("to'g'ri imzo -> 200", r.status_code == 200, f"status={r.status_code}")
    # 3) Xabar DB'га saqlandimi
    cust, msg = await _customer_message(db, "instagram", IG_ID)
    ok("mijoz yaratildi", cust is not None)
    ok("kiruvchi xabar saqlandi", msg is not None and (msg.content or "") == IG_TEXT,
       (msg.content if msg else "yo'q"))
    await _cleanup(db, "instagram", IG_ID)
    info("cleanup", "sintetik instagram mijoz o'chirildi")


async def main() -> None:
    print("═" * 62)
    print("  ALMAZ — TG + IG webhook self-test")
    print("═" * 62)
    async with SessionLocal() as db:
        await check_config(db)
        try:
            await check_telegram_connectivity(db)
        except Exception as e:  # noqa: BLE001
            warn(f"telegram ulanish tekshiruvi xato: {e}")
        try:
            await check_instagram_connectivity(db)
        except Exception as e:  # noqa: BLE001
            warn(f"instagram ulanish tekshiruvi xato: {e}")
        await test_telegram_pipeline(db)
        await test_instagram_pipeline(db)

    print("\n" + "═" * 62)
    print(f"  Natija: {len(PASS)}/{len(PASS) + len(FAIL)} o'tdi"
          + (f" · {len(WARN)} ogohlantirish" if WARN else ""))
    if FAIL:
        print("  ❌ Yiqilgan:", ", ".join(FAIL))
    print("═" * 62)
    if FAIL:
        print("\n  [C] pipeline yiqilsa -> ichki kod muammosi (loglarни ko'ring).")
        raise SystemExit(1)
    print("\n  ✅ Ichki pipeline TO'LIQ ishlaydi.")
    print("     Real xabar hali kelmasa -> muammo Meta/Telegram YETKAZISHида:")
    print("     • Telegram: [B1] webhook URL + oxirgi xato yo'qligini tekshiring.")
    print("     • Instagram: [B2] 'messages' fieldга obuna bo'lsin + Meta App REJIMI:")
    print("       - Dev rejimда faqat app'да ROLI bor akkauntlar (admin/tester) xabari keladi.")
    print("       - Meta App Dashboard -> Webhooks -> Instagram -> 'messages' fieldни belgilang.")
    print("       - Biznes akkaunt Professional bo'lsin va app'га ulangan bo'lsin.")


if __name__ == "__main__":
    asyncio.run(main())
