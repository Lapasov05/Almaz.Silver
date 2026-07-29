"""Location oqimi smoke test (throwaway pg) — supersede + Toshkent/BTS + eng yaqin filial.

Tekshiradi:
  1) create_order SUPERSEDE — yangi order oldingi faol orderni bekor qiladi (bitta faol order).
  2) request_location LINK formati: {frontend_map_url}/map/{token}.
  3) resolve_checkout TOSHKENT (lat/lng Toshkent) → type=Toshkent, 50k, customer_location saqlanadi.
  4) resolve_checkout BTS (Samarqand lat/lng) → type=BTS, 30k, ENG YAQIN filial (Samarqand) biriktiriladi.
  5) get_order_summary → location_type + bts_branch.
"""
import asyncio
import uuid
from decimal import Decimal

import app.core.models_registry  # noqa: F401
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.modules.ai.tools import ToolContext, dispatch
from app.modules.catalog.repository import CatalogRepository
from app.modules.catalog.schemas import ProductCreate, VariantCreate
from app.modules.catalog.service import CatalogService
from app.modules.delivery.repository import DeliveryRepository
from app.modules.delivery.service import DeliveryService
from app.modules.inbox.models import Conversation, Customer
from app.modules.orders.repository import OrdersRepository

OK, FAIL = "✅", "❌"
_fails = []


def check(cond, label):
    print(f"  {OK if cond else FAIL} {label}")
    if not cond:
        _fails.append(label)


async def mk_product(db, name, price):
    return await CatalogService(CatalogRepository(db)).create_product(ProductCreate(
        name_uz=name, price=Decimal(price), status="active",
        variants=[VariantCreate(sku=f"S-{uuid.uuid4().hex[:6]}", stock_qty=10)],
        image_urls=["http://localhost:8000/uploads/x.jpg"]))


