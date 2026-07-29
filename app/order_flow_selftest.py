"""Buyurtma rasmiylashtirish oqimi — uchdan-uchiga smoke test (throwaway Postgres).

Tekshiradi (mijoz aytgan ketma-ketlik bo'yicha):
  1) Rasm URL normalizatsiyasi (localhost → public base) — send_media saqlagan attachment.
  2) send_product_images — har mahsulot rasmi + boyitilgan izoh (nom/narx/material/tosh).
  3) create_order → buyurtma + zaxira.
  4) request_location → checkout link; qayta chaqirilsa YANGI token (regeneratsiya).
  5) resolve_checkout → zona (Toshkent) + delivery_fee + grand_total.
  6) get_order_summary → items_total + delivery + jami + mijoz ma'lumotlari.
  7) get_payment_card → asosiy karta.
  8) submit_receipt → mijozning oxirgi rasmi → chek → to'lovga uzatiladi (order → payment_review).
  9) approve → order confirmed + mijozga xabar.
 10) get_order_status → status_text.

Ishga tushirish (env DB bilan):
  POSTGRES_HOST=localhost POSTGRES_PORT=55442 ... python -m app.order_flow_selftest
"""
import asyncio
import uuid
from decimal import Decimal

import app.core.models_registry  # noqa: F401
from app.modules.ai import tools as ai_tools
from app.modules.ai.tools import ToolContext, dispatch
from app.core.database import SessionLocal
from app.modules.catalog.schemas import ProductCreate, VariantCreate
from app.modules.catalog.repository import CatalogRepository
from app.modules.catalog.service import CatalogService
from app.modules.delivery.service import DeliveryService
from app.modules.inbox.models import Conversation, Customer, Message
from app.modules.orders.repository import OrdersRepository
from app.modules.payments.repository import PaymentRepository
from app.modules.payments.models import PaymentCard
from app.modules.payments.service import PaymentService

OK, FAIL = "✅", "❌"
_fails = []


def check(cond, label):
    print(f"  {OK if cond else FAIL} {label}")
    if not cond:
        _fails.append(label)


async def make_product(db, name, price, ring=False):
    svc = CatalogService(CatalogRepository(db))
    p = await svc.create_product(ProductCreate(
        name_uz=name, price=Decimal(price), status="active",
        variants=[VariantCreate(sku=f"SKU-{name[:4]}-{uuid.uuid4().hex[:5]}", stock_qty=10)],
        image_urls=["http://localhost:8000/uploads/2026/07/demo.jpg"],  # localhost — BUG holati
    ))
    return p


