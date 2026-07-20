"""RBAC admin API (TZ 13) — rollar, permission matritsa, xodimlar.

Ruxsatlar: rol/permission — `roles:manage_roles`; xodimlar — `employees:manage_employees`;
o'qish — `roles:view` / `employees:view`.
"""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.modules.identity.models import User
from app.modules.identity.rbac_service import RbacService
from app.modules.identity.schemas import (
    PermissionOut,
    RoleCreate,
    RoleDetailOut,
    RoleOut,
    RolePermissionsSet,
    UserCreate,
    UserDetailOut,
    UserRolesSet,
    UserUpdate,
)

router = APIRouter(prefix="/rbac", tags=["rbac"])


def get_rbac_service(db: AsyncSession = Depends(get_db)) -> RbacService:
    return RbacService(db)


# ==================== Permissions (matritsa uchun) ====================
@router.get(
    "/permissions",
    response_model=list[PermissionOut],
    dependencies=[Depends(require_permission("roles:view"))],
)
async def list_permissions(service: RbacService = Depends(get_rbac_service)) -> list[PermissionOut]:
    return [PermissionOut.model_validate(p) for p in await service.list_permissions()]


# ==================== Roles ====================
@router.get(
    "/roles",
    response_model=list[RoleOut],
    dependencies=[Depends(require_permission("roles:view"))],
)
async def list_roles(service: RbacService = Depends(get_rbac_service)) -> list[RoleOut]:
    return [RoleOut.model_validate(r) for r in await service.list_roles()]


@router.get(
    "/roles/{role_id}",
    response_model=RoleDetailOut,
    dependencies=[Depends(require_permission("roles:view"))],
)
async def get_role(role_id: uuid.UUID, service: RbacService = Depends(get_rbac_service)) -> RoleDetailOut:
    role = await service.get_role(role_id)
    codes = await service.role_permission_codes(role_id)
    return RoleDetailOut(id=role.id, name=role.name, is_system=role.is_system, permissions=codes)


@router.post("/roles", response_model=RoleOut)
async def create_role(
    payload: RoleCreate,
    service: RbacService = Depends(get_rbac_service),
    user: User = Depends(require_permission("roles:manage_roles")),
) -> RoleOut:
    return RoleOut.model_validate(await service.create_role(payload.name, actor_id=user.id))


@router.put("/roles/{role_id}/permissions", response_model=RoleDetailOut)
async def set_role_permissions(
    role_id: uuid.UUID,
    payload: RolePermissionsSet,
    service: RbacService = Depends(get_rbac_service),
    user: User = Depends(require_permission("roles:manage_roles")),
) -> RoleDetailOut:
    """Rolning permissionlarini to'liq almashtiradi (checkbox matritsa saqlash)."""
    codes = await service.set_role_permissions(role_id, payload.codes, actor_id=user.id)
    role = await service.get_role(role_id)
    return RoleDetailOut(id=role.id, name=role.name, is_system=role.is_system, permissions=codes)


@router.delete("/roles/{role_id}", status_code=204)
async def delete_role(
    role_id: uuid.UUID,
    service: RbacService = Depends(get_rbac_service),
    user: User = Depends(require_permission("roles:manage_roles")),
) -> None:
    await service.delete_role(role_id, actor_id=user.id)


# ==================== Users (xodimlar) ====================
@router.get(
    "/users",
    response_model=list[UserDetailOut],
    dependencies=[Depends(require_permission("employees:view"))],
)
async def list_users(service: RbacService = Depends(get_rbac_service)) -> list[UserDetailOut]:
    users = await service.list_users()
    result = []
    for u in users:
        roles = await service.repo.get_user_roles(u.id)
        result.append(UserDetailOut(id=u.id, full_name=u.full_name, email=u.email, is_active=u.is_active, roles=roles))
    return result


@router.post("/users", response_model=UserDetailOut)
async def create_user(
    payload: UserCreate,
    service: RbacService = Depends(get_rbac_service),
    actor: User = Depends(require_permission("employees:manage_employees")),
) -> UserDetailOut:
    user = await service.create_user(
        full_name=payload.full_name, email=payload.email, password=payload.password,
        role_ids=payload.role_ids, actor_id=actor.id,
    )
    roles = await service.repo.get_user_roles(user.id)
    return UserDetailOut(id=user.id, full_name=user.full_name, email=user.email, is_active=user.is_active, roles=roles)


@router.patch("/users/{user_id}", response_model=UserDetailOut)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    service: RbacService = Depends(get_rbac_service),
    actor: User = Depends(require_permission("employees:manage_employees")),
) -> UserDetailOut:
    user = await service.update_user(user_id, payload.model_dump(exclude_unset=True), actor_id=actor.id)
    roles = await service.repo.get_user_roles(user.id)
    return UserDetailOut(id=user.id, full_name=user.full_name, email=user.email, is_active=user.is_active, roles=roles)


@router.put("/users/{user_id}/roles", response_model=UserDetailOut)
async def set_user_roles(
    user_id: uuid.UUID,
    payload: UserRolesSet,
    service: RbacService = Depends(get_rbac_service),
    actor: User = Depends(require_permission("employees:manage_employees")),
) -> UserDetailOut:
    user = await service.set_user_roles(user_id, payload.role_ids, actor_id=actor.id)
    roles = await service.repo.get_user_roles(user.id)
    return UserDetailOut(id=user.id, full_name=user.full_name, email=user.email, is_active=user.is_active, roles=roles)


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: uuid.UUID,
    service: RbacService = Depends(get_rbac_service),
    actor: User = Depends(require_permission("employees:manage_employees")),
) -> None:
    await service.delete_user(user_id, actor_id=actor.id)
