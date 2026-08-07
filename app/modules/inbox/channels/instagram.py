"""Instagram (Meta Graph API) adapteri — parse, X-Hub imzo, verify challenge, yuborish (TZ 3/15)."""
import hashlib
import hmac
import logging

import httpx

from app.core.config import get_settings
from app.modules.inbox.channels.base import ChannelError, NormalizedIncoming, SendResult, split_message

settings = get_settings()
logger = logging.getLogger(__name__)


def verify_signature(raw_body: bytes, header_value: str | None, app_secret: str | None = None) -> bool:
    """Meta `X-Hub-Signature-256: sha256=<hmac>` imzosini tekshiradi (app_secret bilan)."""
    if app_secret is None:
        app_secret = ""  # DB'дан beriladi
    if not app_secret:  # sozlanmagan bo'lsa dev'da o'tkazib yuboramiz
        return True
    if not header_value or not header_value.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    provided = header_value.split("=", 1)[1]
    return hmac.compare_digest(expected, provided)


def verify_challenge(mode: str | None, token: str | None, challenge: str | None,
                     verify_token: str | None = None) -> str | None:
    """GET webhook verification (hub.mode=subscribe + hub.verify_token mos)."""
    if verify_token is None:
        verify_token = ""  # DB'дан beriladi
    if mode == "subscribe" and token and verify_token and token == verify_token:
        return challenge
    return None


# IG attachment/referral payload'ida media id va havola turli kalitlarda keladi
# (docs/instagram_webhook_flow.md — "Media ID Olish Prioriteti"). Tartib muhim.
_MEDIA_ID_KEYS = (
    "story_media_id", "ig_post_media_id", "ig_reel_media_id", "reel_video_id",
    "reel_media_id", "media_id", "media_share_id", "media_product_id",
    "source_id", "target_id", "id",
)
_MEDIA_URL_KEYS = ("story_media_url", "url", "media_url", "permalink", "link", "share_url")
_REFERRAL_ID_KEYS = ("media_id", "source_id", "story_id", "id")
_REFERRAL_URL_KEYS = ("source_url", "url", "link", "permalink")


def _pick(source: dict, keys: tuple[str, ...]) -> str | None:
    """Berilgan kalitlar tartibida birinchi bo'sh bo'lmagan qiymat."""
    for key in keys:
        value = source.get(key)
        if value:
            return str(value)
    return None


def _normalize_attachment(attachment: dict) -> dict:
    """IG attachment'ni normallashtiradi — havola va media id SAQLANADI.

    Mijoz post/reel/story'ni directga yuborsa, mahsulotni topish uchun aynan shu
    havola/id kerak (`resolve_instagram_media`). Ilgari faqat `payload.url` olinardi,
    shu sabab story yuborilganда hech qanday ma'lumot qolmasdi.
    """
    atype = (attachment.get("type") or "").lower()
    payload = attachment.get("payload") or {}
    item: dict = {"type": atype, "url": _pick(payload, _MEDIA_URL_KEYS)}
    ref = _pick(payload, _MEDIA_ID_KEYS)
    if atype == "ig_story":
        item["story_ref"] = ref
        item["source"] = "share"  # storyni directga yubordi (javob emas)
    elif ref:
        item["media_ref"] = ref
    return item


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
            raw_attachments = message.get("attachments") or []
            text = message.get("text")
            # IG telefon raqam/kontakt kartasi: matnsiz, faqat bo'sh `template` keladi.
            # Bu mijoz xabari EMAS (raqam matn bilan allaqachon kelgan) — saqlamaymiz, AI ham qo'zg'almaydi.
            if not text and raw_attachments and all(
                (att.get("type") or "") == "template" for att in raw_attachments
            ):
                continue
            attachments = [_normalize_attachment(att) for att in raw_attachments]
            reply = message.get("reply_to") or {}
            # Story javobi: mijoz bizning story'ga javob berdi -> story media_id (mahsulotga bog'lash uchun)
            story = reply.get("story") or {}
            if story.get("id"):
                attachments.append({
                    "type": "ig_story",
                    "story_ref": str(story["id"]),
                    "url": story.get("url"),
                    "source": "reply",
                })
            elif reply.get("mid"):
                # Oddiy xabarga reply — AI qaysi xabar nazarda tutilganini bilishi uchun
                attachments.append({
                    "type": "reply",
                    "reply_to_external_id": str(reply["mid"]),
                    "is_self_reply": bool(reply.get("is_self_reply")),
                })
            # Referral: mijoz reklama/post/story ichidagi tugma orqali DM ochdi
            referral = event.get("referral") or (event.get("postback") or {}).get("referral") or {}
            if referral:
                attachments.append({
                    "type": "ig_referral",
                    "url": _pick(referral, _REFERRAL_URL_KEYS),
                    "media_ref": _pick(referral, _REFERRAL_ID_KEYS),
                })
            results.append(
                NormalizedIncoming(
                    channel="instagram",
                    external_user_id=sender_id,
                    text=text,
                    external_message_id=message.get("mid"),
                    attachments=attachments,
                )
            )
    return results


