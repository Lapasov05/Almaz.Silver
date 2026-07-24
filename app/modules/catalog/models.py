"""catalog ORM modellari — reference jadvallar + category, product, variant, product_media.

Yangilanish (0009):
- Ko'p tilli: `name_uz`/`name_ru`, `description_uz`/`description_ru`.
- Reference jadvallar (DB'dan, CRUD bilan): `gender` (kim uchun), `material`, `stone`.
- Narx: `price` (asosiy, chizilgan) + `discount_price` (chegirmali — mijoz to'laydi).
- Og'irlik: `product.weight_grams` + `category.gram_price` (kalkulyator).
"""
import enum
import uuid
from datetime import datetime
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Computed,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import Base, TimestampMixin, UUIDMixin


class ProductStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    archived = "archived"


class FulfillmentType(str, enum.Enum):
    stocked = "stocked"
    made_to_order = "made_to_order"
    unique = "unique"


class MediaChannel(str, enum.Enum):
    instagram = "instagram"
    telegram = "telegram"


# to_tsvector manbasi: uz+ru nom/tavsif + ai_keywords ('simple' konfiguratsiya)
_SEARCH_EXPR = (
    "to_tsvector('simple', "
    "coalesce(name_uz, '') || ' ' || coalesce(name_ru, '') || ' ' || "
    "coalesce(description_uz, '') || ' ' || coalesce(description_ru, '') || ' ' || "
    "coalesce(ai_keywords::text, ''))"
)


class _ReferenceMixin:
    """Ko'p tilli lug'at jadvallari uchun umumiy maydonlar (CRUD orqali boshqariladi)."""

    name_uz: Mapped[str] = mapped_column(String(150), nullable=False)
    name_ru: Mapped[str | None] = mapped_column(String(150), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)


class Gender(_ReferenceMixin, UUIDMixin, TimestampMixin, Base):
    """«Kim uchun» — erkak / ayol / uniseks (DB'dan, qo'lda yozilmaydi)."""

    __tablename__ = "gender"


class Material(_ReferenceMixin, UUIDMixin, TimestampMixin, Base):
    """Material — masalan «Kumush 925 + rodiy»."""

    __tablename__ = "material"


class Stone(_ReferenceMixin, UUIDMixin, TimestampMixin, Base):
    """Tosh turi — masalan «Serkon»."""

    __tablename__ = "stone"


class Category(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "category"

    name_uz: Mapped[str] = mapped_column(String(150), nullable=False)
    name_ru: Mapped[str | None] = mapped_column(String(150), nullable=True)
    slug: Mapped[str] = mapped_column(String(150), unique=True, index=True, nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("category.id", ondelete="SET NULL"), nullable=True
    )

    parent: Mapped["Category | None"] = relationship(remote_side="Category.id")


class Kurs(UUIDMixin, TimestampMixin, Base):
    """Gramm kursi (narx/gramm) — kategoriyaga ulangan. Og'irlik kalkulyatori shundan oladi.

    Bir kategoriyaда bir nechta kurs bo'lishi mumkin; kalkulyator eng oxirgi AKTIV kursni oladi.
    """

    __tablename__ = "kurs"

    category_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("category.id", ondelete="CASCADE"), nullable=False, index=True
    )
    value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)  # 1 gramm narxi
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)

    category: Mapped["Category"] = relationship()


class Product(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "product"

    category_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("category.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # --- Ko'p tilli nom/tavsif ---
    name_uz: Mapped[str] = mapped_column(String(255), nullable=False)
    name_ru: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description_uz: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_ru: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Reference (DB'dan) ---
    gender_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("gender.id", ondelete="SET NULL"), nullable=True
    )
    material_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("material.id", ondelete="SET NULL"), nullable=True
    )
    stone_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("stone.id", ondelete="SET NULL"), nullable=True
    )

    # --- Narx: asosiy + chegirmali ---
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)  # asosiy (chizilgan)
    discount_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)  # mijoz to'laydi
    # --- Og'irlik (kategoriya gram_price bilan kalkulyator) ---
    weight_grams: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)

    status: Mapped[ProductStatus] = mapped_column(
        Enum(ProductStatus, native_enum=False, name="product_status", length=20),
        server_default=ProductStatus.draft.value,
        nullable=False,
        index=True,
    )
    ai_keywords: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed(_SEARCH_EXPR, persisted=True), nullable=True
    )
    # --- Ism yozish (gravyurka) ---
    engraving_available: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    engraving_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    variants: Mapped[list["Variant"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    media: Mapped[list["ProductMedia"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    category: Mapped["Category | None"] = relationship()
    gender: Mapped["Gender | None"] = relationship()
    material: Mapped["Material | None"] = relationship()
    stone: Mapped["Stone | None"] = relationship()

    @property
    def effective_price(self) -> Decimal:
        """Mijoz to'laydigan narx: chegirma bo'lsa — o'sha, aks holda asosiy narx."""
        return self.discount_price if self.discount_price is not None else self.price


class Variant(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "variant"

    product_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("product.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    barcode: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    fulfillment_type: Mapped[FulfillmentType] = mapped_column(
        Enum(FulfillmentType, native_enum=False, name="fulfillment_type", length=20),
        server_default=FulfillmentType.stocked.value,
        nullable=False,
    )
    stock_qty: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    reserved_qty: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    product: Mapped["Product"] = relationship(back_populates="variants")

    @property
    def available(self) -> int:
        return self.stock_qty - self.reserved_qty


class ProductMedia(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "product_media"

    product_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("product.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel: Mapped[MediaChannel] = mapped_column(
        Enum(MediaChannel, native_enum=False, name="media_channel", length=20), nullable=False
    )
    external_media_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    shortcode: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    permalink: Mapped[str | None] = mapped_column(String(500), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)

    product: Mapped["Product"] = relationship(back_populates="media")
