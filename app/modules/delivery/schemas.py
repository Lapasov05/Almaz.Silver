"""delivery Pydantic DTO'lari."""
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.delivery.models import DeliveryProvider, DeliveryStatus, DeliveryZone


class CheckoutLinkOut(BaseModel):
    """Mijozga yuboriladigan bir martalik checkout link + raw token (frontend page uchun)."""

    url: str
    token: str          # frontend o'z page URL'ini qurishi uchun (bir martalik)
    expires_at: datetime


class DeliveryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID
    zone: DeliveryZone | None
    provider: DeliveryProvider | None
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
