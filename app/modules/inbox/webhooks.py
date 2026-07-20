"""Webhook ingestor — IG/TG'dan xabar qabul qiladi (TZ 4/5/15).

Oqim: imzo tekshiruvi → xabarni sinxron saqlash → best-effort navbat → tez 200 OK.
Bu endpointlar OCHIQ (JWT yo'q), lekin imzo/secret bilan himoyalangan.
"""
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import AuthError
from app.core.rate_limit import rate_limit
from app.modules.inbox.channels import instagram as ig
from app.modules.inbox.channels import telegram as tg
from app.modules.inbox.repository import InboxRepository
from app.modules.inbox.service import InboxService
from app.modules.inbox.tasks import enqueue_incoming

settings = get_settings()
# TZ 15: webhook rate limit (IP bo'yicha)
_webhook_rl = Depends(rate_limit(settings.rate_limit_webhook_per_min, "webhook"))

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def get_inbox_service(db: AsyncSession = Depends(get_db)) -> InboxService:
    return InboxService(InboxRepository(db))


# ==================== Telegram ====================
@router.post("/telegram", dependencies=[_webhook_rl])
async def telegram_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    service: InboxService = Depends(get_inbox_service),
) -> dict:
    if not tg.verify_secret(request.headers.get("X-Telegram-Bot-Api-Secret-Token")):
        raise AuthError("Telegram secret token noto'g'ri")

    update = await request.json()

    # Owner/manager tasdiq/rad tugmalari (TZ 12): callback_query
    callback = update.get("callback_query")
    if callback:
        from app.modules.inbox.channels.telegram import TelegramClient
        from app.modules.payments.service import handle_payment_callback

        result_text = await handle_payment_callback(db, callback.get("data", ""))
        await TelegramClient().answer_callback(callback["id"], result_text)
        return {"ok": True}

    normalized = tg.parse_update(update)
    if normalized is not None:
        message = await service.ingest_incoming(normalized)
        enqueue_incoming(message.id)
    return {"ok": True}


# ==================== Instagram ====================
@router.get("/instagram")
async def instagram_verify(request: Request) -> PlainTextResponse:
    """Meta webhook verification (GET hub.challenge)."""
    p = request.query_params
    challenge = ig.verify_challenge(
        p.get("hub.mode"), p.get("hub.verify_token"), p.get("hub.challenge")
    )
    if challenge is None:
        raise AuthError("Instagram verify_token noto'g'ri")
    return PlainTextResponse(challenge)


@router.post("/instagram", dependencies=[_webhook_rl])
async def instagram_webhook(
    request: Request, service: InboxService = Depends(get_inbox_service)
) -> dict:
    raw = await request.body()
    if not ig.verify_signature(raw, request.headers.get("X-Hub-Signature-256")):
        raise AuthError("Instagram imzo (signature) noto'g'ri")

    payload = json.loads(raw or b"{}")
    for normalized in ig.parse_payload(payload):
        message = await service.ingest_incoming(normalized)
        enqueue_incoming(message.id)
    return {"ok": True}
