"""catalog API — reference lug'atlar, kategoriya, mahsulot, qidiruv (TZ 8), RBAC bilan.

Ruxsatlar: ko'rish `products:view`, yaratish `products:create`,
yangilash `products:update`, o'chirish `products:delete`.
"""
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.modules.catalog.repository import CatalogRepository
from app.modules.catalog.schemas import (
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
    MediaCreate,
    MediaOut,
    PriceCalcOut,
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


def get_catalog_service(db: AsyncSession = Depends(get_db)) -> CatalogService:
    return CatalogService(CatalogRepository(db))


# ==================== Reference lug'atlar (gender / material / stone) ====================
# Bir xil CRUD uch lug'at uchun: /catalog/genders, /catalog/materials, /catalog/stones
def _reference_routes(path: str, kind: str, tag: str) -> None:
    @router.get(f"/{path}", response_model=list[ReferenceOut], dependencies=[_VIEW], name=f"list_{kind}")
    async def _list(only_active: bool = False, service: CatalogService = Depends(get_catalog_service)):
        return [ReferenceOut.model_validate(x) for x in await service.list_reference(kind, only_active=only_active)]

    @router.get(f"/{path}/{{ref_id}}", response_model=ReferenceOut, dependencies=[_VIEW], name=f"get_{kind}")
    async def _get(ref_id: uuid.UUID, service: CatalogService = Depends(get_catalog_service)):
        return ReferenceOut.model_validate(await service.get_reference(kind, ref_id))

    @router.post(f"/{path}", response_model=ReferenceOut, dependencies=[_CREATE], name=f"create_{kind}")
    async def _create(payload: ReferenceCreate, service: CatalogService = Depends(get_catalog_service)):
        return ReferenceOut.model_validate(await service.create_reference(kind, payload))

    @router.patch(f"/{path}/{{ref_id}}", response_model=ReferenceOut, dependencies=[_UPDATE], name=f"update_{kind}")
    async def _update(ref_id: uuid.UUID, payload: ReferenceUpdate, service: CatalogService = Depends(get_catalog_service)):
        return ReferenceOut.model_validate(await service.update_reference(kind, ref_id, payload))

    @router.delete(f"/{path}/{{ref_id}}", status_code=204, dependencies=[_DELETE], name=f"delete_{kind}")
    async def _delete(ref_id: uuid.UUID, service: CatalogService = Depends(get_catalog_service)):
        await service.delete_reference(kind, ref_id)


_reference_routes("genders", "gender", "Kim uchun")      # erkak / ayol / uniseks
_reference_routes("materials", "material", "Material")   # Kumush 925 + rodiy
_reference_routes("stones", "stone", "Tosh")             # Serkon


# ==================== Categories (to'liq CRUD) ====================
@router.post("/categories", response_model=CategoryOut, dependencies=[_CREATE])
async def create_category(payload: CategoryCreate, service: CatalogService = Depends(get_catalog_service)):
    return CategoryOut.model_validate(await service.create_category(payload))


@router.get("/categories", response_model=list[CategoryOut], dependencies=[_VIEW])
async def list_categories(service: CatalogService = Depends(get_catalog_service)):
    return [CategoryOut.model_validate(c) for c in await service.list_categories()]


@router.get("/categories/{category_id}", response_model=CategoryOut, dependencies=[_VIEW])
async def get_category(category_id: uuid.UUID, service: CatalogService = Depends(get_catalog_service)):
    return CategoryOut.model_validate(await service.get_category(category_id))


@router.patch("/categories/{category_id}", response_model=CategoryOut, dependencies=[_UPDATE])
async def update_category(category_id: uuid.UUID, payload: CategoryUpdate,
                          service: CatalogService = Depends(get_catalog_service)):
    return CategoryOut.model_validate(await service.update_category(category_id, payload))


@router.delete("/categories/{category_id}", status_code=204, dependencies=[_DELETE])
async def delete_category(category_id: uuid.UUID, service: CatalogService = Depends(get_catalog_service)):
    await service.delete_category(category_id)


# ==================== Og'irlik kalkulyatori ====================
@router.get("/price-calc", response_model=PriceCalcOut, dependencies=[_VIEW])
async def price_calc(
    category_id: uuid.UUID,
    weight_grams: Decimal = Query(ge=0),
    service: CatalogService = Depends(get_catalog_service),
):
    """Kategoriya gramm narxi bo'yicha narxni hisoblab beradi (mahsulot saqlanmaydi)."""
    return PriceCalcOut(**await service.calc_price(category_id, weight_grams))


# ==================== Products ====================
@router.post("/products", response_model=ProductOut, dependencies=[_CREATE])
async def create_product(payload: ProductCreate, service: CatalogService = Depends(get_catalog_service)):
    return ProductOut.model_validate(await service.create_product(payload))


@router.get("/products", response_model=list[ProductOut], dependencies=[_VIEW])
async def list_products(
    service: CatalogService = Depends(get_catalog_service),
    status: ProductStatus | None = None,
    category_id: uuid.UUID | None = None,
    gender_id: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    products = await service.list_products(
        status=status.value if status else None, category_id=category_id,
        gender_id=gender_id, limit=limit, offset=offset,
    )
    return [ProductOut.model_validate(p) for p in products]


@router.get("/products/{product_id}", response_model=ProductOut, dependencies=[_VIEW])
async def get_product(product_id: uuid.UUID, service: CatalogService = Depends(get_catalog_service)):
    return ProductOut.model_validate(await service.get_product(product_id))


@router.patch("/products/{product_id}", response_model=ProductOut, dependencies=[_UPDATE])
async def update_product(product_id: uuid.UUID, payload: ProductUpdate,
                         service: CatalogService = Depends(get_catalog_service)):
    return ProductOut.model_validate(await service.update_product(product_id, payload))


@router.delete("/products/{product_id}", status_code=204, dependencies=[_DELETE])
async def delete_product(product_id: uuid.UUID, service: CatalogService = Depends(get_catalog_service)):
    await service.delete_product(product_id)


# ==================== Variants (zaxira) ====================
@router.post("/products/{product_id}/variants", response_model=VariantOut, dependencies=[_CREATE])
async def add_variant(product_id: uuid.UUID, payload: VariantCreate,
                      service: CatalogService = Depends(get_catalog_service)):
    return VariantOut.model_validate(await service.add_variant(product_id, payload))


@router.patch("/variants/{variant_id}", response_model=VariantOut, dependencies=[_UPDATE])
async def update_variant(variant_id: uuid.UUID, payload: VariantUpdate,
                         service: CatalogService = Depends(get_catalog_service)):
    return VariantOut.model_validate(await service.update_variant(variant_id, payload))


@router.post("/variants/{variant_id}/stock", response_model=VariantOut, dependencies=[_UPDATE])
async def adjust_stock(variant_id: uuid.UUID, payload: StockAdjust,
                       service: CatalogService = Depends(get_catalog_service)):
    return VariantOut.model_validate(await service.adjust_stock(variant_id, payload))


# ==================== Media (rasm) ====================
@router.post("/products/{product_id}/media", response_model=MediaOut, dependencies=[_UPDATE])
async def add_media(product_id: uuid.UUID, payload: MediaCreate,
                    service: CatalogService = Depends(get_catalog_service)):
    """Mahsulotga rasm/IG media qo'shish (image_url yoki shortcode_or_url)."""
    return MediaOut.model_validate(await service.add_media(product_id, payload))


@router.delete("/media/{media_id}", status_code=204, dependencies=[_UPDATE])
async def delete_media(media_id: uuid.UUID, service: CatalogService = Depends(get_catalog_service)):
    await service.delete_media(media_id)


# ==================== Qidiruv ====================
@router.get("/search", response_model=SearchResponse, dependencies=[_VIEW])
async def search(
    service: CatalogService = Depends(get_catalog_service),
    q: str | None = Query(default=None, description="Matn, IG URL yoki SKU"),
    sku: str | None = Query(default=None, description="Aniq SKU/barcode"),
    shortcode: str | None = Query(default=None, description="IG shortcode yoki URL"),
    limit: int = Query(default=10, ge=1, le=50),
):
    match_type, results = await service.search(q=q, sku=sku, shortcode=shortcode, limit=limit)
    hits = [SearchHit(product=ProductOut.model_validate(p), match_type=match_type, score=s) for p, s in results]
    return SearchResponse(query=q, match_type=match_type, hits=hits)


@router.post("/search/semantic", response_model=SearchResponse, dependencies=[_VIEW])
async def semantic_search(payload: SemanticSearchRequest,
                          service: CatalogService = Depends(get_catalog_service)):
    results = await service.semantic_search(payload.embedding, payload.limit)
    hits = [SearchHit(product=ProductOut.model_validate(p), match_type="semantic", score=s) for p, s in results]
    return SearchResponse(query=None, match_type="semantic", hits=hits)
