"""catalog Service qatlami — biznes logika (TZ 8).

- Reference lug'atlar (gender/material/stone) CRUD.
- Kurs (gramm narxi) CRUD, kategoriyaga ulangan; kalkulyator aktiv kursdan oladi.
- Ko'p tilli mahsulot; narx: asosiy + chegirmali (mijoz `effective_price` to'laydi).
- 3 qatlamli qidiruv (TZ 8).
"""
import uuid
from datetime import timedelta
from decimal import Decimal

from app.core.exceptions import AppError, NotFoundError
from app.core.pagination import PageParams
from app.modules.catalog.models import (
    Box,
    BoxMedia,
    Category,
    ComboItem,
    FulfillmentType,
    MediaChannel,
    Product,
    ProductMedia,
    Variant,
)
from app.modules.catalog.repository import REFERENCE_MODELS, CatalogRepository
from app.modules.catalog.schemas import (
    BoxCreate,
    BoxMediaCreate,
    BoxUpdate,
    CategoryCreate,
    CategoryUpdate,
    ComboComponentOut,
    ComboCreate,
    ComboItemIn,
    ComboOut,
    ComboUpdate,
    InstagramMediaCreate,
    InstagramMediaUpdate,
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
from app.modules.catalog.search import (
    extract_asset_id,
    extract_instagram_ref,
    extract_story_ref,
    extract_shortcode,
    is_instagram_url,
    slugify,
)


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
        category = Category(name_uz=data.name_uz, name_ru=data.name_ru, slug=slug,
                            parent_id=data.parent_id, requires_ring_size=data.requires_ring_size,
                            available_sizes=data.available_sizes)
        await self.repo.add(category)
        await self.repo.db.commit()
        # requires_box (column_property) yangi obyektда yuklanmagan — refresh bilan SELECT'дан olamiz
        await self.repo.db.refresh(category)
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
        await self.repo.db.refresh(category)  # requires_box qayta hisoblansin
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
        # Rasm MAJBURIY — mijoz mahsulotni rasm bilan tanidi (AI rasm yuboradi).
        # Kamida bitta to'g'ridan-to'g'ri rasm URL: image_urls yoki media.image_url.
        has_image = bool(data.image_urls) or any(m.image_url for m in (data.media or []))
        if not has_image:
            raise AppError("Mahsulot uchun kamida bitta rasm majburiy (image_urls yoki media rasm URL)")
        product = Product(
            name_uz=data.name_uz, name_ru=data.name_ru,
            description_uz=data.description_uz, description_ru=data.description_ru,
            category_id=data.category_id, gender_id=data.gender_id,
            material_id=data.material_id, stone_id=data.stone_id,
            price=data.price, discount_price=data.discount_price,
            low_stock_threshold=data.low_stock_threshold,
            status=data.status, ai_keywords=data.ai_keywords,
            engraving_available=data.engraving_available, engraving_price=data.engraving_price,
            engraving_max_chars=data.engraving_max_chars,
            warranty_months=data.warranty_months,
            resize_available=data.resize_available, resize_price=data.resize_price,
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

    # ==================== Box (kategoriyaning rangli qutisi) ====================
    async def list_boxes(self, category_id: uuid.UUID, *, only_active: bool, pp: PageParams):
        await self.get_category(category_id)  # kategoriya bor-yo'qligini tekshiradi (404)
        return await self.repo.list_boxes(category_id=category_id, only_active=only_active, pp=pp)

    async def get_box(self, box_id: uuid.UUID) -> Box:
        box = await self.repo.get_box(box_id)
        if box is None:
            raise NotFoundError("Box topilmadi")
        return box

    async def create_box(self, category_id: uuid.UUID, data: BoxCreate) -> Box:
        await self.get_category(category_id)  # kategoriya mavjudligini tasdiqlaydi
        box = Box(category_id=category_id, **data.model_dump())
        await self.repo.add(box)
        await self.repo.db.commit()
        return await self.get_box(box.id)

    async def update_box(self, box_id: uuid.UUID, data: BoxUpdate) -> Box:
        box = await self.get_box(box_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(box, field, value)
        await self.repo.db.commit()
        return await self.get_box(box_id)

    async def delete_box(self, box_id: uuid.UUID) -> None:
        """Soft delete — tarixiy buyurtmalar (order_item.box_id) buzilmaydi."""
        box = await self.get_box(box_id)
        box.deleted_at = _utcnow()
        await self.repo.db.commit()

    async def adjust_box_stock(self, box_id: uuid.UUID, data: StockAdjust) -> Box:
        box = await self.get_box(box_id)
        if data.stock_qty is not None:
            box.stock_qty = data.stock_qty
        elif data.delta is not None:
            new_qty = box.stock_qty + data.delta
            if new_qty < 0:
                raise AppError("Zaxira manfiy bo'la olmaydi")
            box.stock_qty = new_qty
        else:
            raise AppError("stock_qty yoki delta ko'rsatilishi kerak")
        await self.repo.db.commit()
        return box

    # ---------- Box galereya (media) ----------
    async def add_box_media(self, box_id: uuid.UUID, data: BoxMediaCreate) -> Box:
        box = await self.get_box(box_id)
        box.media.append(BoxMedia(image_url=data.image_url, sort_order=data.sort_order))
        await self.repo.db.commit()
        return await self.get_box(box_id)

    async def delete_box_media(self, media_id: uuid.UUID) -> None:
        media = await self.repo.get_box_media(media_id)
        if media is None:
            raise NotFoundError("Box rasmi topilmadi")
        await self.repo.db.delete(media)
        await self.repo.db.commit()

    # ==================== Combo (to'plam = Product is_combo) ====================
    async def _ensure_combo_category(self) -> Category:
        cat = await self.repo.get_category_by_slug("combo")
        if cat is None:
            cat = Category(name_uz="Combo", name_ru="Комбо", slug="combo")
            await self.repo.add(cat)
        return cat

    async def _validate_combo_component(self, variant_id: uuid.UUID) -> Variant:
        v = await self.repo.get_variant(variant_id)
        if v is None or not v.is_active:
            raise AppError(f"Komponent variant topilmadi yoki faol emas: {variant_id}")
        p = await self.repo.get_product(v.product_id)
        if p is not None and p.is_combo:
            raise AppError("Combo ichiga combo qo'shib bo'lmaydi")
        return v

    async def create_combo(self, data: ComboCreate) -> ComboOut:
        if data.discount_price is not None and data.discount_price > data.price:
            raise AppError("Chegirma narx asl narxdan katta bo'lmasligi kerak")
        # Komponentlarni oldindan tekshiramiz (combo bo'lmasin, faol bo'lsin)
        for it in data.items:
            await self._validate_combo_component(it.variant_id)

        cat = await self._ensure_combo_category()
        combo = Product(
            name_uz=data.name_uz, name_ru=data.name_ru, description_uz=data.description_uz,
            category_id=cat.id, price=data.price, discount_price=data.discount_price,
            status=data.status, is_combo=True,
        )
        # Combo o'z varianti — made_to_order (o'z zaxirasi yo'q; zaxira komponentlarda)
        combo.variants.append(Variant(
            sku=self._generate_sku(data.name_uz),
            fulfillment_type=FulfillmentType.made_to_order,
        ))
        await self.repo.add(combo)
        await self.repo.db.flush()  # combo.id kerak
        for i, it in enumerate(data.items):
            self.repo.db.add(ComboItem(
                combo_product_id=combo.id, component_variant_id=it.variant_id,
                quantity=it.quantity, sort_order=i,
            ))
        await self.repo.db.commit()
        return await self.get_combo(combo.id)

    async def get_combo(self, combo_id: uuid.UUID) -> ComboOut:
        product = await self.repo.get_product(combo_id)
        if product is None or not product.is_combo:
            raise NotFoundError("Combo topilmadi")
        items = await self.repo.list_combo_items(combo_id)

        comp_out: list[ComboComponentOut] = []
        avail: list[int] = []
        for ci in items:
            v = ci.component_variant
            p = v.product if v is not None else None
            first_img = next((m.image_url for m in (p.media if p else []) if m.image_url), None)
            comp_out.append(ComboComponentOut(
                combo_item_id=ci.id, variant_id=v.id,
                product_id=p.id if p else v.product_id,
                name_uz=p.name_uz if p else "?",
                price=(p.effective_price if p else Decimal("0")),
                quantity=ci.quantity, available=max(v.available, 0), image_url=first_img,
            ))
            avail.append(max(v.available, 0) // ci.quantity if ci.quantity else 0)

        combo_variant = next(
            (vv for vv in product.variants if vv.is_active and vv.deleted_at is None), None
        )
        return ComboOut(
            id=product.id, name_uz=product.name_uz, name_ru=product.name_ru,
            description_uz=product.description_uz, price=product.effective_price,
            old_price=(product.price if product.discount_price is not None else None),
            status=product.status,
            variant_id=(combo_variant.id if combo_variant else None),
            available=(min(avail) if avail else 0),
            items=comp_out,
            images=[m.image_url for m in product.media if m.image_url],
            created_at=product.created_at,
        )

    async def list_combos(self, *, status: str | None, q: str | None, pp: PageParams):
        products, total = await self.repo.list_combos(status=status, q=q, pp=pp)
        combos = [await self.get_combo(p.id) for p in products]
        return combos, total

    async def update_combo(self, combo_id: uuid.UUID, data: ComboUpdate) -> ComboOut:
        product = await self.repo.get_product(combo_id)
        if product is None or not product.is_combo:
            raise NotFoundError("Combo topilmadi")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(product, field, value)
        if product.discount_price is not None and product.discount_price > product.price:
            raise AppError("Chegirma narx asl narxdan katta bo'lmasligi kerak")
        await self.repo.db.commit()
        return await self.get_combo(combo_id)

    async def delete_combo(self, combo_id: uuid.UUID) -> None:
        product = await self.repo.get_product(combo_id)
        if product is None or not product.is_combo:
            raise NotFoundError("Combo topilmadi")
        product.deleted_at = _utcnow()
        for v in product.variants:
            v.deleted_at = product.deleted_at
        await self.repo.db.commit()

    async def add_combo_item(self, combo_id: uuid.UUID, data: ComboItemIn) -> ComboOut:
        product = await self.repo.get_product(combo_id)
        if product is None or not product.is_combo:
            raise NotFoundError("Combo topilmadi")
        await self._validate_combo_component(data.variant_id)
        # Tartibni oxiriga qo'shamiz
        existing = await self.repo.list_combo_items(combo_id)
        self.repo.db.add(ComboItem(
            combo_product_id=combo_id, component_variant_id=data.variant_id,
            quantity=data.quantity, sort_order=len(existing),
        ))
        await self.repo.db.commit()
        return await self.get_combo(combo_id)

    async def remove_combo_item(self, item_id: uuid.UUID) -> None:
        item = await self.repo.get_combo_item(item_id)
        if item is None:
            raise NotFoundError("Combo elementi topilmadi")
        await self.repo.db.delete(item)
        await self.repo.db.commit()

    # ==================== Instagram media (post/story link -> mahsulot) ====================
    async def add_instagram_media(self, product_id: uuid.UUID, data: InstagramMediaCreate) -> ProductMedia:
        product = await self.get_product(product_id)  # 404 agar yo'q
        pm = ProductMedia(
            product_id=product.id,
            channel=MediaChannel.instagram,
            image_url=data.image_url,
            caption=data.caption,
            status=(data.status or "published"),
            scheduled_at=data.scheduled_at,
        )
        # link IXTIYORIY: berilsa shortcode/story_ref ajratamiz; berilmasa (draft/rejalashtirilgan) — bo'sh
        if data.link:
            ref = extract_instagram_ref(data.link)
            if ref is None:
                raise AppError("Instagram post yoki story linki noto'g'ri (masalan .../p/... yoki .../stories/...)")
            media_type, value = ref
            pm.media_type = media_type
            pm.permalink = data.link
            if media_type == "story":
                pm.story_ref = value
                pm.expires_at = _utcnow() + timedelta(hours=24)  # story 24 soat turadi
            else:  # post / reel
                pm.shortcode = value
        else:
            pm.media_type = "post"  # linksiz qoralama uchun default
        self.repo.db.add(pm)
        await self.repo.db.commit()
        await self.repo.db.refresh(pm)
        return pm

    async def get_instagram_media(self, media_id: uuid.UUID) -> ProductMedia:
        media = await self.repo.get_media(media_id)
        if media is None:
            raise NotFoundError("Instagram media topilmadi")
        return media

    async def list_all_instagram_media(self, **filters) -> list[ProductMedia]:
        """Global IG kontent ro'yxati — filtr (product_id/status/media_type/date_from) + sort + pagination."""
        return await self.repo.list_all_ig_media(**filters)

    async def list_instagram_media(self, product_id: uuid.UUID) -> list[ProductMedia]:
        await self.get_product(product_id)
        return await self.repo.list_product_ig_media(product_id)

    async def update_instagram_media(self, media_id: uuid.UUID, data: InstagramMediaUpdate) -> ProductMedia:
        media = await self.repo.get_media(media_id)
        if media is None:
            raise NotFoundError("Instagram media topilmadi")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(media, field, value)
        await self.repo.db.commit()
        await self.repo.db.refresh(media)
        return media

    async def delete_instagram_media(self, media_id: uuid.UUID) -> None:
        media = await self.repo.get_media(media_id)
        if media is None:
            raise NotFoundError("Instagram media topilmadi")
        await self.repo.db.delete(media)
        await self.repo.db.commit()

    async def resolve_instagram_media(self, link_or_ref: str) -> Product | None:
        """Link, media id yoki story ref bo'yicha mahsulotni topadi (AI tool uchun).

        Mijoz post/reel/story'ni directga yuborsa yoki story'ga javob bersa shu chaqiriladi.
        Tartib (docs/instagram_webhook_flow.md):
          1. Havoladan ajratilgan ref (shortcode / story id / CDN asset_id) bo'yicha aniq moslik.
          2. Berilgan qiymatning o'zi bo'yicha aniq moslik.
          3. Story uchun Graph API'dagi aktiv storylar — webhook id'ni permalink bilan bog'laydi.
          4. Oxirgi zaxira: aktiv story faqat BITTA bo'lsa — o'shanga bog'lanadi.
        Topilgan webhook id media yozuviga saqlanadi, keyingi safar 1-qadamda topiladi.
        """
        value = (link_or_ref or "").strip()
        if not value:
            return None

        candidates: list[str] = []
        asset_id = extract_asset_id(value)     # lookaside CDN havolasi -> story/media id
        if asset_id:
            candidates.append(asset_id)
        ref = extract_instagram_ref(value)     # instagram.com havolasi -> shortcode yoki story id
        if ref is not None:
            candidates.append(ref[1])
        if value not in candidates:
            candidates.append(value)

        for candidate in candidates:
            media = await self.repo.get_ig_media_by_ref(candidate)
            if media is not None:
                return media.product

        return await self._resolve_story_by_webhook_id(value, candidates)

    async def _resolve_story_by_webhook_id(self, value: str, candidates: list[str]) -> Product | None:
        """Webhook story id permalink'dagi id'dan farq qilganда mahsulotni topadi."""
        if is_instagram_url(value):
            return None  # post/reel permalink berilgan — bu story emas, taxmin qilmaymiz
        webhook_ref = next((c for c in candidates if c.isdigit()), None)
        if webhook_ref is None:  # story id emas (masalan noma'lum post shortcode'i) — taxmin qilmaymiz
            return None

        media = await self._story_media_from_graph(webhook_ref)
        if media is None:
            media = await self._only_active_story_media()
        if media is None:
            return None
        if media.external_media_id != webhook_ref:
            media.external_media_id = webhook_ref  # keyingi safar aniq moslik bo'lsin
            await self.repo.db.commit()
        return media.product

    async def _story_media_from_graph(self, webhook_ref: str) -> ProductMedia | None:
        """Graph API'dagi aktiv storylar orqali aniq moslik — nechta story bo'lsa ham ishlaydi.

        Graph API har story uchun `id` (webhook beradigan) va `permalink` (bizda `story_ref`
        sifatida saqlangan share id) ni birga qaytaradi, shu ikkisi ko'prik bo'ladi.
        """
        from app.modules.inbox.channels.instagram import InstagramClient
        from app.modules.integrations.service import get_config_value

        token = await get_config_value(self.repo.db, "instagram", "access_token")
        if not token:
            return None
        for story in await InstagramClient(access_token=token).list_active_stories():
            if str(story.get("id") or "") != webhook_ref:
                continue
            share_id = extract_story_ref(story.get("permalink") or "")
            return await self.repo.get_ig_media_by_ref(share_id) if share_id else None
        return None

    async def _only_active_story_media(self) -> ProductMedia | None:
        """Oxirgi zaxira — Graph API ishlamasa. Faqat aktiv story BITTA bo'lsa bog'laymiz,
        bir nechta bo'lsa noto'g'ri mahsulotni ko'rsatmaslik uchun hech narsa qaytarmaymiz."""
        media_list = await self.repo.list_active_story_media()
        return media_list[0] if len(media_list) == 1 else None

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
