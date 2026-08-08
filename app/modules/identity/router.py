"""identity API qatlami — /auth endpointlari (TZ 15-bo'lim: JWT + refresh)."""
from fastapi import APIRouter, Depends, status

from app.core.config import get_settings
from app.core.deps import get_auth_service, get_current_user
from app.core.rate_limit import rate_limit
from app.modules.identity.models import User
from app.modules.identity.schemas import (
    AuthResponse,
    LoginRequest,
    MeResponse,
    RefreshRequest,
    UserOut,
)
from app.modules.identity.service import AuthService

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])


async def _auth_response(
    service: AuthService, user: User, access: str, refresh: str
) -> AuthResponse:
    """Tokenlar + foydalanuvchi, rollari va permission'lari (frontend darhol ishlatadi)."""
    permissions = await service.get_permissions(user.id)
    roles = await service.repo.get_user_roles(user.id)
    return AuthResponse(
        access_token=access,
        refresh_token=refresh,
        user=UserOut.model_validate(user),
        roles=roles,
        permissions=sorted(permissions),
    )


@router.post(
    "/login",
    response_model=AuthResponse,
    # TZ 15: login brute-force rate limit (IP bo'yicha)
    dependencies=[Depends(rate_limit(settings.rate_limit_login_per_min, "login"))],
)
async def login(
    payload: LoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    """Kirish — tokenlar bilan birga permission ro'yxati ham qaytadi."""
    user, access, refresh = await service.login(payload.email, payload.password)
    return await _auth_response(service, user, access, refresh)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: RefreshRequest,
    service: AuthService = Depends(get_auth_service),
) -> None:
    """Refresh token'ni bekor qiladi (blacklist)."""
    await service.logout(payload.refresh_token)


@router.post("/refresh", response_model=AuthResponse)
async def refresh_tokens(
    payload: RefreshRequest,
    service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    """Token yangilash — permission'lar ham qayta beriladi (rol o'zgargan bo'lsa yangilanadi)."""
    user, access, refresh = await service.refresh(payload.refresh_token)
    return await _auth_response(service, user, access, refresh)


@router.get("/me", response_model=MeResponse)
async def me(
    user: User = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
) -> MeResponse:
    """Joriy foydalanuvchi + rollari va permission'lari (RBAC tekshiruvi ishlashini isbotlaydi)."""
    permissions = await service.get_permissions(user.id)
    roles = await service.repo.get_user_roles(user.id)
    return MeResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        is_active=user.is_active,
        roles=roles,
        permissions=sorted(permissions),
    )
