"""Kanal adapterlari uchun umumiy tiplar va interfeys."""
from dataclasses import dataclass, field
from typing import Protocol


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
