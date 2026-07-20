"""notifications API — yuborilgan xabarnomalar qaydini ko'rish (TZ 4/12)."""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import uuid
from datetime import datetime

from app.core.database import get_db
from app.core.deps import require_permission
from app.modules.notifications.models import Notification

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    channel: str
    target: str | None
    body: str
    status: str
    entity_type: str | None
    entity_id: uuid.UUID | None
    created_at: datetime


@router.get(
    "",
    response_model=list[NotificationOut],
    dependencies=[Depends(require_permission("payments:view"))],
)
async def list_notifications(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[NotificationOut]:
    res = await db.execute(
        select(Notification).order_by(Notification.created_at.desc()).limit(limit).offset(offset)
    )
    return [NotificationOut.model_validate(n) for n in res.scalars().all()]
