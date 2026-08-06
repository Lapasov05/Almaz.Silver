"""delivery Service qatlami — checkout token + lokatsiya + zona fixed narx (TZ 11)."""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppError, NotFoundError
from app.modules.delivery.geo import branches_by_distance, is_in_tashkent
from app.modules.delivery.models import (
    CheckoutToken,
    CustomerLocation,
    Delivery,
    DeliveryProvider,
    DeliveryStatus,
    DeliveryZone,
    LocationType,
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
    def _zone_from_coords(self, lat: Decimal | None, lng: Decimal | None, *, fallback: str | None = None) -> str:
        """lat/lng Toshkent chegara-quti ichida bo'lsa 'tashkent', aks holda 'region'.

        Koordinata bo'lmasa — fallback (frontend bergan zona) yoki 'region'.
        """
        if lat is not None and lng is not None:
            la, ln = float(lat), float(lng)
            if (settings.delivery_tashkent_lat_min <= la <= settings.delivery_tashkent_lat_max
                    and settings.delivery_tashkent_lng_min <= ln <= settings.delivery_tashkent_lng_max):
                return DeliveryZone.tashkent.value
            return DeliveryZone.region.value
        return fallback or DeliveryZone.region.value

    async def create_checkout_link(self, order_id: uuid.UUID) -> tuple[str, str, datetime]:
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
        # Mijozga yuboriladigan xarita linki — frontend sahifasi: {frontend_map_url}/map/{token}
        url = f"{settings.frontend_map_url.rstrip('/')}/map/{raw}"
        return url, raw, expires_at

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

    # Tumandagi filial kam bo'lsa — viloyat darajasiga kengaytirish chegarasi
    _MIN_DISTRICT_BRANCHES = 3

    async def _candidate_branches(self, lat: Decimal, lng: Decimal) -> list[tuple]:
        """Mijozning viloyat+tumanidagi filiallar (masofa bo'yicha). Tumanda kam bo'lsa viloyatga
        kengaytiriladi. Qaytadi: [(branch, masofa_km), ...] yaqindan uzoqqa."""
        branches = await self.repo.list_active_bts_branches()
        if not branches:
            return []
        ranked = branches_by_distance(float(lat), float(lng), branches)
        ref = ranked[0][0]  # eng yaqin filial → mijoz viloyat/tumanini shu belgilaydi
        in_district = [(b, d) for b, d in ranked if b.region == ref.region and b.district == ref.district]
        if len(in_district) < self._MIN_DISTRICT_BRANCHES:  # kam bo'lsa — butun viloyat
            in_district = [(b, d) for b, d in ranked if b.region == ref.region]
        return in_district

    async def preview_location(self, raw_token: str, lat: Decimal | None, lng: Decimal | None) -> dict:
        """1-qadam: zona (operator ma'lumoti). Yetkazish puli OLINMAYDI (fee=0), filial tanlash yo'q.
        Token YOPILMAYDI, DB o'zgarmaydi."""
        token = await self._validate_token(raw_token)  # faqat tekshiradi, yopmaydi
        order = await self.orders.get(token.order_id)
        if lat is None or lng is None:
            raise AppError("Lokatsiya (lat/lng) yuborilishi shart")
        loc = LocationType.toshkent if is_in_tashkent(float(lat), float(lng)) else LocationType.bts
        # fee=0, branches=[] — uniform oqim (filial tanlash yo'q)
        return {"order": order, "location_type": loc, "fee": Decimal("0"), "branches": []}

    async def confirm_location(
        self,
        raw_token: str,
        *,
        lat: Decimal | None = None,
        lng: Decimal | None = None,
        bts_branch_id: uuid.UUID | None = None,
        address_text: str | None = None,
        phone: str | None = None,
        landmark: str | None = None,
        apartment: str | None = None,
    ) -> Delivery:
        """2-qadam: lat/lng + (BTS bo'lsa) TANLANGAN filialni buyurtmaga bog'laydi, token yopadi (TZ 11).

        Toshkent → type=Toshkent (50k). BTS → type=BTS (30k), `bts_branch_id` MAJBURIY (mijoz tanlagan).
        Mijoz lokatsiyasi `customer_location` (id bilan) saqlanadi.
        """
        token = await self._validate_token(raw_token)
        order = await self.orders.get(token.order_id)
        if lat is None or lng is None:
            raise AppError("Lokatsiya (lat/lng) yuborilishi shart")

        delivery = token.delivery or await self.repo.get_by_order(token.order_id)
        if delivery is None:
            delivery = Delivery(order_id=token.order_id)
            await self.repo.add(delivery)

        # Yetkazish puli OLINMAYDI (fee=0). Zona faqat operator ma'lumoti uchun aniqlanadi;
        # filial tanlash yo'q (uniform oqim). Lokatsiya baribir saqlanadi.
        fee = Decimal("0")
        if is_in_tashkent(float(lat), float(lng)):
            location_type = LocationType.toshkent
            resolved_zone = DeliveryZone.tashkent.value
            provider = DeliveryProvider.yandex.value
        else:
            location_type = LocationType.bts
            resolved_zone = DeliveryZone.region.value
            provider = DeliveryProvider.bts.value
        # Filial berilsa saqlaymiz (ixtiyoriy)
        branch = None
        if bts_branch_id is not None:
            branch = await self.repo.get_bts_branch(bts_branch_id)
            if branch is not None and not branch.is_active:
                branch = None
        # BTS zonasi + filial tanlanmagan bo'lsa — ENG YAQIN filialni AVTOMATIK biriktiramiz.
        # Shunda buyurtmaga filial (nom/manzil/ish vaqti) yoziladi va sotuvchi mijozga ayta oladi.
        if branch is None and location_type == LocationType.bts:
            cands = await self._candidate_branches(lat, lng)
            if cands:
                branch = cands[0][0]  # eng yaqin

        # --- Mijoz lokatsiyasini saqlaymiz (id bilan, qayta ishlatiladi) ---
        loc = CustomerLocation(
            customer_id=order.customer_id,
            lat=lat, lng=lng,
            location_type=location_type.value,
            bts_branch_id=(branch.id if branch is not None else None),
            address_text=address_text,
        )
        await self.repo.add(loc)

        # Map formadagi telefonni mijoz profiliga ham yozamiz (to'lov oldidan majburiy ma'lumot)
        if phone:
            from app.modules.inbox.models import Customer

            customer = await self.db.get(Customer, order.customer_id)
            if customer is not None and not (customer.phone or "").strip():
                customer.phone = phone[:32]

        delivery.zone = resolved_zone
        delivery.provider = provider
        delivery.location_type = location_type.value
        delivery.customer_location_id = loc.id
        delivery.bts_branch_id = branch.id if branch is not None else None
        delivery.fee = fee
        delivery.address_text = address_text
        delivery.lat = lat
        delivery.lng = lng
        delivery.phone = phone
        delivery.landmark = landmark
        delivery.apartment = apartment
        delivery.status = DeliveryStatus.ready.value

        # Buyurtmaga narxni qo'shamiz (TZ 11: to'lovdan oldin)
        order.delivery_fee = fee
        order.grand_total = order.items_total + fee
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

    async def resolve_checkout(self, raw_token: str, *, lat=None, lng=None, address_text=None,
                               phone=None, landmark=None, apartment=None, zone=None) -> Delivery:
        """Bir qadamli qulaylik (compat): BTS bo'lsa ENG YAQIN filial avtomatik tanlanadi.

        Frontend 2 qadamli oqim (preview→confirm)ni ishlatadi; bu CRM/eski chaqiruvlar uchun.
        """
        bts_branch_id = None
        if lat is not None and lng is not None and not is_in_tashkent(float(lat), float(lng)):
            cands = await self._candidate_branches(lat, lng)
            if cands:
                bts_branch_id = cands[0][0].id  # eng yaqin
        return await self.confirm_location(
            raw_token, lat=lat, lng=lng, bts_branch_id=bts_branch_id,
            address_text=address_text, phone=phone, landmark=landmark, apartment=apartment,
        )

    # ---------- Matnli manzil (fallback — xarita ishlamasa/mijoz matn yozsa, TZ 11) ----------
    @staticmethod
    def _zone_from_text(address_text: str) -> str:
        """Manzil MATNIdan zona taxminini aniqlaydi (koordinatasiz).

        "Toshkent shahri" -> tashkent; "Toshkent viloyati" yoki boshqa viloyat -> region.
        Aniq emas — operator baribir tekshiradi; narx model zonaga bog'liq emas (kuryerga to'lanadi).
        """
        low = (address_text or "").lower()
        has_tashkent = any(k in low for k in ("toshkent", "tashkent", "тошкент", "ташкент"))
        is_region = any(k in low for k in ("viloyat", "вилоят", "tuman", "туман"))
        if has_tashkent and not is_region:
            return DeliveryZone.tashkent.value
        return DeliveryZone.region.value

    async def set_text_address(
        self, order_id: uuid.UUID, address_text: str, *, phone: str | None = None
    ) -> Delivery:
        """Mijoz manzilni MATN bilan bergan holat — xarita/koordinata talab qilinmaydi.

        Buyurtmага manzilni bog'laydi, zonani matndan taxmin qiladi, holatni `waiting_payment`ga
        o'tkazadi. Yetkazish puli 0 (kuryerga/BTS bazasida to'lanadi — mahsulot summasi prepaid).
        """
        order = await self.orders.get(order_id)
        if order is None:
            raise NotFoundError("Buyurtma topilmadi")
        address_text = (address_text or "").strip()
        if not address_text:
            raise AppError("Manzil matni bo'sh")

        resolved_zone = self._zone_from_text(address_text)
        if resolved_zone == DeliveryZone.tashkent.value:
            location_type, provider = LocationType.toshkent.value, DeliveryProvider.yandex.value
        else:
            location_type, provider = LocationType.bts.value, DeliveryProvider.bts.value

        delivery = await self.repo.get_by_order(order_id)
        if delivery is None:
            delivery = Delivery(order_id=order_id)
            await self.repo.add(delivery)

        delivery.zone = resolved_zone
        delivery.provider = provider
        delivery.location_type = location_type
        delivery.address_text = address_text
        delivery.fee = Decimal("0")
        delivery.status = DeliveryStatus.ready.value
        if phone:
            delivery.phone = phone[:32]
            from app.modules.inbox.models import Customer

            customer = await self.db.get(Customer, order.customer_id)
            if customer is not None and not (customer.phone or "").strip():
                customer.phone = phone[:32]

        order.delivery_fee = Decimal("0")
        order.grand_total = order.items_total  # yetkazish qo'shilmaydi (kuryerga to'lanadi)
        if order.status == OrderStatus.pending.value:
            order.history.append(
                OrderStatusHistory(
                    from_status=order.status, to_status=OrderStatus.waiting_payment.value, changed_by=None
                )
            )
            order.status = OrderStatus.waiting_payment.value
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
