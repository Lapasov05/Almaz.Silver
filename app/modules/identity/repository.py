"""identity Repository qatlami — faqat DB kirish (biznes logika Service'da)."""
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.models import (
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)


class IdentityRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email, User.deleted_at.is_(None))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        stmt = select(User).where(User.id == user_id, User.deleted_at.is_(None))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_permissions(self, user_id: uuid.UUID) -> set[str]:
        """Foydalanuvchining barcha rollaridan yig'ilgan permission kodlari."""
        stmt = (
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(UserRole, UserRole.role_id == RolePermission.role_id)
            .where(UserRole.user_id == user_id)
        )
        result = await self.db.execute(stmt)
        return {row[0] for row in result.all()}

    async def get_user_roles(self, user_id: uuid.UUID) -> list[str]:
        stmt = (
            select(Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
        )
        result = await self.db.execute(stmt)
        return [row[0] for row in result.all()]

    # ---------- RBAC admin (Faza 6) ----------
    async def add(self, obj):
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def list_permissions(self) -> list[Permission]:
        res = await self.db.execute(select(Permission).order_by(Permission.code))
        return list(res.scalars().all())

    async def get_permissions_by_codes(self, codes: list[str]) -> list[Permission]:
        res = await self.db.execute(select(Permission).where(Permission.code.in_(codes)))
        return list(res.scalars().all())

    async def list_roles(self) -> list[Role]:
        res = await self.db.execute(select(Role).order_by(Role.name))
        return list(res.scalars().all())

    async def get_role(self, role_id: uuid.UUID) -> Role | None:
        return await self.db.get(Role, role_id)

    async def get_role_by_name(self, name: str) -> Role | None:
        res = await self.db.execute(select(Role).where(Role.name == name))
        return res.scalar_one_or_none()

    async def role_permission_codes(self, role_id: uuid.UUID) -> list[str]:
        res = await self.db.execute(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role_id)
            .order_by(Permission.code)
        )
        return [row[0] for row in res.all()]

    async def replace_role_permissions(self, role_id: uuid.UUID, permission_ids: list[uuid.UUID]) -> None:
        """Rolning permissionlarini to'liq almashtiradi (checkbox matritsa saqlash)."""
        await self.db.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
        for pid in permission_ids:
            self.db.add(RolePermission(role_id=role_id, permission_id=pid))
        await self.db.flush()

    async def list_users(self, *, include_deleted: bool = False) -> list[User]:
        stmt = select(User)
        if not include_deleted:
            stmt = stmt.where(User.deleted_at.is_(None))
        stmt = stmt.order_by(User.full_name)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def replace_user_roles(self, user_id: uuid.UUID, role_ids: list[uuid.UUID]) -> None:
        await self.db.execute(delete(UserRole).where(UserRole.user_id == user_id))
        for rid in role_ids:
            self.db.add(UserRole(user_id=user_id, role_id=rid))
        await self.db.flush()

    async def user_ids_with_role(self, role_id: uuid.UUID) -> list[uuid.UUID]:
        res = await self.db.execute(select(UserRole.user_id).where(UserRole.role_id == role_id))
        return [row[0] for row in res.all()]
