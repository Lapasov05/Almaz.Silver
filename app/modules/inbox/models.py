"""inbox ORM modellari — customer, conversation, message (TZ 6.2 / 9-bo'lim).

IG + TG xabarlar bitta inbox'da, kanal bo'yicha ajratiladi. Har xabarда kim yozgani
ko'rinadi (`sender_type`). 15-daqiqalik handoff: operator yozsa AI pauza qilinadi.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import Base, TimestampMixin, UUIDMixin


# --- Enum'lar (VARCHAR + CHECK: native_enum=False migratsiyada) ---
class Channel(str, enum.Enum):
    instagram = "instagram"
    telegram = "telegram"


class AiState(str, enum.Enum):
    """Conversation state machine (TZ 7.1)."""

    greeting = "greeting"
    browsing = "browsing"
    recommending = "recommending"
    ordering = "ordering"
    awaiting_location = "awaiting_location"
    awaiting_payment = "awaiting_payment"
    payment_review = "payment_review"
    handed_off = "handed_off"
    closed = "closed"


class ConversationStatus(str, enum.Enum):
    open = "open"
    closed = "closed"


class MessageDirection(str, enum.Enum):
    incoming = "incoming"
    outgoing = "outgoing"


class SenderType(str, enum.Enum):
    customer = "customer"
    ai = "ai"
    operator = "operator"
    system = "system"


class DeliveryStatus(str, enum.Enum):
    pending = "pending"
    sent = "sent"
    delivered = "delivered"
    read = "read"
    failed = "failed"


class Customer(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "customer"
    __table_args__ = (
        UniqueConstraint("channel", "external_id", name="uq_customer_channel_external"),
    )

    channel: Mapped[Channel] = mapped_column(
        String(20), nullable=False
    )
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)  # IG/TG user id
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    language: Mapped[str] = mapped_column(String(8), server_default="uz", nullable=False)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # TZ 6.1: soft delete (customer)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    conversations: Mapped[list["Conversation"]] = relationship(back_populates="customer")


class Conversation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "conversation"
    __table_args__ = (
        # TZ 6.3: conversation(status, last_activity_at)
        Index("ix_conversation_status_activity", "status", "last_activity_at"),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("customer.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel: Mapped[Channel] = mapped_column(String(20), nullable=False)
    ai_state: Mapped[AiState] = mapped_column(
        String(30), server_default=AiState.greeting.value, nullable=False
    )
    status: Mapped[ConversationStatus] = mapped_column(
        String(20), server_default=ConversationStatus.open.value, nullable=False
    )
    assigned_operator_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    # TZ 9: operator yozgach AI pauzasi (now + ai_pause_minutes)
    ai_paused_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    unread_count: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    last_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    customer: Mapped["Customer"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "message"
    __table_args__ = (
        # TZ 6.3: message(conversation_id, created_at)
        Index("ix_message_conversation_created", "conversation_id", "created_at"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False
    )
    direction: Mapped[MessageDirection] = mapped_column(String(10), nullable=False)
    sender_type: Mapped[SenderType] = mapped_column(String(10), nullable=False)
    sender_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    # rasm/video/voice metadata (TZ 9). Voice→transkripsiya keyingi bosqichда.
    attachments: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # AI tool-calling izlari (TZ 6.2) — Faza 3'да to'ldiriladi
    tool_call: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    delivery_status: Mapped[DeliveryStatus] = mapped_column(
        String(12), server_default=DeliveryStatus.pending.value, nullable=False
    )
    is_read: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Kanaldagi tashqi xabar id (delivery mapping/dedup uchun)
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
