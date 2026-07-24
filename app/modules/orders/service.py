"""orders Service qatlami — buyurtma yaratish + reservation + status tarixi (TZ 10)."""
import secrets
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, NotFoundError
from app.modules.catalog.repository import CatalogRepository
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
        """Buyurtma + order_item yaratadi va zaxirani band qiladi (reserved_qty++)."""
        if not items:
            raise AppError("Buyurtmada kamida bitta mahsulot bo'lishi kerak")

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

        order = Order(
            order_no=await self._generate_order_no(),
            customer_id=customer_id,
            status=OrderStatus.pending.value,
            created_by_ai=created_by_ai,
        )
        items_total = Decimal("0")

        for it in items:
            variant = await self.catalog.get_variant(it.variant_id)
            if variant is None or not variant.is_active:
                raise AppError(f"Variant topilmadi yoki faol emas: {it.variant_id}")
            product = await self.catalog.get_product(variant.product_id)
            if product is None:
                raise AppError("Mahsulot topilmadi")

            # Zaxira tekshiruvi (faqat 'stocked' uchun; made_to_order/unique — talab qilmaydi)
            if variant.fulfillment_type == "stocked" and variant.available < it.quantity:
                raise AppError(
                    f"Zaxira yetarli emas (SKU {variant.sku}): mavjud {variant.available}, so'ralgan {it.quantity}"
                )

            variant.reserved_qty += it.quantity  # TZ 10: reservation
            unit_price = product.effective_price  # chegirma bo'lsa o'sha

            # --- Ism yozish (gravyurka) narxini aniqlash ---
            engraving_text = (it.engraving_text or "").strip() or None
            engraving_price = Decimal("0")
            if engraving_text is not None:
                if not engraving_enabled:
                    raise AppError("Ism yozish xizmati hozircha o'chirilgan")
                if not product.engraving_available:
                    raise AppError(f"Bu mahsulotga ism yozib bo'lmaydi: {product.name_uz}")
                # Mahsulotда o'z narxi bo'lsa o'sha, aks holda Settings'dagi narx
                engraving_price = (
                    product.engraving_price
                    if product.engraving_price is not None
                    else default_engraving_price
                )

            items_total += (unit_price + engraving_price) * it.quantity

            order.items.append(
                OrderItem(
                    variant_id=variant.id,
                    quantity=it.quantity,
                    unit_price=unit_price,
                    ring_size=it.ring_size,
                    bonus_snapshot=bonus_snapshot,
                    engraving_text=engraving_text,
                    engraving_price=engraving_price,
                )
            )

        order.items_total = items_total
        order.grand_total = items_total  # delivery_fee lokatsiyadan keyin qo'shiladi
        # Tarixni flush'dan OLDIN qo'shamiz (transient obyektда lazy-load bo'lmaydi)
        order.history.append(
            OrderStatusHistory(from_status=None, to_status=OrderStatus.pending.value, changed_by=changed_by)
        )

        await self.repo.add(order)
        await self.db.commit()
        return await self.get(order.id)

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

    async def cancel_order(self, order_id: uuid.UUID, *, changed_by: uuid.UUID | None = None) -> Order:
        order = await self.get(order_id)
        if OrderStatus(order.status) not in _CANCELLABLE:
            raise AppError(f"Buyurtmani bekor qilib bo'lmaydi (status={order.status})")
        return await self.change_status(
            order_id, OrderStatus.cancelled, changed_by=changed_by, release_reservation=True
        )

    async def _release_reservation(self, order: Order) -> None:
        """Band qilingan zaxirani bo'shatadi (reserved_qty--), TZ 10."""
        for item in order.items:
            variant = await self.catalog.get_variant(item.variant_id)
            if variant is not None:
                variant.reserved_qty = max(0, variant.reserved_qty - item.quantity)
