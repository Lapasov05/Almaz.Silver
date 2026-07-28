"""catalog Pydantic DTO'lari (ko'p tilli + reference jadvallar)."""
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.catalog.models import (
    FulfillmentType,
    MediaChannel,
    ProductStatus,
)


# ---------- Reference lug'atlar (gender / material / stone) ----------
class ReferenceCreate(BaseModel):
    name_uz: str = Field(min_length=1, max_length=150)
    name_ru: str | None = Field(default=None, max_length=150)
    is_active: bool = True
    sort_order: int = 0


class ReferenceUpdate(BaseModel):
    name_uz: str | None = Field(default=None, max_length=150)
    name_ru: str | None = Field(default=None, max_length=150)
    is_active: bool | None = None
    sort_order: int | None = None


class ReferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name_uz: str
    name_ru: str | None
    is_active: bool
    sort_order: int


# ---------- Category ----------
class CategoryCreate(BaseModel):
    name_uz: str = Field(min_length=1, max_length=150)
    name_ru: str | None = Field(default=None, max_length=150)
    slug: str | None = Field(default=None, max_length=150)  # bo'sh -> name_uz'dan
    parent_id: uuid.UUID | None = None
    requires_ring_size: bool = False  # faqat Uzuklar uchun true


class CategoryUpdate(BaseModel):
    name_uz: str | None = Field(default=None, max_length=150)
    name_ru: str | None = Field(default=None, max_length=150)
    slug: str | None = Field(default=None, max_length=150)
    parent_id: uuid.UUID | None = None
    requires_ring_size: bool | None = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name_uz: str
    name_ru: str | None
    slug: str
    parent_id: uuid.UUID | None
    requires_ring_size: bool


# ---------- Variant ----------
class VariantCreate(BaseModel):
    sku: str | None = Field(default=None, max_length=64)
    barcode: str | None = Field(default=None, max_length=64)
    fulfillment_type: FulfillmentType = FulfillmentType.stocked
    stock_qty: int = Field(default=0, ge=0)
    is_active: bool = True


class VariantUpdate(BaseModel):
    barcode: str | None = Field(default=None, max_length=64)
    fulfillment_type: FulfillmentType | None = None
    is_active: bool | None = None


class StockAdjust(BaseModel):
    stock_qty: int | None = Field(default=None, ge=0)
    delta: int | None = None


# ---------- Box (kategoriyaning rangli qutisi) ----------
class BoxCreate(BaseModel):
    name_uz: str = Field(min_length=1, max_length=100)          # rang nomi, masalan "Qizil"
    name_ru: str | None = Field(default=None, max_length=100)
    color_hex: str | None = Field(default=None, max_length=9)   # "#E53935"
    price: Decimal = Field(default=Decimal("0"), ge=0)          # 0 = tekin
    stock_qty: int = Field(default=0, ge=0)
    is_active: bool = True
    sort_order: int = 0


class BoxUpdate(BaseModel):
    name_uz: str | None = Field(default=None, min_length=1, max_length=100)
    name_ru: str | None = Field(default=None, max_length=100)
    color_hex: str | None = Field(default=None, max_length=9)
    price: Decimal | None = Field(default=None, ge=0)
    is_active: bool | None = None
    sort_order: int | None = None


class BoxMediaCreate(BaseModel):
    image_url: str = Field(min_length=1, max_length=500)  # /files upload'dan qaytgan URL
    sort_order: int = 0


class BoxMediaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    image_url: str
    sort_order: int


class BoxOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category_id: uuid.UUID
    name_uz: str
    name_ru: str | None
    color_hex: str | None
    price: Decimal
    is_free: bool
    stock_qty: int
    reserved_qty: int
    available: int
    is_active: bool
    sort_order: int
    media: list[BoxMediaOut] = []  # galereya (rasm URL'lari)
    created_at: datetime


# ---------- Combo (to'plam = maxsus Product) ----------
class ComboItemIn(BaseModel):
    variant_id: uuid.UUID                    # komponent variant (odatda mahsulotning default varianti)
    quantity: int = Field(default=1, ge=1)


class ComboCreate(BaseModel):
    name_uz: str = Field(min_length=1, max_length=255)
    name_ru: str | None = Field(default=None, max_length=255)
    description_uz: str | None = None
    price: Decimal = Field(ge=0)                       # combo o'z narxi (qo'lda)
    discount_price: Decimal | None = Field(default=None, ge=0)
    status: ProductStatus = ProductStatus.draft
    items: list[ComboItemIn] = Field(min_length=1)     # kamida 1 komponent


class ComboUpdate(BaseModel):
    name_uz: str | None = Field(default=None, max_length=255)
    name_ru: str | None = Field(default=None, max_length=255)
    description_uz: str | None = None
    price: Decimal | None = Field(default=None, ge=0)
    discount_price: Decimal | None = Field(default=None, ge=0)
    status: ProductStatus | None = None


class ComboComponentOut(BaseModel):
    combo_item_id: uuid.UUID
    variant_id: uuid.UUID
    product_id: uuid.UUID
    name_uz: str
    price: Decimal            # komponent effective_price (faqat ko'rsatish)
    quantity: int
    available: int            # komponent mavjud zaxirasi
    image_url: str | None     # komponent birinchi rasmi


