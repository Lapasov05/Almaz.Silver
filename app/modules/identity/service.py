"""identity Service qatlami — auth oqimi va permission cache (TZ 13/15-bo'lim)."""
import json
import uuid

from app.core.config import get_settings
from app.core.exceptions import AuthError
from app.core.redis import get_redis
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.core.token_blacklist import blacklist_jti, is_blacklisted
from app.modules.identity.models import User
from app.modules.identity.repository import IdentityRepository

settings = get_settings()

_PERM_CACHE_PREFIX = "perm:"


class AuthService:
    def __init__(self, repo: IdentityRepository):
        self.repo = repo

    async def authenticate(self, email: str, password: str) -> User | None:
        user = await self.repo.get_user_by_email(email)
        if user is None or not user.is_active:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    async def login(self, email: str, password: str) -> tuple[str, str]:
        user = await self.authenticate(email, password)
        if user is None:
            raise AuthError("Email yoki parol noto'g'ri")
        return self._issue_tokens(str(user.id))

    async def refresh(self, refresh_token: str) -> tuple[str, str]:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise AuthError("Noto'g'ri refresh token")
        if await is_blacklisted(payload.get("jti")):
            raise AuthError("Token bekor qilingan (logout)")
        user = await self.repo.get_user_by_id(uuid.UUID(payload["sub"]))
        if user is None or not user.is_active:
            raise AuthError("Foydalanuvchi topilmadi yoki faol emas")
        return self._issue_tokens(str(user.id))

    async def logout(self, refresh_token: str) -> None:
        """Refresh token'ni bekor qiladi (Redis blacklist, muddatigacha)."""
        payload = decode_token(refresh_token)
        jti = payload.get("jti")
        if jti:
            await blacklist_jti(jti, int(payload.get("exp", 0)))

    @staticmethod
    def _issue_tokens(subject: str) -> tuple[str, str]:
        # Refresh rotatsiyasi: har yangilanishда yangi refresh ham beriladi
        return create_access_token(subject), create_refresh_token(subject)

    async def get_permissions(self, user_id: uuid.UUID, use_cache: bool = True) -> set[str]:
        """Permission'lar Redis'da keshlanadi (TZ 13-bo'lim: har so'rovда DB'ga bormaslik)."""
        redis = await get_redis()
        cache_key = f"{_PERM_CACHE_PREFIX}{user_id}"

        if use_cache:
            cached = await redis.get(cache_key)
            if cached is not None:
                return set(json.loads(cached))

        permissions = await self.repo.get_user_permissions(user_id)
        await redis.set(
            cache_key,
            json.dumps(sorted(permissions)),
            ex=settings.permission_cache_ttl,
        )
        return permissions

    @staticmethod
    async def invalidate_permission_cache(user_id: uuid.UUID) -> None:
        """Rol/permission o'zgarganда chaqiriladi (Faza 6'da rol boshqaruvi bilan)."""
        redis = await get_redis()
        await redis.delete(f"{_PERM_CACHE_PREFIX}{user_id}")
