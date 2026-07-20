"""settings Repository qatlami."""
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.settings.models import Setting


class SettingsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_all(self) -> list[Setting]:
        result = await self.db.execute(select(Setting).order_by(Setting.key))
        return list(result.scalars().all())

    async def get(self, key: str) -> Setting | None:
        result = await self.db.execute(select(Setting).where(Setting.key == key))
        return result.scalar_one_or_none()

    async def upsert(self, key: str, value: Any) -> Setting:
        setting = await self.get(key)
        if setting is None:
            setting = Setting(key=key, value=value)
            self.db.add(setting)
        else:
            setting.value = value
        await self.db.flush()
        return setting
