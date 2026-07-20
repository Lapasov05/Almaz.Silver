"""Telegram Bot API adapteri — parse, webhook secret tekshiruvi, xabar yuborish (TZ 3/15)."""
import hmac

import httpx

from app.core.config import get_settings
from app.modules.inbox.channels.base import ChannelError, NormalizedIncoming, SendResult

settings = get_settings()


def verify_secret(header_value: str | None) -> bool:
    """Telegram webhook secret token tekshiruvi (setWebhook secret_token).

    Telegram tanani imzolamaydi — o'rniga `X-Telegram-Bot-Api-Secret-Token` header'i ishlatiladi.
    """
    expected = settings.telegram_webhook_secret
    if not expected:  # sozlanmagan bo'lsa dev'da tekshiruvni o'tkazib yuboramiz
        return True
    if not header_value:
        return False
    return hmac.compare_digest(header_value, expected)


def parse_update(update: dict) -> NormalizedIncoming | None:
    """Telegram update'idan xabarni normallashtiradi. Xabar bo'lmasa None."""
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return None  # boshqa update turlari (callback, join va h.k.) — hozir e'tiborsiz

    frm = msg.get("from") or {}
    external_user_id = str(frm.get("id") or (msg.get("chat") or {}).get("id"))
    full_name = " ".join(
        part for part in [frm.get("first_name"), frm.get("last_name")] if part
    ) or None

    attachments: list[dict] = []
    for kind in ("photo", "voice", "video", "document", "audio", "sticker"):
        if kind in msg:
            payload = msg[kind]
            file_id = payload[-1]["file_id"] if kind == "photo" else payload.get("file_id")
            attachments.append({"type": kind, "file_id": file_id})

    return NormalizedIncoming(
        channel="telegram",
        external_user_id=external_user_id,
        text=msg.get("text") or msg.get("caption"),
        username=frm.get("username"),
        full_name=full_name,
        external_message_id=str(msg.get("message_id")) if msg.get("message_id") else None,
        attachments=attachments,
    )


class TelegramClient:
    """Telegram sendMessage klienti."""

    def __init__(self) -> None:
        self._token = settings.telegram_bot_token
        self._base = settings.telegram_api_base_url.rstrip("/")

    async def send_text(
        self, recipient_id: str, text: str, reply_markup: dict | None = None
    ) -> SendResult:
        if not self._token:
            raise ChannelError("TELEGRAM_BOT_TOKEN sozlanmagan")
        payload: dict = {"chat_id": recipient_id, "text": text}
        if reply_markup is not None:  # inline tugmalar (masalan tasdiq/rad)
            payload["reply_markup"] = reply_markup
        url = f"{self._base}/bot{self._token}/sendMessage"
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            resp = await client.post(url, json=payload)
        if resp.status_code != 200 or not resp.json().get("ok"):
            raise ChannelError(f"Telegram sendMessage xato: {resp.status_code} {resp.text[:200]}")
        result = resp.json().get("result", {})
        return SendResult(external_message_id=str(result.get("message_id")) if result.get("message_id") else None)

    async def answer_callback(self, callback_query_id: str, text: str | None = None) -> None:
        if not self._token:
            return
        url = f"{self._base}/bot{self._token}/answerCallbackQuery"
        body: dict = {"callback_query_id": callback_query_id}
        if text:
            body["text"] = text
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            await client.post(url, json=body)
