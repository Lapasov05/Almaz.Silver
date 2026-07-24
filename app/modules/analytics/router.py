"""analytics API — KPI dashboard (TZ 1), `analytics:view_reports` bilan."""
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.modules.analytics.service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get(
    "/dashboard",
    dependencies=[Depends(require_permission("analytics:view_reports"))],
)
async def dashboard(db: AsyncSession = Depends(get_db)) -> dict:
    """KPI dashboard: konversiya, daromad, to'lovlar, AI ulushi (TZ 1)."""
    return await AnalyticsService(db).dashboard()


@router.get(
    "/top-products",
    dependencies=[Depends(require_permission("analytics:view_reports"))],
)
async def top_products(
    db: AsyncSession = Depends(get_db),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict]:
    """Eng ko'p so'ralgan/sotilgan mahsulotlar + daromad (sana oralig'i bilan)."""
    return await AnalyticsService(db).top_products(date_from=date_from, date_to=date_to, limit=limit)
