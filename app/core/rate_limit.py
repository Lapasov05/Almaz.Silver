"""Rate limiting (TZ 15) — Redis fixed-window hisoblagich; API va webhook uchun.

Kalit bo'yicha (masalan IP) belgilangan oyna ichida so'rovlar sonini cheklaydi.
"""
from fastapi import Request

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.redis import get_redis

settings = get_settings()


class RateLimitExceeded(AppError):
    status_code = 429


async def check_rate_limit(key: str, limit: int, window_seconds: int = 60) -> None:
    if not settings.rate_limit_enabled:
        return
    redis = await get_redis()
    redis_key = f"ratelimit:{key}"
    count = await redis.incr(redis_key)
    if count == 1:
        await redis.expire(redis_key, window_seconds)
    if count > limit:
        raise RateLimitExceeded("So'rovlar chekloviga yetdingiz. Birozdan keyin urinib ko'ring.")


def _client_ip(request: Request) -> str:
    # Nginx orqasida — X-Forwarded-For birinchi qiymati
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(limit_per_min: int, scope: str):
    """FastAPI dependency fabrikasi — IP bo'yicha scope'da cheklaydi."""

    async def _dep(request: Request) -> None:
        await check_rate_limit(f"{scope}:{_client_ip(request)}", limit_per_min, 60)

    return _dep
