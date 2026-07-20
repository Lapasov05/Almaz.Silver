"""catalog Repository qatlami — DB kirish + qidiruv so'rovlari (TZ 6.3 / 8-bo'lim).

Soft delete (TZ 6.1): product/variant o'chirilganда `deleted_at` to'ldiriladi;
o'qishда `deleted_at IS NULL` filtri qo'llanadi.
"""
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.catalog.models import (
    Category,
    Product,
    ProductMedia,
    Variant,
)

# Async'da relationlarni oldindan yuklash (lazy load I/O'siz)
_PRODUCT_LOADERS = (
    selectinload(Product.variants),
    selectinload(Product.media),
)


class CatalogRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------- Category ----------
    async def add(self, obj):
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def get_category(self, category_id: uuid.UUID) -> Category | None:
        return await self.db.get(Category, category_id)

    async def get_category_by_slug(self, slug: str) -> Category | None:
        res = await self.db.execute(select(Category).where(Category.slug == slug))
        return res.scalar_one_or_none()

    async def list_categories(self) -> list[Category]:
        res = await self.db.execute(select(Category).order_by(Category.name))
        return list(res.scalars().all())

    # ---------- Product ----------
    async def get_product(self, product_id: uuid.UUID) -> Product | None:
        res = await self.db.execute(
            select(Product)
            .options(*_PRODUCT_LOADERS)
            .where(Product.id == product_id, Product.deleted_at.is_(None))
        )
        return res.scalar_one_or_none()

    async def list_products(
        self,
        *,
        status: str | None = None,
        category_id: uuid.UUID | None = None,
        gender: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Product]:
        stmt = (
            select(Product)
            .options(*_PRODUCT_LOADERS)
            .where(Product.deleted_at.is_(None))
        )
        if status is not None:
            stmt = stmt.where(Product.status == status)
        if category_id is not None:
            stmt = stmt.where(Product.category_id == category_id)
        if gender is not None:
            stmt = stmt.where(Product.gender == gender)
        stmt = stmt.order_by(Product.created_at.desc()).limit(limit).offset(offset)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def refresh_product(self, product: Product) -> Product:
        """Yaratish/yangilashdan keyin to'liq relation'lar bilan qayta yuklash."""
        await self.db.refresh(product, attribute_names=["variants", "media"])
        return product

    # ---------- Variant ----------
    async def get_variant(self, variant_id: uuid.UUID) -> Variant | None:
        res = await self.db.execute(
            select(Variant).where(Variant.id == variant_id, Variant.deleted_at.is_(None))
        )
        return res.scalar_one_or_none()

    async def get_variant_by_code(self, code: str) -> Variant | None:
        """SKU yoki barcode bo'yicha aniq mos (TZ 8-bo'lim 1-qatlam)."""
        res = await self.db.execute(
            select(Variant).where(
                Variant.deleted_at.is_(None),
                (Variant.sku == code) | (Variant.barcode == code),
            )
        )
        return res.scalars().first()

    # ---------- Media ----------
    async def get_media(self, media_id: uuid.UUID) -> ProductMedia | None:
        return await self.db.get(ProductMedia, media_id)

    async def get_product_by_shortcode(self, shortcode: str) -> Product | None:
        """IG shortcode → product (TZ 7.5 deterministik lookup, 2-qatlam)."""
        res = await self.db.execute(
            select(Product)
            .options(*_PRODUCT_LOADERS)
            .join(ProductMedia, ProductMedia.product_id == Product.id)
            .where(ProductMedia.shortcode == shortcode, Product.deleted_at.is_(None))
        )
        return res.scalars().first()

    # ---------- Search ----------
    async def search_text(self, query: str, limit: int) -> list[tuple[Product, float]]:
        """tsvector to'liq matn qidiruvi (TZ 6.3 GIN, 3-qatlam)."""
        tsquery = func.websearch_to_tsquery("simple", query)
        rank = func.ts_rank(Product.search_vector, tsquery)
        stmt = (
            select(Product, rank.label("rank"))
            .options(*_PRODUCT_LOADERS)
            .where(
                Product.deleted_at.is_(None),
                Product.search_vector.op("@@")(tsquery),
            )
            .order_by(rank.desc())
            .limit(limit)
        )
        res = await self.db.execute(stmt)
        return [(row[0], float(row[1])) for row in res.all()]

    async def search_by_embedding(
        self, embedding: list[float], limit: int
    ) -> list[tuple[Product, float]]:
        """pgvector semantik qidiruv (TZ 6.3 hnsw / 7.5 fallback).

        Kosinus masofasi bo'yicha eng yaqin media → product. Masofa kichik = yaqinroq.
        """
        distance = ProductMedia.embedding.cosine_distance(embedding)
        stmt = (
            select(Product, distance.label("distance"))
            .options(*_PRODUCT_LOADERS)
            .join(ProductMedia, ProductMedia.product_id == Product.id)
            .where(
                Product.deleted_at.is_(None),
                ProductMedia.embedding.is_not(None),
            )
            .order_by(distance.asc())
            .limit(limit)
        )
        res = await self.db.execute(stmt)
        # score = 1 - distance (yuqori = yaqinroq), o'qish uchun qulay
        return [(row[0], 1.0 - float(row[1])) for row in res.all()]
