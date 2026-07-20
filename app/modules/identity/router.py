"""identity API qatlami — /auth endpointlari (TZ 15-bo'lim: JWT + refresh)."""
from fastapi import APIRouter, Depends, status

from app.core.config import get_settings
from app.core.deps import get_auth_service, get_current_user
from app.core.rate_limit import rate_limit
from app.modules.identity.models import User
from app.modules.identity.schemas import (
    LoginRequest,
    MeResponse,
    RefreshRequest,
    TokenResponse,
)
from app.modules.identity.service import AuthService

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=TokenResponse,
    # TZ 15: login brute-force rate limit (IP bo'yicha)
    dependencies=[Depends(rate_limit(settings.rate_limit_login_per_min, "login"))],
)
async def login(
    payload: LoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    access, refresh = await service.login(payload.email, payload.password)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: RefreshRequest,
    service: AuthService = Depends(get_auth_service),
) -> None:
    """Refresh token'ni bekor qiladi (blacklist)."""
    await service.logout(payload.refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(
    payload: RefreshRequest,
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    access, refresh = await service.refresh(payload.refresh_token)
    return TokenResponse(access_token=access, refresh_token=refresh)


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
