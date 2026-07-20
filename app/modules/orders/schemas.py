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


class OrderCreate(BaseModel):
    customer_id: uuid.UUID
    items: list[OrderItemCreate] = Field(min_length=1)


class OrderCancel(BaseModel):
    reason: str | None = Field(default=None, max_length=255)


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    variant_id: uuid.UUID
    quantity: int
    unit_price: Decimal
    ring_size: str | None
    bonus_snapshot: list | None


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
    created_at: datetime
    items: list[OrderItemOut]
    history: list[OrderStatusHistoryOut]
