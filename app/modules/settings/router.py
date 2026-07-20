"""settings API qatlami — RBAC bilan himoyalangan (TZ 13/14-bo'lim).

Ko'rish: `settings:view`; o'zgartirish: `settings:manage_settings`.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.modules.settings.repository import SettingsRepository
from app.modules.settings.schemas import SettingOut, SettingUpdate
from app.modules.settings.service import SettingsService

router = APIRouter(prefix="/settings", tags=["settings"])


def get_settings_service(db: AsyncSession = Depends(get_db)) -> SettingsService:
    return SettingsService(SettingsRepository(db))


@router.get(
    "",
    response_model=list[SettingOut],
    dependencies=[Depends(require_permission("settings:view"))],
)
async def list_settings(
    service: SettingsService = Depends(get_settings_service),
) -> list[SettingOut]:
    settings = await service.list_all()
    return [SettingOut.model_validate(s) for s in settings]


@router.get(
    "/{key}",
    response_model=SettingOut,
    dependencies=[Depends(require_permission("settings:view"))],
)
async def get_setting(
    key: str,
    service: SettingsService = Depends(get_settings_service),
) -> SettingOut:
    return SettingOut.model_validate(await service.get(key))


@router.put(
    "/{key}",
    response_model=SettingOut,
    dependencies=[Depends(require_permission("settings:manage_settings"))],
)
async def update_setting(
    key: str,
    payload: SettingUpdate,
    service: SettingsService = Depends(get_settings_service),
) -> SettingOut:
    return SettingOut.model_validate(await service.update(key, payload.value))
