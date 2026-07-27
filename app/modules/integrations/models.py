"""integrations ORM — IntegrationConfig (DB-driven token) + IntegrationEvent (xom payload audit).

Asosiy g'oya (INTEGRATIONS.md): tokenlar kodda emas, `(provider, key) -> value` jadvalida.
Admin API orqali almashtiradi — deploy shart emas.
"""
import enum

from sqlalchemy import String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import Base, TimestampMixin, UUIDMixin


class IntegrationConfig(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "integration_config"
    __table_args__ = (UniqueConstraint("provider", "key", name="uq_integration_provider_key"),)

    provider: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # telegram|instagram|openai
    key: Mapped[str] = mapped_column(String(120), nullable=False)                  # bot_token, access_token, ...
    value: Mapped[str | None] = mapped_column(Text, nullable=True)                 # haqiqiy qiymat (token)
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true", nullable=False)


class EventStatus(str, enum.Enum):
    received = "received"
    parsed = "parsed"
    ignored = "ignored"
    error = "error"


class IntegrationEvent(UUIDMixin, TimestampMixin, Base):
    """Har kelgan xom webhook payload (parse qilinsa ham, qilinmasa ham) — audit/debug."""

    __tablename__ = "integration_event"

    provider: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(10), server_default="inbound", nullable=False)
    raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)     # xom payload
    status: Mapped[str] = mapped_column(String(16), server_default="received", nullable=False, index=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)  # xato/izoh
