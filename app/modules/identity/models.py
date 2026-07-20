"""identity ORM modellari — RBAC (TZ 6.2 / 13-bo'lim).

Jadvallar: user, role, permission, role_permission, user_role.
Eslatma: `user`/`role` — PostgreSQL'da rezerv so'zlar; SQLAlchemy ularni avtomatik
qo'shtirnoq bilan quote qiladi. TZ nomlarini saqlash uchun birlik shaklda qoldirildi.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import Base, TimestampMixin, UUIDMixin


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "user"

    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default="true", default=True, nullable=False
    )
    # TZ 6.1: soft delete faqat user/customer/product/variant uchun
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    roles: Mapped[list["UserRole"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Role(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "role"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    # is_system=True bo'lgan rollar (Super Admin, Owner, ...) o'chirilmaydi
    is_system: Mapped[bool] = mapped_column(
        Boolean, server_default="false", default=False, nullable=False
    )

    permissions: Mapped[list["RolePermission"]] = relationship(
        back_populates="role", cascade="all, delete-orphan"
    )


class Permission(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "permission"

    # Kod formati: `resource:action` (masalan `orders:approve`) — TZ 13-bo'lim
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)


class RolePermission(TimestampMixin, Base):
    __tablename__ = "role_permission"

    role_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("role.id", ondelete="CASCADE"),
        primary_key=True,
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("permission.id", ondelete="CASCADE"),
        primary_key=True,
    )

    role: Mapped["Role"] = relationship(back_populates="permissions")
    permission: Mapped["Permission"] = relationship()


class UserRole(TimestampMixin, Base):
    __tablename__ = "user_role"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("role.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # TZ 13-bo'lim: row-level scoping (ABAC) — masalan operatorga assign qilingan
    # suhbatlar yoki region bo'yicha cheklov. Faza 0'da faqat sxema tayyor.
    scope: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    user: Mapped["User"] = relationship(back_populates="roles")
    role: Mapped["Role"] = relationship()
