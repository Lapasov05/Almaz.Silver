"""Redis taqsimlangan qulf — bitta resurs ustida bir vaqtda faqat bitta ish bajarilsin.

AI javobi uchun kerak: mijoz ketma-ket yozsa har xabar alohida Celery task ochadi va
ular parallel ishlab, bir xil javobni ikki marta yuborib qo'yadi. Qulf ularni navbatga soladi.
"""
import asyncio
import logging
import uuid
from contextlib import asynccontextmanager

from app.core.redis import get_redis

logger = logging.getLogger(__name__)

# Qulfni faqat egasi ochsin (TTL tugab boshqa jarayon olib ulgurgan bo'lishi mumkin)
_RELEASE_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""


@asynccontextmanager
async def redis_lock(
    key: str,
    *,
    ttl_seconds: int = 180,
    wait_seconds: float = 0.0,
    poll_seconds: float = 0.5,
):
    """`key` bo'yicha qulf oladi; `wait_seconds` davomida bo'shashini kutadi.

    `True` — qulf bizda (ish bajarilsin), `False` — boshqa jarayon ushlab turibdi.
    Redis ishlamasa oqim to'xtamasin: qulfsiz (`True`) davom etadi.
    """
    try:
        redis = await get_redis()
    except Exception as exc:  # noqa: BLE001 — qulf ixtiyoriy, javob berish muhimroq
        logger.warning("Redis qulfi olinmadi (%s) — qulfsiz davom etamiz: %s", key, exc)
        yield True
        return

    redis_key = f"lock:{key}"
    token = uuid.uuid4().hex
    acquired = False
    try:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + wait_seconds
        acquired = bool(await redis.set(redis_key, token, nx=True, ex=ttl_seconds))
        while not acquired and loop.time() < deadline:
            await asyncio.sleep(poll_seconds)
            acquired = bool(await redis.set(redis_key, token, nx=True, ex=ttl_seconds))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redis qulfi xatosi (%s) — qulfsiz davom etamiz: %s", key, exc)
        yield True
        return

    try:
        yield acquired
    finally:
        if acquired:
            try:
                await redis.eval(_RELEASE_LUA, 1, redis_key, token)
            except Exception:  # noqa: BLE001 — TTL baribir bo'shatadi
                logger.warning("Redis qulfi bo'shatilmadi: %s", redis_key, exc_info=True)
