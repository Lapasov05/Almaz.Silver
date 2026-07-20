"""Dependency Injection (TZ 4-bo'lim) — DB, joriy foydalanuvchi, permission tekshiruvi.

`require_permission(code)` — RBAC dependency: permission Redis'da keshlangan holda
tekshiriladi (TZ 13-bo'lim: har so'rovda DB'ga bormaslik).
"""
import uuid

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AuthError, PermissionDenied
from app.core.security import decode_token
from app.modules.identity.models import User
from app.modules.identity.repository import IdentityRepository
from app.modules.identity.service import AuthService

bearer_scheme = HTTPBearer(auto_error=False)


def get_identity_repository(db: AsyncSession = Depends(get_db)) -> IdentityRepository:
    return IdentityRepository(db)


def get_auth_service(
    repo: IdentityRepository = Depends(get_identity_repository),
) -> AuthService:
    return AuthService(repo)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    repo: IdentityRepository = Depends(get_identity_repository),
) -> User:
    """Bearer access token'dan joriy foydalanuvchini yuklaydi."""
    if credentials is None:
        raise AuthError("Avtorizatsiya talab qilinadi")

    payload = decode_token(credentials.credentials)
    if payload.get("type") != "access":
        raise AuthError("Noto'g'ri token turi")

    user = await repo.get_user_by_id(uuid.UUID(payload["sub"]))
    if user is None or not user.is_active:
        raise AuthError("Foydalanuvchi topilmadi yoki faol emas")
    return user


def require_permission(code: str):
    """Berilgan permission kodini talab qiluvchi dependency fabrikasi.

    Namuna: `Depends(require_permission("settings:manage_settings"))`.
    """

    async def _checker(
        user: User = Depends(get_current_user),
        service: AuthService = Depends(get_auth_service),
    ) -> User:
        permissions = await service.get_permissions(user.id)
        if code not in permissions:
            raise PermissionDenied(f"Ruxsat yo'q: {code}")
        return user

    return _checker
