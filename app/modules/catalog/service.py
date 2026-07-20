"""catalog Service qatlami — biznes logika (TZ 8-bo'lim).

- Universal "mahsulot qo'shish": product + variantlar + media bitta oqimda.
- Default variant (TZ muhim qaror 1): variant berilmasa, 1 ta default variant yaratiladi.
- 3 qatlamli qidiruv (TZ 8): (1) SKU/barcode → (2) IG shortcode → (3) tsvector.
"""
import uuid
from decimal import Decimal

from app.core.exceptions import AppError, NotFoundError
from app.modules.catalog.models import (
    Category,
    Product,
    ProductMedia,
    Variant,
)
from app.modules.catalog.repository import CatalogRepository
from app.modules.catalog.schemas import (
    CategoryCreate,
    CategoryUpdate,
    MediaCreate,
    ProductCreate,
    ProductUpdate,
    StockAdjust,
    VariantCreate,
    VariantUpdate,
)
from app.modules.catalog.search import extract_shortcode, is_instagram_url, slugify


class CatalogService:
    def __init__(self, repo: CatalogRepository):
        self.repo = repo

    # ---------- Category ----------
    async def create_category(self, data: CategoryCreate) -> Category:
        slug = data.slug or slugify(data.name)
        if await self.repo.get_category_by_slug(slug) is not None:
            raise AppError(f"Bu slug band: {slug}")
        category = Category(name=data.name, slug=slug, parent_id=data.parent_id)
        await self.repo.add(category)
        await self.repo.db.commit()
        return category

    async def list_categories(self) -> list[Category]:
        return await self.repo.list_categories()

    async def update_category(self, category_id: uuid.UUID, data: CategoryUpdate) -> Category:
        category = await self.repo.get_category(category_id)
        if category is None:
            raise NotFoundError("Kategoriya topilmadi")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(category, field, value)
        await self.repo.db.commit()
        return category

    async def delete_category(self, category_id: uuid.UUID) -> None:
        category = await self.repo.get_category(category_id)
        if category is None:
            raise NotFoundError("Kategoriya topilmadi")
        await self.repo.db.delete(category)
        await self.repo.db.commit()

    # ---------- Product ----------
    async def create_product(self, data: ProductCreate) -> Product:
        product = Product(
            name=data.name,
            category_id=data.category_id,
            gender=data.gender,
            material=data.material,
            stone=data.stone,
            price=data.price,
            compare_at_price=data.compare_at_price,
            status=data.status,
            description=data.description,
            ai_keywords=data.ai_keywords,
        )
        # Variantlar: berilganini ishlat, bo'lmasa 1 ta default (TZ muhim qaror 1)
        variant_inputs = data.variants or [VariantCreate()]
        for vin in variant_inputs:
            product.variants.append(self._build_variant(vin, data.name))
        # Media (IG shortcode ajratiladi)
        for min_ in data.media or []:
            product.media.append(self._build_media(min_))

        await self.repo.add(product)
        await self.repo.db.commit()
        # search_vector va default'lar DB tomonidan to'ldirilgani uchun qayta yuklaymiz
        refreshed = await self.repo.get_product(product.id)
        assert refreshed is not None
        return refreshed

    async def get_product(self, product_id: uuid.UUID) -> Product:
        product = await self.repo.get_product(product_id)
        if product is None:
            raise NotFoundError("Mahsulot topilmadi")
        return product

    async def list_products(self, **filters) -> list[Product]:
        return await self.repo.list_products(**filters)

    async def update_product(self, product_id: uuid.UUID, data: ProductUpdate) -> Product:
        product = await self.get_product(product_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(product, field, value)
        await self.repo.db.commit()
        return await self.get_product(product_id)

    async def delete_product(self, product_id: uuid.UUID) -> None:
        """Soft delete (TZ 6.1) — deleted_at to'ldiriladi."""
        product = await self.get_product(product_id)
        product.deleted_at = _utcnow()
        for variant in product.variants:
            variant.deleted_at = product.deleted_at
        await self.repo.db.commit()

    # ---------- Variant ----------
    def _build_variant(self, data: VariantCreate, product_name: str) -> Variant:
        return Variant(
            sku=data.sku or self._generate_sku(product_name),
            barcode=data.barcode,
            fulfillment_type=data.fulfillment_type,
            stock_qty=data.stock_qty,
            is_active=data.is_active,
        )

    @staticmethod
    def _generate_sku(product_name: str) -> str:
        base = slugify(product_name)[:16].upper().replace("-", "")
        return f"{base or 'SKU'}-{uuid.uuid4().hex[:6].upper()}"

    async def add_variant(self, product_id: uuid.UUID, data: VariantCreate) -> Variant:
        product = await self.get_product(product_id)
        variant = self._build_variant(data, product.name)
        variant.product_id = product.id
        await self.repo.add(variant)
        await self.repo.db.commit()
        return variant

    async def update_variant(self, variant_id: uuid.UUID, data: VariantUpdate) -> Variant:
        variant = await self.repo.get_variant(variant_id)
        if variant is None:
            raise NotFoundError("Variant topilmadi")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(variant, field, value)
        await self.repo.db.commit()
        return variant

    async def adjust_stock(self, variant_id: uuid.UUID, data: StockAdjust) -> Variant:
        """Zaxirani o'rnatish (stock_qty) yoki nisbiy o'zgartirish (delta).

        Eslatma: reservation transitions (reserved_qty) — Faza 4 (orders).
        """
        variant = await self.repo.get_variant(variant_id)
        if variant is None:
            raise NotFoundError("Variant topilmadi")
        if data.stock_qty is not None:
            variant.stock_qty = data.stock_qty
        elif data.delta is not None:
            new_qty = variant.stock_qty + data.delta
            if new_qty < 0:
                raise AppError("Zaxira manfiy bo'la olmaydi")
            variant.stock_qty = new_qty
        else:
            raise AppError("stock_qty yoki delta ko'rsatilishi kerak")
        await self.repo.db.commit()
        return variant

    # ---------- Media ----------
    def _build_media(self, data: MediaCreate) -> ProductMedia:
        shortcode = (
            extract_shortcode(data.shortcode_or_url) if data.shortcode_or_url else None
        )
        return ProductMedia(
            channel=data.channel,
            external_media_id=data.external_media_id,
            shortcode=shortcode,
            permalink=data.permalink,
            image_url=data.image_url,
        )

    async def add_media(self, product_id: uuid.UUID, data: MediaCreate) -> ProductMedia:
        product = await self.get_product(product_id)
        media = self._build_media(data)
        media.product_id = product.id
        await self.repo.add(media)
        await self.repo.db.commit()
        return media

    async def delete_media(self, media_id: uuid.UUID) -> None:
        media = await self.repo.get_media(media_id)
        if media is None:
            raise NotFoundError("Media topilmadi")
        await self.repo.db.delete(media)
        await self.repo.db.commit()

    # ---------- Qidiruv (3 qatlam, TZ 8) ----------
    async def search(
        self,
        *,
        q: str | None = None,
        sku: str | None = None,
        shortcode: str | None = None,
        limit: int = 10,
    ) -> tuple[str, list[tuple[Product, float | None]]]:
        """Qaytaradi: (match_type, [(product, score)])."""
        # 1-qatlam: aniq SKU/barcode (aniq param sifatida berilsa)
        if sku is not None:
            variant = await self.repo.get_variant_by_code(sku)
            if variant is not None:
                product = await self.repo.get_product(variant.product_id)
                if product is not None:
                    return ("sku", [(product, None)])
            return ("sku", [])

        # 2-qatlam: IG shortcode (aniq shortcode param yoki q ichidagi IG URL)
        sc = None
        if shortcode is not None:
            sc = extract_shortcode(shortcode)
        elif q is not None and is_instagram_url(q):
            sc = extract_shortcode(q)
        if sc is not None:
            product = await self.repo.get_product_by_shortcode(sc)
            return ("shortcode", [(product, None)] if product else [])

        # q toza matn bo'lsa: avval aniq kod, keyin tsvector
        if q:
            variant = await self.repo.get_variant_by_code(q)
            if variant is not None:
                product = await self.repo.get_product(variant.product_id)
                if product is not None:
                    return ("sku", [(product, None)])
            hits = await self.repo.search_text(q, limit)
            return ("text", [(p, s) for p, s in hits])

        return ("none", [])

    async def semantic_search(
        self, embedding: list[float], limit: int
    ) -> list[tuple[Product, float]]:
        """pgvector semantik qidiruv + product bo'yicha dedup (eng yaxshi skor)."""
        raw = await self.repo.search_by_embedding(embedding, limit * 3)
        seen: dict[uuid.UUID, tuple[Product, float]] = {}
        for product, score in raw:
            if product.id not in seen:
                seen[product.id] = (product, score)
        return list(seen.values())[:limit]


def _utcnow():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)