async def main():
    settings = get_settings()
    async with SessionLocal() as db:
        p1 = await mk_product(db, "Uzuk A", "300000")
        p2 = await mk_product(db, "Uzuk B", "500000")
        cust = Customer(channel="telegram", external_id=f"selftest-{uuid.uuid4().hex[:8]}", source="telegram")
        db.add(cust); await db.flush()
        conv = Conversation(customer_id=cust.id, channel="telegram"); db.add(conv); await db.flush()
        await db.commit()
        ctx = ToolContext(db=db, conversation=conv)
        v1 = str(p1.variants[0].id); v2 = str(p2.variants[0].id)

        print("── 1) SUPERSEDE: yangi order eskisini bekor qiladi ──")
        r1 = await dispatch("create_order", {"items": [{"variant_id": v1, "quantity": 1, "ring_size": "18"}]}, ctx)
        r2 = await dispatch("create_order", {"items": [{"variant_id": v2, "quantity": 1, "ring_size": "19"}]}, ctx)
        check(r1["order_id"] != r2["order_id"], "Ikki xil mahsulot → ikki xil order")
        active = await OrdersRepository(db).list_active_orders(cust.id)
        check(len(active) == 1 and str(active[0].id) == r2["order_id"],
              f"Faqat BITTA faol order qoldi (yangisi): {len(active)} ta")
        o1 = await OrdersRepository(db).get(uuid.UUID(r1["order_id"]))
        check(o1.status == "cancelled", f"Eski order bekor qilindi ({o1.status})")
        # variant A reservation bo'shadimi
        vA = await CatalogRepository(db).get_variant(p1.variants[0].id)
        check(vA.reserved_qty == 0, f"Eski order zaxirasi bo'shadi (reserved={vA.reserved_qty})")
        oid = r2["order_id"]

        # Bir xil mahsulot qayta → dubl yaratmaydi (already_exists)
        r3 = await dispatch("create_order", {"items": [{"variant_id": v2, "quantity": 1, "ring_size": "19"}]}, ctx)
        check(r3.get("already_exists") and r3["order_id"] == oid, "Aynan shu mahsulot qayta → dubl yo'q")

        print("\n── 2) request_location LINK formati ──")
        rl = await dispatch("request_location", {}, ctx)  # order_id'siz — faol orderni topadi
        url = rl.get("checkout_url", "")
        check(url.startswith(f"{settings.frontend_map_url.rstrip('/')}/map/"), f"Link /map/ formatida: {url}")

        print("\n── 3) TOSHKENT lokatsiya → type=Toshkent, 50k ──")
        _u, raw, _e = await DeliveryService(db).create_checkout_link(uuid.UUID(oid))
        dlv = await DeliveryService(db).resolve_checkout(raw, lat=Decimal("41.311"), lng=Decimal("69.279"),
                                                         address_text="Toshkent, Chilonzor")
        check(dlv.location_type == "Toshkent" and float(dlv.fee) == 50000, f"type=Toshkent, fee=50000 ({dlv.location_type}/{dlv.fee})")
        check(dlv.customer_location_id is not None and dlv.bts_branch_id is None, "customer_location saqlandi, BTS filiali yo'q")

        print("\n── 4) BTS lokatsiya (Samarqand) → type=BTS, 30k, eng yaqin filial ──")
        # yangi order (supersede) + yangi token
        rord = await dispatch("create_order", {"items": [{"variant_id": v1, "quantity": 1, "ring_size": "17"}]}, ctx)
        _u, raw2, _e = await DeliveryService(db).create_checkout_link(uuid.UUID(rord["order_id"]))
        # Samarqand markazi ~ 39.65, 66.96
        dlv2 = await DeliveryService(db).resolve_checkout(raw2, lat=Decimal("39.654"), lng=Decimal("66.959"),
                                                          address_text="Samarqand shahar")
        check(dlv2.location_type == "BTS" and float(dlv2.fee) == 30000, f"type=BTS, fee=30000 ({dlv2.location_type}/{dlv2.fee})")
        branch = await DeliveryRepository(db).get_bts_branch(dlv2.bts_branch_id) if dlv2.bts_branch_id else None
        check(branch is not None, "Eng yaqin BTS filiali biriktirildi")
        if branch:
            check(branch.region == "Samarqand", f"Eng yaqin filial Samarqandda: {branch.name} ({branch.region})")

        print("\n── 4b) IKKI QADAM: preview_location (ro'yxat) → confirm_location (tanlash) ──")
        rord2 = await dispatch("create_order", {"items": [{"variant_id": v2, "quantity": 1, "ring_size": "16"}]}, ctx)
        _u, raw3, _e = await DeliveryService(db).create_checkout_link(uuid.UUID(rord2["order_id"]))
        prev = await DeliveryService(db).preview_location(raw3, Decimal("39.654"), Decimal("66.959"))
        check(prev["location_type"].value == "BTS" and len(prev["branches"]) >= 1,
              f"preview: BTS + filiallar ro'yxati ({len(prev['branches'])} ta)")
        dists = [d for _b, d in prev["branches"]]
        check(dists == sorted(dists), "preview: masofa bo'yicha saralangan")
        # Filialsiz confirm (BTS) → xato
        from app.core.exceptions import AppError
        try:
            await DeliveryService(db).confirm_location(raw3, lat=Decimal("39.654"), lng=Decimal("66.959"))
            check(False, "BTS'да filialsiz confirm → xato kutilgan edi")
        except AppError:
            check(True, "BTS'да filialsiz confirm → AppError (to'g'ri)")
        # Ro'yxatdan 2-filialni tanlab confirm
        chosen = prev["branches"][1][0] if len(prev["branches"]) > 1 else prev["branches"][0][0]
        dlv3 = await DeliveryService(db).confirm_location(
            raw3, lat=Decimal("39.654"), lng=Decimal("66.959"), bts_branch_id=chosen.id, address_text="Samarqand")
        check(dlv3.bts_branch_id == chosen.id and float(dlv3.fee) == 30000,
              f"TANLANGAN filial saqlandi ({chosen.name}), 30k")

        print("\n── 5) get_order_summary → location_type + bts_branch ──")
        summ = await dispatch("get_order_summary", {}, ctx)
        check(summ.get("location_type") == "BTS", f"summary location_type=BTS ({summ.get('location_type')})")
        check(summ.get("bts_branch") and summ["bts_branch"].get("address"),
              f"summary'да BTS filial ma'lumoti bor: {summ.get('bts_branch',{}).get('name')}")
        check(float(summ["delivery_fee"]) == 30000 and float(summ["grand_total"]) == float(summ["items_total"]) + 30000,
              f"jami = mahsulot + 30000 ({summ['items_total']}+30000={summ['grand_total']})")

        print("\n" + "═" * 56)
        if _fails:
            print(f"{FAIL} {len(_fails)} yiqildi:"); [print("   -", f) for f in _fails]
        else:
            print(f"{OK} BARCHA LOCATION TEKSHIRUVLARI O'TDI")
        print("═" * 56)


if __name__ == "__main__":
    asyncio.run(main())
