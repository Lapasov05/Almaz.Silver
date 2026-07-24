"""DEMO seed — barcha jadvallarga realistik test ma'lumot (tizimni to'liq ko'rish uchun).

Asosiy `app/seed.py` (prod: rol/permission/settings/admin) DAN keyin ishga tushiriladi.
Servislar orqali ishlaydi => reservation, stock, audit, notification oqimlari ham to'ldiriladi.

Ishga tushirish:
    docker compose exec api python -m app.demo_seed
Qayta to'ldirish uchun (toza boshlash): `docker compose down -v` keyin `up` + shu skript.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.modules.ai.models import KnowledgeBase
from app.modules.catalog.models import Gender, Material, Stone
from app.modules.catalog.repository import CatalogRepository
from app.modules.catalog.schemas import (
    CategoryCreate,
    KursCreate,
    MediaCreate,
    ProductCreate,
    VariantCreate,
)
from app.modules.catalog.service import CatalogService
from app.modules.delivery.service import DeliveryService
from app.modules.identity.models import Role, User, UserRole
from app.modules.identity.rbac_service import RbacService
from app.modules.inbox.channels.base import NormalizedIncoming
from app.modules.inbox.models import Message
from app.modules.inbox.repository import InboxRepository
from app.modules.inbox.service import InboxService
from app.modules.orders.schemas import OrderItemCreate
from app.modules.orders.service import OrdersService
from app.modules.payments.service import PaymentCardService, PaymentService
from app.modules.settings.repository import SettingsRepository

DEMO_FLAG = "demo_seeded"
DEMO_PASSWORD = "demo1234"
# Demo mahsulot rasmi — API o'zi beradi (docs/uzuk.jpg -> /static/uzuk.jpg)
DEMO_IMAGE_URL = f"{get_settings().public_base_url.rstrip('/')}/static/uzuk.jpg"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Har rol uchun xodim (Super Admin allaqachon asosiy seed'da) ──
DEMO_USERS = [
    ("Owner", "owner@almazsilver.uz", "Jasur Egamberdiyev (Owner)"),
    ("General Manager", "gm@almazsilver.uz", "Kamola Yusupova (Bosh menejer)"),
    ("Sales Manager", "sales@almazsilver.uz", "Sardor Aliyev (Savdo menejeri)"),
    ("Operator", "operator@almazsilver.uz", "Aziza Karimova (Operator)"),
    ("Support", "support@almazsilver.uz", "Nodira Salimova (Support)"),
    ("Warehouse", "warehouse@almazsilver.uz", "Botir Tursunov (Ombor)"),
    ("Courier Manager", "courier@almazsilver.uz", "Otabek Rashidov (Kuryer)"),
    ("Finance", "finance@almazsilver.uz", "Dilfuza Ergasheva (Moliya)"),
    ("Marketing", "marketing@almazsilver.uz", "Jamshid Qodirov (Marketing)"),
    ("Content Manager", "content@almazsilver.uz", "Malika Rahimova (Kontent)"),
    ("AI Manager", "ai@almazsilver.uz", "Sanjar Umarov (AI menejer)"),
    ("Analyst", "analyst@almazsilver.uz", "Zafar Nazarov (Analitik)"),
    ("Auditor", "auditor@almazsilver.uz", "Gulnoza Sobirova (Auditor)"),
    ("Guest", "guest@almazsilver.uz", "Mehmon Foydalanuvchi"),
]

# ── Kategoriyalar ──
DEMO_CATEGORIES = ["Uzuklar", "Brasletlar", "Sepochkalar", "Komplektlar"]

# ── ~12 mahsulot (97% uzuk), Kumush 925 + rodiy, serkon; eski/yangi narx ──
# (kategoriya, nom, gender, yangi_narx, eski_narx, stock, engraving_available, engraving_price, shortcode, keywords)
DEMO_PRODUCTS = [
    ("Uzuklar", "Nozik ayollar uzugi 'Malika'", "ayol", 450000, 900000, 15, True, None, "MALIKA01", ["uzuk", "ayollar", "nozik", "serkon"]),
    ("Uzuklar", "Klassik ayollar uzugi 'Gulnoza'", "ayol", 520000, 1040000, 12, True, None, "GULNOZA02", ["uzuk", "ayollar", "klassik"]),
    ("Uzuklar", "Serkon gulli uzuk 'Sevgi'", "ayol", 610000, 1200000, 8, True, 70000, "SEVGI03", ["uzuk", "gul", "serkon", "sovga"]),
    ("Uzuklar", "Erkaklar uzugi 'Sulton'", "erkak", 680000, 1300000, 10, True, None, "SULTON04", ["uzuk", "erkak", "mujskoy"]),
    ("Uzuklar", "Erkaklar pechat uzuk 'Amir'", "erkak", 750000, 1500000, 6, True, None, "AMIR05", ["uzuk", "erkak", "pechat"]),
    ("Uzuklar", "Ikki qatorli uzuk 'Nur'", "ayol", 560000, 1100000, 9, False, None, "NUR06", ["uzuk", "ikki qator"]),
    ("Uzuklar", "Minimalist uzuk 'Sokin'", "uniseks", 390000, 780000, 20, True, None, "SOKIN07", ["uzuk", "minimalist", "sodda"]),
    ("Uzuklar", "Bezakli uzuk 'Shahzoda'", "ayol", 720000, 1450000, 7, True, None, "SHAHZODA08", ["uzuk", "bezak", "hashamatli"]),
    ("Brasletlar", "Kumush braslet 'Oydin'", "ayol", 830000, 1650000, 5, False, None, "OYDIN09", ["braslet", "ayollar"]),
    ("Sepochkalar", "Kumush sepochka 'Ipak'", "ayol", 540000, 1080000, 11, False, None, "IPAK10", ["sepochka", "zanjir", "ayollar"]),
    ("Sepochkalar", "Erkaklar sepochka 'Qudrat'", "erkak", 690000, 1380000, 8, False, None, "QUDRAT11", ["sepochka", "erkak", "zanjir"]),
    ("Komplektlar", "Komplekt 'Malika Set' (uzuk+sepochka)", "ayol", 1450000, 2900000, 4, False, None, "MALIKASET12", ["komplekt", "set", "sovga"]),
]

# ── Mijozlar (IG + TG) ──
DEMO_CUSTOMERS = [
    ("telegram", "700100", "dilnoza_tg", "Dilnoza Karimova"),
    ("telegram", "700200", "aziz_tg", "Aziz Rahimov"),
    ("instagram", "800100", "malika.ig", "Malika Yusupova"),
    ("instagram", "800200", "sardor.ig", "Sardor Aliyev"),
    ("telegram", "700300", "nodira_tg", "Nodira Salimova"),
]


async def _flag_set(db) -> bool:
    s = await SettingsRepository(db).get(DEMO_FLAG)
    return bool(s and s.value)


async def seed_users(db) -> dict[str, User]:
    users: dict[str, User] = {}
    for role_name, email, full_name in DEMO_USERS:
        existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if existing is not None:
            users[email] = existing
            continue
        user = User(full_name=full_name, email=email, password_hash=hash_password(DEMO_PASSWORD), is_active=True)
        db.add(user)
        await db.flush()
        role = (await db.execute(select(Role).where(Role.name == role_name))).scalar_one_or_none()
        if role is not None:
            db.add(UserRole(user_id=user.id, role_id=role.id))
        users[email] = user
    await db.commit()
    print(f"  ✓ {len(DEMO_USERS)} xodim (har rol uchun bittadan)")
    return users


async def seed_custom_role(db, actor_id) -> None:
    """RbacService orqali — audit_log (role.create/set_permissions) ni ham to'ldiradi."""
    rbac = RbacService(db)
    if await rbac.repo.get_role_by_name("VIP Sotuvchi") is None:
        role = await rbac.create_role("VIP Sotuvchi", actor_id=actor_id)
        await rbac.set_role_permissions(
            role.id, ["orders:view", "orders:create", "products:view", "conversations:view",
                      "conversations:create", "analytics:view_reports"], actor_id=actor_id)
        print("  ✓ custom rol 'VIP Sotuvchi' (+audit)")


