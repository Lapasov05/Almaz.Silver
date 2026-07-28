"""catalog Repository qatlami — DB kirish + filtrlangan pagination (TZ 6.3 / 8)."""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.pagination import PageParams, paginate
from app.modules.catalog.models import (
    Box,
    BoxMedia,
    Category,
    ComboItem,
    Gender,
    Material,
    Product,
    ProductMedia,
    Stone,
    Variant,
)

_PRODUCT_LOADERS = (
    selectinload(Product.variants),
    selectinload(Product.media),
    selectinload(Product.gender),
    selectinload(Product.material),
    selectinload(Product.stone),
    selectinload(Product.category),  # requires_ring_size uchun
)

REFERENCE_MODELS = {"gender": Gender, "material": Material, "stone": Stone}


class CatalogRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add(self, obj):
        self.db.add(obj)
        await self.db.flush()
        return obj

    # ---------- Reference (gender / material / stone) ----------
    async def list_reference(self, kind: str, *, only_active: bool, q: str | None, pp: PageParams):
        model = REFERENCE_MODELS[kind]
        stmt = select(model)
        if only_active:
            stmt = stmt.where(model.is_active.is_(True))
        if q:
            like = f"%{q}%"
            stmt = stmt.where(or_(model.name_uz.ilike(like), model.name_ru.ilike(like)))
        return await paginate(self.db, stmt, [model.sort_order, model.name_uz], pp)

    async def get_reference(self, kind: str, ref_id: uuid.UUID):
        return await self.db.get(REFERENCE_MODELS[kind], ref_id)

    # ---------- Category ----------
    async def get_category(self, category_id: uuid.UUID) -> Category | None:
        return await self.db.get(Category, category_id)

    async def get_category_by_slug(self, slug: str) -> Category | None:
        res = await self.db.execute(select(Category).where(Category.slug == slug))
        return res.scalar_one_or_none()

    async def list_categories(self, *, parent_id: uuid.UUID | None, q: str | None, pp: PageParams):
        stmt = select(Category)
        if parent_id is not None:
            stmt = stmt.where(Category.parent_id == parent_id)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(or_(Category.name_uz.ilike(like), Category.name_ru.ilike(like)))
        return await paginate(self.db, stmt, [Category.name_uz], pp)

    # ---------- Sklad: kam qolgan mahsulotlar ----------
    async def list_low_stock(self, *, global_threshold: int, status: str | None, pp: PageParams):
        """Mavjud zaxira chegaradan kam bo'lgan mahsulotlar (faqat 'stocked' variantlar).

        Chegara: mahsulotning `low_stock_threshold` (bo'lsa), aks holda global sozlama.
        """
        avail = func.coalesce(func.sum(Variant.stock_qty - Variant.reserved_qty), 0)
        threshold = func.coalesce(Product.low_stock_threshold, global_threshold)
        base = (
            select(Product.id)
            .join(Variant, Variant.product_id == Product.id)
            .where(
                Product.deleted_at.is_(None),
                Variant.deleted_at.is_(None),
                Variant.is_active.is_(True),
                Variant.fulfillment_type == "stocked",
            )
        )
        if status is not None:
            base = base.where(Product.status == status)
        low_ids = base.group_by(Product.id, Product.low_stock_threshold).having(avail < threshold)

        stmt = select(Product).where(Product.id.in_(low_ids), Product.deleted_at.is_(None))
        return await paginate(self.db, stmt, [Product.created_at.desc()], pp, loaders=_PRODUCT_LOADERS)

    # ---------- Product ----------
    async def get_product(self, product_id: uuid.UUID) -> Product | None:
        res = await self.db.execute(
            select(Product).options(*_PRODUCT_LOADERS)
            .where(Product.id == product_id, Product.deleted_at.is_(None))
        )
        return res.scalar_one_or_none()

    async def list_products(
        self,
        *,
        pp: PageParams,
        status: str | None = None,
        category_id: uuid.UUID | None = None,
        gender_id: uuid.UUID | None = None,
        material_id: uuid.UUID | None = None,
        stone_id: uuid.UUID | None = None,
        engraving_available: bool | None = None,
        min_price: Decimal | None = None,
        max_price: Decimal | None = None,
        in_stock: bool | None = None,
        q: str | None = None,
    ):
        stmt = select(Product).where(Product.deleted_at.is_(None))
        if status is not None:
            stmt = stmt.where(Product.status == status)
        if category_id is not None:
            stmt = stmt.where(Product.category_id == category_id)
        if gender_id is not None:
            stmt = stmt.where(Product.gender_id == gender_id)
        if material_id is not None:
            stmt = stmt.where(Product.material_id == material_id)
        if stone_id is not None:
            stmt = stmt.where(Product.stone_id == stone_id)
        if engraving_available is not None:
            stmt = stmt.where(Product.engraving_available.is_(engraving_available))
        # Narx filtri amaldagi (effective) narx bo'yicha: coalesce(discount_price, price)
        eff = func.coalesce(Product.discount_price, Product.price)
        if min_price is not None:
            stmt = stmt.where(eff >= min_price)
        if max_price is not None:
            stmt = stmt.where(eff <= max_price)
        if in_stock:
            stmt = stmt.where(
                Product.id.in_(
                    select(Variant.product_id).where(
                        Variant.deleted_at.is_(None),
                        Variant.is_active.is_(True),
                        (Variant.stock_qty - Variant.reserved_qty) > 0,
                    )
                )
            )
        if q:
            like = f"%{q}%"
            stmt = stmt.where(or_(Product.name_uz.ilike(like), Product.name_ru.ilike(like)))
        return await paginate(self.db, stmt, [Product.created_at.desc()], pp, loaders=_PRODUCT_LOADERS)

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
    # ---------- Box (kategoriyaning rangli qutisi) ----------
    async def get_box(self, box_id: uuid.UUID) -> Box | None:
        res = await self.db.execute(
            select(Box).options(selectinload(Box.media)).where(
                Box.id == box_id, Box.deleted_at.is_(None)
            )
        )
        return res.scalar_one_or_none()

    async def list_boxes(self, *, category_id: uuid.UUID, only_active: bool, pp: PageParams):
        """Kategoriyaning box (rang) ro'yxati — admin (category bo'limi)."""
        stmt = select(Box).where(Box.category_id == category_id, Box.deleted_at.is_(None))
        if only_active:
            stmt = stmt.where(Box.is_active.is_(True))
        return await paginate(
            self.db, stmt, [Box.sort_order, Box.name_uz], pp, loaders=(selectinload(Box.media),)
        )

    async def list_active_boxes(self, category_id: uuid.UUID) -> list[Box]:
        """Faol boxlar (AI tool / checkout uchun) — pagination'siz, tartiblangan."""
        res = await self.db.execute(
            select(Box)
            .options(selectinload(Box.media))
            .where(
                Box.category_id == category_id,
                Box.deleted_at.is_(None),
                Box.is_active.is_(True),
            )
            .order_by(Box.sort_order, Box.name_uz)
        )
        return list(res.scalars().all())

    async def get_box_media(self, media_id: uuid.UUID) -> BoxMedia | None:
        return await self.db.get(BoxMedia, media_id)

    # ---------- Combo (to'plam = Product is_combo) ----------
    async def list_combos(self, *, status: str | None, q: str | None, pp: PageParams):
        stmt = select(Product).where(Product.is_combo.is_(True), Product.deleted_at.is_(None))
        if status:
            stmt = stmt.where(Product.status == status)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(or_(Product.name_uz.ilike(like), Product.name_ru.ilike(like)))
        return await paginate(self.db, stmt, [Product.created_at.desc()], pp, loaders=_PRODUCT_LOADERS)

    async def list_combo_items(self, combo_id: uuid.UUID) -> list[ComboItem]:
        """Combo tarkibi — komponent variant + uning mahsuloti + rasmlari bilan."""
        res = await self.db.execute(
            select(ComboItem)
            .where(ComboItem.combo_product_id == combo_id)
            .options(
                selectinload(ComboItem.component_variant)
                .selectinload(Variant.product)
                .selectinload(Product.media)
            )
            .order_by(ComboItem.sort_order)
        )
        return list(res.scalars().all())

    async def get_combo_item(self, item_id: uuid.UUID) -> ComboItem | None:
        return await self.db.get(ComboItem, item_id)

    async def resolve_stock_targets(
        self, variant_id: uuid.UUID, order_qty: int
    ) -> list[tuple[Variant, int]]:
        """Buyurtma order_item uchun zaxira o'zgaradigan variantlar + miqdor.

        Oddiy mahsulot -> [(variant, order_qty)].
        Combo (is_combo) -> har komponent [(component_variant, order_qty * combo_item.quantity)].
        """
        variant = await self.get_variant(variant_id)
        if variant is None:
            return []
        product = await self.get_product(variant.product_id)
        if product is not None and product.is_combo:
            items = await self.list_combo_items(product.id)
            return [(ci.component_variant, order_qty * ci.quantity) for ci in items]
        return [(variant, order_qty)]

    async def get_media(self, media_id: uuid.UUID) -> ProductMedia | None:
        return await self.db.get(ProductMedia, media_id)

    async def get_product_by_shortcode(self, shortcode: str) -> Product | None:
        res = await self.db.execute(
            select(Product).options(*_PRODUCT_LOADERS)
            .join(ProductMedia, ProductMedia.product_id == Product.id)
            .where(ProductMedia.shortcode == shortcode, Product.deleted_at.is_(None))
        )
        return res.scalars().first()

    async def get_product_by_story_ref(self, story_ref: str) -> Product | None:
        """Story_ref bo'yicha mahsulot — faol + muddati o'tmagan story."""
        now = datetime.now(timezone.utc)
        res = await self.db.execute(
            select(Product).options(*_PRODUCT_LOADERS)
            .join(ProductMedia, ProductMedia.product_id == Product.id)
            .where(
                ProductMedia.story_ref == story_ref,
                ProductMedia.is_active.is_(True),
                (ProductMedia.expires_at.is_(None)) | (ProductMedia.expires_at > now),
                Product.deleted_at.is_(None),
            )
        )
        return res.scalars().first()

    async def list_product_ig_media(self, product_id: uuid.UUID) -> list[ProductMedia]:
        """Mahsulotning IG media (post/reel/story) ro'yxati — admin bo'lim."""
        res = await self.db.execute(
            select(ProductMedia)
            .where(
                ProductMedia.product_id == product_id,
                ProductMedia.media_type.in_(("post", "reel", "story")),
            )
            .order_by(ProductMedia.created_at.desc())
        )
        return list(res.scalars().all())

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
