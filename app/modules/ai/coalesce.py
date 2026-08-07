"""Javob takrorlanmasligi uchun "qayergacha javob berildi" belgisi (Redis).

Mijoz ketma-ket bir necha xabar yozganda AI ularning HAMMASINI bitta javobda qamrab oladi.
Shu sabab qolgan tasklar (har xabar uchun bittadan) qayta javob yozmasligi kerak.
Bu yerda oxirgi javob qamrab olgan kiruvchi xabar vaqti saqlanadi.
"""
import logging
import uuid
from datetime import datetime, timezone

from app.core.redis import get_redis

logger = logging.getLogger(__name__)

_TTL_SECONDS = 24 * 3600


def _key(conversation_id: uuid.UUID) -> str:
    return f"ai:answered_upto:{conversation_id}"


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


async def already_answered(conversation_id: uuid.UUID, message_created_at: datetime) -> bool:
    """Shu xabar allaqachon berilgan javob ichiga kirganmi?

    Redis ishlamasa `False` — javob berilaveradi (xabarsiz qolgandan ko'ra takror yaxshiroq).
    """
    try:
        raw = await (await get_redis()).get(_key(conversation_id))
    except Exception as exc:  # noqa: BLE001
        logger.warning("answered_upto o'qilmadi (%s): %s", conversation_id, exc)
        return False
    if not raw:
        return False
    try:
        return _as_utc(datetime.fromisoformat(raw)) >= _as_utc(message_created_at)
    except ValueError:
        return False


async def mark_answered(conversation_id: uuid.UUID, upto: datetime | None) -> None:
    """Javob shu vaqtgacha bo'lgan kiruvchi xabarlarni qamrab oldi."""
    if upto is None:
        return
    try:
        await (await get_redis()).set(_key(conversation_id), _as_utc(upto).isoformat(), ex=_TTL_SECONDS)
    except Exception as exc:  # noqa: BLE001 — belgisiz ham oqim buzilmasin
        logger.warning("answered_upto saqlanmadi (%s): %s", conversation_id, exc)