async def main():
    async with SessionLocal() as db:
        print("── Setup ──")
        # Uzuk (o'lchamli) va braslet (universal)
        uzuk = await make_product(db, "Sirli uzuk", "300000")
        braslet = await make_product(db, "Nafis braslet", "250000")
        check(uzuk and braslet, "2 ta mahsulot yaratildi (rasm bilan)")

        # Asosiy karta
        card = PaymentCard(holder_name="Almaz Silver", card_number_masked="8600 **** **** 1234",
                           is_primary=True, is_active=True)
        db.add(card)
        # Mijoz + suhbat (telegram)
        cust = Customer(channel="telegram", external_id=f"selftest-{uuid.uuid4().hex[:8]}", source="telegram")
        db.add(cust)
        await db.flush()
        conv = Conversation(customer_id=cust.id, channel="telegram")
        db.add(conv)
        await db.flush()
        await db.commit()
        ctx = ToolContext(db=db, conversation=conv)

        uzuk_pid = str(uzuk.id)
        uzuk_vid = str([v for v in uzuk.variants][0].id)

        print("\n── 1-2) send_product_images (rasm + boyitilgan izoh + URL normalizatsiya) ──")
        r = await dispatch("send_product_images", {"product_ids": [uzuk_pid, str(braslet.id)]}, ctx)
        check(r.get("sent") == 2, f"2 ta rasm yuborildi (natija: {r})")
        # Saqlangan chiquvchi media xabarlari
        msgs = (await db.execute(
            Message.__table__.select().where(Message.conversation_id == conv.id)
        )).all()
        media_msgs = [m for m in msgs if m.attachments]
        check(len(media_msgs) == 2, f"2 ta media xabar saqlandi ({len(media_msgs)})")
        url0 = media_msgs[0].attachments[0]["url"]
        check(url0.startswith("https://shop.example.uz/uploads/"),
              f"Rasm URL public bazaga normalizatsiya qilindi: {url0}")
        # Ma'lumot endi ALOHIDA matn xabarida (rasmdan keyin) — caption emas
        text_msgs = [m for m in msgs if not m.attachments and m.direction == "outgoing"]
        info_ok = any("Narx:" in (m.content or "") and "so'm" in (m.content or "") for m in text_msgs)
        check(info_ok, "Ma'lumot rasmdan KEYIN alohida matn xabarida (nom+narx)")

        print("\n── 3) create_order (uzuk + o'lcham) ──")
        r = await dispatch("create_order", {"items": [{"variant_id": uzuk_vid, "quantity": 1, "ring_size": "18"}]}, ctx)
        oid = r.get("order_id")
        check(oid and r.get("status") == "pending", f"Buyurtma yaratildi: {r.get('order_no')} / {r.get('status')}")
        check(float(r.get("items_total")) == 300000.0, f"items_total=300000 ({r.get('items_total')})")

        print("\n── 4) MIJOZ MA'LUMOTLARI: save_customer_name (ism + telefon) ──")
        r = await dispatch("save_customer_name", {"name": "Ali Valiyev", "phone": "+998901234567"}, ctx)
        check(r.get("saved") and r.get("phone") == "+998901234567", f"Ism+telefon saqlandi: {r}")

        print("\n── 5) request_location (+ regeneratsiya: qayta chaqirsa yangi token) ──")
        r1 = await dispatch("request_location", {"order_id": oid}, ctx)
        r2 = await dispatch("request_location", {"order_id": oid}, ctx)
        check(r1.get("checkout_url") and r2.get("checkout_url"), "Checkout link(lar) generatsiya qilindi")
        check(r1["checkout_url"] != r2["checkout_url"], "Qayta so'ralganда YANGI (boshqa) token berildi")

        print("\n── 5b) Mijoz lokatsiya yuboradi (Toshkent) → zona+narx ──")
        # Yangi tokenni raw sifatida olish uchun to'g'ridan-to'g'ri servisdan generatsiya qilamiz
        url, raw, _exp = await DeliveryService(db).create_checkout_link(uuid.UUID(oid))
        delivery = await DeliveryService(db).resolve_checkout(
            raw, lat=Decimal("41.311"), lng=Decimal("69.279"),
            address_text="Toshkent, Chilonzor", phone="+998901234567",
        )
        check(delivery.zone == "tashkent" and float(delivery.fee) == 50000.0,
              f"Zona=tashkent, dastavka=50000 ({delivery.zone}/{delivery.fee})")

        print("\n── 6-7) get_order_summary (jami + dastavka + mijoz ma'lumoti) ──")
        r = await dispatch("get_order_summary", {}, ctx)
        check(float(r["items_total"]) == 300000 and float(r["delivery_fee"]) == 50000
              and float(r["grand_total"]) == 350000,
              f"items=300000 + dastavka=50000 = jami=350000 ({r['items_total']}/{r['delivery_fee']}/{r['grand_total']})")
        check(r["customer_name"] == "Ali Valiyev" and r["customer_phone"] == "+998901234567"
              and r["has_location"], "Mijoz ismi/telefon/manzil xulosaда bor")

        print("\n── 7b) get_payment_card (asosiy karta) ──")
        r = await dispatch("get_payment_card", {}, ctx)
        check(r.get("card_number_masked") == "8600 **** **** 1234", f"Asosiy karta: {r}")

        print("\n── 8) submit_receipt (mijoz chek rasmini yuboradi) ──")
        # Mijozdan kelgan rasm xabari (IG uslubida url attachment)
        img_msg = Message(conversation_id=conv.id, direction="incoming", sender_type="customer",
                          content=None, attachments=[{"type": "image", "url": "http://x/receipt.jpg"}],
                          delivery_status="delivered")
        db.add(img_msg)
        await db.commit()

        # Yuklab olishni mock qilamiz (tarmoqsiz smoke) — real'da Telegram getFile / IG url ishlaydi
        async def fake_dl(db_, conv_, att):
            return b"\xff\xd8\xff\xe0FAKEJPEG", "jpg"
        ai_tools._download_attachment = fake_dl

        r = await dispatch("submit_receipt", {}, ctx)
        check(r.get("status") == "pending" and r.get("payment_id"), f"Chek to'lovga uzatildi: {r}")
        order = await OrdersRepository(db).get(uuid.UUID(oid))
        check(order.status == "payment_review", f"Order → payment_review ({order.status})")
        pay = await PaymentRepository(db).get_by_order(uuid.UUID(oid))
        check(pay.receipt_url.startswith("https://shop.example.uz/uploads/"),
              f"Chek public URL bilan saqlandi: {pay.receipt_url}")

        print("\n── 9) approve (operator tasdiqlaydi) → order confirmed + mijozga xabar ──")
        await PaymentService(db).approve(pay.id, reviewer_id=None)
        order = await OrdersRepository(db).get(uuid.UUID(oid))
        check(order.status == "confirmed", f"Order → confirmed ({order.status})")
        sys_msgs = (await db.execute(
            Message.__table__.select().where(Message.conversation_id == conv.id,
                                             Message.sender_type == "system")
        )).all()
        check(any("tasdiq" in (m.content or "").lower() for m in sys_msgs),
              "Mijozga tasdiq xabari yozildi (system)")

        print("\n── 10) get_order_status ──")
        r = await dispatch("get_order_status", {}, ctx)
        check(r.get("found") and r.get("status") == "confirmed" and r.get("status_text"),
              f"Status: {r.get('status')} — {r.get('status_text')!r}")

        print("\n" + "═" * 56)
        if _fails:
            print(f"{FAIL} {len(_fails)} ta tekshiruv yiqildi:")
            for f in _fails:
                print("   -", f)
        else:
            print(f"{OK} BARCHA TEKSHIRUVLAR O'TDI — buyurtma oqimi to'liq ishlaydi.")
        print("═" * 56)


if __name__ == "__main__":
    asyncio.run(main())
