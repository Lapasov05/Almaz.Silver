"""Kanal adapterlari uchun umumiy tiplar va interfeys."""
import re
from dataclasses import dataclass, field
from typing import Protocol

# LLM javobidagi markdown belgilarini oddiy matnга aylantirish (TG/IG render qilmaydi)
_MD_PATTERNS = [
    (re.compile(r"\*\*(.+?)\*\*", re.DOTALL), r"\1"),   # **bold**
    (re.compile(r"__(.+?)__", re.DOTALL), r"\1"),       # __bold__
    (re.compile(r"`{1,3}([^`]+)`{1,3}"), r"\1"),        # `code`
    (re.compile(r"^#{1,6}\s*", re.MULTILINE), ""),      # # sarlavha
    (re.compile(r"^\s*[-*]\s+", re.MULTILINE), "• "),   # ro'yxat -> •
]


def strip_markdown(text: str | None) -> str:
    """Chiquvchi xabardan markdown belgilarini olib tashlaydi (bitta markazlashgan joy)."""
    if not text:
        return ""
    for pattern, repl in _MD_PATTERNS:
        text = pattern.sub(repl, text)
    return text


class ChannelError(Exception):
    """Kanal (IG/TG) bilan ishlashда yuzaga kelgan xato (config yo'q, API xatosi)."""


@dataclass
class NormalizedIncoming:
    """Kanaldan kelgan xabarning yagona (normallashtirilgan) ko'rinishi."""

    channel: str  # "telegram" | "instagram"
    external_user_id: str
    text: str | None = None
    username: str | None = None
    full_name: str | None = None
    external_message_id: str | None = None
    attachments: list[dict] = field(default_factory=list)


@dataclass
class SendResult:
    external_message_id: str | None = None


class ChannelClient(Protocol):
    """Outbound xabar yuborish interfeysi (Telegram/Instagram amalga oshiradi)."""

    async def send_text(self, recipient_id: str, text: str) -> SendResult: ...

    async def send_image(self, recipient_id: str, image_url: str, caption: str | None = None) -> SendResult:
        """Rasm (URL) yuboradi — ixtiyoriy izoh (caption) bilan."""
        ...

    async def send_typing(self, recipient_id: str) -> None:
        """"Yozyapti..." indikatorini yuboradi (best-effort — xato bo'lsa jim)."""
        ...
