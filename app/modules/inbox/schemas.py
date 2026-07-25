"""inbox Pydantic DTO'lari."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.inbox.models import (
    AiState,
    Channel,
    ConversationStatus,
    DeliveryStatus,
    MessageDirection,
    SenderType,
)


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    channel: Channel
    external_id: str
    username: str | None
    full_name: str | None
    language: str


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    customer_id: uuid.UUID
    channel: Channel
    ai_state: AiState
    status: ConversationStatus
    assigned_operator_id: uuid.UUID | None
    ai_enabled: bool
    ai_paused_until: datetime | None
    unread_count: int
    last_message: str | None
    last_activity_at: datetime
    customer: CustomerOut | None = None


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    direction: MessageDirection
    sender_type: SenderType
    sender_user_id: uuid.UUID | None
    content: str | None
    attachments: list | None
    delivery_status: DeliveryStatus
    is_read: bool
    created_at: datetime


class SendMessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class TransferRequest(BaseModel):
    operator_id: uuid.UUID | None = None  # None -> o'ziga oladi (current user)
    reason: str | None = Field(default=None, max_length=255)


class AssignRequest(BaseModel):
    operator_id: uuid.UUID


class AiControlRequest(BaseModel):
    """Shu suhbatда AI'ni boshqarish (operator qo'lda)."""

    # pause_minutes: N daqiqaga · pause_until: aniq sana-vaqtgacha · off: butunlay o'chir · on: yoq
    mode: str = Field(pattern="^(pause_minutes|pause_until|off|on)$")
    minutes: int | None = Field(default=None, ge=1)      # pause_minutes uchun
    until: datetime | None = None                         # pause_until uchun (kelajakda)
