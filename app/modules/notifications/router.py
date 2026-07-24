"""notifications API — yuborilgan xabarnomalar qaydini ko'rish (TZ 4/12)."""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import uuid
from datetime import datetime

from app.core.database import get_db
from app.core.deps import require_permission
from app.core.pagination import Page, PageParams, page_params, paginate
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
    response_model=Page[NotificationOut],
    dependencies=[Depends(require_permission("payments:view"))],
)
async def list_notifications(
    db: AsyncSession = Depends(get_db),
    pp: PageParams = Depends(page_params),
    type: str | None = None,
    status: str | None = None,
    channel: str | None = None,
) -> Page[NotificationOut]:
    stmt = select(Notification)
    if type is not None:
        stmt = stmt.where(Notification.type == type)
    if status is not None:
        stmt = stmt.where(Notification.status == status)
    if channel is not None:
        stmt = stmt.where(Notification.channel == channel)
    items, total = await paginate(db, stmt, [Notification.created_at.desc()], pp)
    return Page(items=[NotificationOut.model_validate(n) for n in items], total=total, limit=pp.limit, offset=pp.offset)