async def seed_catalog(db) -> dict[str, object]:
    catalog = CatalogService(CatalogRepository(db))
    # Reference lug'atlar (asosiy seed'da yaratilgan)
    genders = {g.name_uz: g.id for g in (await db.execute(select(Gender))).scalars()}
    material_id = (await db.execute(select(Material.id))).scalars().first()
    stone_id = (await db.execute(select(Stone.id))).scalars().first()
    gmap = {"erkak": genders.get("Erkak"), "ayol": genders.get("Ayol"), "uniseks": genders.get("Uniseks")}
    # Kategoriya + kurs (gramm narxi — og'irlik kalkulyatori uchun)
    gram_prices = {"Uzuklar": 150000, "Brasletlar": 120000, "Sepochkalar": 110000, "Komplektlar": 130000}
    cats = {}
    for name in DEMO_CATEGORIES:
        cats[name] = await catalog.create_category(CategoryCreate(name_uz=name, name_ru=name))
        await catalog.create_kurs(KursCreate(
            category_id=cats[name].id, value=Decimal(str(gram_prices[name])), is_active=True, note="demo kurs"))
    products = {}
    for (cat, name, gender, price, old, stock, eng_av, eng_price, shortcode, kw) in DEMO_PRODUCTS:
        p = await catalog.create_product(ProductCreate(
            name_uz=name, name_ru=name, category_id=cats[cat].id,
            gender_id=gmap.get(gender), material_id=material_id, stone_id=stone_id,
            price=Decimal(str(old)), discount_price=Decimal(str(price)),
            weight_grams=Decimal("3.5"),
            status="active", ai_keywords=kw,
            description_uz=f"{name} — Kumush 925 proba + rodiy qoplama, serkon toshli.",
            description_ru=f"{name} — Серебро 925 + родий, камень серкон.",
            engraving_available=eng_av,
            engraving_price=Decimal(str(eng_price)) if eng_price else None,
            variants=[VariantCreate(stock_qty=stock)],
            media=[MediaCreate(shortcode_or_url=shortcode,
                               image_url=DEMO_IMAGE_URL)],
        ))
        products[name] = p
    print(f"  ✓ {len(DEMO_CATEGORIES)} kategoriya, {len(DEMO_PRODUCTS)} mahsulot (variant+media+zaxira)")
    return products


