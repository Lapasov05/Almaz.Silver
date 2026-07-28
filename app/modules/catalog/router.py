"""catalog API — reference lug'atlar, kategoriya, kurs, mahsulot, qidiruv (TZ 8), RBAC bilan.

Barcha ro'yxat (GET) endpointlari: pagination `{items,total,limit,offset}` + filtrlar.
"""
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.core.pagination import Page, PageParams, page_params, page_params_ref
from app.modules.catalog.repository import CatalogRepository
from app.modules.catalog.schemas import (
    BoxCreate,
    BoxMediaCreate,
    BoxOut,
    BoxUpdate,
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
    ComboCreate,
    ComboItemIn,
    ComboOut,
    ComboUpdate,
    MediaCreate,
    MediaOut,
    ProductCreate,
    ProductOut,
    ProductStatus,
    ProductUpdate,
    ReferenceCreate,
    ReferenceOut,
    ReferenceUpdate,
    SearchHit,
    SearchResponse,
    SemanticSearchRequest,
    StockAdjust,
    VariantCreate,
    VariantOut,
    VariantUpdate,
)
from app.modules.catalog.service import CatalogService

router = APIRouter(prefix="/catalog", tags=["catalog"])

_VIEW = Depends(require_permission("products:view"))
_CREATE = Depends(require_permission("products:create"))
_UPDATE = Depends(require_permission("products:update"))
_DELETE = Depends(require_permission("products:delete"))


def svc(db: AsyncSession = Depends(get_db)) -> CatalogService:
    return CatalogService(CatalogRepository(db))


# ==================== Reference lug'atlar (gender / material / stone) ====================
def _reference_routes(path: str, kind: str) -> None:
    @router.get(f"/{path}", response_model=Page[ReferenceOut], dependencies=[_VIEW], name=f"list_{kind}")
    async def _list(only_active: bool = False, q: str | None = None,
                    pp: PageParams = Depends(page_params_ref), service: CatalogService = Depends(svc)):
        items, total = await service.list_reference(kind, only_active=only_active, q=q, pp=pp)
        return Page(items=[ReferenceOut.model_validate(x) for x in items], total=total, limit=pp.limit, offset=pp.offset)

    @router.get(f"/{path}/{{ref_id}}", response_model=ReferenceOut, dependencies=[_VIEW], name=f"get_{kind}")
    async def _get(ref_id: uuid.UUID, service: CatalogService = Depends(svc)):
        return ReferenceOut.model_validate(await service.get_reference(kind, ref_id))

    @router.post(f"/{path}", response_model=ReferenceOut, dependencies=[_CREATE], name=f"create_{kind}")
    async def _create(payload: ReferenceCreate, service: CatalogService = Depends(svc)):
        return ReferenceOut.model_validate(await service.create_reference(kind, payload))

    @router.patch(f"/{path}/{{ref_id}}", response_model=ReferenceOut, dependencies=[_UPDATE], name=f"update_{kind}")
    async def _update(ref_id: uuid.UUID, payload: ReferenceUpdate, service: CatalogService = Depends(svc)):
        return ReferenceOut.model_validate(await service.update_reference(kind, ref_id, payload))

    @router.delete(f"/{path}/{{ref_id}}", status_code=204, dependencies=[_DELETE], name=f"delete_{kind}")
    async def _delete(ref_id: uuid.UUID, service: CatalogService = Depends(svc)):
        await service.delete_reference(kind, ref_id)


_reference_routes("genders", "gender")
_reference_routes("materials", "material")
_reference_routes("stones", "stone")


# ==================== Categories ====================
@router.post("/categories", response_model=CategoryOut, dependencies=[_CREATE])
async def create_category(payload: CategoryCreate, service: CatalogService = Depends(svc)):
    return CategoryOut.model_validate(await service.create_category(payload))


@router.get("/categories", response_model=Page[CategoryOut], dependencies=[_VIEW])
async def list_categories(parent_id: uuid.UUID | None = None, q: str | None = None,
                          pp: PageParams = Depends(page_params_ref), service: CatalogService = Depends(svc)):
    items, total = await service.list_categories(parent_id=parent_id, q=q, pp=pp)
    return Page(items=[CategoryOut.model_validate(c) for c in items], total=total, limit=pp.limit, offset=pp.offset)


@router.get("/categories/{category_id}", response_model=CategoryOut, dependencies=[_VIEW])
async def get_category(category_id: uuid.UUID, service: CatalogService = Depends(svc)):
    return CategoryOut.model_validate(await service.get_category(category_id))


@router.patch("/categories/{category_id}", response_model=CategoryOut, dependencies=[_UPDATE])
async def update_category(category_id: uuid.UUID, payload: CategoryUpdate, service: CatalogService = Depends(svc)):
    return CategoryOut.model_validate(await service.update_category(category_id, payload))


