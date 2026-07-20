"""Async Redis klienti — permission cache, rate limit, session uchun (TZ 3/13-bo'lim)."""
import redis.asyncio as aioredis

from app.core.config import get_settings

settings = get_settings()

_redis_client: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Umumiy Redis klienti (lazy singleton, decode_responses=True)."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
    return _redis_client
