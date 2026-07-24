"""catalog Service qatlami — biznes logika (TZ 8).

- Reference lug'atlar (gender/material/stone) CRUD.
- Kurs (gramm narxi) CRUD, kategoriyaga ulangan; kalkulyator aktiv kursdan oladi.
- Ko'p tilli mahsulot; narx: asosiy + chegirmali (mijoz `effective_price` to'laydi).
- 3 qatlamli qidiruv (TZ 8).
"""
import uuid

from app.core.exceptions import AppError, NotFoundError
from app.core.pagination import PageParams
from app.modules.catalog.models import (
    Category,
    Product,
    ProductMedia,
    Variant,
)
from app.modules.catalog.repository import REFERENCE_MODELS, CatalogRepository
from app.modules.catalog.schemas import (
    CategoryCreate,
    CategoryUpdate,
    MediaCreate,
    ProductCreate,
    ProductUpdate,
    ReferenceCreate,
    ReferenceUpdate,
    StockAdjust,
    VariantCreate,
    VariantUpdate,
)
from app.modules.settings.repository import SettingsRepository
from app.modules.catalog.search import extract_shortcode, is_instagram_url, slugify


class CatalogService:
    def __init__(self, repo: CatalogRepository):
        self.repo = repo

    # ==================== Reference (gender / material / stone) ====================
    async def list_reference(self, kind: str, *, only_active: bool, q: str | None, pp: PageParams):
        return await self.repo.list_reference(kind, only_active=only_active, q=q, pp=pp)

    async def get_reference(self, kind: str, ref_id: uuid.UUID):
        item = await self.repo.get_reference(kind, ref_id)
        if item is None:
            raise NotFoundError(f"{kind} topilmadi")
        return item

    async def create_reference(self, kind: str, data: ReferenceCreate):
        item = REFERENCE_MODELS[kind](**data.model_dump())
        await self.repo.add(item)
        await self.repo.db.commit()
        return item

    async def update_reference(self, kind: str, ref_id: uuid.UUID, data: ReferenceUpdate):
        item = await self.get_reference(kind, ref_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(item, field, value)
        await self.repo.db.commit()
        return item

    async def delete_reference(self, kind: str, ref_id: uuid.UUID) -> None:
        item = await self.get_reference(kind, ref_id)
        await self.repo.db.delete(item)
        await self.repo.db.commit()

    # ==================== Category ====================
    async def create_category(self, data: CategoryCreate) -> Category:
        slug = data.slug or slugify(data.name_uz)
        if await self.repo.get_category_by_slug(slug) is not None:
            raise AppError(f"Bu slug band: {slug}")
        category = Category(name_uz=data.name_uz, name_ru=data.name_ru, slug=slug, parent_id=data.parent_id)
        await self.repo.add(category)
        await self.repo.db.commit()
        return category

    async def list_categories(self, *, parent_id, q, pp: PageParams):
        return await self.repo.list_categories(parent_id=parent_id, q=q, pp=pp)

    async def get_category(self, category_id: uuid.UUID) -> Category:
        category = await self.repo.get_category(category_id)
        if category is None:
            raise NotFoundError("Kategoriya topilmadi")
        return category

    async def update_category(self, category_id: uuid.UUID, data: CategoryUpdate) -> Category:
        category = await self.get_category(category_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(category, field, value)
        await self.repo.db.commit()
        return category

    async def delete_category(self, category_id: uuid.UUID) -> None:
        category = await self.get_category(category_id)
        await self.repo.db.delete(category)
        await self.repo.db.commit()

    # ==================== Sklad: kam qolgan mahsulotlar ====================
    async def list_low_stock(self, *, status, pp: PageParams):
        setting = await SettingsRepository(self.repo.db).get("low_stock_threshold")
        global_threshold = int(setting.value) if setting is not None else 10
        return await self.repo.list_low_stock(global_threshold=global_threshold, status=status, pp=pp)

    # ==================== Product ====================
    async def create_product(self, data: ProductCreate) -> Product:
        if data.discount_price is not None and data.discount_price > data.price:
            raise AppError("Chegirma narx asl narxdan katta bo'lmasligi kerak")
        product = Product(
            name_uz=data.name_uz, name_ru=data.name_ru,
            description_uz=data.description_uz, description_ru=data.description_ru,
            category_id=data.category_id, gender_id=data.gender_id,
            material_id=data.material_id, stone_id=data.stone_id,
            price=data.price, discount_price=data.discount_price,
            low_stock_threshold=data.low_stock_threshold,
            status=data.status, ai_keywords=data.ai_keywords,
            engraving_available=data.engraving_available, engraving_price=data.engraving_price,
        )
        for vin in (data.variants or [VariantCreate()]):
            product.variants.append(self._build_variant(vin, data.name_uz))
        for min_ in (data.media or []):
            product.media.append(self._build_media(min_))
        for url in (data.image_urls or []):
            product.media.append(self._build_media(MediaCreate(image_url=url)))
        await self.repo.add(product)
        await self.repo.db.commit()
        refreshed = await self.repo.get_product(product.id)
        assert refreshed is not None
        return refreshed

    async def get_product(self, product_id: uuid.UUID) -> Product:
        product = await self.repo.get_product(product_id)
        if product is None:
            raise NotFoundError("Mahsulot topilmadi")
        return product

    async def list_products(self, *, pp: PageParams, **filters):
        return await self.repo.list_products(pp=pp, **filters)

    async def update_product(self, product_id: uuid.UUID, data: ProductUpdate) -> Product:
        product = await self.get_product(product_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(product, field, value)
        if product.discount_price is not None and product.discount_price > product.price:
            raise AppError("Chegirma narx asl narxdan katta bo'lmasligi kerak")
        await self.repo.db.commit()
        return await self.get_product(product_id)

    async def delete_product(self, product_id: uuid.UUID) -> None:
        product = await self.get_product(product_id)
        product.deleted_at = _utcnow()
        for variant in product.variants:
            variant.deleted_at = product.deleted_at
        await self.repo.db.commit()

    # ==================== Variant ====================
    def _build_variant(self, data: VariantCreate, product_name: str) -> Variant:
        return Variant(
            sku=data.sku or self._generate_sku(product_name), barcode=data.barcode,
            fulfillment_type=data.fulfillment_type, stock_qty=data.stock_qty, is_active=data.is_active,
        )

    @staticmethod
    def _generate_sku(product_name: str) -> str:
        base = slugify(product_name)[:16].upper().replace("-", "")
        return f"{base or 'SKU'}-{uuid.uuid4().hex[:6].upper()}"

    async def add_variant(self, product_id: uuid.UUID, data: VariantCreate) -> Variant:
        product = await self.get_product(product_id)
        variant = self._build_variant(data, product.name_uz)
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

    # ==================== Media ====================
    def _build_media(self, data: MediaCreate) -> ProductMedia:
        shortcode = extract_shortcode(data.shortcode_or_url) if data.shortcode_or_url else None
        return ProductMedia(
            channel=data.channel, external_media_id=data.external_media_id,
            shortcode=shortcode, permalink=data.permalink, image_url=data.image_url,
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

    # ==================== Qidiruv (3 qatlam, TZ 8) ====================
    async def search(self, *, q=None, sku=None, shortcode=None, limit=10):
        if sku is not None:
            variant = await self.repo.get_variant_by_code(sku)
            if variant is not None:
                product = await self.repo.get_product(variant.product_id)
                if product is not None:
                    return ("sku", [(product, None)])
            return ("sku", [])
        sc = None
        if shortcode is not None:
            sc = extract_shortcode(shortcode)
        elif q is not None and is_instagram_url(q):
            sc = extract_shortcode(q)
        if sc is not None:
            product = await self.repo.get_product_by_shortcode(sc)
            return ("shortcode", [(product, None)] if product else [])
        if q:
            variant = await self.repo.get_variant_by_code(q)
            if variant is not None:
                product = await self.repo.get_product(variant.product_id)
                if product is not None:
                    return ("sku", [(product, None)])
            hits = await self.repo.search_text(q, limit)
            return ("text", [(p, s) for p, s in hits])
        return ("none", [])

    async def semantic_search(self, embedding, limit):
        raw = await self.repo.search_by_embedding(embedding, limit * 3)
        seen: dict[uuid.UUID, tuple[Product, float]] = {}
        for product, score in raw:
            if product.id not in seen:
                seen[product.id] = (product, score)
        return list(seen.values())[:limit]


def _utcnow():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)
