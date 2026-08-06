"""delivery ORM modellari — delivery, checkout_token (TZ 6.2 / 11).

Yetkazish narxi zona bo'yicha FIXED (Toshkent 50k / viloyat 30k). Yandex API yo'q.
checkout_token: hash saqlanadi, muddatli, bir martalik (replay himoya).
"""
import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import Base, TimestampMixin, UUIDMixin


class DeliveryZone(str, enum.Enum):
    tashkent = "tashkent"
    region = "region"


class DeliveryProvider(str, enum.Enum):
    yandex = "yandex"  # Toshkent (manual — API yo'q)
    bts = "bts"        # viloyat (operator qo'lda)


class DeliveryStatus(str, enum.Enum):
    pending = "pending"
    awaiting_address = "awaiting_address"
    ready = "ready"
    dispatched = "dispatched"
    delivered = "delivered"


class LocationType(str, enum.Enum):
    """Lokatsiya turi — narx va yetkazish usulini belgilaydi (TZ 11)."""

    toshkent = "Toshkent"  # Toshkent shahar ichida — kuryer, 50k
    bts = "BTS"            # Toshkentdan tashqarida — eng yaqin BTS filiali, 30k


class BtsBranch(UUIDMixin, TimestampMixin, Base):
    """BTS filiali (yetkazish punkti) — bot_branches.json'dan seed qilinadi, dinamik qo'shsa bo'ladi."""

    __tablename__ = "bts_branch"

    ext_id: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)  # BTS "Id"
    name: Mapped[str] = mapped_column(String(150), nullable=False)          # Filial
    region: Mapped[str | None] = mapped_column(String(120), nullable=True)  # viloyat/shahar
    district: Mapped[str | None] = mapped_column(String(120), nullable=True)  # tuman
    address: Mapped[str | None] = mapped_column(Text, nullable=True)        # Manzil
    landmark: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Moljal (mo'ljal)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    work_hours: Mapped[str | None] = mapped_column(String(255), nullable=True)  # IshVaqtlari
    lat: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    lng: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)


class CustomerLocation(UUIDMixin, TimestampMixin, Base):
    """Mijoz lokatsiyasi — id bilan saqlanadi, buyurtmaga biriktiriladi, qayta ishlatiladi (TZ 7.3)."""

    __tablename__ = "customer_location"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("customer.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lat: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    lng: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    location_type: Mapped[LocationType] = mapped_column(String(20), nullable=False)  # Toshkent | BTS
    bts_branch_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("bts_branch.id", ondelete="SET NULL"), nullable=True
    )
    address_text: Mapped[str | None] = mapped_column(Text, nullable=True)


class Delivery(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "delivery"

    order_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("order.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    zone: Mapped[DeliveryZone | None] = mapped_column(String(20), nullable=True)
    provider: Mapped[DeliveryProvider | None] = mapped_column(String(20), nullable=True)
    fee: Mapped[Decimal] = mapped_column(Numeric(12, 2), server_default="0", nullable=False)
    address_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    lat: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    lng: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    # Qo'shimcha manzil (kuryer uchun)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    landmark: Mapped[str | None] = mapped_column(String(255), nullable=True)   # orientir (mo'ljal)
    apartment: Mapped[str | None] = mapped_column(String(255), nullable=True)  # qavat/kvartira/domofon
    # Lokatsiya turi (Toshkent/BTS) + biriktirilgan yozuvlar (TZ 11)
    location_type: Mapped[LocationType | None] = mapped_column(String(20), nullable=True)
    customer_location_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("customer_location.id", ondelete="SET NULL"), nullable=True
    )
    bts_branch_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("bts_branch.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[DeliveryStatus] = mapped_column(
        String(20), server_default=DeliveryStatus.pending.value, nullable=False
    )

    checkout_tokens: Mapped[list["CheckoutToken"]] = relationship(
        back_populates="delivery", cascade="all, delete-orphan"
    )
    # Tanlangan BTS filiali (mijozga "buyurtmangiz shu filialga boradi" deб ko'rsatish uchun).
    # lazy=selectin: har Delivery yuklanganda avtomatik eager (async'да xavfsiz, hamma yo'lni qamraydi).
    bts_branch: Mapped["BtsBranch | None"] = relationship("BtsBranch", lazy="selectin")


class CheckoutToken(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "checkout_token"

    order_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("order.id", ondelete="CASCADE"), nullable=False, index=True
    )
    delivery_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("delivery.id", ondelete="CASCADE"), nullable=True
    )
    # TZ 11/15: token ochiq saqlanmaydi — faqat hash
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)

    delivery: Mapped["Delivery | None"] = relationship(back_populates="checkout_tokens")
