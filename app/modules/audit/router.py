"""audit API — audit_log ko'rish (TZ 13/15), `audit:view` bilan."""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.core.pagination import Page, PageParams, page_params
from app.modules.audit.schemas import AuditLogOut
from app.modules.audit.service import AuditService

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get(
    "",
    response_model=Page[AuditLogOut],
    dependencies=[Depends(require_permission("audit:view"))],
)
async def list_audit(
    db: AsyncSession = Depends(get_db),
    pp: PageParams = Depends(page_params),
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> Page[AuditLogOut]:
    items, total = await AuditService(db).list(
        pp=pp, action=action, entity_type=entity_type, entity_id=entity_id,
        actor_id=actor_id, date_from=date_from, date_to=date_to,
    )
    return Page(items=[AuditLogOut.model_validate(x) for x in items], total=total, limit=pp.limit, offset=pp.offset)
