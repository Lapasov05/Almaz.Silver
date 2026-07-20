"""catalog API qatlami — admin CRUD + qidiruv (TZ 8-bo'lim), RBAC bilan himoyalangan.

Ruxsatlar (TZ 13): ko'rish `products:view`, yaratish `products:create`,
yangilash `products:update`, o'chirish `products:delete`.
"""
import uuid

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
    ProductCreate,
    ProductOut,
    ProductStatus,
    ProductUpdate,
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


def get_catalog_service(db: AsyncSession = Depends(get_db)) -> CatalogService:
    return CatalogService(CatalogRepository(db))


# ==================== Categories ====================
@router.post(
    "/categories",
    response_model=CategoryOut,
    dependencies=[Depends(require_permission("products:create"))],
)
async def create_category(
    payload: CategoryCreate, service: CatalogService = Depends(get_catalog_service)
) -> CategoryOut:
    return CategoryOut.model_validate(await service.create_category(payload))


@router.get(
    "/categories",
    response_model=list[CategoryOut],
    dependencies=[Depends(require_permission("products:view"))],
)
async def list_categories(
    service: CatalogService = Depends(get_catalog_service),
) -> list[CategoryOut]:
    return [CategoryOut.model_validate(c) for c in await service.list_categories()]


@router.patch(
    "/categories/{category_id}",
    response_model=CategoryOut,
    dependencies=[Depends(require_permission("products:update"))],
)
async def update_category(
    category_id: uuid.UUID,
    payload: CategoryUpdate,
    service: CatalogService = Depends(get_catalog_service),
) -> CategoryOut:
    return CategoryOut.model_validate(await service.update_category(category_id, payload))


@router.delete(
    "/categories/{category_id}",
    status_code=204,
    dependencies=[Depends(require_permission("products:delete"))],
)
async def delete_category(
    category_id: uuid.UUID, service: CatalogService = Depends(get_catalog_service)
) -> None:
    await service.delete_category(category_id)


# ==================== Products ====================
@router.post(
    "/products",
    response_model=ProductOut,
    dependencies=[Depends(require_permission("products:create"))],
)
async def create_product(
    payload: ProductCreate, service: CatalogService = Depends(get_catalog_service)
) -> ProductOut:
    return ProductOut.model_validate(await service.create_product(payload))


@router.get(
    "/products",
    response_model=list[ProductOut],
    dependencies=[Depends(require_permission("products:view"))],
)
async def list_products(
    service: CatalogService = Depends(get_catalog_service),
    status: ProductStatus | None = None,
    category_id: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[ProductOut]:
    products = await service.list_products(
        status=status.value if status else None,
        category_id=category_id,
        limit=limit,
        offset=offset,
    )
    return [ProductOut.model_validate(p) for p in products]


@router.get(
    "/products/{product_id}",
    response_model=ProductOut,
    dependencies=[Depends(require_permission("products:view"))],
)
async def get_product(
    product_id: uuid.UUID, service: CatalogService = Depends(get_catalog_service)
) -> ProductOut:
    return ProductOut.model_validate(await service.get_product(product_id))


@router.patch(
    "/products/{product_id}",
    response_model=ProductOut,
    dependencies=[Depends(require_permission("products:update"))],
)
async def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdate,
    service: CatalogService = Depends(get_catalog_service),
) -> ProductOut:
    return ProductOut.model_validate(await service.update_product(product_id, payload))


@router.delete(
    "/products/{product_id}",
    status_code=204,
    dependencies=[Depends(require_permission("products:delete"))],
)
async def delete_product(
    product_id: uuid.UUID, service: CatalogService = Depends(get_catalog_service)
) -> None:
    await service.delete_product(product_id)


# ==================== Variants (zaxira) ====================
@router.post(
    "/products/{product_id}/variants",
    response_model=VariantOut,
    dependencies=[Depends(require_permission("products:create"))],
)
async def add_variant(
    product_id: uuid.UUID,
    payload: VariantCreate,
    service: CatalogService = Depends(get_catalog_service),
) -> VariantOut:
    return VariantOut.model_validate(await service.add_variant(product_id, payload))


@router.patch(
    "/variants/{variant_id}",
    response_model=VariantOut,
    dependencies=[Depends(require_permission("products:update"))],
)
async def update_variant(
    variant_id: uuid.UUID,
    payload: VariantUpdate,
    service: CatalogService = Depends(get_catalog_service),
) -> VariantOut:
    return VariantOut.model_validate(await service.update_variant(variant_id, payload))


@router.post(
    "/variants/{variant_id}/stock",
    response_model=VariantOut,
    dependencies=[Depends(require_permission("products:update"))],
)
async def adjust_stock(
    variant_id: uuid.UUID,
    payload: StockAdjust,
    service: CatalogService = Depends(get_catalog_service),
) -> VariantOut:
    return VariantOut.model_validate(await service.adjust_stock(variant_id, payload))


# ==================== Media ====================
@router.post(
    "/products/{product_id}/media",
    response_model=MediaOut,
    dependencies=[Depends(require_permission("products:update"))],
)
async def add_media(
    product_id: uuid.UUID,
    payload: MediaCreate,
    service: CatalogService = Depends(get_catalog_service),
) -> MediaOut:
    return MediaOut.model_validate(await service.add_media(product_id, payload))


@router.delete(
    "/media/{media_id}",
    status_code=204,
    dependencies=[Depends(require_permission("products:update"))],
)
async def delete_media(
    media_id: uuid.UUID, service: CatalogService = Depends(get_catalog_service)
) -> None:
    await service.delete_media(media_id)


# ==================== Qidiruv ====================
@router.get(
    "/search",
    response_model=SearchResponse,
    dependencies=[Depends(require_permission("products:view"))],
)
async def search(
    service: CatalogService = Depends(get_catalog_service),
    q: str | None = Query(default=None, description="Matn, IG URL yoki SKU"),
    sku: str | None = Query(default=None, description="Aniq SKU/barcode"),
    shortcode: str | None = Query(default=None, description="IG shortcode yoki URL"),
    limit: int = Query(default=10, ge=1, le=50),
) -> SearchResponse:
    match_type, results = await service.search(q=q, sku=sku, shortcode=shortcode, limit=limit)
    hits = [
        SearchHit(product=ProductOut.model_validate(p), match_type=match_type, score=s)
        for p, s in results
    ]
    return SearchResponse(query=q, match_type=match_type, hits=hits)


@router.post(
    "/search/semantic",
    response_model=SearchResponse,
    dependencies=[Depends(require_permission("products:view"))],
)
async def semantic_search(
    payload: SemanticSearchRequest,
    service: CatalogService = Depends(get_catalog_service),
) -> SearchResponse:
    """pgvector embedding bo'yicha qidiruv (embedding generatsiyasi — Faza 3)."""
    results = await service.semantic_search(payload.embedding, payload.limit)
    hits = [
        SearchHit(product=ProductOut.model_validate(p), match_type="semantic", score=s)
        for p, s in results
    ]
    return SearchResponse(query=None, match_type="semantic", hits=hits)
