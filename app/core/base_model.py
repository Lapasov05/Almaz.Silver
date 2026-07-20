"""SQLAlchemy 2.0 deklarativ baza va umumiy mixinlar.

TZ 6.1: hamma jadvalда UUID PK (`gen_random_uuid()`) + `created_at`/`updated_at` (timestamptz).
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, func, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Barcha ORM modellari uchun umumiy deklarativ baza."""


class UUIDMixin:
    """UUID birlamchi kalit — DB tomonida gen_random_uuid() bilan generatsiya qilinadi."""

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )


class TimestampMixin:
    """created_at / updated_at — timestamptz, DB tomonida boshqariladi."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
