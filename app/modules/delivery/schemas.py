"""delivery Pydantic DTO'lari."""
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.delivery.models import (
    DeliveryProvider,
    DeliveryStatus,
    DeliveryZone,
    LocationType,
)


class CheckoutLinkOut(BaseModel):
    """Mijozga yuboriladigan bir martalik checkout link + raw token (frontend page uchun)."""

    url: str
    token: str          # frontend o'z page URL'ini qurishi uchun (bir martalik)
    expires_at: datetime


class BtsBranchOut(BaseModel):
    """BTS filiali (yetkazish punkti) — mijozga ko'rsatiladigan ma'lumot."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    region: str | None
    district: str | None
    address: str | None
    landmark: str | None
    phone: str | None
    work_hours: str | None
    lat: Decimal
    lng: Decimal


class BtsBranchWithDistanceOut(BtsBranchOut):
    """BTS filiali + mijoz nuqtasiga masofa (km) — ro'yxatni yaqindan uzoqqa ko'rsatish uchun."""

    distance_km: float


class LocationResolveIn(BaseModel):
    """1-qadam: mijoz xaritada belgilagan nuqta (token yopilmaydi)."""

    lat: Decimal
    lng: Decimal


class LocationResolveOut(BaseModel):
    """1-qadam natijasi: zona + narx + (BTS bo'lsa) tanlash uchun filiallar ro'yxati."""

    order_no: str
    location_type: LocationType             # Toshkent | BTS
    delivery_fee: Decimal
    items_total: Decimal
    grand_total: Decimal                    # items_total + delivery_fee (oldindan ko'rsatish)
    requires_branch_selection: bool         # BTS bo'lsa true — mijoz filial tanlashi kerak
    branches: list[BtsBranchWithDistanceOut]  # Toshkent bo'lsa bo'sh


class LocationConfirmIn(BaseModel):
    """2-qadam: mijoz filialni tanlab (BTS bo'lsa) tasdiqlaydi — token yopiladi."""

    lat: Decimal
    lng: Decimal
    bts_branch_id: uuid.UUID | None = None   # BTS bo'lsa MAJBURIY (tanlangan filial)
    address_text: str | None = Field(default=None, max_length=500)
    phone: str | None = Field(default=None, max_length=32)
    landmark: str | None = Field(default=None, max_length=255)
    apartment: str | None = Field(default=None, max_length=255)


class DeliveryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID
    zone: DeliveryZone | None
    provider: DeliveryProvider | None
    location_type: LocationType | None
    fee: Decimal
    address_text: str | None
    lat: Decimal | None
    lng: Decimal | None
    phone: str | None
    landmark: str | None
    apartment: str | None
    status: DeliveryStatus


class CheckoutContextOut(BaseModel):
    """Checkout sahifasi uchun (mijoz ko'radi): buyurtma xulosasi + zona narxlari."""

    order_no: str
    items_total: Decimal
    zones: dict[str, Decimal]  # {"tashkent": 50000, "region": 30000}


class CheckoutResultOut(BaseModel):
    """Mijoz lokatsiyani yuborgach frontendga qaytadigan natija (tasdiq sahifasi uchun)."""

    order_no: str
    location_type: LocationType       # Toshkent | BTS
    delivery_fee: Decimal
    items_total: Decimal
    grand_total: Decimal
    address_text: str | None = None
    bts_branch: BtsBranchOut | None = None  # BTS bo'lsa — eng yaqin filial


class CheckoutSubmit(BaseModel):
    # zona lat/lng'dan AVTOMATIK aniqlanadi; berilsa faqat koordinata bo'lmaganda fallback
    zone: DeliveryZone | None = None
    lat: Decimal | None = None
    lng: Decimal | None = None
    address_text: str | None = Field(default=None, max_length=500)
    phone: str | None = Field(default=None, max_length=32)
    landmark: str | None = Field(default=None, max_length=255)   # orientir (mo'ljal)
    apartment: str | None = Field(default=None, max_length=255)  # qavat/kvartira/domofon


class DeliveryStatusUpdate(BaseModel):
    status: DeliveryStatus