@router.delete("/categories/{category_id}", status_code=204, dependencies=[_DELETE])
async def delete_category(category_id: uuid.UUID, service: CatalogService = Depends(svc)):
    await service.delete_category(category_id)


# ==================== Box (kategoriyaning rangli qutilari) — «category bo'limi»da ====================
@router.get("/categories/{category_id}/boxes", response_model=Page[BoxOut], dependencies=[_VIEW])
async def list_category_boxes(
    category_id: uuid.UUID,
    only_active: bool = False,
    pp: PageParams = Depends(page_params_ref),
    service: CatalogService = Depends(svc),
):
    items, total = await service.list_boxes(category_id, only_active=only_active, pp=pp)
    return Page[BoxOut](items=items, total=total, limit=pp.limit, offset=pp.offset)


@router.post("/categories/{category_id}/boxes", response_model=BoxOut, dependencies=[_CREATE])
async def create_category_box(
    category_id: uuid.UUID, payload: BoxCreate, service: CatalogService = Depends(svc)
):
    return BoxOut.model_validate(await service.create_box(category_id, payload))


@router.get("/boxes/{box_id}", response_model=BoxOut, dependencies=[_VIEW])
async def get_box(box_id: uuid.UUID, service: CatalogService = Depends(svc)):
    return BoxOut.model_validate(await service.get_box(box_id))


@router.patch("/boxes/{box_id}", response_model=BoxOut, dependencies=[_UPDATE])
async def update_box(box_id: uuid.UUID, payload: BoxUpdate, service: CatalogService = Depends(svc)):
    return BoxOut.model_validate(await service.update_box(box_id, payload))


@router.delete("/boxes/{box_id}", status_code=204, dependencies=[_DELETE])
async def delete_box(box_id: uuid.UUID, service: CatalogService = Depends(svc)):
    await service.delete_box(box_id)


@router.post("/boxes/{box_id}/stock", response_model=BoxOut, dependencies=[_UPDATE])
async def adjust_box_stock(box_id: uuid.UUID, payload: StockAdjust, service: CatalogService = Depends(svc)):
    return BoxOut.model_validate(await service.adjust_box_stock(box_id, payload))


@router.post("/boxes/{box_id}/media", response_model=BoxOut, dependencies=[_UPDATE])
async def add_box_media(box_id: uuid.UUID, payload: BoxMediaCreate, service: CatalogService = Depends(svc)):
    return BoxOut.model_validate(await service.add_box_media(box_id, payload))


@router.delete("/boxes/media/{media_id}", status_code=204, dependencies=[_UPDATE])
async def delete_box_media(media_id: uuid.UUID, service: CatalogService = Depends(svc)):
    await service.delete_box_media(media_id)


# ==================== Combo (to'plam = maxsus Product) ====================
@router.post("/combos", response_model=ComboOut, dependencies=[_CREATE])
async def create_combo(payload: ComboCreate, service: CatalogService = Depends(svc)):
    return await service.create_combo(payload)


@router.get("/combos", response_model=Page[ComboOut], dependencies=[_VIEW])
async def list_combos(
    status: ProductStatus | None = None,
    q: str | None = None,
    pp: PageParams = Depends(page_params),
    service: CatalogService = Depends(svc),
):
    items, total = await service.list_combos(status=status.value if status else None, q=q, pp=pp)
    return Page[ComboOut](items=items, total=total, limit=pp.limit, offset=pp.offset)


@router.get("/combos/{combo_id}", response_model=ComboOut, dependencies=[_VIEW])
async def get_combo(combo_id: uuid.UUID, service: CatalogService = Depends(svc)):
    return await service.get_combo(combo_id)


@router.patch("/combos/{combo_id}", response_model=ComboOut, dependencies=[_UPDATE])
async def update_combo(combo_id: uuid.UUID, payload: ComboUpdate, service: CatalogService = Depends(svc)):
    return await service.update_combo(combo_id, payload)


@router.delete("/combos/{combo_id}", status_code=204, dependencies=[_DELETE])
async def delete_combo(combo_id: uuid.UUID, service: CatalogService = Depends(svc)):
    await service.delete_combo(combo_id)


@router.post("/combos/{combo_id}/items", response_model=ComboOut, dependencies=[_UPDATE])
async def add_combo_item(combo_id: uuid.UUID, payload: ComboItemIn, service: CatalogService = Depends(svc)):
    return await service.add_combo_item(combo_id, payload)


@router.delete("/combos/items/{item_id}", status_code=204, dependencies=[_UPDATE])
async def remove_combo_item(item_id: uuid.UUID, service: CatalogService = Depends(svc)):
    await service.remove_combo_item(item_id)


# ==================== Products ====================
@router.post("/products", response_model=ProductOut, dependencies=[_CREATE])
async def create_product(payload: ProductCreate, service: CatalogService = Depends(svc)):
    return ProductOut.model_validate(await service.create_product(payload))


