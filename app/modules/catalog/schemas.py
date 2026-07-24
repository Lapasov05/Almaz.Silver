"""catalog Pydantic DTO'lari (ko'p tilli + reference jadvallar)."""
import uuid
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
    gram_price: Decimal | None = Field(default=None, ge=0)  # og'irlik kalkulyatori


class CategoryUpdate(BaseModel):
    name_uz: str | None = Field(default=None, max_length=150)
    name_ru: str | None = Field(default=None, max_length=150)
    slug: str | None = Field(default=None, max_length=150)
    parent_id: uuid.UUID | None = None
    gram_price: Decimal | None = Field(default=None, ge=0)


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name_uz: str
    name_ru: str | None
    slug: str
    parent_id: uuid.UUID | None
    gram_price: Decimal | None


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
    # Narx: bo'sh bo'lsa kategoriya gram_price * weight_grams orqali hisoblanadi
    price: Decimal | None = Field(default=None, ge=0)
    discount_price: Decimal | None = Field(default=None, ge=0)  # mijoz to'laydi
    weight_grams: Decimal | None = Field(default=None, ge=0)
    status: ProductStatus = ProductStatus.draft
    ai_keywords: list[str] | None = None
    engraving_available: bool = False
    engraving_price: Decimal | None = Field(default=None, ge=0)
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
    weight_grams: Decimal | None = Field(default=None, ge=0)
    status: ProductStatus | None = None
    ai_keywords: list[str] | None = None
    engraving_available: bool | None = None
    engraving_price: Decimal | None = Field(default=None, ge=0)


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category_id: uuid.UUID | None
    name_uz: str
    name_ru: str | None
    description_uz: str | None
    description_ru: str | None
    price: Decimal                 # asosiy (chizilgan)
    discount_price: Decimal | None  # chegirmali
    effective_price: Decimal        # mijoz to'laydigan narx
    weight_grams: Decimal | None
    status: ProductStatus
    ai_keywords: list[str] | None
    engraving_available: bool
    engraving_price: Decimal | None
    gender: ReferenceOut | None
    material: ReferenceOut | None
    stone: ReferenceOut | None
    variants: list[VariantOut]
    media: list[MediaOut]


# ---------- Og'irlik kalkulyatori ----------
class PriceCalcOut(BaseModel):
    category_id: uuid.UUID
    gram_price: Decimal
    weight_grams: Decimal
    price: Decimal


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
