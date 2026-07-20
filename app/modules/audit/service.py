"""audit Service — audit_log yozish (atomik: chaqiruvchi tranzaksiyasi bilan commit bo'ladi)."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLog


class AuditService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def record(
        self,
        *,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID | None = None,
        actor_id: uuid.UUID | None = None,
        before: dict | None = None,
        after: dict | None = None,
        ip: str | None = None,
    ) -> None:
        """Audit yozuvini sessiyaga qo'shadi (commit qilmaydi — chaqiruvchi commit qiladi)."""
        self.db.add(
            AuditLog(
                actor_id=actor_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                before=before,
                after=after,
                ip=ip,
            )
        )

    async def list(
        self,
        *,
        action: str | None = None,
        entity_type: str | None = None,
        actor_id: uuid.UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLog]:
        stmt = select(AuditLog)
        if action is not None:
            stmt = stmt.where(AuditLog.action == action)
        if entity_type is not None:
            stmt = stmt.where(AuditLog.entity_type == entity_type)
        if actor_id is not None:
            stmt = stmt.where(AuditLog.actor_id == actor_id)
        stmt = stmt.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())
