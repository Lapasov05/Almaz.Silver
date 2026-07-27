"""integrations Repository qatlami."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PageParams, paginate
from app.modules.integrations.models import IntegrationConfig, IntegrationEvent


class IntegrationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add(self, obj):
        self.db.add(obj)
        await self.db.flush()
        return obj

    # ---------- Config ----------
    async def get(self, provider: str, key: str) -> IntegrationConfig | None:
        """Aktiv qiymat (bir (provider,key) unikal)."""
        res = await self.db.execute(
            select(IntegrationConfig).where(
                IntegrationConfig.provider == provider,
                IntegrationConfig.key == key,
                IntegrationConfig.is_active.is_(True),
            )
        )
        return res.scalar_one_or_none()

    async def get_by_id(self, config_id: uuid.UUID) -> IntegrationConfig | None:
        return await self.db.get(IntegrationConfig, config_id)

    async def get_pair(self, provider: str, key: str) -> IntegrationConfig | None:
        res = await self.db.execute(
            select(IntegrationConfig).where(
                IntegrationConfig.provider == provider, IntegrationConfig.key == key
            )
        )
        return res.scalar_one_or_none()

    async def list_configs(self, *, provider: str | None, pp: PageParams):
        stmt = select(IntegrationConfig)
        if provider is not None:
            stmt = stmt.where(IntegrationConfig.provider == provider)
        return await paginate(self.db, stmt, [IntegrationConfig.provider, IntegrationConfig.key], pp)

    # ---------- Event ----------
    async def list_events(self, *, provider: str | None, status: str | None, pp: PageParams):
        stmt = select(IntegrationEvent)
        if provider is not None:
            stmt = stmt.where(IntegrationEvent.provider == provider)
        if status is not None:
            stmt = stmt.where(IntegrationEvent.status == status)
        return await paginate(self.db, stmt, [IntegrationEvent.created_at.desc()], pp)
