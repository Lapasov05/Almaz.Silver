"""catalog Repository qatlami — DB kirish + qidiruv (TZ 6.3 / 8)."""
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.catalog.models import (
    Category,
    Gender,
    Material,
    Product,
    ProductMedia,
    Stone,
    Variant,
)

# Async'da relationlarni oldindan yuklash (lazy load I/O'siz)
_PRODUCT_LOADERS = (
    selectinload(Product.variants),
    selectinload(Product.media),
    selectinload(Product.gender),
    selectinload(Product.material),
    selectinload(Product.stone),
)

# Reference jadval nomi -> model
REFERENCE_MODELS = {"gender": Gender, "material": Material, "stone": Stone}


class CatalogRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add(self, obj):
        self.db.add(obj)
        await self.db.flush()
        return obj

    # ---------- Reference (gender / material / stone) ----------
    async def list_reference(self, kind: str, *, only_active: bool = False) -> list:
        model = REFERENCE_MODELS[kind]
        stmt = select(model)
        if only_active:
            stmt = stmt.where(model.is_active.is_(True))
        stmt = stmt.order_by(model.sort_order, model.name_uz)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_reference(self, kind: str, ref_id: uuid.UUID):
        return await self.db.get(REFERENCE_MODELS[kind], ref_id)

    # ---------- Category ----------
    async def get_category(self, category_id: uuid.UUID) -> Category | None:
        return await self.db.get(Category, category_id)

    async def get_category_by_slug(self, slug: str) -> Category | None:
        res = await self.db.execute(select(Category).where(Category.slug == slug))
        return res.scalar_one_or_none()

    async def list_categories(self) -> list[Category]:
        res = await self.db.execute(select(Category).order_by(Category.name_uz))
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
        gender_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Product]:
        stmt = select(Product).options(*_PRODUCT_LOADERS).where(Product.deleted_at.is_(None))
        if status is not None:
            stmt = stmt.where(Product.status == status)
        if category_id is not None:
            stmt = stmt.where(Product.category_id == category_id)
        if gender_id is not None:
            stmt = stmt.where(Product.gender_id == gender_id)
        stmt = stmt.order_by(Product.created_at.desc()).limit(limit).offset(offset)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    # ---------- Variant ----------
    async def get_variant(self, variant_id: uuid.UUID) -> Variant | None:
        res = await self.db.execute(
            select(Variant).where(Variant.id == variant_id, Variant.deleted_at.is_(None))
        )
        return res.scalar_one_or_none()

    async def get_variant_by_code(self, code: str) -> Variant | None:
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
        res = await self.db.execute(
            select(Product)
            .options(*_PRODUCT_LOADERS)
            .join(ProductMedia, ProductMedia.product_id == Product.id)
            .where(ProductMedia.shortcode == shortcode, Product.deleted_at.is_(None))
        )
        return res.scalars().first()

    # ---------- Search ----------
    async def search_text(self, query: str, limit: int) -> list[tuple[Product, float]]:
        tsquery = func.websearch_to_tsquery("simple", query)
        rank = func.ts_rank(Product.search_vector, tsquery)
        stmt = (
            select(Product, rank.label("rank"))
            .options(*_PRODUCT_LOADERS)
            .where(Product.deleted_at.is_(None), Product.search_vector.op("@@")(tsquery))
            .order_by(rank.desc())
            .limit(limit)
        )
        res = await self.db.execute(stmt)
        return [(row[0], float(row[1])) for row in res.all()]

    async def search_by_embedding(self, embedding: list[float], limit: int) -> list[tuple[Product, float]]:
        distance = ProductMedia.embedding.cosine_distance(embedding)
        stmt = (
            select(Product, distance.label("distance"))
            .options(*_PRODUCT_LOADERS)
            .join(ProductMedia, ProductMedia.product_id == Product.id)
            .where(Product.deleted_at.is_(None), ProductMedia.embedding.is_not(None))
            .order_by(distance.asc())
            .limit(limit)
        )
        res = await self.db.execute(stmt)
        return [(row[0], 1.0 - float(row[1])) for row in res.all()]
