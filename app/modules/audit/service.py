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
        pp=None,
        action: str | None = None,
        entity_type: str | None = None,
        entity_id: uuid.UUID | None = None,
        actor_id: uuid.UUID | None = None,
        date_from=None,
        date_to=None,
    ):
        from app.core.pagination import PageParams, paginate

        stmt = select(AuditLog)
        if action is not None:
            stmt = stmt.where(AuditLog.action == action)
        if entity_type is not None:
            stmt = stmt.where(AuditLog.entity_type == entity_type)
        if entity_id is not None:
            stmt = stmt.where(AuditLog.entity_id == entity_id)
        if actor_id is not None:
            stmt = stmt.where(AuditLog.actor_id == actor_id)
        if date_from is not None:
            stmt = stmt.where(AuditLog.created_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(AuditLog.created_at <= date_to)
        if pp is None:  # ichki chaqiruvlar uchun (test/smoke) — oddiy ro'yxat
            pp = PageParams(limit=100, offset=0)
            items, _ = await paginate(self.db, stmt, [AuditLog.created_at.desc()], pp)
            return items
        return await paginate(self.db, stmt, [AuditLog.created_at.desc()], pp)
