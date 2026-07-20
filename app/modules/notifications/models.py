"""notifications ORM modeli — yuborilgan xabarnomalar qaydi (TZ 4/12)."""
import uuid

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import Base, TimestampMixin, UUIDMixin


class Notification(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "notification"

    type: Mapped[str] = mapped_column(String(48), nullable=False)  # masalan payment_review
    channel: Mapped[str] = mapped_column(String(20), nullable=False)  # telegram
    target: Mapped[str | None] = mapped_column(String(128), nullable=True)  # chat id
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(12), server_default="pending", nullable=False)  # sent|failed|skipped
    entity_type: Mapped[str | None] = mapped_column(String(48), nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
