"""catalog ORM modellari — category, product, variant, product_media (TZ 6.2 / 8-bo'lim).

Muhim qarorlar (TZ 6.2 / 18-bo'lim):
1. O'lcham variant EMAS — buyurtmada belgilanadi (`order_item.ring_size`), hamma o'lcham bir narx.
   `variant` asosan 1:1 (har product'ga bitta default variant); qatlam komplekt/kelajak uchun.
2. Zaxira `variant` ichida (`stock_qty`/`reserved_qty`); `available = stock_qty − reserved_qty`.
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


# --- Enum'lar (VARCHAR + CHECK sifatida saqlanadi: native_enum=False) ---
class Gender(str, enum.Enum):
    erkak = "erkak"
    ayol = "ayol"
    uniseks = "uniseks"


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


# to_tsvector uchun manba ifoda (TZ 6.3: nom + tavsif + ai_keywords).
# 'simple' konfiguratsiya — o'zbekcha uchun xavfsiz (noto'g'ri stemming yo'q);
# maxsus o'zbek lug'ati Faza 7'da qo'shilishi mumkin.
_SEARCH_EXPR = (
    "to_tsvector('simple', "
    "coalesce(name, '') || ' ' || "
    "coalesce(description, '') || ' ' || "
    "coalesce(ai_keywords::text, ''))"
)


class Category(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "category"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    slug: Mapped[str] = mapped_column(String(150), unique=True, index=True, nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("category.id", ondelete="SET NULL"), nullable=True
    )

    parent: Mapped["Category | None"] = relationship(remote_side="Category.id")


class Product(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "product"

    category_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("category.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    gender: Mapped[Gender] = mapped_column(
        Enum(Gender, native_enum=False, name="gender", length=20),
        server_default=Gender.uniseks.value,
        nullable=False,
    )
    # TZ 15-bo'lim guardrail: material doim "Kumush 925 + rodiy", tosh doim "serkon"
    material: Mapped[str] = mapped_column(
        String(100), server_default="Kumush 925 + rodiy", nullable=False
    )
    stone: Mapped[str] = mapped_column(String(100), server_default="serkon", nullable=False)
    # TZ 2/15-bo'lim: qat'iy (fixed) narx + yuqori eski narx (compare_at_price)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    compare_at_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    status: Mapped[ProductStatus] = mapped_column(
        Enum(ProductStatus, native_enum=False, name="product_status", length=20),
        server_default=ProductStatus.draft.value,
        nullable=False,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # AI qidiruvi uchun kalit so'zlar/sinonimlar (TZ 6.2/8)
    ai_keywords: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # --- Ism yozish (gravyurka) xizmati ---
    # Shu mahsulotga ism yozish mumkinmi (mahsulot qo'shishда belgilanadi)
    engraving_available: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False
    )
    # Ixtiyoriy narx override; NULL bo'lsa Settings'dagi `engraving_price` ishlatiladi
    engraving_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    # DB tomonidan generatsiya qilinadigan to'liq matn indeksi (TZ 6.3 GIN)
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed(_SEARCH_EXPR, persisted=True), nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    variants: Mapped[list["Variant"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    media: Mapped[list["ProductMedia"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    category: Mapped["Category | None"] = relationship()


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
    # TZ 6.2 muhim qaror 2: zaxira variant ichida
    stock_qty: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    reserved_qty: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default="true", nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    product: Mapped["Product"] = relationship(back_populates="variants")

    @property
    def available(self) -> int:
        """available = stock_qty − reserved_qty (TZ 6.1)."""
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
    # TZ 7.5: IG URL → shortcode → aniq mahsulot (deterministik lookup). UNIQUE.
    shortcode: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    permalink: Mapped[str | None] = mapped_column(String(500), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # TZ 6.3/7.5: rasm/semantik fallback uchun embedding (hnsw). To'ldirish — Faza 3 (AI).
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)

    product: Mapped["Product"] = relationship(back_populates="media")
