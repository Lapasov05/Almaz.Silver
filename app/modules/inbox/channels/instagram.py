"""Instagram (Meta Graph API) adapteri — parse, X-Hub imzo, verify challenge, yuborish (TZ 3/15)."""
import hashlib
import hmac

import httpx

from app.core.config import get_settings
from app.modules.inbox.channels.base import ChannelError, NormalizedIncoming, SendResult

settings = get_settings()


def verify_signature(raw_body: bytes, header_value: str | None) -> bool:
    """Meta `X-Hub-Signature-256: sha256=<hmac>` imzosini tekshiradi (app_secret bilan)."""
    app_secret = settings.instagram_app_secret
    if not app_secret:  # sozlanmagan bo'lsa dev'da o'tkazib yuboramiz
        return True
    if not header_value or not header_value.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    provided = header_value.split("=", 1)[1]
    return hmac.compare_digest(expected, provided)


def verify_challenge(mode: str | None, token: str | None, challenge: str | None) -> str | None:
    """GET webhook verification (hub.mode=subscribe + hub.verify_token mos)."""
    if mode == "subscribe" and token and token == settings.instagram_verify_token:
        return challenge
    return None


def parse_payload(payload: dict) -> list[NormalizedIncoming]:
    """IG webhook payload'idan barcha kelgan xabarlarni normallashtiradi (echo'lar tashlanadi)."""
    results: list[NormalizedIncoming] = []
    for entry in payload.get("entry", []):
        for event in entry.get("messaging", []):
            message = event.get("message")
            if not message or message.get("is_echo"):
                continue  # bizning yuborgan (echo) xabarlarni e'tiborsiz qoldiramiz
            sender_id = str((event.get("sender") or {}).get("id", ""))
            if not sender_id:
                continue
            attachments = [
                {"type": att.get("type"), "url": (att.get("payload") or {}).get("url")}
                for att in message.get("attachments", [])
            ]
            results.append(
                NormalizedIncoming(
                    channel="instagram",
                    external_user_id=sender_id,
                    text=message.get("text"),
                    external_message_id=message.get("mid"),
                    attachments=attachments,
                )
            )
    return results


class InstagramClient:
    """Instagram Send API klienti (Graph API /me/messages)."""

    def __init__(self) -> None:
        self._token = settings.instagram_page_access_token
        self._base = settings.instagram_graph_base_url.rstrip("/")
        self._version = settings.instagram_graph_version

    async def send_text(self, recipient_id: str, text: str) -> SendResult:
        if not self._token:
            raise ChannelError("INSTAGRAM_PAGE_ACCESS_TOKEN sozlanmagan")
        url = f"{self._base}/{self._version}/me/messages"
        body = {"recipient": {"id": recipient_id}, "message": {"text": text}}
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            resp = await client.post(url, params={"access_token": self._token}, json=body)
        if resp.status_code >= 400:
            raise ChannelError(f"Instagram send xato: {resp.status_code} {resp.text[:200]}")
        return SendResult(external_message_id=resp.json().get("message_id"))
