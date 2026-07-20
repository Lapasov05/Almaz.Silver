"""RBAC boshqaruvi (TZ 13) — custom rollar, permission matritsa, user/rol tayinlash.

O'zgarishlarда: audit_log yoziladi + tegishli userlarning permission cache'i tozalanadi.
"""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, NotFoundError
from app.core.security import hash_password
from app.modules.audit.service import AuditService
from app.modules.identity.models import Permission, Role, User
from app.modules.identity.repository import IdentityRepository
from app.modules.identity.service import AuthService


class RbacService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = IdentityRepository(db)
        self.audit = AuditService(db)

    # ---------- Permissions ----------
    async def list_permissions(self) -> list[Permission]:
        return await self.repo.list_permissions()

    # ---------- Roles ----------
    async def list_roles(self) -> list[Role]:
        return await self.repo.list_roles()

    async def get_role(self, role_id: uuid.UUID) -> Role:
        role = await self.repo.get_role(role_id)
        if role is None:
            raise NotFoundError("Rol topilmadi")
        return role

    async def role_permission_codes(self, role_id: uuid.UUID) -> list[str]:
        await self.get_role(role_id)
        return await self.repo.role_permission_codes(role_id)

    async def create_role(self, name: str, *, actor_id: uuid.UUID | None) -> Role:
        if await self.repo.get_role_by_name(name) is not None:
            raise AppError(f"Bu nomli rol mavjud: {name}")
        role = await self.repo.add(Role(name=name, is_system=False))
        await self.audit.record(
            action="role.create", entity_type="role", entity_id=role.id,
            actor_id=actor_id, after={"name": name},
        )
        await self.db.commit()
        return role

    async def delete_role(self, role_id: uuid.UUID, *, actor_id: uuid.UUID | None) -> None:
        role = await self.get_role(role_id)
        if role.is_system:
            raise AppError("System rolni o'chirib bo'lmaydi")
        affected = await self.repo.user_ids_with_role(role_id)
        await self.audit.record(
            action="role.delete", entity_type="role", entity_id=role_id,
            actor_id=actor_id, before={"name": role.name},
        )
        await self.db.delete(role)
        await self.db.commit()
        await self._invalidate_users(affected)

    async def set_role_permissions(
        self, role_id: uuid.UUID, codes: list[str], *, actor_id: uuid.UUID | None
    ) -> list[str]:
        """Rolning permissionlarini to'liq almashtiradi (checkbox matritsa)."""
        await self.get_role(role_id)
        before = await self.repo.role_permission_codes(role_id)
        permissions = await self.repo.get_permissions_by_codes(codes)
        found = {p.code for p in permissions}
        unknown = set(codes) - found
        if unknown:
            raise AppError(f"Noma'lum permission(lar): {', '.join(sorted(unknown))}")

        await self.repo.replace_role_permissions(role_id, [p.id for p in permissions])
        await self.audit.record(
            action="role.set_permissions", entity_type="role", entity_id=role_id,
            actor_id=actor_id, before={"codes": before}, after={"codes": sorted(found)},
        )
        await self.db.commit()
        # Shu rolga ega barcha userlar cache'ini tozalaymiz (TZ 13)
        await self._invalidate_users(await self.repo.user_ids_with_role(role_id))
        return sorted(found)

    # ---------- Users ----------
    async def list_users(self) -> list[User]:
        return await self.repo.list_users()

    async def get_user(self, user_id: uuid.UUID) -> User:
        user = await self.repo.get_user_by_id(user_id)
        if user is None:
            raise NotFoundError("Foydalanuvchi topilmadi")
        return user

    async def create_user(
        self,
        *,
        full_name: str,
        email: str,
        password: str,
        role_ids: list[uuid.UUID] | None,
        actor_id: uuid.UUID | None,
    ) -> User:
        if await self.repo.get_user_by_email(email) is not None:
            raise AppError(f"Bu email band: {email}")
        user = await self.repo.add(
            User(full_name=full_name, email=email, password_hash=hash_password(password), is_active=True)
        )
        if role_ids:
            await self.repo.replace_user_roles(user.id, role_ids)
        await self.audit.record(
            action="user.create", entity_type="user", entity_id=user.id,
            actor_id=actor_id, after={"email": email, "full_name": full_name},
        )
        await self.db.commit()
        return user

    async def update_user(
        self, user_id: uuid.UUID, data: dict, *, actor_id: uuid.UUID | None
    ) -> User:
        user = await self.get_user(user_id)
        for field, value in data.items():
            setattr(user, field, value)
        await self.audit.record(
            action="user.update", entity_type="user", entity_id=user.id,
            actor_id=actor_id, after=data,
        )
        await self.db.commit()
        return user

    async def set_user_roles(
        self, user_id: uuid.UUID, role_ids: list[uuid.UUID], *, actor_id: uuid.UUID | None
    ) -> User:
        user = await self.get_user(user_id)
        await self.repo.replace_user_roles(user_id, role_ids)
        await self.audit.record(
            action="user.set_roles", entity_type="user", entity_id=user_id,
            actor_id=actor_id, after={"role_ids": [str(r) for r in role_ids]},
        )
        await self.db.commit()
        await self._invalidate_users([user_id])
        return user

    async def delete_user(self, user_id: uuid.UUID, *, actor_id: uuid.UUID | None) -> None:
        from datetime import datetime, timezone

        user = await self.get_user(user_id)
        user.deleted_at = datetime.now(timezone.utc)  # soft delete (TZ 6.1)
        await self.audit.record(
            action="user.delete", entity_type="user", entity_id=user_id, actor_id=actor_id,
        )
        await self.db.commit()
        await self._invalidate_users([user_id])

    async def _invalidate_users(self, user_ids: list[uuid.UUID]) -> None:
        for uid in user_ids:
            await AuthService.invalidate_permission_cache(uid)
