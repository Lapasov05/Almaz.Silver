"""AI tool'lari (function-calling) — CRM ma'lumotiga grounding (TZ 7.4 / 7.6).

Faza 3'da amalga oshirilgan (o'qish/tavsiya/RAG): search_product, get_product_details,
check_stock, recommend, calc_delivery, get_payment_card, search_knowledge_base, handoff_to_operator.
Buyurtma/lokatsiya/to'lov yaratuvchi tool'lar — Faza 4/5 (orders/delivery/payments).
"""
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai.repository import KnowledgeRepository
from app.modules.catalog.models import Product
from app.modules.catalog.repository import CatalogRepository
from app.modules.catalog.service import CatalogService
from app.modules.inbox.models import AiState, Conversation
from app.modules.settings.repository import SettingsRepository


@dataclass
class ToolContext:
    db: AsyncSession
    conversation: Conversation


# ---------- OpenAI function-calling sxemalari ----------
TOOL_SPECS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "search_product",
            "description": (
                "Katalogdan mahsulot topish: matn, Instagram shortcode, va/yoki NARX (byudjet) bo'yicha. "
                "Mijoz byudjet aytsa (masalan '300 ming atrofi') max_price/min_price bilan qidiring."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Matnli qidiruv (nom/tavsif)"},
                    "shortcode": {"type": "string", "description": "Instagram shortcode yoki post URL"},
                    "min_price": {"type": "number", "description": "Eng past narx (so'm)"},
                    "max_price": {"type": "number", "description": "Eng baland narx (so'm) — mijoz byudjeti"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_details",
            "description": "Mahsulotning to'liq ma'lumoti: narx, material, tosh, variant/zaxira.",
            "parameters": {
                "type": "object",
                "properties": {"product_id": {"type": "string"}},
                "required": ["product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_stock",
            "description": "Variant zaxirasi: available = stock_qty - reserved_qty.",
            "parameters": {
                "type": "object",
                "properties": {"variant_id": {"type": "string"}},
                "required": ["variant_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recommend",
            "description": "Faol mahsulotlardan tavsiya (upsell/cross-sell). Byudjet berilsa max_price bilan.",
            "parameters": {
                "type": "object",
                "properties": {
                    "context": {"type": "string", "description": "Tavsiya konteksti"},
                    "min_price": {"type": "number", "description": "Eng past narx (so'm)"},
                    "max_price": {"type": "number", "description": "Eng baland narx (so'm) — byudjet"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calc_delivery",
            "description": "Zona bo'yicha yetkazish narxi (fixed).",
            "parameters": {
                "type": "object",
                "properties": {"zone": {"type": "string", "enum": ["tashkent", "region"]}},
                "required": ["zone"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_payment_card",
            "description": "Asosiy (primary) to'lov kartasi ma'lumoti.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": "Bilim bazasidan (FAQ/policy/delivery/payment/company/guarantee) javob topish.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_order",
            "description": (
                "Buyurtma yaratish + zaxira band qilish. Uzuk uchun ring_size so'ralsin. "
                "Mijoz uzukka ism yozdirmoqchi bo'lsa engraving_text yuboriladi (qo'shimcha narx)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "variant_id": {"type": "string"},
                                "quantity": {"type": "integer", "minimum": 1},
                                "ring_size": {"type": "string"},
                                "engraving_text": {
                                    "type": "string",
                                    "description": "Uzukka yoziladigan ism (faqat engraving.available=true bo'lsa)",
                                },
                                "box_id": {
                                    "type": "string",
                                    "description": "Tanlangan rangli quti (box) id — list_boxes natijasidan. Ixtiyoriy.",
                                },
                            },
                            "required": ["variant_id"],
                        },
                    }
                },
                "required": ["items"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_boxes",
            "description": (
                "Mahsulot kategoriyasi uchun mavjud rangli qutilar (box) ro'yxati — mijoz qadoq/quti "
                "so'raganda yoki taklif qilishdan oldin. Narx 0 = tekin. Faqat zaxirada borlari qaytadi."
            ),
            "parameters": {
                "type": "object",
                "properties": {"product_id": {"type": "string"}},
                "required": ["product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_location",
            "description": "Buyurtma uchun bir martalik checkout (lokatsiya) linki generatsiya qilish.",
            "parameters": {
                "type": "object",
                "properties": {"order_id": {"type": "string"}},
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_payment",
            "description": "Mijoz chek va ism-familiyasini yuborganда to'lovni ko'rib chiqishga uzatish.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "receipt_url": {"type": "string", "description": "Chek rasmi URL (object storage)"},
                    "payer_name": {"type": "string", "description": "Karta egasi ism-familiyasi"},
                },
                "required": ["order_id", "receipt_url", "payer_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_product_images",
            "description": (
                "Tavsiya qilinayotgan mahsulot(lar) RASMLARINI mijozga yuboradi — mijoz nom bilan "
                "tanimasligi mumkin, rasm bilan aniq tanlaydi. Mahsulotni tavsiya qilganda/gapirganda "
                "ishlating. Har mahsulotning 1-rasmi yuboriladi (rasmi bo'lganlarniki)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product_ids": {
                        "type": "array", "items": {"type": "string"},
                        "description": "Rasm yuboriladigan mahsulot id'lari (search/recommend natijasidan)",
                    }
                },
                "required": ["product_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resolve_instagram_media",
            "description": (
                "Instagram post/story linkidan yoki story javobidan mahsulotni topadi (bazadan). "
                "Mijoz IG link tashlasa yoki story'ga javob bersa ishlatiladi. found=false bo'lsa mijozdan so'ra."
            ),
            "parameters": {
                "type": "object",
                "properties": {"link_or_ref": {"type": "string", "description": "IG post/story link yoki story_ref"}},
                "required": ["link_or_ref"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "handoff_to_operator",
            "description": "Suhbatni jonli operatorga o'tkazish (o'zi hal qila olmaganda).",
            "parameters": {
                "type": "object",
                "properties": {"reason": {"type": "string"}},
            },
        },
    },
]


def _product_brief(product: Product, engraving: tuple[bool, Decimal] | None = None) -> dict:
    active_variants = [v for v in product.variants if v.is_active and v.deleted_at is None]
    default_variant = active_variants[0] if active_variants else None
    available = sum(max(v.available, 0) for v in active_variants)
    brief = {
        "product_id": str(product.id),
        "name": product.name_uz,
        "name_ru": product.name_ru,
        # Mijoz to'laydigan narx (chegirma bo'lsa o'sha) + chizilgan eski narx
        "price": _num(product.effective_price),
        "old_price": _num(product.price) if product.discount_price is not None else None,
        "material": product.material.name_uz if product.material else None,
        "stone": product.stone.name_uz if product.stone else None,
        "gender": product.gender.name_uz if product.gender else None,
        "requires_ring_size": product.requires_ring_size,  # uzuk=true, boshqalar universal
        "available": available,
        "default_variant_id": str(default_variant.id) if default_variant else None,
        "shortcodes": [m.shortcode for m in product.media if m.shortcode],
        # Rasm URL'lari — AI mijozga rasm yuborishi uchun (send_product_images)
        "images": [m.image_url for m in product.media if m.image_url][:5],
    }
    # Ism yozish (gravyurka) — AI mijozga taklif qilishi uchun amaldagi narx
    if engraving is not None:
        enabled_globally, default_price = engraving
        offered = bool(enabled_globally and product.engraving_available)
        brief["engraving"] = {
            "available": offered,
            "price": _num(product.engraving_price if product.engraving_price is not None else default_price)
            if offered
            else None,
        }
    return brief


async def _engraving_settings(db: AsyncSession) -> tuple[bool, Decimal]:
    """(global yoqilganmi, standart narx) — Settings'dan."""
    enabled = bool(await _get_setting(db, "engraving_enabled", False))
    price = await _get_setting(db, "engraving_price", 0)
    return enabled, Decimal(str(price))


def _box_brief(box) -> dict:
    """AI uchun box (rang) qisqacha: narx 0 = tekin, faqat zaxirada borlar taklif qilinadi."""
    return {
        "box_id": str(box.id),
        "color": box.name_uz,
        "color_hex": box.color_hex,
        "price": _num(box.price),  # 0.0 = tekin
        "free": box.is_free,
        "available": max(box.available, 0),
    }


async def _boxes_for_product(db: AsyncSession, product: Product) -> list[dict]:
    """Mahsulot kategoriyasidagi faol + zaxirada bor boxlar (boxes_enabled bo'lsa)."""
    if product.category_id is None:
        return []
    if not bool(await _get_setting(db, "boxes_enabled", False)):
        return []
    boxes = await CatalogRepository(db).list_active_boxes(product.category_id)
    return [_box_brief(b) for b in boxes if b.available > 0]


def _num(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


async def _get_setting(db: AsyncSession, key: str, default: Any = None) -> Any:
    setting = await SettingsRepository(db).get(key)
    return setting.value if setting is not None else default


# ---------- Dispatcher ----------
async def dispatch(name: str, args: dict, ctx: ToolContext) -> dict:
    db = ctx.db
    catalog = CatalogService(CatalogRepository(db))

    if name == "search_product":
        min_p, max_p = args.get("min_price"), args.get("max_price")
        eng = await _engraving_settings(db)
        if min_p is not None or max_p is not None:  # byudjet bo'yicha (effective narx)
            from app.core.pagination import PageParams

            items, _ = await catalog.list_products(
                pp=PageParams(limit=6, offset=0), status="active", q=args.get("query"),
                min_price=Decimal(str(min_p)) if min_p is not None else None,
                max_price=Decimal(str(max_p)) if max_p is not None else None,
                in_stock=True,  # faqat zaxirada bor (tavsiya qilingan mahsulot buyurtma qilinsin)
            )
            items.sort(key=lambda p: p.effective_price)  # arzonroqdan
            return {"match_type": "price", "products": [_product_brief(p, eng) for p in items]}
        match_type, results = await catalog.search(
            q=args.get("query"), shortcode=args.get("shortcode"), limit=5
        )
        return {"match_type": match_type, "products": [_product_brief(p, eng) for p, _ in results]}

    if name == "get_product_details":
        product = await catalog.get_product(uuid.UUID(args["product_id"]))
        brief = _product_brief(product, await _engraving_settings(db))
        brief["description"] = product.description_uz
        brief["variants"] = [
            {"variant_id": str(v.id), "sku": v.sku, "available": max(v.available, 0)}
            for v in product.variants
            if v.deleted_at is None
        ]
        brief["boxes"] = await _boxes_for_product(db, product)  # kategoriya rangli qutilari
        if product.is_combo:  # combo (to'plam) — ichidagi mahsulotlar
            items = await CatalogRepository(db).list_combo_items(product.id)
            brief["is_combo"] = True
            brief["combo_items"] = [
                {
                    "name": ci.component_variant.product.name_uz if ci.component_variant.product else "?",
                    "quantity": ci.quantity,
                }
                for ci in items
            ]
        return brief

    if name == "list_boxes":
        product = await CatalogRepository(db).get_product(uuid.UUID(args["product_id"]))
        if product is None:
            return {"boxes": [], "error": "mahsulot topilmadi"}
        return {"boxes": await _boxes_for_product(db, product)}

    if name == "send_product_images":
        from app.modules.inbox.repository import InboxRepository
        from app.modules.inbox.service import InboxService

        inbox = InboxService(InboxRepository(db))
        sent, skipped = 0, 0
        for pid in (args.get("product_ids") or [])[:8]:
            try:
                product = await CatalogRepository(db).get_product(uuid.UUID(pid))
            except (ValueError, TypeError):
                product = None
            if product is None:
                skipped += 1
                continue
            img = next((m.image_url for m in product.media if m.image_url), None)
            if not img:
                skipped += 1  # rasmi yo'q — yuborilmaydi
                continue
            caption = f"{product.name_uz} — {int(product.effective_price)} so'm"
            await inbox.send_media(ctx.conversation, img, caption=caption)
            sent += 1
        return {"sent": sent, "skipped_no_image": skipped}

    if name == "resolve_instagram_media":
        product = await catalog.resolve_instagram_media(args.get("link_or_ref", ""))
        if product is None:
            return {"found": False}
        brief = _product_brief(product, await _engraving_settings(db))
        brief["found"] = True
        brief["boxes"] = await _boxes_for_product(db, product)
        return brief

    if name == "check_stock":
        variant = await CatalogRepository(db).get_variant(uuid.UUID(args["variant_id"]))
        if variant is None:
            return {"error": "variant topilmadi"}
        return {
            "variant_id": str(variant.id),
            "stock_qty": variant.stock_qty,
            "reserved_qty": variant.reserved_qty,
            "available": max(variant.available, 0),
        }

    if name == "recommend":
        from app.core.pagination import PageParams

        min_p, max_p = args.get("min_price"), args.get("max_price")
        products, _ = await catalog.list_products(
            pp=PageParams(limit=5, offset=0), status="active",
            min_price=Decimal(str(min_p)) if min_p is not None else None,
            max_price=Decimal(str(max_p)) if max_p is not None else None,
            in_stock=True,  # faqat zaxirada bor mahsulotlar tavsiya qilinadi
        )
        eng = await _engraving_settings(db)
        return {"products": [_product_brief(p, eng) for p in products]}

    if name == "calc_delivery":
        zone = args.get("zone")
        key = "delivery_fee_tashkent" if zone == "tashkent" else "delivery_fee_region"
        fee = await _get_setting(db, key, 0)
        return {"zone": zone, "fee": fee, "currency": "UZS"}

    if name == "get_payment_card":
        from app.modules.payments.repository import PaymentRepository

        card = await PaymentRepository(db).get_primary_card()
        if card is None:
            return {"error": "Asosiy karta sozlanmagan"}
        return {
            "holder_name": card.holder_name,
            "card_number_masked": card.card_number_masked,
        }

    if name == "search_knowledge_base":
        entries = await KnowledgeRepository(db).search_text(args["query"], limit=3)
        return {"results": [{"type": e.type, "title": e.title, "content": e.content} for e in entries]}

    if name == "create_order":
        from app.modules.orders.schemas import OrderItemCreate
        from app.modules.orders.service import OrdersService

        items = [
            OrderItemCreate(
                variant_id=uuid.UUID(it["variant_id"]),
                quantity=int(it.get("quantity", 1)),
                ring_size=it.get("ring_size"),
                engraving_text=it.get("engraving_text"),
                box_id=uuid.UUID(it["box_id"]) if it.get("box_id") else None,
            )
            for it in args.get("items", [])
        ]
        order = await OrdersService(db).create_order(
            ctx.conversation.customer_id, items, created_by_ai=True
        )
        return {
            "order_id": str(order.id),
            "order_no": order.order_no,
            "status": order.status,
            "items_total": _num(order.items_total),
            "grand_total": _num(order.grand_total),
        }

    if name == "request_location":
        from app.modules.delivery.service import DeliveryService

        url, _token, expires_at = await DeliveryService(db).create_checkout_link(uuid.UUID(args["order_id"]))
        return {"checkout_url": url, "expires_at": expires_at.isoformat()}

    if name == "submit_payment":
        from app.modules.payments.service import PaymentService

        payment = await PaymentService(db).submit_payment(
            uuid.UUID(args["order_id"]), args["receipt_url"], args["payer_name"]
        )
        return {"payment_id": str(payment.id), "status": payment.status}

    if name == "handoff_to_operator":
        ctx.conversation.ai_state = AiState.handed_off.value
        return {"status": "handed_off", "reason": args.get("reason")}

    return {"error": f"noma'lum tool: {name}"}
