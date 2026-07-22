"""catalog Pydantic DTO'lari (API kontrakti)."""
import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.catalog.models import (
    FulfillmentType,
    Gender,
    MediaChannel,
    ProductStatus,
)


# ---------- Category ----------
class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    slug: str | None = Field(default=None, max_length=150)  # bo'sh bo'lsa name'dan generatsiya
    parent_id: uuid.UUID | None = None


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=150)
    slug: str | None = Field(default=None, max_length=150)
    parent_id: uuid.UUID | None = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    parent_id: uuid.UUID | None


# ---------- Variant ----------
class VariantCreate(BaseModel):
    sku: str | None = Field(default=None, max_length=64)  # bo'sh bo'lsa auto-generatsiya
    barcode: str | None = Field(default=None, max_length=64)
    fulfillment_type: FulfillmentType = FulfillmentType.stocked
    stock_qty: int = Field(default=0, ge=0)
    is_active: bool = True


class VariantUpdate(BaseModel):
    barcode: str | None = Field(default=None, max_length=64)
    fulfillment_type: FulfillmentType | None = None
    is_active: bool | None = None


class StockAdjust(BaseModel):
    """Zaxirani o'rnatish yoki nisbiy o'zgartirish (delta)."""

    stock_qty: int | None = Field(default=None, ge=0)  # aniq qiymat o'rnatish
    delta: int | None = None  # nisbiy o'zgartirish (+/-)


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
    # IG URL yoki tayyor shortcode — service ajratadi
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
    name: str = Field(min_length=1, max_length=255)
    category_id: uuid.UUID | None = None
    gender: Gender = Gender.uniseks
    material: str = "Kumush 925 + rodiy"
    stone: str = "serkon"
    price: Decimal = Field(ge=0)
    compare_at_price: Decimal | None = Field(default=None, ge=0)
    status: ProductStatus = ProductStatus.draft
    description: str | None = None
    ai_keywords: list[str] | None = None
    # Ism yozish (gravyurka): shu mahsulotga mumkinmi + ixtiyoriy narx.
    # engraving_price bo'sh bo'lsa Settings'dagi `engraving_price` ishlatiladi.
    engraving_available: bool = False
    engraving_price: Decimal | None = Field(default=None, ge=0)
    variants: list[VariantCreate] | None = None  # bo'sh bo'lsa default variant yaratiladi
    media: list[MediaCreate] | None = None


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    category_id: uuid.UUID | None = None
    gender: Gender | None = None
    material: str | None = None
    stone: str | None = None
    price: Decimal | None = Field(default=None, ge=0)
    compare_at_price: Decimal | None = Field(default=None, ge=0)
    status: ProductStatus | None = None
    description: str | None = None
    ai_keywords: list[str] | None = None
    engraving_available: bool | None = None
    engraving_price: Decimal | None = Field(default=None, ge=0)


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category_id: uuid.UUID | None
    name: str
    gender: Gender
    material: str
    stone: str
    price: Decimal
    compare_at_price: Decimal | None
    status: ProductStatus
    description: str | None
    ai_keywords: list[str] | None
    engraving_available: bool
    engraving_price: Decimal | None  # None -> Settings'dagi narx qo'llanadi
    variants: list[VariantOut]
    media: list[MediaOut]


# ---------- Search ----------
class SearchHit(BaseModel):
    product: ProductOut
    match_type: str  # sku | barcode | shortcode | text | semantic
    score: float | None = None


class SearchResponse(BaseModel):
    query: str | None
    match_type: str
    hits: list[SearchHit]


class SemanticSearchRequest(BaseModel):
    """pgvector semantik qidiruv — embedding to'g'ridan-to'g'ri beriladi.

    Embedding generatsiyasi (OpenAI) — Faza 3 (AI); Faza 1'da mexanizm tayyor.
    """

    embedding: list[float] = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=50)