async def _add_msg(db, conv, direction, sender_type, content, *, sender_user_id=None, read=True):
    db.add(Message(conversation_id=conv.id, direction=direction, sender_type=sender_type,
                   sender_user_id=sender_user_id, content=content,
                   delivery_status="delivered" if direction == "incoming" else "sent", is_read=read))
    conv.last_message = content
    conv.last_activity_at = _utcnow()
    if direction == "incoming" and not read:
        conv.unread_count += 1


async def seed_inbox(db, operator: User) -> list:
    inbox = InboxService(InboxRepository(db))
    convs = []
    scripts = [
        ("recommending", [("incoming", "customer", "Assalomu alaykum, ayollar uzuklaringiz bormi?"),
                          ("outgoing", "ai", "Va alaykum assalom! Ha, albatta 😊 Nozik 'Malika' uzugimiz bor — Kumush 925 + rodiy, serkon toshli. Narxi 450 000 so'm."),
                          ("incoming", "customer", "Rasm bormi?")]),
        ("ordering", [("incoming", "customer", "Instagram'dagi 'Sulton' uzukni olmoqchiman"),
                      ("outgoing", "ai", "Ajoyib tanlov! O'lchamingizni ayta olasizmi? (16/17/18)"),
                      ("incoming", "customer", "18")]),
        ("payment_review", [("incoming", "customer", "To'lov qildim, chek yubordim"),
                            ("outgoing", "ai", "Rahmat! Chekingiz ko'rib chiqilmoqda, tez orada tasdiqlaymiz.")]),
        ("handed_off", [("incoming", "customer", "Menga aniq maslahat kerak, operator bilan gaplashsam bo'ladimi?"),
                       ("outgoing", "system", "Suhbat operatorga o'tkazildi."),
                       ("outgoing", "operator", "Assalomu alaykum, men operatorman. Qanday yordam bera olaman?", operator.id)]),
        ("greeting", [("incoming", "customer", "Narxlar qanday?")]),
    ]
    for (channel, ext, uname, fname), (state, msgs) in zip(DEMO_CUSTOMERS, scripts):
        first = msgs[0]
        inc = await inbox.ingest_incoming(NormalizedIncoming(
            channel=channel, external_user_id=ext, username=uname, full_name=fname, text=first[2]))
        conv = await InboxRepository(db).get_conversation(inc.conversation_id)
        for m in msgs[1:]:
            await _add_msg(db, conv, m[0], m[1], m[2], sender_user_id=(m[3] if len(m) > 3 else None))
        conv.ai_state = state
        convs.append(conv)
    await db.commit()
    print(f"  ✓ {len(DEMO_CUSTOMERS)} mijoz + suhbat + xabarlar (turli ai_state)")
    return convs


