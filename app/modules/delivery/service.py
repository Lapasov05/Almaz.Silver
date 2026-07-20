"""delivery Service qatlami — checkout token + lokatsiya + zona fixed narx (TZ 11)."""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppError, NotFoundError
from app.modules.delivery.models import (
    CheckoutToken,
    Delivery,
    DeliveryProvider,
    DeliveryStatus,
    DeliveryZone,
)
from app.modules.delivery.repository import DeliveryRepository
from app.modules.delivery.tokens import generate_token, hash_token
from app.modules.orders.models import OrderStatus, OrderStatusHistory
from app.modules.orders.repository import OrdersRepository
from app.modules.settings.repository import SettingsRepository

settings = get_settings()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DeliveryService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = DeliveryRepository(db)
        self.orders = OrdersRepository(db)
        self.settings_repo = SettingsRepository(db)

    async def _fee_for_zone(self, zone: str) -> Decimal:
        key = "delivery_fee_tashkent" if zone == DeliveryZone.tashkent.value else "delivery_fee_region"
        setting = await self.settings_repo.get(key)
        return Decimal(str(setting.value)) if setting is not None else Decimal("0")

    async def _zone_fees(self) -> dict[str, Decimal]:
        return {
            DeliveryZone.tashkent.value: await self._fee_for_zone(DeliveryZone.tashkent.value),
            DeliveryZone.region.value: await self._fee_for_zone(DeliveryZone.region.value),
        }

    # ---------- Checkout link generatsiya (AI/operator chaqiradi) ----------
    async def create_checkout_link(self, order_id: uuid.UUID) -> tuple[str, datetime]:
        order = await self.orders.get(order_id)
        if order is None:
            raise NotFoundError("Buyurtma topilmadi")

        delivery = await self.repo.get_by_order(order_id)
        if delivery is None:
            delivery = Delivery(order_id=order_id, status=DeliveryStatus.awaiting_address.value)
            await self.repo.add(delivery)

        raw, token_hash = generate_token()
        expires_at = _utcnow() + timedelta(hours=settings.checkout_token_expiry_hours)
        await self.repo.add(
            CheckoutToken(
                order_id=order_id,
                delivery_id=delivery.id,
                token_hash=token_hash,
                expires_at=expires_at,
                used=False,
            )
        )
        await self.db.commit()
        url = f"{settings.public_base_url.rstrip('/')}/checkout/{raw}"
        return url, expires_at

    # ---------- Public checkout (mijoz sahifasi) ----------
    async def _validate_token(self, raw_token: str) -> CheckoutToken:
        token = await self.repo.get_token_by_hash(hash_token(raw_token))
        if token is None:
            raise NotFoundError("Checkout linki yaroqsiz")
        if token.used:
            raise AppError("Bu link allaqachon ishlatilgan")  # one-time / replay himoya
        if token.expires_at < _utcnow():
            raise AppError("Checkout linki muddati o'tgan")
        return token

    async def get_checkout_context(self, raw_token: str) -> dict:
        token = await self._validate_token(raw_token)
        order = await self.orders.get(token.order_id)
        return {
            "order_no": order.order_no,
            "items_total": order.items_total,
            "zones": await self._zone_fees(),
        }

    async def resolve_checkout(
        self,
        raw_token: str,
        *,
        zone: str,
        address_text: str | None,
        lat: Decimal | None,
        lng: Decimal | None,
    ) -> Delivery:
        """Lokatsiyani buyurtmaga bog'laydi, zona narxini qo'shadi, tokenni yopadi (TZ 11)."""
        token = await self._validate_token(raw_token)
        order = await self.orders.get(token.order_id)

        delivery = token.delivery or await self.repo.get_by_order(token.order_id)
        if delivery is None:
            delivery = Delivery(order_id=token.order_id)
            await self.repo.add(delivery)

        fee = await self._fee_for_zone(zone)
        provider = (
            DeliveryProvider.yandex.value
            if zone == DeliveryZone.tashkent.value
            else DeliveryProvider.bts.value
        )
        delivery.zone = zone
        delivery.provider = provider
        delivery.fee = fee
        delivery.address_text = address_text
        delivery.lat = lat
        delivery.lng = lng
        delivery.status = DeliveryStatus.ready.value

        # Buyurtmaga narxni qo'shamiz (TZ 11: to'lovdan oldin)
        order.delivery_fee = fee
        order.grand_total = order.items_total + fee
        # pending → waiting_payment (to'lovga tayyor)
        if order.status == OrderStatus.pending.value:
            order.history.append(
                OrderStatusHistory(
                    from_status=order.status, to_status=OrderStatus.waiting_payment.value, changed_by=None
                )
            )
            order.status = OrderStatus.waiting_payment.value

        token.used = True  # one-time use
        await self.db.commit()
        return delivery

    # ---------- CRM ----------
    async def get_by_order(self, order_id: uuid.UUID) -> Delivery:
        delivery = await self.repo.get_by_order(order_id)
        if delivery is None:
            raise NotFoundError("Yetkazish topilmadi")
        return delivery

    async def update_status(self, delivery_id: uuid.UUID, status: DeliveryStatus) -> Delivery:
        delivery = await self.repo.get(delivery_id)
        if delivery is None:
            raise NotFoundError("Yetkazish topilmadi")
        delivery.status = status.value
        await self.db.commit()
        return delivery
