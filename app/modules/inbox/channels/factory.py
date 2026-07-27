"""Kanal bo'yicha outbound klient tanlash."""
from app.modules.inbox.channels.base import ChannelClient, ChannelError
from app.modules.inbox.channels.instagram import InstagramClient
from app.modules.inbox.channels.telegram import TelegramClient


def get_channel_client(channel: str) -> ChannelClient:
    """.env tokenlari bilan (DB'siz)."""
    if channel == "telegram":
        return TelegramClient()
    if channel == "instagram":
        return InstagramClient()
    raise ChannelError(f"Noma'lum kanal: {channel}")


async def build_channel_client(db, channel: str) -> ChannelClient:
    """Tokenni IntegrationConfig (DB) → .env dan olib klient quradi."""
    from app.modules.integrations.service import get_config_value

    if channel == "telegram":
        token = await get_config_value(db, "telegram", "bot_token")
        return TelegramClient(bot_token=token)
    if channel == "instagram":
        token = await get_config_value(db, "instagram", "access_token")
        return InstagramClient(access_token=token)
    raise ChannelError(f"Noma'lum kanal: {channel}")