class ComboOut(BaseModel):
    id: uuid.UUID             # combo product id
    name_uz: str
    name_ru: str | None
    description_uz: str | None
    price: Decimal            # combo narxi (chegirma bo'lsa o'sha)
    old_price: Decimal | None
    status: ProductStatus
    variant_id: uuid.UUID | None  # buyurtma uchun combo varianti
    available: int            # min(komponent.available // quantity)
    items: list[ComboComponentOut]
    images: list[str] = []    # combo o'z galereyasi (product_media URL'lari)
    created_at: datetime


class VariantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    sku: str
    barcode: str | None
    fulfillment_type: FulfillmentType
    stock_qty: int
    reserved_qty: int
    available: int
    is_active: bool


# ---------- Media ----------
class MediaCreate(BaseModel):
    channel: MediaChannel = MediaChannel.instagram
    external_media_id: str | None = None
    permalink: str | None = Field(default=None, max_length=500)
    image_url: str | None = Field(default=None, max_length=500)
    shortcode_or_url: str | None = Field(default=None, max_length=500)


class MediaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    channel: MediaChannel
    external_media_id: str | None
    shortcode: str | None
    permalink: str | None
    image_url: str | None


# ---------- Instagram media (post/story link -> mahsulot) ----------
class InstagramMediaCreate(BaseModel):
    link: str = Field(min_length=1, max_length=500)              # IG post yoki story link
    image_url: str | None = Field(default=None, max_length=500)  # ixtiyoriy thumbnail (/files upload)


class InstagramMediaUpdate(BaseModel):
    is_active: bool | None = None
    image_url: str | None = Field(default=None, max_length=500)


class InstagramMediaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    media_type: str            # post | reel | story
    shortcode: str | None
    story_ref: str | None
    permalink: str | None
    image_url: str | None
    is_active: bool
    is_expired: bool           # story muddati o'tganmi
    expires_at: datetime | None
    created_at: datetime


# ---------- Product ----------
class ProductCreate(BaseModel):
    name_uz: str = Field(min_length=1, max_length=255)
    name_ru: str | None = Field(default=None, max_length=255)
    description_uz: str | None = None
    description_ru: str | None = None
    category_id: uuid.UUID | None = None
    gender_id: uuid.UUID | None = None
    material_id: uuid.UUID | None = None
    stone_id: uuid.UUID | None = None
    # Narx: asl (eski) narx majburiy; chegirma ixtiyoriy (bo'sh -> mijoz price to'laydi)
    price: Decimal = Field(ge=0)
    discount_price: Decimal | None = Field(default=None, ge=0)
    status: ProductStatus = ProductStatus.draft
    ai_keywords: list[str] | None = None
    engraving_available: bool = False
    engraving_price: Decimal | None = Field(default=None, ge=0)
    low_stock_threshold: int | None = Field(default=None, ge=0)  # bo'sh -> global sozlama
    variants: list[VariantCreate] | None = None
    media: list[MediaCreate] | None = None
    # Qulaylik: faqat rasm URL'larini berish (media yaratiladi)
    image_urls: list[str] | None = None


class ProductUpdate(BaseModel):
    name_uz: str | None = Field(default=None, max_length=255)
    name_ru: str | None = Field(default=None, max_length=255)
    description_uz: str | None = None
    description_ru: str | None = None
    category_id: uuid.UUID | None = None
    gender_id: uuid.UUID | None = None
    material_id: uuid.UUID | None = None
    stone_id: uuid.UUID | None = None
    price: Decimal | None = Field(default=None, ge=0)
    discount_price: Decimal | None = Field(default=None, ge=0)
    status: ProductStatus | None = None
    ai_keywords: list[str] | None = None
    engraving_available: bool | None = None
    engraving_price: Decimal | None = Field(default=None, ge=0)
    low_stock_threshold: int | None = Field(default=None, ge=0)


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category_id: uuid.UUID | None
    name_uz: str
    name_ru: str | None
    description_uz: str | None
    description_ru: str | None
    price: Decimal                  # asl (eski, chizilgan) narx
    discount_price: Decimal | None  # chegirma narx
    effective_price: Decimal        # mijoz to'laydigan narx (chegirma bo'lsa o'sha, aks holda price)
    status: ProductStatus
    ai_keywords: list[str] | None
    engraving_available: bool
    engraving_price: Decimal | None
    low_stock_threshold: int | None
    available: int                  # umumiy mavjud zaxira
    requires_ring_size: bool        # buyurtmada o'lcham kerakmi (kategoriyadan)
    gender: ReferenceOut | None
    material: ReferenceOut | None
    stone: ReferenceOut | None
    variants: list[VariantOut]
    media: list[MediaOut]


# ---------- Search ----------
class SearchHit(BaseModel):
    product: ProductOut
    match_type: str
    score: float | None = None


class SearchResponse(BaseModel):
    query: str | None
    match_type: str
    hits: list[SearchHit]


class SemanticSearchRequest(BaseModel):
    embedding: list[float] = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=50)
