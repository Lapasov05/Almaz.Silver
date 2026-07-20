"""analytics API — KPI dashboard (TZ 1), `analytics:view_reports` bilan."""
from fastapi import APIRouter, Depends
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