class InstagramClient:
    """Instagram Send API klienti (Graph API /me/messages)."""

    def __init__(self, access_token: str | None = None, business_id: str | None = None) -> None:
        self._token = access_token or ""  # token DB'дан beriladi
        # Send endpoint: `{business_id}/messages` (DB'да business_id bo'lsa) yoki `me/messages`
        self._sender = (business_id or "").strip() or "me"
        self._base = settings.instagram_graph_base_url.rstrip("/")
        self._version = settings.instagram_graph_version

    async def list_active_stories(self) -> list[dict]:
        """Aktiv (24 soat ichidagi) storylar: [{"id": ..., "permalink": ...}].

        Webhook story javobida keladigan `id` permalink'dagi share id'дан farq qiladi.
        Graph API ikkalasini birga qaytaradi — mahsulotni aniq topish uchun shu kerak
        (docs/instagram_webhook_flow.md, "Story Linklash Algoritmi").
        """
        if not self._token:
            return []
        url = f"{settings.instagram_stories_base_url.rstrip('/')}/{self._version}/me/stories"
        try:
            async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
                resp = await client.get(url, params={"fields": "id,permalink", "access_token": self._token})
        except Exception as e:  # noqa: BLE001 — lookup ixtiyoriy, oqim to'xtamasin
            logger.warning("Instagram active stories olinmadi: %s", e)
            return []
        if resp.status_code >= 400:
            logger.warning("Instagram active stories xato: %s %s", resp.status_code, resp.text[:250])
            return []
        data = resp.json()
        return [item for item in (data.get("data") or []) if isinstance(item, dict)]

    async def send_text(self, recipient_id: str, text: str) -> SendResult:
        if not self._token:
            raise ChannelError("Instagram access_token sozlanmagan")
        url = f"{self._base}/{self._version}/{self._sender}/messages"
        # Instagram matn limiti ~1000 belgi — uzun matnni bo'laklab yuboramiz (aks holda 400/xato)
        chunks = split_message(text, 950) or [""]
        last = SendResult()
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            for chunk in chunks:
                body = {"recipient": {"id": recipient_id}, "message": {"text": chunk}}
                resp = await client.post(url, params={"access_token": self._token}, json=body)
                if resp.status_code >= 400:
                    raise ChannelError(f"Instagram send xato: {resp.status_code} {resp.text[:200]}")
                last = SendResult(external_message_id=resp.json().get("message_id"))
        return last

    async def send_image(self, recipient_id: str, image_url: str, caption: str | None = None) -> SendResult:
        """Rasm attachment yuboradi (IG /me/messages). Caption alohida matn sifatida oldin ketadi."""
        if not self._token:
            raise ChannelError("Instagram access_token sozlanmagan")
        url = f"{self._base}/{self._version}/{self._sender}/messages"
        # IG bitta xabarda rasm+matnni birga qo'llamaydi. Tartib MUHIM: avval RASM, keyin caption
        # (aks holda matn rasmdan oldin chiqib, chalkash ko'rinadi).
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            body = {"recipient": {"id": recipient_id},
                    "message": {"attachment": {"type": "image", "payload": {"url": image_url}}}}
            resp = await client.post(url, params={"access_token": self._token}, json=body)
            if resp.status_code >= 400:
                raise ChannelError(f"Instagram rasm yuborish xato: {resp.status_code} {resp.text[:200]}")
            data = resp.json()
            # IG ba'zan 200 bilan {"error": ...} qaytaradi (rasm URL'ini ololmasa) — jim o'tmasin
            if isinstance(data, dict) and data.get("error"):
                raise ChannelError(f"Instagram rasm rad etildi (200): {str(data['error'])[:200]}")
            result_id = data.get("message_id")
            if caption:  # rasmdan KEYIN matn
                await client.post(url, params={"access_token": self._token},
                                  json={"recipient": {"id": recipient_id}, "message": {"text": caption}})
        return SendResult(external_message_id=result_id)

    async def send_images(self, recipient_id: str, items: list[dict]) -> SendResult:
        if not self._token:
            raise ChannelError("Instagram access_token sozlanmagan")
        elements = []
        for index, item in enumerate(items[:10], start=1):
            elements.append({
                "title": str(item.get("title") or f"{index}-mahsulot")[:80],
                "image_url": item["image_url"],
                "subtitle": str(item.get("subtitle") or "")[:80],
            })
        if not elements:
            raise ChannelError("Instagram carousel uchun rasm topilmadi")
        url = f"{self._base}/{self._version}/{self._sender}/messages"
        body = {
            "recipient": {"id": recipient_id},
            "message": {
                "attachment": {
                    "type": "template",
                    "payload": {"template_type": "generic", "elements": elements},
                }
            },
        }
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            response = await client.post(url, params={"access_token": self._token}, json=body)
        if response.status_code >= 400:
            raise ChannelError(f"Instagram carousel xato: {response.status_code} {response.text[:200]}")
        data = response.json()
        if isinstance(data, dict) and data.get("error"):
            raise ChannelError(f"Instagram carousel rad etildi: {str(data['error'])[:200]}")
        return SendResult(external_message_id=data.get("message_id"))

    async def send_typing(self, recipient_id: str) -> None:
        """sender_action=typing_on — "yozyapti..." (best-effort)."""
        if not self._token:
            return
        url = f"{self._base}/{self._version}/{self._sender}/messages"
        body = {"recipient": {"id": recipient_id}, "sender_action": "typing_on"}
        try:
            async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
                resp = await client.post(url, params={"access_token": self._token}, json=body)
            if resp.status_code >= 400:  # httpx 4xx'da istisno tashlamaydi — o'zimiz log qilamiz
                logger.warning("Instagram typing_on xato: %s %s", resp.status_code, resp.text[:250])
        except Exception as e:  # noqa: BLE001 — indikator muhim emas, javobga ta'sir qilmasin
            logger.warning("Instagram typing_on yuborilmadi: %s", e)
