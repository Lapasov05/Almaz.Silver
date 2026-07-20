"""payments ORM modellari — payment, payment_card (TZ 6.2 / 12).

Faqat prepaid. Bitta order = bitta payment (order_id UNIQUE). Tasdiqlagan xodim
"to'landi" qaroriga javobgar (reviewed_by). Idempotentlik: bir payment bir marta approve.
"""
import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import Base, TimestampMixin, UUIDMixin


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class PaymentCard(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "payment_card"

    holder_name: Mapped[str] = mapped_column(String(255), nullable=False)
    card_number_masked: Mapped[str] = mapped_column(String(32), nullable=False)  # masalan 8600****1234
    is_primary: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)


class Payment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "payment"

    order_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("order.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    card_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("payment_card.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[PaymentStatus] = mapped_column(
        String(12), server_default=PaymentStatus.pending.value, nullable=False, index=True
    )
    receipt_url: Mapped[str | None] = mapped_column(String(500), nullable=True)  # chek — object storage
    payer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # TZ 12: tasdiqlagan/rad etgan xodim javobgar
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    card: Mapped["PaymentCard | None"] = relationship()
