"""Boshlang'ich ma'lumot seed'i (idempotent) — migratsiyadan keyin ishga tushiriladi.

Yaratadi (agar mavjud bo'lmasa):
- barcha permission kodlari (TZ 13-bo'lim),
- 15 ta system rol + ularning permission'lari,
- Super Admin foydalanuvchi (.env: SEED_ADMIN_*),
- boshlang'ich settings (TZ 14-bo'lim).

Ishga tushirish: `python -m app.seed`.
"""
import asyncio

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.modules.identity.models import (
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)
from app.modules.identity.permissions import (
    ALL,
    SYSTEM_ROLES,
    all_permission_codes,
)
from app.modules.ai.knowledge_defaults import DEFAULT_KNOWLEDGE
from app.modules.catalog.models import Gender, Material, Stone
from app.modules.ai.models import KnowledgeBase
from app.modules.settings.defaults import DEFAULT_SETTINGS
from app.modules.settings.models import Setting

settings = get_settings()


async def seed_permissions(db) -> dict[str, Permission]:
    existing = {p.code: p for p in (await db.execute(select(Permission))).scalars()}
    for code in all_permission_codes():
        if code not in existing:
            perm = Permission(code=code)
            db.add(perm)
            existing[code] = perm
    await db.flush()
    return existing


async def seed_roles(db, perms: dict[str, Permission]) -> None:
    existing_roles = {r.name: r for r in (await db.execute(select(Role))).scalars()}
    all_codes = set(all_permission_codes())

    for role_name, codes in SYSTEM_ROLES.items():
        role = existing_roles.get(role_name)
        if role is None:
            role = Role(name=role_name, is_system=True)
            db.add(role)
            await db.flush()

        wanted = all_codes if codes == ALL else set(codes)
        current = {
            rp.permission_id
            for rp in (
                await db.execute(
                    select(RolePermission).where(RolePermission.role_id == role.id)
                )
            ).scalars()
        }
        for code in wanted:
            perm = perms.get(code)
            if perm is not None and perm.id not in current:
                db.add(RolePermission(role_id=role.id, permission_id=perm.id))
    await db.flush()


async def seed_admin(db) -> None:
    user = (
        await db.execute(select(User).where(User.email == settings.seed_admin_email))
    ).scalar_one_or_none()
    if user is None:
        user = User(
            full_name=settings.seed_admin_name,
            email=settings.seed_admin_email,
            password_hash=hash_password(settings.seed_admin_password),
            is_active=True,
        )
        db.add(user)
        await db.flush()

    super_admin = (
        await db.execute(select(Role).where(Role.name == "Super Admin"))
    ).scalar_one_or_none()
    if super_admin is not None:
        link = (
            await db.execute(
                select(UserRole).where(
                    UserRole.user_id == user.id,
                    UserRole.role_id == super_admin.id,
                )
            )
        ).scalar_one_or_none()
        if link is None:
            db.add(UserRole(user_id=user.id, role_id=super_admin.id))


async def seed_settings(db) -> None:
    existing = {s.key for s in (await db.execute(select(Setting))).scalars()}
    for key, value in DEFAULT_SETTINGS.items():
        if key not in existing:
            db.add(Setting(key=key, value=value))


async def seed_knowledge(db) -> None:
    existing = {k.title for k in (await db.execute(select(KnowledgeBase))).scalars()}
    for entry in DEFAULT_KNOWLEDGE:
        if entry["title"] not in existing:
            db.add(KnowledgeBase(type=entry["type"], title=entry["title"], content=entry["content"]))


async def seed_catalog_references(db) -> None:
    """gender/material/stone lug'atlari (bo'sh bo'lsa boshlang'ich qiymatlar)."""
    defaults = {
        Gender: [("Erkak", "Мужской", 1), ("Ayol", "Женский", 2), ("Uniseks", "Унисекс", 3)],
        Material: [("Kumush 925 + rodiy", "Серебро 925 + родий", 1)],
        Stone: [("Serkon", "Серкон (фианит)", 1)],
    }
    for model, rows in defaults.items():
        existing = {r.name_uz for r in (await db.execute(select(model))).scalars()}
        for name_uz, name_ru, order in rows:
            if name_uz not in existing:
                db.add(model(name_uz=name_uz, name_ru=name_ru, sort_order=order))
    await db.flush()


async def main() -> None:
    async with SessionLocal() as db:
        perms = await seed_permissions(db)
        await seed_roles(db, perms)
        await seed_admin(db)
        await seed_catalog_references(db)
        await seed_settings(db)
        await seed_knowledge(db)
        await db.commit()
    print(
        f"✅ Seed yakunlandi. Super Admin: {settings.seed_admin_email} "
        f"({len(all_permission_codes())} permission, {len(SYSTEM_ROLES)} system rol)"
    )


if __name__ == "__main__":
    asyncio.run(main())
