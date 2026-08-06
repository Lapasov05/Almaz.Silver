"""Telegram Bot API adapteri — parse, webhook secret tekshiruvi, xabar yuborish (TZ 3/15)."""
import hmac
import logging

import httpx

from app.core.config import get_settings
from app.modules.inbox.channels.base import ChannelError, NormalizedIncoming, SendResult, split_message

settings = get_settings()
logger = logging.getLogger(__name__)


def verify_secret(header_value: str | None, expected: str | None = None) -> bool:
    """Telegram webhook secret token tekshiruvi (setWebhook secret_token).

    Telegram tanani imzolamaydi — o'rniga `X-Telegram-Bot-Api-Secret-Token` header'i ishlatiladi.
    `expected` berilmasa .env'dan olinadi (DB-token uchun chaqiruvchi uzatadi).
    """
    if expected is None:
        expected = ""  # DB'да yo'q bo'lsa — tekshiruv o'tkazib yuboriladi (chaqiruvchi DB'дан beradi)
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

    # GURUH/kanal xabarlarini E'TIBORSIZ qoldiramiz — bot faqat SHAXSIY (private) suhbatlarda mijoz
    # bilan ishlaydi. Orders-guruhi (yoki bot a'zo bo'lgan boshqa guruh) xabarlari inbox'ga tushmasin
    # va AI ularга javob bermasin (bot privacy off bo'lsa ham). Guruhga faqat xabar YUBORAMIZ.
    chat_type = (msg.get("chat") or {}).get("type")
    if chat_type and chat_type != "private":
        return None

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

    def __init__(self, bot_token: str | None = None) -> None:
        self._token = bot_token or ""  # token DB'дан beriladi (chaqiruvchi build_channel_client orqali)
        self._base = settings.telegram_api_base_url.rstrip("/")

    async def send_text(
        self, recipient_id: str, text: str, reply_markup: dict | None = None
    ) -> SendResult:
        if not self._token:
            raise ChannelError("TELEGRAM_BOT_TOKEN sozlanmagan")
        url = f"{self._base}/bot{self._token}/sendMessage"
        chunks = split_message(text, 4000) or [""]  # Telegram limiti 4096
        last = SendResult()
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            for i, chunk in enumerate(chunks):
                payload: dict = {"chat_id": recipient_id, "text": chunk}
                if reply_markup is not None and i == len(chunks) - 1:  # tugmalar oxirgi bo'lakda
                    payload["reply_markup"] = reply_markup
                resp = await client.post(url, json=payload)
                if resp.status_code != 200 or not resp.json().get("ok"):
                    raise ChannelError(f"Telegram sendMessage xato: {resp.status_code} {resp.text[:200]}")
                result = resp.json().get("result", {})
                last = SendResult(external_message_id=str(result.get("message_id")) if result.get("message_id") else None)
        return last

    async def send_image(self, recipient_id: str, image_url: str, caption: str | None = None) -> SendResult:
        """sendPhoto — rasm (URL) + ixtiyoriy caption."""
        if not self._token:
            raise ChannelError("TELEGRAM_BOT_TOKEN sozlanmagan")
        payload: dict = {"chat_id": recipient_id, "photo": image_url}
        if caption:
            payload["caption"] = caption[:1024]  # Telegram caption limiti
        url = f"{self._base}/bot{self._token}/sendPhoto"
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            resp = await client.post(url, json=payload)
        if resp.status_code != 200 or not resp.json().get("ok"):
            raise ChannelError(f"Telegram sendPhoto xato: {resp.status_code} {resp.text[:200]}")
        result = resp.json().get("result", {})
        return SendResult(external_message_id=str(result.get("message_id")) if result.get("message_id") else None)

    async def send_images(self, recipient_id: str, items: list[dict]) -> SendResult:
        if not self._token:
            raise ChannelError("TELEGRAM_BOT_TOKEN sozlanmagan")
        if len(items) == 1:
            item = items[0]
            caption = "\n".join(value for value in (item.get("title"), item.get("subtitle")) if value)
            return await self.send_image(recipient_id, item["image_url"], caption)
        media = []
        for item in items[:10]:
            caption = "\n".join(value for value in (item.get("title"), item.get("subtitle")) if value)
            media.append({"type": "photo", "media": item["image_url"], "caption": caption[:1024]})
        url = f"{self._base}/bot{self._token}/sendMediaGroup"
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            response = await client.post(url, json={"chat_id": recipient_id, "media": media})
        if response.status_code != 200 or not response.json().get("ok"):
            raise ChannelError(f"Telegram sendMediaGroup xato: {response.status_code} {response.text[:200]}")
        messages = response.json().get("result") or []
        message_id = messages[-1].get("message_id") if messages else None
        return SendResult(external_message_id=str(message_id) if message_id else None)

    async def send_typing(self, recipient_id: str) -> None:
        """sendChatAction(typing) — "yozyapti..." (best-effort, ~5s ko'rinadi)."""
        if not self._token:
            return
        url = f"{self._base}/bot{self._token}/sendChatAction"
        try:
            async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
                resp = await client.post(url, json={"chat_id": recipient_id, "action": "typing"})
            if resp.status_code != 200 or not resp.json().get("ok"):
                logger.warning("Telegram sendChatAction xato: %s %s", resp.status_code, resp.text[:200])
        except Exception as e:  # noqa: BLE001 — indikator muhim emas
            logger.warning("Telegram sendChatAction yuborilmadi: %s", e)

    async def answer_callback(self, callback_query_id: str, text: str | None = None) -> None:
        if not self._token:
            return
        url = f"{self._base}/bot{self._token}/answerCallbackQuery"
        body: dict = {"callback_query_id": callback_query_id}
        if text:
            body["text"] = text
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            await client.post(url, json=body)
