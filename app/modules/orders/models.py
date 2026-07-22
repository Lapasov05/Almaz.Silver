"""orders ORM modellari — order, order_item, order_status_history (TZ 6.2 / 10).

Invariantlar (TZ 18):
1. O'lcham variant EMAS → `order_item.ring_size` (hamma o'lcham bir narx).
2. Zaxira variant ichida — `create_order` da `reserved_qty++` (band).
3. Bonuslar global (Settings) → `order_item.bonus_snapshot` (yaratish vaqtidagi nusxa).
"""
import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import Base, TimestampMixin, UUIDMixin


class OrderStatus(str, enum.Enum):
    """TZ 10: buyurtma hayotiy sikli."""

    draft = "draft"
    pending = "pending"
    waiting_payment = "waiting_payment"
    payment_review = "payment_review"
    confirmed = "confirmed"
    preparing = "preparing"
    packed = "packed"
    shipping = "shipping"
    delivered = "delivered"
    completed = "completed"
    cancelled = "cancelled"
    refunded = "refunded"
    returned = "returned"


class Order(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "order"

    order_no: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("customer.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    assigned_operator_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[OrderStatus] = mapped_column(
        String(20), server_default=OrderStatus.pending.value, nullable=False, index=True
    )
    items_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), server_default="0", nullable=False)
    delivery_fee: Mapped[Decimal] = mapped_column(Numeric(12, 2), server_default="0", nullable=False)
    grand_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), server_default="0", nullable=False)
    # TZ 1 KPI 3: AI o'zi yaratgan buyurtmalar sonini hisoblash uchun
    created_by_ai: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    history: Mapped[list["OrderStatusHistory"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "order_item"

    order_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("order.id", ondelete="CASCADE"), nullable=False, index=True
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("variant.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, server_default="1", nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)  # yaratish vaqtidagi fixed narx
    ring_size: Mapped[str | None] = mapped_column(String(10), nullable=True)  # TZ invariant 1
    bonus_snapshot: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # TZ invariant 3
    # --- Ism yozish (gravyurka) — o'lcham kabi, variant EMAS, order'da belgilanadi ---
    engraving_text: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Buyurtma vaqtidagi BIR DONA uchun ism yozish narxi (snapshot; keyin settings o'zgarsa ta'sir qilmaydi)
    engraving_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), server_default="0", nullable=False
    )

    order: Mapped["Order"] = relationship(back_populates="items")


class OrderStatusHistory(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "order_status_history"

    order_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("order.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    # changed_by: user id (operator/owner) yoki NULL (AI/system)
    changed_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )

    order: Mapped["Order"] = relationship(back_populates="history")
