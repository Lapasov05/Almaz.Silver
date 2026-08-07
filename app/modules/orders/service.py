"""orders Service qatlami — buyurtma yaratish + reservation + status tarixi (TZ 10)."""
import logging
import secrets
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, NotFoundError
from app.modules.catalog.repository import CatalogRepository

logger = logging.getLogger(__name__)
from app.modules.orders.models import (
    Order,
    OrderItem,
    OrderStatus,
    OrderStatusHistory,
)
from app.modules.orders.repository import OrdersRepository
from app.modules.orders.schemas import OrderItemCreate
from app.modules.settings.repository import SettingsRepository

# Bekor qilinsa reservation bo'shatiladigan holatlar (aktiv buyurtmalar)
_CANCELLABLE = {
    OrderStatus.draft,
    OrderStatus.pending,
    OrderStatus.waiting_payment,
    OrderStatus.payment_review,
    OrderStatus.confirmed,
    OrderStatus.preparing,
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OrdersService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = OrdersRepository(db)
        self.catalog = CatalogRepository(db)

    async def _generate_order_no(self) -> str:
        for _ in range(10):
            candidate = f"ORD-{_utcnow():%y%m%d}-{secrets.token_hex(3).upper()}"
            if not await self.repo.order_no_exists(candidate):
                return candidate
        raise AppError("Buyurtma raqamini generatsiya qilib bo'lmadi")

    async def create_order(
        self,
        customer_id: uuid.UUID,
        items: list[OrderItemCreate],
        *,
        changed_by: uuid.UUID | None = None,
        created_by_ai: bool = False,
    ) -> Order:
        """Buyurtma + order_item yaratadi va zaxirani band qiladi (reserved_qty++).

        Bir mijozda BITTA faol buyurtma invarianti (TZ 11): yangi buyurtma yaratilganda mijozning
        oldingi faol (to'lanmagan) buyurtmalari avtomatik BEKOR qilinadi (reservation bo'shaydi).
        Shunda lokatsiya tokeni doim yagona faol buyurtmaga tegishli bo'ladi — chalkashlik yo'q.
        """
        if not items:
            raise AppError("Buyurtmada kamida bitta mahsulot bo'lishi kerak")

        # Oldingi faol buyurtmalarni bekor qilamiz (supersede)
        for prev in await self.repo.list_active_orders(customer_id):
            await self._release_reservation(prev)
            prev.history.append(
                OrderStatusHistory(
                    from_status=prev.status, to_status=OrderStatus.cancelled.value, changed_by=changed_by
                )
            )
            prev.status = OrderStatus.cancelled.value

        order = Order(
            order_no=await self._generate_order_no(),
            customer_id=customer_id,
            status=OrderStatus.pending.value,
            created_by_ai=created_by_ai,
        )
        order.items_total = await self._process_items(order, items)
        order.grand_total = order.items_total  # delivery_fee lokatsiyadan keyin qo'shiladi (hozir 0)
        # Tarixni flush'dan OLDIN qo'shamiz (transient obyektда lazy-load bo'lmaydi)
        order.history.append(
            OrderStatusHistory(from_status=None, to_status=OrderStatus.pending.value, changed_by=changed_by)
        )
        await self.repo.add(order)
        await self.db.commit()
        order = await self.get(order.id)
        # Buyurtma tushdi — operator guruhiga darhol yuboriladi (tasdiqlash uchun). Best-effort.
        try:
            from app.modules.notifications.service import NotificationService

            await NotificationService(self.db).notify_new_order(order)
        except Exception:  # noqa: BLE001 — guruh xabari buyurtmani buzmasin
            logger.warning("guruhga yangi buyurtma yuborilmadi (order=%s)", order.id, exc_info=True)
        return order

    async def _process_items(self, order: Order, items) -> Decimal:
        """Buyurtma itemlarini yaratadi: validatsiya + zaxira rezerv + narx (gravyurka/box/o'lcham).

        `order.items` ga qo'shadi, items_total qaytaradi. create_order VA replace_items ishlatadi.
        """
        settings_repo = SettingsRepository(self.db)
        # Bonuslar global (TZ 18): yaratish vaqtidagi nusxa
        bonus_setting = await settings_repo.get("bonus_items")
        bonus_snapshot = bonus_setting.value if bonus_setting is not None else []

        # Ism yozish (gravyurka) — global sozlamalar
        engraving_enabled_setting = await settings_repo.get("engraving_enabled")
        engraving_enabled = (
            bool(engraving_enabled_setting.value) if engraving_enabled_setting is not None else False
        )
        engraving_price_setting = await settings_repo.get("engraving_price")
        default_engraving_price = (
            Decimal(str(engraving_price_setting.value)) if engraving_price_setting is not None else Decimal("0")
        )
        # Gravyurka belgi limiti (global default; mahsulotда override) — 0 = cheksiz
        engraving_max_setting = await settings_repo.get("engraving_max_chars")
        default_engraving_max = (
            int(engraving_max_setting.value) if engraving_max_setting is not None else 0
        )

        # Box (rangli quti) — global on/off
        boxes_enabled_setting = await settings_repo.get("boxes_enabled")
        boxes_enabled = (
            bool(boxes_enabled_setting.value) if boxes_enabled_setting is not None else False
        )

        items_total = Decimal("0")

        for it in items:
            variant = await self.catalog.get_variant(it.variant_id)
            if variant is None or not variant.is_active:
                raise AppError(f"Variant topilmadi yoki faol emas: {it.variant_id}")
            product = await self.catalog.get_product(variant.product_id)
            if product is None:
                raise AppError("Mahsulot topilmadi")

            # Zaxira maqsadlari: oddiy mahsulot -> o'zi; combo -> komponent variantlar (× combo soni)
            targets = await self.catalog.resolve_stock_targets(variant.id, it.quantity)
            if product.is_combo and not targets:
                raise AppError(f"Combo bo'sh (tarkibsiz): {product.name_uz}")
            # Tekshiruv (faqat 'stocked'); made_to_order/unique — talab qilmaydi
            for tv, need in targets:
                if tv.fulfillment_type == "stocked" and tv.available < need:
                    raise AppError(
                        f"Zaxira yetarli emas (SKU {tv.sku}): mavjud {tv.available}, kerak {need}"
                    )
            for tv, need in targets:
                tv.reserved_qty += need  # TZ 10: reservation (combo -> komponentlar)
            unit_price = product.effective_price  # combo/mahsulot narxi (chegirma bo'lsa o'sha)

            # --- O'lcham (razmer) — kategoriyaga bog'langan ro'yxatga tekshirish ---
            ring_size = (it.ring_size or "").strip() or None
            if ring_size and product.requires_ring_size and product.category is not None:
                sizes = product.category.available_sizes or []
                if sizes and ring_size not in sizes:
                    raise AppError(
                        f"Bu kategoriyada mavjud o'lchamlar: {', '.join(str(s) for s in sizes)}. "
                        f"'{ring_size}' o'lchami mavjud emas."
                    )

            # --- Ism yozish (gravyurka) narxini aniqlash ---
            engraving_text = (it.engraving_text or "").strip() or None
            engraving_price = Decimal("0")
            if engraving_text is not None:
                if not engraving_enabled:
                    raise AppError("Ism yozish xizmati hozircha o'chirilgan")
                if not product.engraving_available:
                    raise AppError(f"Bu mahsulotga ism yozib bo'lmaydi: {product.name_uz}")
                # Belgi limiti: bu uzukka sig'adigan maksimal belgi (mahsulot override yoki global)
                max_chars = (
                    product.engraving_max_chars
                    if product.engraving_max_chars is not None
                    else default_engraving_max
                )
                if max_chars and len(engraving_text) > max_chars:
                    raise AppError(
                        f"Bu uzukka eng ko'pi {max_chars} ta belgi sig'adi, "
                        f"siz {len(engraving_text)} ta yubordingiz. Iltimos, qisqaroq yozuv tanlang."
                    )
                # Mahsulotда o'z narxi bo'lsa o'sha, aks holda Settings'dagi narx
                engraving_price = (
                    product.engraving_price
                    if product.engraving_price is not None
                    else default_engraving_price
                )

            # --- Box (rangli quti) narxi + zaxira band qilish ---
            box_id = None
            box_price = Decimal("0")
            box_label = None
            # Quti MAJBURIY: kategoriyada faol qutilar bo'lsa, mijoz rang tanlashi shart
            if boxes_enabled and it.box_id is None and product.category_id is not None:
                cat_boxes = await self.catalog.list_active_boxes(product.category_id)
                if any(b.available > 0 for b in cat_boxes):
                    raise AppError(
                        f"Iltimos, '{product.name_uz}' uchun quti rangini tanlang "
                        f"(mavjud: {', '.join(b.name_uz for b in cat_boxes if b.available > 0)})."
                    )
            if it.box_id is not None:
                if not boxes_enabled:
                    raise AppError("Box (quti) xizmati hozircha o'chirilgan")
                box = await self.catalog.get_box(it.box_id)
                if box is None or not box.is_active:
                    raise AppError(f"Box topilmadi yoki faol emas: {it.box_id}")
                # Box mahsulot kategoriyasiga tegishli bo'lishi shart (boshqa kategoriya box'i emas)
                if product.category_id is None or box.category_id != product.category_id:
                    raise AppError("Box bu mahsulot kategoriyasiga tegishli emas")
                if box.available < it.quantity:
                    raise AppError(
                        f"Box zaxirasi yetarli emas ({box.name_uz}): mavjud {box.available}, so'ralgan {it.quantity}"
                    )
                box.reserved_qty += it.quantity  # TZ 10: reservation (variant kabi)
                box_id = box.id
                box_price = box.price  # snapshot (0 = tekin)
                cat_name = product.category.name_uz if product.category is not None else None
                box_label = f"{cat_name} — {box.name_uz}" if cat_name else box.name_uz

            items_total += (unit_price + engraving_price + box_price) * it.quantity

            order.items.append(
                OrderItem(
                    variant_id=variant.id,
                    quantity=it.quantity,
                    unit_price=unit_price,
                    ring_size=ring_size,
                    bonus_snapshot=bonus_snapshot,
                    engraving_text=engraving_text,
                    engraving_price=engraving_price,
                    box_id=box_id,
                    box_price=box_price,
                    box_label=box_label,
                )
            )

        return items_total

    async def get(self, order_id: uuid.UUID) -> Order:
        order = await self.repo.get(order_id)
        if order is None:
            raise NotFoundError("Buyurtma topilmadi")
        return order

    async def list(self, **filters) -> list[Order]:
        return await self.repo.list(**filters)

    async def change_status(
        self,
        order_id: uuid.UUID,
        to_status: OrderStatus,
        *,
        changed_by: uuid.UUID | None = None,
        release_reservation: bool = False,
        commit: bool = True,
    ) -> Order:
        """Statusni o'zgartiradi + order_status_history yozadi (TZ 10)."""
        order = await self.get(order_id)
        from_status = order.status
        order.status = to_status.value
        order.history.append(
            OrderStatusHistory(from_status=from_status, to_status=to_status.value, changed_by=changed_by)
        )
        if release_reservation:
            await self._release_reservation(order)
        if commit:
            await self.db.commit()
        return order

    async def update_order(self, order_id: uuid.UUID, data) -> Order:
        """Buyurtmani tahrirlaydi (partial): customer_id, assigned_operator_id, notes.

        Status/bekor/item bu yerda emas (/status, /cancel; item — zaxira ta'siri). Berilmagan
        maydonlar o'zgarmaydi (exclude_unset). customer/operator berilsa — mavjudligi tekshiriladi.
        """
        from app.modules.identity.models import User
        from app.modules.inbox.models import Customer

        order = await self.get(order_id)
        fields = data.model_dump(exclude_unset=True)
        if "customer_id" in fields and fields["customer_id"] is not None:
            if await self.db.get(Customer, fields["customer_id"]) is None:
                raise NotFoundError("Mijoz topilmadi")
            order.customer_id = fields["customer_id"]
        if "assigned_operator_id" in fields:
            op_id = fields["assigned_operator_id"]
            if op_id is not None and await self.db.get(User, op_id) is None:
                raise NotFoundError("Operator (foydalanuvchi) topilmadi")
            order.assigned_operator_id = op_id
        if "notes" in fields:
            order.notes = fields["notes"]
        await self.db.commit()
        return await self.get(order_id)

    # Tarkibni (item) tahrirlash faqat to'lov TASDIQLANMAGAN holatlarда — bunда faqat rezerv (reserved_qty)
    # ta'sirlanadi (stock_qty hali kamaymagan). confirmed+ da tahrirlash xavfli -> rad etamiz.
    _ITEMS_EDITABLE = {
        OrderStatus.draft, OrderStatus.pending, OrderStatus.waiting_payment, OrderStatus.payment_review,
    }

    async def replace_items(self, order_id: uuid.UUID, items, *, changed_by: uuid.UUID | None = None) -> Order:
        """Buyurtma TARKIBINI to'liq almashtiradi (mahsulot/soni/o'lcham/quti/gravyurka) + zaxira rezervini
        QAYTA hisoblaydi. `items` — buyurtmaning yangi to'liq ro'yxati (replace semantikasi)."""
        if not items:
            raise AppError("Buyurtmada kamida bitta mahsulot bo'lishi kerak")
        order = await self.get(order_id)
        if OrderStatus(order.status) not in self._ITEMS_EDITABLE:
            raise AppError(
                f"Bu holatda buyurtma tarkibini tahrirlab bo'lmaydi (holat={order.status}). "
                "To'lov tasdiqlangan/yetkazish boshlangan — bekor qilib qayta yarating."
            )
        # 1) eski itemlarning rezervini bo'shatamiz (reserved_qty--; variant/combo + box)
        await self._release_reservation(order)
        # 2) eski itemlarni o'chiramiz
        for old in list(order.items):
            await self.db.delete(old)
        order.items.clear()
        await self.db.flush()
        # 3) yangi itemlar: validatsiya + rezerv + narx (create_order bilan bir xil qoidalar)
        order.items_total = await self._process_items(order, items)
        order.grand_total = order.items_total + (order.delivery_fee or Decimal("0"))
        await self.db.commit()
        return await self.get(order_id)

    async def cancel_order(self, order_id: uuid.UUID, *, changed_by: uuid.UUID | None = None) -> Order:
        order = await self.get(order_id)
        if OrderStatus(order.status) not in _CANCELLABLE:
            raise AppError(f"Buyurtmani bekor qilib bo'lmaydi (status={order.status})")
        return await self.change_status(
            order_id, OrderStatus.cancelled, changed_by=changed_by, release_reservation=True
        )

    # Zaxira bo'shatishni talab qiladigan statuslar — bular /status orqali EMAS, /cancel orqali.
    _STATUS_VIA_CANCEL = {OrderStatus.cancelled, OrderStatus.refunded, OrderStatus.returned}

    async def set_status(
        self, order_id: uuid.UUID, to_status: OrderStatus, *, changed_by: uuid.UUID | None = None
    ) -> Order:
        """Kanban board: buyurtma statusini qo'lda o'zgartiradi (admin/menejer, drag-&-drop).

        Statusni yozadi + order_status_history qo'shadi. Zaxira-ta'sirli bekor/qaytarish
        (cancelled/refunded/returned) bu yerda QABUL QILINMAYDI — /orders/{id}/cancel ishlatiladi
        (u zaxirani bo'shatadi). Idempotent: yangi status eskisi bilan bir xil bo'lsa — o'zgarishsiz.
        """
        if to_status in self._STATUS_VIA_CANCEL:
            raise AppError("Bekor/qaytarish uchun /orders/{id}/cancel ishlating (zaxira bo'shatiladi)")
        order = await self.get(order_id)  # yo'q bo'lsa 404 "Buyurtma topilmadi"
        if order.status == to_status.value:
            return order  # idempotent — history yozilmaydi
        result = await self.change_status(order_id, to_status, changed_by=changed_by)
        # Buyurtma yo'lga chiqqanda mijozga avtomatik xabar (best-effort)
        if to_status == OrderStatus.shipping:
            await self._notify_customer_status(result, "ai_msg_order_shipping")
        return result

    async def _notify_customer_status(self, order: Order, msg_key: str) -> None:
        """Buyurtma statusi bo'yicha mijozga xabar (registrdagi matn). Best-effort — xato oqimni buzmaydi."""
        try:
            from app.modules.ai.prompt_registry import get_ai_text
            from app.modules.inbox.models import Customer
            from app.modules.inbox.repository import InboxRepository
            from app.modules.inbox.service import InboxService

            customer = await self.db.get(Customer, order.customer_id)
            if customer is None:
                return
            text = await get_ai_text(self.db, msg_key)
            await InboxService(InboxRepository(self.db)).notify_customer(order.customer_id, customer.channel, text)
        except Exception:  # noqa: BLE001
            logger.warning("status xabari yuborilmadi (order=%s)", order.id, exc_info=True)

    async def _release_reservation(self, order: Order) -> None:
        """Band qilingan zaxirani bo'shatadi (reserved_qty--), TZ 10. Variant/combo + box."""
        for item in order.items:
            for tv, need in await self.catalog.resolve_stock_targets(item.variant_id, item.quantity):
                tv.reserved_qty = max(0, tv.reserved_qty - need)
            if item.box_id is not None:
                box = await self.catalog.get_box(item.box_id)
                if box is not None:
                    box.reserved_qty = max(0, box.reserved_qty - item.quantity)
