"""integrations API — token config CRUD + webhook eventlar + setup (INTEGRATIONS.md).

Hammasi `settings:manage_integrations` bilan (sezgir — tokenlar).
"""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.core.pagination import Page, PageParams, page_params, page_params_ref
from app.modules.integrations.schemas import (
    IntegrationConfigCreate,
    IntegrationConfigOut,
    IntegrationConfigUpdate,
    IntegrationEventOut,
    WebhookSetupRequest,
)
from app.modules.integrations.service import IntegrationService

router = APIRouter(prefix="/integrations", tags=["integrations"])
_MANAGE = Depends(require_permission("settings:manage_integrations"))


def svc(db: AsyncSession = Depends(get_db)) -> IntegrationService:
    return IntegrationService(db)


# ==================== Token config (DB-driven) ====================
@router.get("/configs", response_model=Page[IntegrationConfigOut], dependencies=[_MANAGE])
async def list_configs(provider: str | None = None, pp: PageParams = Depends(page_params_ref),
                       service: IntegrationService = Depends(svc)):
    items, total = await service.list_configs(provider=provider, pp=pp)
    return Page(items=[IntegrationConfigOut.model_validate(x) for x in items], total=total, limit=pp.limit, offset=pp.offset)


@router.post("/configs", response_model=IntegrationConfigOut, dependencies=[_MANAGE])
async def upsert_config(payload: IntegrationConfigCreate, service: IntegrationService = Depends(svc)):
    """(provider,key) bo'yicha yaratadi yoki yangilaydi. Masalan telegram/bot_token."""
    return IntegrationConfigOut.model_validate(await service.upsert_config(payload))


@router.patch("/configs/{config_id}", response_model=IntegrationConfigOut, dependencies=[_MANAGE])
async def update_config(config_id: uuid.UUID, payload: IntegrationConfigUpdate, service: IntegrationService = Depends(svc)):
    return IntegrationConfigOut.model_validate(await service.update_config(config_id, payload))


@router.delete("/configs/{config_id}", status_code=204, dependencies=[_MANAGE])
async def delete_config(config_id: uuid.UUID, service: IntegrationService = Depends(svc)):
    await service.delete_config(config_id)


# ==================== Webhook eventlar (xom payload audit) ====================
@router.get("/events", response_model=Page[IntegrationEventOut], dependencies=[_MANAGE])
async def list_events(provider: str | None = None, status: str | None = None,
                      pp: PageParams = Depends(page_params), service: IntegrationService = Depends(svc)):
    items, total = await service.list_events(provider=provider, status=status, pp=pp)
    return Page(items=[IntegrationEventOut.model_validate(x) for x in items], total=total, limit=pp.limit, offset=pp.offset)


# ==================== Setup (bir martalik) ====================
@router.post("/telegram/set-webhook", dependencies=[_MANAGE])
async def telegram_set_webhook(payload: WebhookSetupRequest, service: IntegrationService = Depends(svc)) -> dict:
    """Telegram'ga webhook URL o'rnatadi (bot_token DB/env'dan)."""
    return {"result": await service.telegram_set_webhook(payload.url)}


@router.get("/telegram/webhook-info", dependencies=[_MANAGE])
async def telegram_webhook_info(service: IntegrationService = Depends(svc)) -> dict:
    return await service.telegram_webhook_info()


@router.get("/telegram/me", dependencies=[_MANAGE])
async def telegram_get_me(service: IntegrationService = Depends(svc)) -> dict:
    """Qaysi bot ulanganini tekshirish."""
    return await service.telegram_get_me()


@router.post("/telegram/delete-webhook", dependencies=[_MANAGE])
async def telegram_delete_webhook(service: IntegrationService = Depends(svc)) -> dict:
    return {"result": await service.telegram_delete_webhook()}


@router.post("/instagram/subscribe", dependencies=[_MANAGE])
async def instagram_subscribe(service: IntegrationService = Depends(svc)) -> dict:
    """Akkauntni webhook eventlariga obuna qiladi (aks holda xabar kelmaydi)."""
    return await service.instagram_subscribe()
