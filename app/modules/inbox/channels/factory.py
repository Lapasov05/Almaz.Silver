"""Kanal bo'yicha outbound klient tanlash."""
from app.modules.inbox.channels.base import ChannelClient, ChannelError
from app.modules.inbox.channels.instagram import InstagramClient
from app.modules.inbox.channels.telegram import TelegramClient


def get_channel_client(channel: str) -> ChannelClient:
    if channel == "telegram":
        return TelegramClient()
    if channel == "instagram":
        return InstagramClient()
    raise ChannelError(f"Noma'lum kanal: {channel}")
