"""catalog Service qatlami — biznes logika (TZ 8).

- Reference lug'atlar (gender/material/stone) CRUD.
- Ko'p tilli mahsulot; narx: asosiy + chegirmali (mijoz `effective_price` to'laydi).
- Og'irlik kalkulyatori: narx berilmasa `category.gram_price * weight_grams`.
- 3 qatlamli qidiruv (TZ 8): SKU/barcode -> IG shortcode -> tsvector.
"""
import uuid
from decimal import ROUND_HALF_UP, Decimal

from app.core.exceptions import AppError, NotFoundError
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
from app.modules.catalog.search import extract_shortcode, is_instagram_url, slugify


class CatalogService:
    def __init__(self, repo: CatalogRepository):
        self.repo = repo

    # ==================== Reference (gender / material / stone) ====================
    async def list_reference(self, kind: str, *, only_active: bool = False) -> list:
        return await self.repo.list_reference(kind, only_active=only_active)

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
        category = Category(
            name_uz=data.name_uz, name_ru=data.name_ru, slug=slug,
            parent_id=data.parent_id, gram_price=data.gram_price,
        )
        await self.repo.add(category)
        await self.repo.db.commit()
        return category

    async def list_categories(self) -> list[Category]:
        return await self.repo.list_categories()

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

    # ==================== Og'irlik kalkulyatori ====================
    @staticmethod
    def _calc_price(gram_price: Decimal, weight_grams: Decimal) -> Decimal:
        return (gram_price * weight_grams).quantize(Decimal("1"), rounding=ROUND_HALF_UP)

    async def calc_price(self, category_id: uuid.UUID, weight_grams: Decimal) -> dict:
        """Kategoriya gramm narxi bo'yicha narxni hisoblab beradi (oldindan ko'rish)."""
        category = await self.get_category(category_id)
        if category.gram_price is None:
            raise AppError("Bu kategoriyada gramm narxi (gram_price) belgilanmagan")
        return {
            "category_id": category.id,
            "gram_price": category.gram_price,
            "weight_grams": weight_grams,
            "price": self._calc_price(category.gram_price, weight_grams),
        }

    async def _resolve_price(self, data: ProductCreate) -> Decimal:
        """Narx: qo'lda berilgan bo'lsa o'sha; aks holda og'irlik x gramm narxi."""
        if data.price is not None:
            return data.price
        if data.category_id is not None and data.weight_grams is not None:
            category = await self.repo.get_category(data.category_id)
            if category is not None and category.gram_price is not None:
                return self._calc_price(category.gram_price, data.weight_grams)
        raise AppError(
            "Narx ko'rsatilmagan. Yo `price` bering, yoki kategoriyada `gram_price` "
            "va mahsulotда `weight_grams` bo'lsin (kalkulyator)."
        )

    # ==================== Product ====================
    async def create_product(self, data: ProductCreate) -> Product:
        price = await self._resolve_price(data)
        if data.discount_price is not None and data.discount_price > price:
            raise AppError("Chegirmali narx asosiy narxdan katta bo'lmasligi kerak")

        product = Product(
            name_uz=data.name_uz, name_ru=data.name_ru,
            description_uz=data.description_uz, description_ru=data.description_ru,
            category_id=data.category_id, gender_id=data.gender_id,
            material_id=data.material_id, stone_id=data.stone_id,
            price=price, discount_price=data.discount_price, weight_grams=data.weight_grams,
            status=data.status, ai_keywords=data.ai_keywords,
            engraving_available=data.engraving_available, engraving_price=data.engraving_price,
        )
        # Variantlar: berilganini ishlat, bo'lmasa 1 ta default (TZ muhim qaror 1)
        for vin in (data.variants or [VariantCreate()]):
            product.variants.append(self._build_variant(vin, data.name_uz))
        # Media: to'liq obyekt yoki oddiy URL ro'yxati
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

    async def list_products(self, **filters) -> list[Product]:
        return await self.repo.list_products(**filters)

    async def update_product(self, product_id: uuid.UUID, data: ProductUpdate) -> Product:
        product = await self.get_product(product_id)
        payload = data.model_dump(exclude_unset=True)
        for field, value in payload.items():
            setattr(product, field, value)
        # Og'irlik/kategoriya o'zgarsa va narx qo'lda berilmagan bo'lsa — qayta hisoblash
        if "price" not in payload and ("weight_grams" in payload or "category_id" in payload):
            if product.category_id and product.weight_grams:
                category = await self.repo.get_category(product.category_id)
                if category is not None and category.gram_price is not None:
                    product.price = self._calc_price(category.gram_price, product.weight_grams)
        if product.discount_price is not None and product.discount_price > product.price:
            raise AppError("Chegirmali narx asosiy narxdan katta bo'lmasligi kerak")
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
    async def search(
        self, *, q: str | None = None, sku: str | None = None,
        shortcode: str | None = None, limit: int = 10,
    ) -> tuple[str, list[tuple[Product, float | None]]]:
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

    async def semantic_search(self, embedding: list[float], limit: int) -> list[tuple[Product, float]]:
        raw = await self.repo.search_by_embedding(embedding, limit * 3)
        seen: dict[uuid.UUID, tuple[Product, float]] = {}
        for product, score in raw:
            if product.id not in seen:
                seen[product.id] = (product, score)
        return list(seen.values())[:limit]


def _utcnow():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)
