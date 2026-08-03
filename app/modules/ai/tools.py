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
            "name": "list_categories",
            "description": (
                "Zaxirada MAHSULOTI BOR kategoriyalar ro'yxati (har birida nechta zaxiradagi mahsulot bor). "
                "Mijozga kategoriya/tur taklif qilishdan OLDIN shu tool'ni chaqiring — bo'sh yoki zaxirasi "
                "tugagan kategoriyani taklif qilmang. Faqat shu ro'yxatdagilarni ayting."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_boxes",
            "description": (
                "Rangli qutilar (box) ro'yxati — mijoz qadoq/quti/sovg'a qutisi so'raganda yoki taklif "
                "qilishdan oldin. Aniq mahsulot bo'lsa `product_id` bering (o'sha kategoriya qutilari); "
                "mijoz UMUMIY so'rasa (masalan 'qanday qutilaringiz bor') `product_id` SIZ ham chaqiring "
                "(barcha qutilar qaytadi). Narx 0 = tekin. Faqat zaxirada borlari qaytadi."
            ),
            "parameters": {
                "type": "object",
                "properties": {"product_id": {"type": "string", "description": "Ixtiyoriy — aniq mahsulot bo'lsa"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_location",
            "description": (
                "Buyurtma uchun bir martalik checkout (lokatsiya) linki generatsiya qilish. Mijoz link "
                "orqali manzil yubormasa yoki qayta so'rasa — YANA chaqiring (yangi link/kod beriladi). "
                "order_id ixtiyoriy (berilmasa faol buyurtma olinadi)."
            ),
            "parameters": {
                "type": "object",
                "properties": {"order_id": {"type": "string", "description": "Ixtiyoriy"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_delivery_address",
            "description": (
                "Manzilni MATN bilan qabul qiladi (xarita/link SHART EMAS) — FALLBACK: mijoz xarita "
                "linkidan foydalana olmaganda ('topolmadim/ishlamadi') YOKI manzilni to'g'ridan-to'g'ri "
                "matn bilan yozganida ('Samarqand viloyati Narpay tumani Mirbozor', '📪 Qashqadaryo "
                "Kitob') chaqiring. Zona matndan aniqlanadi. Chaqirilgач tizim mijozga yetkazish "
                "ma'lumoti + to'lov kartasini AVTOMATIK yuboradi. order_id ixtiyoriy (berilmasa faol buyurtma)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "address_text": {"type": "string", "description": "Mijoz yozgan to'liq manzil (viloyat/tuman/mo'ljal)"},
                    "phone": {"type": "string", "description": "Telefon raqami (mijoz shu xabarда bergan bo'lsa, ixtiyoriy)"},
                    "order_id": {"type": "string", "description": "Ixtiyoriy"},
                },
                "required": ["address_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_order_summary",
            "description": (
                "Buyurtma XULOSASI: mahsulotlar, mahsulotlar summasi (items_total), yetkazish narxi "
                "(delivery_fee) va zonasi, JAMI to'lov (grand_total), hamda mijoz ma'lumotlari "
                "(ism, telefon, manzil). Lokatsiya olingach TO'LOVdan OLDIN chaqiring — mijozga jami "
                "summa + dastavkani ko'rsatish va ma'lumotlarini tasdiqlatish uchun. order_id ixtiyoriy "
                "(berilmasa faol buyurtma olinadi)."
            ),
            "parameters": {
                "type": "object",
                "properties": {"order_id": {"type": "string", "description": "Ixtiyoriy"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_order_status",
            "description": (
                "Mijozning buyurtma HOLATINI (statusini) qaytaradi — mijoz 'buyurtmam qayerda', "
                "'holati qanday', 'tasdiqlandimi' deб so'raganда ishlating. order_id ixtiyoriy."
            ),
            "parameters": {
                "type": "object",
                "properties": {"order_id": {"type": "string", "description": "Ixtiyoriy"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_receipt",
            "description": (
                "Mijoz TO'LOV CHEKINING RASMINI yuborganда uni to'lovga tasdiqlashga (operator/owner) "
                "uzatadi. Chek rasmini mijozning oxirgi yuborgan rasmidan AVTOMATIK oladi — receipt_url "
                "berish shart EMAS. Faqat mijoz chek RASMINI yuborganда chaqiring (matn emas). order_id "
                "va payer_name ixtiyoriy (berilmasa faol buyurtma va mijoz ismi olinadi)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "Ixtiyoriy"},
                    "payer_name": {"type": "string", "description": "Karta egasi ismi (ixtiyoriy)"},
                },
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
            "name": "save_customer_name",
            "description": (
                "Mijozning ISM-FAMILIYASI va/yoki TELEFON raqamini saqlaydi — buyurtma rasmiylashtirish "
                "uchun kerak (CRM'da 'Mijoz' o'rniga ismi ko'rinadi). Mijoz ismini yoki telefonini aytsa "
                "DARHOL chaqiring. Ikkalasidan biri bo'lsa ham bo'ladi."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Mijozning ism-familiyasi (ixtiyoriy)"},
                    "phone": {"type": "string", "description": "Telefon raqami (ixtiyoriy)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete_order",
            "description": (
                "Buyurtmani YAKUNLANGAN (completed) qiladi — mijoz buyumni OLGANINI tasdiqlaganda "
                "('oldim', 'yetib keldi', 'qo'limda') chaqiring. Faqat buyurtma yo'lda/yetkazilgan bo'lsa ishlaydi."
            ),
            "parameters": {"type": "object", "properties": {}},
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


def _product_brief(product: Product, ctx: dict | None = None) -> dict:
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
        # Kategoriyaga bog'langan mavjud o'lchamlar (masalan ["16","17","18"]); bo'sh -> cheklovsiz
        "available_sizes": (
            product.category.available_sizes
            if (product.requires_ring_size and product.category is not None)
            else None
        ),
        "available": available,
        "default_variant_id": str(default_variant.id) if default_variant else None,
        "shortcodes": [m.shortcode for m in product.media if m.shortcode],
        # Rasm URL'lari — AI mijozga rasm yuborishi uchun (send_product_images)
        "images": [m.image_url for m in product.media if m.image_url][:5],
    }
    if ctx is not None:
        # Ism yozish (gravyurka) — AI taklif qilishi uchun amaldagi narx + belgi limiti
        eng_enabled, eng_price, eng_max_default = ctx["engraving"]
        eng_offered = bool(eng_enabled and product.engraving_available)
        eng_max = (
            product.engraving_max_chars
            if product.engraving_max_chars is not None
            else eng_max_default
        )
        brief["engraving"] = {
            "available": eng_offered,
            "price": _num(product.engraving_price if product.engraving_price is not None else eng_price)
            if eng_offered
            else None,
            # 0 = cheksiz; AI shu limitdan oshiq yozuvni qabul qilmasin
            "max_chars": (eng_max or 0) if eng_offered else None,
        }
        # Garantiya (kafolat) — global default, mahsulotда `warranty_months` override
        w_enabled, w_months, w_text = ctx["warranty"]
        if w_enabled:
            months = product.warranty_months if product.warranty_months is not None else w_months
            brief["warranty"] = {"available": True, "months": months, "text": w_text}
        else:
            brief["warranty"] = {"available": False}
        # O'lcham o'zgartirish (zargar) — faqat uzuk (requires_ring_size) uchun; global narx / override
        r_enabled, r_price, r_text = ctx["resize"]
        r_offered = bool(r_enabled and product.resize_available and product.requires_ring_size)
        brief["resize"] = {
            "available": r_offered,
            "price": _num(product.resize_price if product.resize_price is not None else r_price)
            if r_offered
            else None,
            "text": r_text if r_offered else None,
        }
    return brief


def _image_caption(product: Product) -> str:
    """Mahsulot rasmi ostidagi izoh — nom, narx (chegirma bo'lsa eski narx ham), material, tosh.

    Guardrail send_media ichida caption'ni ham tekshiradi (taqiqlangan atama almashadi).
    """
    price = int(product.effective_price)
    if product.discount_price is not None:
        price_line = f"{price:,} so'm (eski narx {int(product.price):,})".replace(",", " ")
    else:
        price_line = f"{price:,} so'm".replace(",", " ")
    lines = [product.name_uz, f"Narx: {price_line}"]
    detail = []
    if product.material:
        detail.append(product.material.name_uz)
    if product.stone:
        detail.append(product.stone.name_uz)
    if detail:
        lines.append(" · ".join(detail))
    if product.requires_ring_size:
        lines.append("O'lcham (razmer)ni belgilashingiz mumkin.")
    return "\n".join(lines)


async def _engraving_settings(db: AsyncSession) -> tuple[bool, Decimal, int]:
    """(global yoqilganmi, standart narx, standart belgi limiti) — Settings'dan."""
    enabled = bool(await _get_setting(db, "engraving_enabled", False))
    price = await _get_setting(db, "engraving_price", 0)
    max_chars = await _get_setting(db, "engraving_max_chars", 0)
    return enabled, Decimal(str(price)), int(max_chars or 0)


async def _sale_ctx(db: AsyncSession) -> dict:
    """Global qo'shimcha xizmat sozlamalari (bir marta o'qiladi): gravyurka + kafolat + o'lcham o'zgartirish."""
    return {
        "engraving": await _engraving_settings(db),
        "warranty": (
            bool(await _get_setting(db, "warranty_enabled", False)),
            await _get_setting(db, "warranty_months", 0),
            await _get_setting(db, "warranty_text", ""),
        ),
        "resize": (
            bool(await _get_setting(db, "resize_enabled", False)),
            Decimal(str(await _get_setting(db, "resize_price", 0))),
            await _get_setting(db, "resize_text", ""),
        ),
    }


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


async def _all_boxes(db: AsyncSession) -> list[dict]:
    """Barcha kategoriyalardagi faol+zaxirada qutilar, rang bo'yicha yagona (umumiy savol uchun)."""
    if not bool(await _get_setting(db, "boxes_enabled", False)):
        return []
    seen: set[tuple] = set()
    out: list[dict] = []
    for b in await CatalogRepository(db).list_all_active_boxes():
        if b.available <= 0:
            continue
        key = (b.name_uz, str(b.price))  # kategoriyalararo bir xil ranglarni takrorlamaymiz
        if key in seen:
            continue
        seen.add(key)
        out.append(_box_brief(b))
    return out


def _num(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


async def _get_setting(db: AsyncSession, key: str, default: Any = None) -> Any:
    setting = await SettingsRepository(db).get(key)
    return setting.value if setting is not None else default


async def _resolve_variant_id(repo, catalog, raw):
    """AI bergan 'variant_id'ni haqiqiy variant id'ga hal qiladi (chidamli).

    Qabul qiladi: variant UUID | product UUID | mahsulot nomi/matn. Topilmasa None.
    (AI ba'zan variant_id o'rniga product_id, nom yoki buzuq UUID yuboradi.)
    """
    if not raw:
        return None
    raw = str(raw).strip()
    try:
        vid = uuid.UUID(raw)
    except (ValueError, TypeError):
        vid = None
    if vid is not None:
        if await repo.get_variant(vid) is not None:
            return vid
        product = await repo.get_product(vid)  # product_id yuborilgan bo'lsa -> default variant
        if product is not None:
            active = [v for v in product.variants if v.is_active and v.deleted_at is None]
            if active:
                return active[0].id
        return None
    # UUID emas — mahsulot nomi/matn bo'yicha qidiramiz
    try:
        _mt, results = await catalog.search(q=raw, limit=1)
    except Exception:  # noqa: BLE001
        results = []
    if results:
        p = results[0][0]
        active = [v for v in p.variants if v.is_active and v.deleted_at is None]
        if active:
            return active[0].id
    return None


# Buyurtma statuslari — mijozga tushunarli o'zbekcha matn
_ORDER_STATUS_UZ: dict[str, str] = {
    "draft": "shakllantirilmoqda",
    "pending": "yaratildi, manzil/to'lov kutilmoqda",
    "waiting_payment": "to'lov kutilmoqda",
    "payment_review": "to'lov cheki tekshirilmoqda",
    "confirmed": "tasdiqlandi — tayyorlanmoqda",
    "preparing": "tayyorlanmoqda",
    "packed": "qadoqlandi",
    "shipping": "yetkazilmoqda",
    "delivered": "yetkazildi",
    "completed": "yakunlandi",
    "cancelled": "bekor qilindi",
    "refunded": "pul qaytarildi",
    "returned": "qaytarildi",
}


async def _resolve_order(db: AsyncSession, ctx: ToolContext, raw_order_id, *, latest: bool = False):
    """order_id berilsa o'shani, aks holda mijozning faol (yoki latest=True bo'lsa eng so'nggi) buyurtmasi."""
    from app.modules.orders.repository import OrdersRepository

    repo = OrdersRepository(db)
    if raw_order_id:
        try:
            return await repo.get(uuid.UUID(str(raw_order_id)))
        except (ValueError, TypeError):
            pass
    if latest:
        return await repo.get_latest_order(ctx.conversation.customer_id)
    return await repo.get_active_order(ctx.conversation.customer_id)


async def _order_items_brief(db: AsyncSession, order) -> list[dict]:
    """Buyurtma itemlari qisqacha (mahsulot nomi lazy-load'siz olinadi)."""
    repo = CatalogRepository(db)
    out: list[dict] = []
    for it in order.items:
        variant = await repo.get_variant(it.variant_id)
        product = await repo.get_product(variant.product_id) if variant else None
        out.append({
            "name": product.name_uz if product else "?",
            "quantity": it.quantity,
            "ring_size": it.ring_size,
            "unit_price": _num(it.unit_price),
            "engraving_text": it.engraving_text,
        })
    return out


async def _resolve_latest_receipt_image(db: AsyncSession, conv: Conversation) -> tuple[str, str] | None:
    """Mijozning oxirgi yuborgan RASMINI topib, uni public URL sifatida saqlaydi → (url, ext).

    Telegram: attachment `file_id` → getFile → yuklab olish. Instagram: attachment `url` → yuklab olish.
    Topilmasa/yuklab bo'lmasa None.
    """
    from sqlalchemy import select

    from app.modules.files.service import save_bytes
    from app.modules.inbox.models import Message

    rows = (await db.execute(
        select(Message)
        .where(Message.conversation_id == conv.id, Message.direction == "incoming")
        .order_by(Message.created_at.desc())
        .limit(10)
    )).scalars().all()

    for msg in rows:
        for att in (msg.attachments or []):
            if not isinstance(att, dict):
                continue
            atype = (att.get("type") or "").lower()
            if atype in ("photo", "image") or att.get("file_id") or att.get("url"):
                data_ext = await _download_attachment(db, conv, att)
                if data_ext is not None:
                    data, ext = data_ext
                    url = await save_bytes(data, ext)
                    return url, ext
    return None


async def _download_attachment(db: AsyncSession, conv: Conversation, att: dict) -> tuple[bytes, str] | None:
    """Bitta attachmentni baytlarga yuklab oladi (kanalga qarab). (bytes, ext) yoki None."""
    import httpx

    from app.core.config import get_settings as _gs

    cfg = _gs()
    timeout = cfg.http_timeout_seconds
    try:
        if conv.channel == "telegram" and att.get("file_id"):
            from app.modules.integrations.service import get_config_value

            token = await get_config_value(db, "telegram", "bot_token")
            if not token:
                return None
            base = cfg.telegram_api_base_url.rstrip("/")
            async with httpx.AsyncClient(timeout=timeout) as client:
                r = await client.get(f"{base}/bot{token}/getFile", params={"file_id": att["file_id"]})
                if r.status_code != 200 or not r.json().get("ok"):
                    return None
                file_path = r.json()["result"].get("file_path")
                if not file_path:
                    return None
                fr = await client.get(f"{base}/file/bot{token}/{file_path}")
                if fr.status_code != 200:
                    return None
                ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else "jpg"
                return fr.content, ext
        url = att.get("url")
        if url:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                fr = await client.get(url)
                if fr.status_code != 200:
                    return None
                ext = "jpg"
                path = str(fr.url).split("?", 1)[0]
                if "." in path.rsplit("/", 1)[-1]:
                    ext = path.rsplit(".", 1)[-1].lower()
                return fr.content, ext
    except Exception:  # noqa: BLE001 — yuklab bo'lmasa jim None (AI qayta so'raydi)
        return None
    return None


# ---------- Dispatcher ----------
async def dispatch(name: str, args: dict, ctx: ToolContext) -> dict:
    db = ctx.db
    catalog = CatalogService(CatalogRepository(db))

    if name == "search_product":
        min_p, max_p = args.get("min_price"), args.get("max_price")
        sctx = await _sale_ctx(db)
        if min_p is not None or max_p is not None:  # byudjet bo'yicha (effective narx)
            from app.core.pagination import PageParams

            items, _ = await catalog.list_products(
                pp=PageParams(limit=6, offset=0), status="active", q=args.get("query"),
                min_price=Decimal(str(min_p)) if min_p is not None else None,
                max_price=Decimal(str(max_p)) if max_p is not None else None,
                in_stock=True,  # faqat zaxirada bor (tavsiya qilingan mahsulot buyurtma qilinsin)
            )
            items.sort(key=lambda p: p.effective_price)  # arzonroqdan
            return {"match_type": "price", "products": [_product_brief(p, sctx) for p in items]}
        match_type, results = await catalog.search(
            q=args.get("query"), shortcode=args.get("shortcode"), limit=5
        )
        return {"match_type": match_type, "products": [_product_brief(p, sctx) for p, _ in results]}

    if name == "get_product_details":
        try:
            product = await catalog.get_product(uuid.UUID(str(args.get("product_id"))))
        except (ValueError, TypeError):
            return {"error": "product_id noto'g'ri — avval search_product bilan mahsulotni toping"}
        brief = _product_brief(product, await _sale_ctx(db))
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

    if name == "list_categories":
        rows = await CatalogRepository(db).categories_with_stock()
        return {"categories": [
            {"category_id": str(c.id), "name": c.name_uz, "in_stock_count": n} for c, n in rows
        ]}

    if name == "list_boxes":
        # product_id IXTIYORIY: berilsa -> shu mahsulot kategoriyasi qutilari;
        # berilmasa/xato bo'lsa -> barcha faol qutilar (mijoz umumiy so'raganda xato bermaydi).
        raw = args.get("product_id")
        product = None
        if raw:
            try:
                product = await CatalogRepository(db).get_product(uuid.UUID(str(raw)))
            except (ValueError, TypeError):
                product = None
        if product is not None:
            return {"boxes": await _boxes_for_product(db, product)}
        return {"boxes": await _all_boxes(db)}

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
            # MUHIM (Instagram tartibi): avval RASM (captionsiz), KEYIN alohida matn xabari.
            # Caption bilan yuborilса IG matnni rasmdan OLDIN ko'rsatadi — shuning uchun ajratamiz:
            # rasm → tagidan ma'lumot (nom, narx, material, tosh). Har mahsulot ketma-ket.
            from app.modules.ai.guardrail import enforce

            await inbox.send_media(ctx.conversation, img, caption=None)
            await inbox.ai_send(ctx.conversation, enforce(_image_caption(product)).text)
            sent += 1
        return {"sent": sent, "skipped_no_image": skipped}

    if name == "save_customer_name":
        from app.modules.inbox.models import Customer

        nm = (args.get("name") or "").strip()
        phone = (args.get("phone") or "").strip()
        if not nm and not phone:
            return {"saved": False}
        cust = await db.get(Customer, ctx.conversation.customer_id)
        if cust is None:
            return {"saved": False}
        if nm:
            cust.full_name = nm[:255]
        if phone:
            cust.phone = phone[:32]
        await db.commit()
        return {"saved": True, "name": cust.full_name, "phone": cust.phone}

    if name == "resolve_instagram_media":
        product = await catalog.resolve_instagram_media(args.get("link_or_ref", ""))
        if product is None:
            return {"found": False}
        brief = _product_brief(product, await _sale_ctx(db))
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
        sctx = await _sale_ctx(db)
        return {"products": [_product_brief(p, sctx) for p in products]}

    if name == "calc_delivery":
        zone = args.get("zone")
        key = "delivery_fee_tashkent" if zone == "tashkent" else "delivery_fee_region"
        fee = await _get_setting(db, key, 0)
        return {"zone": zone, "fee": fee, "currency": "UZS"}

    if name == "get_payment_card":
        from app.modules.payments.repository import PaymentRepository

        card = await PaymentRepository(db).get_default_card()
        if card is None:
            return {"error": "To'lov kartasi sozlanmagan"}
        return {
            "holder_name": card.holder_name,
            "card_number_masked": card.card_number_masked,
        }

    if name == "search_knowledge_base":
        entries = await KnowledgeRepository(db).search_text(args["query"], limit=3)
        return {"results": [{"type": e.type, "title": e.title, "content": e.content} for e in entries]}

    if name == "create_order":
        from app.modules.orders.repository import OrdersRepository
        from app.modules.orders.schemas import OrderItemCreate
        from app.modules.orders.service import OrdersService

        repo = CatalogRepository(db)
        items = []
        for it in args.get("items", []):
            vid = await _resolve_variant_id(repo, catalog, it.get("variant_id"))
            if vid is None:
                return {"error": f"Mahsulot/variant topilmadi: {it.get('variant_id')!r}. "
                                 f"Avval search_product bilan toping va default_variant_id ni bering."}
            box_id = None
            if it.get("box_id"):
                try:
                    box_id = uuid.UUID(str(it["box_id"]))
                except (ValueError, TypeError):
                    box_id = None
            items.append(OrderItemCreate(
                variant_id=vid,
                quantity=int(it.get("quantity", 1)),
                ring_size=it.get("ring_size"),
                engraving_text=it.get("engraving_text"),
                box_id=box_id,
            ))

        # Bir turdagi dublni oldini olish: mijozning faol buyurtmasi AYNAN shu mahsulotlar bo'lsa,
        # yangi yaratmaymiz (bir suhbatда ikki marta chaqirilса). Boshqa mahsulot bo'lsa —
        # create_order oldingisini avtomatik bekor qiladi (supersede) va yangisini yaratadi.
        existing = await OrdersRepository(db).get_active_order(ctx.conversation.customer_id)
        if existing is not None:
            want = sorted((str(i.variant_id), i.quantity, i.ring_size or "") for i in items)
            have = sorted((str(i.variant_id), i.quantity, i.ring_size or "") for i in existing.items)
            if want == have:
                return {
                    "order_id": str(existing.id),
                    "order_no": existing.order_no,
                    "status": existing.status,
                    "items_total": _num(existing.items_total),
                    "grand_total": _num(existing.grand_total),
                    "already_exists": True,
                    "note": "Aynan shu buyurtma allaqachon bor — shu bilan davom eting (manzil/to'lov).",
                }

        from app.core.exceptions import AppError

        try:
            order = await OrdersService(db).create_order(
                ctx.conversation.customer_id, items, created_by_ai=True
            )
        except AppError as exc:
            # Biznes qoidasi (masalan gravyurka belgi limiti, zaxira) — AI mijozga muloyim aytadi
            return {"error": exc.message}
        return {
            "order_id": str(order.id),
            "order_no": order.order_no,
            "status": order.status,
            "items_total": _num(order.items_total),
            "grand_total": _num(order.grand_total),
        }

    if name == "request_location":
        from app.modules.delivery.service import DeliveryService

        # order_id berilmasa/xato bo'lsa faol buyurtmani olamiz (AI tool natijasini qadamlararo
        # yo'qotishi mumkin — memory'да tool javoblari saqlanmaydi). Shunda link doim generatsiya bo'ladi.
        order = await _resolve_order(db, ctx, args.get("order_id"))
        if order is None:
            return {"error": "Faol buyurtma topilmadi — avval create_order chaqiring."}
        url, _token, expires_at = await DeliveryService(db).create_checkout_link(order.id)
        return {"checkout_url": url, "expires_at": expires_at.isoformat()}

    if name == "set_delivery_address":
        from app.core.exceptions import AppError
        from app.modules.delivery.service import DeliveryService

        if not bool(await _get_setting(db, "accept_text_address", True)):
            return {"error": "Matnli manzil o'chirilgan — request_location bilan xarita linkini bering."}
        order = await _resolve_order(db, ctx, args.get("order_id"))
        if order is None:
            return {"error": "Faol buyurtma topilmadi — avval create_order chaqiring."}
        try:
            delivery = await DeliveryService(db).set_text_address(
                order.id, args.get("address_text", ""), phone=(args.get("phone") or None)
            )
        except AppError as exc:
            return {"error": exc.message}
        # Manzil qabul qilingach — yetkazish ma'lumoti + karta + chek so'rovi AVTOMATIK ketadi
        # (xarita confirm bilan bir xil follow-up). ism/telefon yetmasa avval o'shani so'raydi.
        from app.modules.delivery.checkout import _send_payment_followup

        await db.refresh(order)
        await _send_payment_followup(db, order)
        return {
            "saved": True,
            "address": delivery.address_text,
            "zone": delivery.zone,
            "location_type": delivery.location_type,
            "note": "Manzil qabul qilindi. Tizim yetkazish ma'lumoti + kartani yubordi (ism/telefon "
                    "bo'lsa). Kartani QAYTA yubormang.",
        }

    if name == "get_order_summary":
        from app.modules.delivery.repository import DeliveryRepository
        from app.modules.inbox.models import Customer

        order = await _resolve_order(db, ctx, args.get("order_id"))
        if order is None:
            return {"error": "Faol buyurtma topilmadi — avval create_order chaqiring."}
        cust = await db.get(Customer, ctx.conversation.customer_id)
        drepo = DeliveryRepository(db)
        delivery = await drepo.get_by_order(order.id)
        has_location = bool(delivery and (delivery.address_text or (delivery.lat is not None)))
        bts = None
        if delivery is not None and delivery.bts_branch_id is not None:
            b = await drepo.get_bts_branch(delivery.bts_branch_id)
            if b is not None:  # BTS bo'lsa — mijoz shu filialdan oladi
                bts = {"name": b.name, "region": b.region, "district": b.district,
                       "address": b.address, "phone": b.phone, "work_hours": b.work_hours}
        return {
            "order_no": order.order_no,
            "status": order.status,
            "items": await _order_items_brief(db, order),
            "items_total": _num(order.items_total),
            "delivery_fee": _num(order.delivery_fee),
            "location_type": delivery.location_type if delivery else None,  # Toshkent | BTS
            "bts_branch": bts,  # BTS bo'lsa eng yaqin filial (mijoz shu yerdan oladi)
            "grand_total": _num(order.grand_total),
            "customer_name": cust.full_name if cust else None,
            "customer_phone": cust.phone if cust else None,
            "address": delivery.address_text if delivery else None,
            "has_location": has_location,
        }

    if name == "get_order_status":
        order = await _resolve_order(db, ctx, args.get("order_id"), latest=True)
        if order is None:
            return {"found": False, "note": "Mijozda buyurtma yo'q."}
        return {
            "found": True,
            "order_no": order.order_no,
            "status": order.status,
            "status_text": _ORDER_STATUS_UZ.get(order.status, order.status),
            "grand_total": _num(order.grand_total),
        }

    if name == "submit_receipt":
        from app.modules.inbox.models import Customer
        from app.modules.payments.service import PaymentService

        order = await _resolve_order(db, ctx, args.get("order_id"))
        if order is None:
            return {"error": "Faol buyurtma topilmadi."}
        image = await _resolve_latest_receipt_image(db, ctx.conversation)
        if image is None:
            return {"error": "Chek rasmi topilmadi — mijozdan to'lov chekining RASMINI yuborishini so'rang."}
        receipt_url, _ext = image
        payer = (args.get("payer_name") or "").strip()
        if not payer:
            cust = await db.get(Customer, ctx.conversation.customer_id)
            payer = (cust.full_name if cust and cust.full_name else "Mijoz")
        payment = await PaymentService(db).submit_payment(order.id, receipt_url, payer)
        return {"payment_id": str(payment.id), "status": payment.status,
                "note": "Chek to'lovga tasdiqlashga yuborildi. Operator tekshiradi."}

    if name == "complete_order":
        from app.modules.orders.models import OrderStatus
        from app.modules.orders.repository import OrdersRepository
        from app.modules.orders.service import OrdersService

        order = await OrdersRepository(db).get_current_order(ctx.conversation.customer_id)
        if order is None:
            return {"error": "Faol buyurtma topilmadi."}
        if order.status not in ("shipping", "delivered"):
            return {"error": f"Buyurtma hali yakunlanmaydi (holat: {order.status}). Yo'lda/yetkazilgan bo'lishi kerak."}
        await OrdersService(db).set_status(order.id, OrderStatus.completed)
        return {"order_no": order.order_no, "status": "completed",
                "note": "Buyurtma yakunlandi — mijozga minnatdorchilik bildir."}

    if name == "handoff_to_operator":
        # AI VAQTINCHALIK to'xtaydi (pauza) — operator qo'lga oladi. DOIMIY O'CHIRILMAYDI: pauza
        # tugagach (yoki operator ishlagach) AI qayta ishlaydi. Operator inbox'da handed_off bo'yicha ko'radi.
        from datetime import datetime, timedelta, timezone

        minutes = int(await _get_setting(db, "handoff_pause_minutes", 60) or 60)
        ctx.conversation.ai_state = AiState.handed_off.value
        ctx.conversation.ai_paused_until = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        return {"status": "handed_off", "reason": args.get("reason")}

    return {"error": f"noma'lum tool: {name}"}
