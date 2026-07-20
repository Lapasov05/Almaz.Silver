"""Parol hash (argon2) va JWT access/refresh token'lari (TZ 15-bo'lim).

Refresh oqimi: token turida `type` (access|refresh) belgilanadi. Faza 0'da
stateless (JWT ichida). Token revocation (blacklist) — keyingi fazada Redis bilan.
"""
import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings
from app.core.exceptions import AuthError

settings = get_settings()

# TZ 15-bo'lim: argon2 (zamonaviy, tavsiya etilgan) parol hashlash sxemasi
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def _create_token(subject: str, token_type: str, expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "type": token_type,
        "jti": uuid.uuid4().hex,  # revocation (blacklist) uchun
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str) -> str:
    return _create_token(
        subject, "access", timedelta(minutes=settings.access_token_expire_minutes)
    )


def create_refresh_token(subject: str) -> str:
    return _create_token(
        subject, "refresh", timedelta(days=settings.refresh_token_expire_days)
    )


def decode_token(token: str) -> dict:
    """JWT'ni dekod qiladi; yaroqsiz/muddati o'tgan bo'lsa AuthError ko'taradi."""
    try:
        return jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except JWTError as exc:
        raise AuthError("Token yaroqsiz yoki muddati o'tgan") from exc
