"""payments Pydantic DTO'lari."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.payments.models import PaymentStatus


# ---------- Payment Card ----------
class PaymentCardCreate(BaseModel):
    holder_name: str = Field(min_length=1, max_length=255)
    card_number_masked: str = Field(min_length=4, max_length=32)
    is_primary: bool = False
    is_active: bool = True


class PaymentCardUpdate(BaseModel):
    holder_name: str | None = Field(default=None, max_length=255)
    card_number_masked: str | None = Field(default=None, max_length=32)
    is_primary: bool | None = None
    is_active: bool | None = None


class PaymentCardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    holder_name: str
    card_number_masked: str
    is_primary: bool
    is_active: bool


# ---------- Payment ----------
class PaymentSubmit(BaseModel):
    order_id: uuid.UUID
    receipt_url: str = Field(max_length=500)
    payer_name: str = Field(min_length=1, max_length=255)


class PaymentReject(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID
    card_id: uuid.UUID | None
    status: PaymentStatus
    receipt_url: str | None
    payer_name: str | None
    reject_reason: str | None
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None
    created_at: datetime


class ReceiptUploadOut(BaseModel):
    url: str
    key: str
