from dataclasses import dataclass, field
from typing import Protocol


def split_message(text: str | None, limit: int) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= limit:
        return [text]
    parts: list[str] = []
    current = ""
    for line in text.split("\n"):
        while len(line) > limit:
            if current:
                parts.append(current)
                current = ""
            parts.append(line[:limit])
            line = line[limit:]
        if len(current) + len(line) + 1 > limit:
            if current:
                parts.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        parts.append(current)
    return parts


class ChannelError(Exception):
    pass


@dataclass
class NormalizedIncoming:
    channel: str
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
    async def send_text(self, recipient_id: str, text: str) -> SendResult: ...

    async def send_image(self, recipient_id: str, image_url: str, caption: str | None = None) -> SendResult: ...

    async def send_images(self, recipient_id: str, items: list[dict]) -> SendResult: ...

    async def send_typing(self, recipient_id: str) -> None: ...