async def seed_payment_cards(db) -> None:
    cards = PaymentCardService(db)
    existing = await cards.repo.get_primary_card()
    if existing is None:
        await cards.create({"holder_name": "ALMAZ SILVER", "card_number_masked": "8600 **** **** 1234",
                            "is_primary": True, "is_active": True})
        await cards.create({"holder_name": "JASUR EGAMBERDIYEV", "card_number_masked": "9860 **** **** 5678",
                            "is_primary": False, "is_active": True})
        print("  ✓ 2 to'lov kartasi (1 asosiy)")


async def seed_orders(db, convs, products, reviewer: User) -> None:
    orders = OrdersService(db)
    delivery = DeliveryService(db)
    payments = PaymentService(db)

    async def cust(i):
        c = await InboxRepository(db).get_conversation(convs[i].id)
        return c.customer_id

    def vid(name):
        return products[name].variants[0].id

    async def checkout(order_id, zone):
        url, _ = await delivery.create_checkout_link(order_id)
        raw = url.rsplit("/", 1)[1]
        await delivery.resolve_checkout(raw, zone=zone, address_text="Toshkent sh., Chilonzor 12-45",
                                        lat=Decimal("41.28"), lng=Decimal("69.20"))

    # 1) pending
    await orders.create_order(await cust(0), [OrderItemCreate(variant_id=vid("Nozik ayollar uzugi 'Malika'"),
                              quantity=1, ring_size="17")], created_by_ai=True)
    # 2) waiting_payment (checkout qilingan)
    o2 = await orders.create_order(await cust(1), [OrderItemCreate(variant_id=vid("Erkaklar uzugi 'Sulton'"),
                                   quantity=1, ring_size="18")], created_by_ai=True)
    await checkout(o2.id, "tashkent")
    # 3) payment_review (chek yuborilgan) — ism yozish bilan
    o3 = await orders.create_order(await cust(2), [OrderItemCreate(variant_id=vid("Serkon gulli uzuk 'Sevgi'"),
                                   quantity=1, ring_size="16", engraving_text="Malika")], created_by_ai=True)
    await checkout(o3.id, "tashkent")
    await payments.submit_payment(o3.id, "https://cdn.almazsilver.uz/receipts/demo3.jpg", "Malika Yusupova")
    # 4) confirmed (to'lov tasdiqlangan -> stock--)
    o4 = await orders.create_order(await cust(0), [OrderItemCreate(variant_id=vid("Minimalist uzuk 'Sokin'"),
                                   quantity=2, ring_size="17")], created_by_ai=True)
    await checkout(o4.id, "region")
    p4 = await payments.submit_payment(o4.id, "https://cdn.almazsilver.uz/receipts/demo4.jpg", "Dilnoza Karimova")
    await payments.approve(p4.id, reviewer.id)
    # 5) rejected to'lov
    o5 = await orders.create_order(await cust(3), [OrderItemCreate(variant_id=vid("Erkaklar sepochka 'Qudrat'"),
                                   quantity=1)])
    await checkout(o5.id, "tashkent")
    p5 = await payments.submit_payment(o5.id, "https://cdn.almazsilver.uz/receipts/demo5.jpg", "Sardor Aliyev")
    await payments.reject(p5.id, reviewer.id, reason="Chek summasi mos kelmadi")
    # 6) cancelled
    o6 = await orders.create_order(await cust(4), [OrderItemCreate(variant_id=vid("Kumush braslet 'Oydin'"),
                                   quantity=1)])
    await orders.cancel_order(o6.id, changed_by=reviewer.id)
    # 7) confirmed komplekt (region)
    o7 = await orders.create_order(await cust(2), [OrderItemCreate(
        variant_id=vid("Komplekt 'Malika Set' (uzuk+sepochka)"), quantity=1, ring_size="17")])
    await checkout(o7.id, "region")
    p7 = await payments.submit_payment(o7.id, "https://cdn.almazsilver.uz/receipts/demo7.jpg", "Malika Yusupova")
    await payments.approve(p7.id, reviewer.id)
    print("  ✓ 7 buyurtma: pending/waiting_payment/payment_review/confirmed/rejected/cancelled")
    print("    (+ delivery, checkout_token, payment, audit_log, notification avtomatik to'ldi)")


