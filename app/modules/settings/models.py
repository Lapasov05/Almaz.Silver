"""settings ORM modeli — universal key-value do'kon (TZ 6.2: setting(key, value jsonb))."""
from typing import Any

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import Base, TimestampMixin, UUIDMixin


class Setting(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "setting"

    key: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    # JSONB har qanday JSON qiymatni saqlaydi (bool/son/matn/list/obyekt).
    # nullable=True — `primary_card` kabi qiymatlar null bo'lishi mumkin.
    value: Mapped[Any] = mapped_column(JSONB, nullable=True)
