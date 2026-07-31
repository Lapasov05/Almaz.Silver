"""orders Pydantic DTO'lari."""
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.orders.models import OrderStatus


class OrderItemCreate(BaseModel):
    variant_id: uuid.UUID
    quantity: int = Field(default=1, ge=1)
    ring_size: str | None = Field(default=None, max_length=10)  # TZ: o'lcham order'da
    # Ism yozish (gravyurka): matn berilsa xizmat narxi qo'shiladi
    engraving_text: str | None = Field(default=None, max_length=50)
    # Box (rangli quti) — ixtiyoriy; berilsa mahsulot kategoriyasidagi box bo'lishi kerak
    box_id: uuid.UUID | None = None


class OrderCreate(BaseModel):
    customer_id: uuid.UUID
    items: list[OrderItemCreate] = Field(min_length=1)


class OrderCancel(BaseModel):
    reason: str | None = Field(default=None, max_length=255)


class OrderStatusUpdate(BaseModel):
    """Kanban board — buyurtma statusini qo'lda o'zgartirish (drag-&-drop)."""
    status: OrderStatus


class OrderUpdate(BaseModel):
    """Buyurtmaning SKALAR maydonlarini tahrirlash (PATCH). Faqat berilgan maydonlar yangilanadi.

    Qo'llab-quvvatlanmaydigan maydon (status, items, ...) yuborilsa -> 422 (jim tashlanmaydi).
    Status -> POST /orders/{id}/status; bekor -> POST /orders/{id}/cancel; tarkib -> PATCH /orders/{id}/items.
    """
    model_config = ConfigDict(extra="forbid")  # noma'lum maydon -> 422

    customer_id: uuid.UUID | None = None
    assigned_operator_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)


class OrderItemsUpdate(BaseModel):
    """Buyurtma TARKIBINI to'liq almashtirish (PATCH /orders/{id}/items). Zaxira rezervi qayta hisoblanadi."""
    model_config = ConfigDict(extra="forbid")

    items: list[OrderItemCreate] = Field(min_length=1)


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    variant_id: uuid.UUID
    quantity: int
    unit_price: Decimal
    ring_size: str | None
    bonus_snapshot: list | None
    engraving_text: str | None
    engraving_price: Decimal  # bir dona uchun (jami: (unit_price + engraving_price + box_price) * quantity)
    box_id: uuid.UUID | None
    box_price: Decimal  # bir dona box narxi (snapshot; 0 = tekin/boxsiz)
    box_label: str | None


class OrderStatusHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    from_status: str | None
    to_status: str
    changed_by: uuid.UUID | None
    created_at: datetime


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_no: str
    customer_id: uuid.UUID
    assigned_operator_id: uuid.UUID | None
    status: OrderStatus
    items_total: Decimal
    delivery_fee: Decimal
    grand_total: Decimal
    notes: str | None
    created_at: datetime
    items: list[OrderItemOut]
    history: list[OrderStatusHistoryOut]
