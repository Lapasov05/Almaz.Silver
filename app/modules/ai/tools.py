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
            "description": "Katalogdan mahsulot topish: matn, Instagram post linki/shortcode bo'yicha.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Matnli qidiruv (nom/tavsif)"},
                    "shortcode": {"type": "string", "description": "Instagram shortcode yoki post URL"},
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
            "description": "Faol mahsulotlardan tavsiya (upsell/cross-sell).",
            "parameters": {
                "type": "object",
                "properties": {"context": {"type": "string", "description": "Tavsiya konteksti"}},
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
            "description": "Buyurtma yaratish + zaxira band qilish. Uzuk uchun ring_size so'ralsin.",
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
            "name": "handoff_to_operator",
            "description": "Suhbatni jonli operatorga o'tkazish (o'zi hal qila olmaganda).",
            "parameters": {
                "type": "object",
                "properties": {"reason": {"type": "string"}},
            },
        },
    },
]


def _product_brief(product: Product) -> dict:
    active_variants = [v for v in product.variants if v.is_active and v.deleted_at is None]
    default_variant = active_variants[0] if active_variants else None
    available = sum(max(v.available, 0) for v in active_variants)
    return {
        "product_id": str(product.id),
        "name": product.name,
        "price": _num(product.price),
        "compare_at_price": _num(product.compare_at_price),
        "material": product.material,  # doim "Kumush 925 + rodiy"
        "stone": product.stone,        # doim "serkon"
        "gender": product.gender if isinstance(product.gender, str) else product.gender.value,
        "available": available,
        "default_variant_id": str(default_variant.id) if default_variant else None,
        "shortcodes": [m.shortcode for m in product.media if m.shortcode],
    }


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
        match_type, results = await catalog.search(
            q=args.get("query"), shortcode=args.get("shortcode"), limit=5
        )
        return {"match_type": match_type, "products": [_product_brief(p) for p, _ in results]}

    if name == "get_product_details":
        product = await catalog.get_product(uuid.UUID(args["product_id"]))
        brief = _product_brief(product)
        brief["description"] = product.description
        brief["variants"] = [
            {"variant_id": str(v.id), "sku": v.sku, "available": max(v.available, 0)}
            for v in product.variants
            if v.deleted_at is None
        ]
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
        products = await catalog.list_products(status="active", limit=5)
        return {"products": [_product_brief(p) for p in products]}

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

        url, expires_at = await DeliveryService(db).create_checkout_link(uuid.UUID(args["order_id"]))
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