async def seed_extra_kb(db) -> None:
    """3.2 bo'shlig'i: 'tayyorlik muddati' — AI mijozga aytishi uchun."""
    exists = (await db.execute(select(KnowledgeBase).where(KnowledgeBase.title == "Tayyorlik muddati"))).scalar_one_or_none()
    if exists is None:
        db.add(KnowledgeBase(type="instruction", title="Tayyorlik muddati",
               content="Mahsulotlar omborда tayyor turadi. Buyurtma odatда 1 kun ichида tayyorlanadi va jo'natishga topshiriladi. Nostandart o'lcham (masalan 15/19/20) ham 1 kunда moslanadi."))
        await db.commit()
        print("  ✓ KB: 'Tayyorlik muddati' (1 kun) — 3.2 bo'shlig'i yopildi")


async def main() -> None:
    async with SessionLocal() as db:
        if await _flag_set(db):
            # Rasm URL'i o'zgargan bo'lsa — mavjud demo mediani yangilaymiz (to'liq qayta seed shart emas)
            from sqlalchemy import update as _update
            from app.modules.catalog.models import ProductMedia
            await db.execute(_update(ProductMedia).values(image_url=DEMO_IMAGE_URL))
            await db.commit()
            print(f"ℹ️  Demo allaqachon bor. Mahsulot rasmlari yangilandi -> {DEMO_IMAGE_URL}")
            return
        print("🎬 DEMO seed boshlandi...")
        users = await seed_users(db)
        await seed_custom_role(db, users["owner@almazsilver.uz"].id)
        products = await seed_catalog(db)
        convs = await seed_inbox(db, users["operator@almazsilver.uz"])
        await seed_payment_cards(db)
        await seed_orders(db, convs, products, users["finance@almazsilver.uz"])
        await seed_extra_kb(db)
        await SettingsRepository(db).upsert(DEMO_FLAG, True)
        await db.commit()

    print("\n✅ DEMO seed yakunlandi. Kirish (parol: demo1234):")
    print("   admin@almazsilver.uz / admin123  (Super Admin)")
    for role_name, email, _ in DEMO_USERS:
        print(f"   {email:<28} {DEMO_PASSWORD}   ({role_name})")


if __name__ == "__main__":
    asyncio.run(main())
