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
    UniqueConstraint,
    exists,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, column_property, mapped_column, relationship

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
    # Bu kategoriya mahsulotlarida o'lcham (uzuk razmeri) bo'ladimi. Faqat «Uzuklar» = true;
    # braslet/sepochka/zirak/komplekt — universal (o'lchamsiz).
    requires_ring_size: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    # requires_ring_size=true bo'lsa — bu kategoriyada mavjud o'lchamlar (masalan ["16","16.5","17","18"]).
    # Bo'sh/NULL bo'lsa istalgan o'lcham qabul qilinadi. O'lcham order_item'da (variant EMAS, TZ invariant 1).
    available_sizes: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    parent: Mapped["Category | None"] = relationship(remote_side="Category.id")


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

    # --- Narx: asosiy (eski) + chegirmali (yangi, mijoz to'laydi) ---
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)  # asl/eski narx
    discount_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)  # chegirma narx
    # --- Sklad: shu mahsulot uchun «kam qolgan» chegarasi (bo'sh -> global sozlama) ---
    low_stock_threshold: Mapped[int | None] = mapped_column(Integer, nullable=True)

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
    # Belgi limiti: bu uzukka sig'adigan maksimal belgi soni (NULL -> global settings.engraving_max_chars)
    engraving_max_chars: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- Garantiya override (NULL bo'lsa global settings.warranty_months) ---
    warranty_months: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- O'lcham o'zgartirish (zargar) — uzuklar uchun; NULL narx bo'lsa global settings.resize_price ---
    resize_available: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    resize_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    # --- Combo (to'plam) — is_combo=true bo'lsa bu mahsulot combo; ichi combo_item'da ---
    # Combo o'z narxiga ega (price/discount_price), lekin O'Z zaxirasi yo'q:
    # sotilganda ichidagi komponent variantlar zaxirasi band bo'ladi (order xizmati hal qiladi).
    is_combo: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False, index=True)

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
        """Mijoz to'laydigan narx: chegirma bo'lsa — o'sha, aks holda asl narx."""
        return self.discount_price if self.discount_price is not None else self.price

    @property
    def available(self) -> int:
        """Umumiy mavjud zaxira (faol, o'chirilmagan variantlar bo'yicha)."""
        return sum(
            max(v.stock_qty - v.reserved_qty, 0)
            for v in self.variants
            if v.is_active and v.deleted_at is None
        )

    @property
    def requires_ring_size(self) -> bool:
        """Bu mahsulotга buyurtmada o'lcham kerakmi (kategoriyadan). Universal bo'lsa False."""
        return bool(self.category and self.category.requires_ring_size)

    @property
    def available_sizes(self) -> list | None:
        """Kategoriyaga bog'langan mavjud o'lchamlar (uzuk bo'lsa). Bo'sh/universal -> None."""
        if self.requires_ring_size and self.category is not None:
            return self.category.available_sizes
        return None

    @property
    def requires_box(self) -> bool:
        """Bu mahsulotga buyurtmada quti (rang) MAJBURIYmi — kategoriyada zaxirada quti bo'lsa True."""
        return bool(self.category is not None and self.category.requires_box)


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


class Box(UUIDMixin, TimestampMixin, Base):
    """Kategoriyaning rangli qutisi (packaging) — har rang ALOHIDA yozuv.

    Foydalanuvchi qarorlari:
    - Har KATEGORIYA o'z rang ro'yxatiga ega (dynamic qo'shish/o'chirish); umumiy emas.
    - Har rangda ALOHIDA narx: `price=0` -> tekin, `>0` -> pulli.
    - Count (zaxira) har rangda — Variant kabi (`stock_qty`/`reserved_qty`, TZ 10 reservation).
    - Boshqaruv «category bo'limi»da (kategoriyaga scoped endpointlar).
    """

    __tablename__ = "box"

    category_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("category.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name_uz: Mapped[str] = mapped_column(String(100), nullable=False)      # rang nomi, masalan "Qizil"
    name_ru: Mapped[str | None] = mapped_column(String(100), nullable=True)
    color_hex: Mapped[str | None] = mapped_column(String(9), nullable=True)  # UI swatch, masalan "#E53935"
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), server_default="0", nullable=False)  # 0 = tekin
    stock_qty: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    reserved_qty: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    category: Mapped["Category"] = relationship()
    media: Mapped[list["BoxMedia"]] = relationship(
        back_populates="box", cascade="all, delete-orphan", order_by="BoxMedia.sort_order"
    )

    @property
    def available(self) -> int:
        return self.stock_qty - self.reserved_qty

    @property
    def is_free(self) -> bool:
        return self.price == 0


# Kategoriyada quti MAJBURIYmi — kategoriyada faol, ZAXIRADA bor (available>0) quti bo'lsa True.
# Buyurtmada quti majburiyligi shu shart bilan tekshiriladi; frontend oldindan bilishi uchun.
Category.requires_box = column_property(
    exists()
    .where(
        Box.category_id == Category.id,
        Box.is_active.is_(True),
        Box.deleted_at.is_(None),
        Box.stock_qty > Box.reserved_qty,
    )
    .correlate_except(Box),
    deferred=False,
)


class BoxMedia(UUIDMixin, TimestampMixin, Base):
    """Box (rangli quti) galereyasi — har box'da bir nechta rasm (URL, /files upload'dan)."""

    __tablename__ = "box_media"

    box_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("box.id", ondelete="CASCADE"), nullable=False, index=True
    )
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)

    box: Mapped["Box"] = relationship(back_populates="media")


class ComboItem(UUIDMixin, TimestampMixin, Base):
    """Combo tarkibi — combo (Product is_combo) ichidagi bitta komponent variant + soni.

    `component_variant_id` orqali zaxira band qilinadi (variant -> product -> media rasmi).
    """

    __tablename__ = "combo_item"
    __table_args__ = (
        UniqueConstraint("combo_product_id", "component_variant_id", name="uq_combo_item"),
    )

    combo_product_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("product.id", ondelete="CASCADE"), nullable=False, index=True
    )
    component_variant_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("variant.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, server_default="1", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)

    combo: Mapped["Product"] = relationship(foreign_keys=[combo_product_id])
    component_variant: Mapped["Variant"] = relationship(foreign_keys=[component_variant_id])


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

    # --- Instagram media turi (post/reel/story/image) va story bog'lash ---
    # media_type: image (oddiy rasm) | post | reel | story
    media_type: Mapped[str] = mapped_column(String(20), server_default="image", nullable=False)
    # story_ref: IG story media_id — webhook `reply_to.story.id` bilan mos (story uchun)
    story_ref: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    # expires_at: story 24 soat turadi (post/reel/image = NULL, doimiy)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    # --- Kontent boshqaruvi: matn + holat (rejalashtirish) + samaradorlik (engagement) ---
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)  # kontent matni
    # status: draft (qoralama) | scheduled (rejalashtirilgan) | published (e'lon qilingan)
    status: Mapped[str] = mapped_column(String(20), server_default="published", nullable=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # engagement: NULL = hali o'lchanmagan (IG'dan olinmagan); son = o'lchangan. 0 emas!
    like_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    view_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comment_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    product: Mapped["Product"] = relationship(back_populates="media")

    @property
    def is_expired(self) -> bool:
        """Story muddati o'tганmi (expires_at bo'lsa va o'tган bo'lsa)."""
        from datetime import timezone as _tz

        return self.expires_at is not None and self.expires_at < datetime.now(_tz.utc)