# Sklad: kam qolgan mahsulotlar (admin qayta zakaz qilishi uchun). /products dan OLDIN bo'lsin.
@router.get("/products/low-stock", response_model=Page[ProductOut], dependencies=[_VIEW])
async def low_stock_products(
    service: CatalogService = Depends(svc),
    pp: PageParams = Depends(page_params),
    status: ProductStatus | None = Query(default=None, description="masalan active"),
):
    items, total = await service.list_low_stock(status=status.value if status else None, pp=pp)
    return Page(items=[ProductOut.model_validate(p) for p in items], total=total, limit=pp.limit, offset=pp.offset)


@router.get("/products", response_model=Page[ProductOut], dependencies=[_VIEW])
async def list_products(
    service: CatalogService = Depends(svc),
    pp: PageParams = Depends(page_params),
    status: ProductStatus | None = None,
    category_id: uuid.UUID | None = None,
    gender_id: uuid.UUID | None = None,
    material_id: uuid.UUID | None = None,
    stone_id: uuid.UUID | None = None,
    engraving_available: bool | None = None,
    in_stock: bool | None = Query(default=None, description="Faqat zaxirada bor"),
    min_price: Decimal | None = Query(default=None, ge=0),
    max_price: Decimal | None = Query(default=None, ge=0),
    q: str | None = Query(default=None, description="Nom bo'yicha (uz/ru)"),
):
    items, total = await service.list_products(
        pp=pp, status=status.value if status else None, category_id=category_id,
        gender_id=gender_id, material_id=material_id, stone_id=stone_id,
        engraving_available=engraving_available, in_stock=in_stock,
        min_price=min_price, max_price=max_price, q=q,
    )
    return Page(items=[ProductOut.model_validate(p) for p in items], total=total, limit=pp.limit, offset=pp.offset)


@router.get("/products/{product_id}", response_model=ProductOut, dependencies=[_VIEW])
async def get_product(product_id: uuid.UUID, service: CatalogService = Depends(svc)):
    return ProductOut.model_validate(await service.get_product(product_id))


@router.patch("/products/{product_id}", response_model=ProductOut, dependencies=[_UPDATE])
async def update_product(product_id: uuid.UUID, payload: ProductUpdate, service: CatalogService = Depends(svc)):
    return ProductOut.model_validate(await service.update_product(product_id, payload))


@router.delete("/products/{product_id}", status_code=204, dependencies=[_DELETE])
async def delete_product(product_id: uuid.UUID, service: CatalogService = Depends(svc)):
    await service.delete_product(product_id)


# ==================== Variants (zaxira) ====================
@router.post("/products/{product_id}/variants", response_model=VariantOut, dependencies=[_CREATE])
async def add_variant(product_id: uuid.UUID, payload: VariantCreate, service: CatalogService = Depends(svc)):
    return VariantOut.model_validate(await service.add_variant(product_id, payload))


@router.patch("/variants/{variant_id}", response_model=VariantOut, dependencies=[_UPDATE])
async def update_variant(variant_id: uuid.UUID, payload: VariantUpdate, service: CatalogService = Depends(svc)):
    return VariantOut.model_validate(await service.update_variant(variant_id, payload))


@router.post("/variants/{variant_id}/stock", response_model=VariantOut, dependencies=[_UPDATE])
async def adjust_stock(variant_id: uuid.UUID, payload: StockAdjust, service: CatalogService = Depends(svc)):
    return VariantOut.model_validate(await service.adjust_stock(variant_id, payload))


# ==================== Media (rasm) ====================
@router.post("/products/{product_id}/media", response_model=MediaOut, dependencies=[_UPDATE])
async def add_media(product_id: uuid.UUID, payload: MediaCreate, service: CatalogService = Depends(svc)):
    return MediaOut.model_validate(await service.add_media(product_id, payload))


@router.delete("/media/{media_id}", status_code=204, dependencies=[_UPDATE])
async def delete_media(media_id: uuid.UUID, service: CatalogService = Depends(svc)):
    await service.delete_media(media_id)


# ==================== Qidiruv ====================
@router.get("/search", response_model=SearchResponse, dependencies=[_VIEW])
async def search(service: CatalogService = Depends(svc), q: str | None = None,
                 sku: str | None = None, shortcode: str | None = None,
                 limit: int = Query(default=10, ge=1, le=50)):
    match_type, results = await service.search(q=q, sku=sku, shortcode=shortcode, limit=limit)
    hits = [SearchHit(product=ProductOut.model_validate(p), match_type=match_type, score=s) for p, s in results]
    return SearchResponse(query=q, match_type=match_type, hits=hits)


@router.post("/search/semantic", response_model=SearchResponse, dependencies=[_VIEW])
async def semantic_search(payload: SemanticSearchRequest, service: CatalogService = Depends(svc)):
    results = await service.semantic_search(payload.embedding, payload.limit)
    hits = [SearchHit(product=ProductOut.model_validate(p), match_type="semantic", score=s) for p, s in results]
    return SearchResponse(query=None, match_type="semantic", hits=hits)
