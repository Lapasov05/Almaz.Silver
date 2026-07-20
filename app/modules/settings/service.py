"""settings Service qatlami."""
from typing import Any

from app.core.exceptions import NotFoundError
from app.modules.settings.models import Setting
from app.modules.settings.repository import SettingsRepository


class SettingsService:
    def __init__(self, repo: SettingsRepository):
        self.repo = repo

    async def list_all(self) -> list[Setting]:
        return await self.repo.list_all()

    async def get(self, key: str) -> Setting:
        setting = await self.repo.get(key)
        if setting is None:
            raise NotFoundError(f"Sozlama topilmadi: {key}")
        return setting

    async def update(self, key: str, value: Any) -> Setting:
        setting = await self.repo.upsert(key, value)
        await self.repo.db.commit()
        return setting
