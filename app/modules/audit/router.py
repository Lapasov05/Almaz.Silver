"""audit API — audit_log ko'rish (TZ 13/15), `audit:view` bilan."""
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.modules.audit.schemas import AuditLogOut
from app.modules.audit.service import AuditService

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get(
    "",
    response_model=list[AuditLogOut],
    dependencies=[Depends(require_permission("audit:view"))],
)
async def list_audit(
    db: AsyncSession = Depends(get_db),
    action: str | None = None,
    entity_type: str | None = None,
    actor_id: uuid.UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[AuditLogOut]:
    logs = await AuditService(db).list(
        action=action, entity_type=entity_type, actor_id=actor_id, limit=limit, offset=offset
    )
    return [AuditLogOut.model_validate(x) for x in logs]
