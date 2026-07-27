"""integrations Service — DB-driven token (env fallback) + CRUD + event log + setup helperlar.

Token o'qish tartibi: IntegrationConfig (DB, aktiv) → .env (settings) → default.
Shunда admin API orqali tokenni almashtirsa, keyingi so'rov avtomatik yangisini oladi.
"""
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppError, NotFoundError
from app.modules.integrations.models import IntegrationConfig, IntegrationEvent
from app.modules.integrations.repository import IntegrationRepository

settings = get_settings()


async def get_config_value(db: AsyncSession, provider: str, key: str, default: str = "") -> str:
    """Faqat DB'dan (IntegrationConfig, aktiv). Env'дан OLINMAYDI — token yagona manba: DB."""
    row = await IntegrationRepository(db).get(provider, key)
    if row is not None and row.value:
        return row.value
    return default


async def log_event(db: AsyncSession, provider: str, raw: dict, *, status: str = "received", note: str | None = None):
    """Xom webhook payload'ni saqlaydi (audit/debug). Best-effort — xato bo'lsa yutiladi."""
    try:
        db.add(IntegrationEvent(provider=provider, direction="inbound", raw=raw, status=status, note=note))
        await db.flush()
    except Exception:  # noqa: BLE001
        pass


async def ensure_telegram_webhook(db: AsyncSession) -> str:
    """Ishga tushganда webhook'ni avtomatik ulaydi. Ulangan bo'lsa tegmaydi.

    Qaytadi: disabled | no_token | skip_not_https | already_connected | set.
    """
    if not settings.telegram_auto_webhook:
        return "disabled"
    token = await get_config_value(db, "telegram", "bot_token")
    if not token:
        return "no_token"  # token yo'q — hech narsa qilinmaydi
    base = settings.public_base_url.rstrip("/")
    if not base.startswith("https://"):
        return "skip_not_https"  # Telegram faqat https public URL qabul qiladi (dev'da o'tkazamiz)

    desired = f"{base}/webhooks/telegram"
    svc = IntegrationService(db)
    try:
        info = await svc.telegram_webhook_info()
        if (info or {}).get("url") == desired:
            return "already_connected"  # allaqachon shu URL'ga ulangan — TEGMAYMIZ
    except Exception:  # noqa: BLE001 — info olinmasa ham set qilib ko'ramiz
        pass
    await svc.telegram_set_webhook(desired)
    return "set"


class IntegrationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = IntegrationRepository(db)

    # ---------- Config CRUD ----------
    async def list_configs(self, *, provider, pp):
        return await self.repo.list_configs(provider=provider, pp=pp)

    async def get_config(self, config_id):
        cfg = await self.repo.get_by_id(config_id)
        if cfg is None:
            raise NotFoundError("Integration config topilmadi")
        return cfg

    async def upsert_config(self, data) -> IntegrationConfig:
        """(provider,key) bo'yicha yaratadi yoki yangilaydi (unikal)."""
        existing = await self.repo.get_pair(data.provider, data.key)
        if existing is not None:
            existing.value = data.value
            existing.is_active = data.is_active
            await self.db.commit()
            await self.db.refresh(existing)  # updated_at (onupdate) ni async qayta yuklash
            return existing
        cfg = IntegrationConfig(provider=data.provider, key=data.key, value=data.value, is_active=data.is_active)
        await self.repo.add(cfg)
        await self.db.commit()
        return cfg

    async def update_config(self, config_id, data) -> IntegrationConfig:
        cfg = await self.get_config(config_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(cfg, field, value)
        await self.db.commit()
        await self.db.refresh(cfg)
        return cfg

    async def delete_config(self, config_id) -> None:
        cfg = await self.get_config(config_id)
        await self.db.delete(cfg)
        await self.db.commit()

    async def list_events(self, *, provider, status, pp):
        return await self.repo.list_events(provider=provider, status=status, pp=pp)

    # ---------- Telegram setup helperlar (Bot API) ----------
    async def _tg_call(self, method: str, payload: dict | None = None) -> dict:
        token = await get_config_value(self.db, "telegram", "bot_token")
        if not token:
            raise AppError("Telegram bot_token sozlanmagan (IntegrationConfig yoki .env)")
        url = f"{settings.telegram_api_base_url.rstrip('/')}/bot{token}/{method}"
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as c:
            resp = await c.post(url, json=payload or {})
        data = resp.json()
        if not data.get("ok"):
            raise AppError(f"Telegram {method} xato: {data.get('description', resp.text[:200])}")
        return data.get("result", data)

    async def telegram_set_webhook(self, url: str) -> dict:
        secret = await get_config_value(self.db, "telegram", "webhook_secret")
        payload = {"url": url, "allowed_updates": ["message", "edited_message", "callback_query"]}
        if secret:
            payload["secret_token"] = secret
        return await self._tg_call("setWebhook", payload)

    async def telegram_webhook_info(self) -> dict:
        return await self._tg_call("getWebhookInfo")

    async def telegram_get_me(self) -> dict:
        return await self._tg_call("getMe")

    async def telegram_delete_webhook(self) -> dict:
        return await self._tg_call("deleteWebhook")

    # ---------- Instagram setup (Graph API) ----------
    async def instagram_subscribe(self) -> dict:
        """me/subscribed_apps — akkauntni webhook eventlariga obuna qiladi (majburiy qadam)."""
        token = await get_config_value(self.db, "instagram", "access_token")
        if not token:
            raise AppError("Instagram access_token sozlanmagan")
        base = settings.instagram_graph_base_url.rstrip("/")
        url = f"{base}/{settings.instagram_graph_version}/me/subscribed_apps"
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as c:
            resp = await c.post(url, params={"access_token": token, "subscribed_fields": "messages"})
        if resp.status_code >= 400:
            raise AppError(f"Instagram subscribe xato: {resp.status_code} {resp.text[:200]}")
        return resp.json()
