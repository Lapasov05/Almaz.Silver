"""JWT revocation (TZ 15) — Redis blacklist (logout uchun).

Refresh token'ning `jti` si blacklist'ga qo'yiladi (token muddatigacha TTL bilan).
"""
import time

from app.core.redis import get_redis

_PREFIX = "jwt:blacklist:"


async def blacklist_jti(jti: str, exp_ts: int) -> None:
    """jti ni token muddati tugagunicha blacklist qiladi."""
    ttl = max(1, int(exp_ts - time.time()))
    redis = await get_redis()
    await redis.set(f"{_PREFIX}{jti}", "1", ex=ttl)


async def is_blacklisted(jti: str | None) -> bool:
    if not jti:
        return False
    redis = await get_redis()
    return (await redis.get(f"{_PREFIX}{jti}")) is not None
