"""inbox CRM API — suhbatlar/xabarlar (TZ 9), RBAC bilan himoyalangan.

Ruxsatlar (TZ 13): o'qish `conversations:view`, javob yozish `conversations:create`,
transfer `conversations:transfer_chat`, assign `conversations:update`.
"""
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.core.pagination import Page, PageParams, page_params
from app.modules.identity.models import User
from app.modules.inbox.models import AiState
from app.modules.inbox.repository import InboxRepository
from app.modules.inbox.schemas import (
    AssignRequest,
    Channel,
    ConversationOut,
    ConversationStatus,
    MessageOut,
    SendMessageRequest,
    TransferRequest,
)
from app.modules.inbox.service import InboxService

router = APIRouter(prefix="/inbox", tags=["inbox"])


def get_inbox_service(db: AsyncSession = Depends(get_db)) -> InboxService:
    return InboxService(InboxRepository(db))


@router.get(
    "/conversations",
    response_model=Page[ConversationOut],
    dependencies=[Depends(require_permission("conversations:view"))],
)
async def list_conversations(
    service: InboxService = Depends(get_inbox_service),
    pp: PageParams = Depends(page_params),
    status: ConversationStatus | None = None,
    channel: Channel | None = None,
    ai_state: AiState | None = None,
    assigned_operator_id: uuid.UUID | None = None,
    unread_only: bool | None = Query(default=None, description="Faqat o'qilmagan"),
    q: str | None = Query(default=None, description="Mijoz ismi/username/id bo'yicha"),
) -> Page[ConversationOut]:
    items, total = await service.list_conversations(
        pp=pp, status=status.value if status else None,
        channel=channel.value if channel else None,
        ai_state=ai_state.value if ai_state else None,
        assigned_operator_id=assigned_operator_id, unread_only=unread_only, q=q,
    )
    return Page(items=[ConversationOut.model_validate(c) for c in items], total=total, limit=pp.limit, offset=pp.offset)


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationOut,
    dependencies=[Depends(require_permission("conversations:view"))],
)
async def get_conversation(
    conversation_id: uuid.UUID, service: InboxService = Depends(get_inbox_service)
) -> ConversationOut:
    return ConversationOut.model_validate(await service.get_conversation(conversation_id))


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=Page[MessageOut],
    dependencies=[Depends(require_permission("conversations:view"))],
)
async def list_messages(
    conversation_id: uuid.UUID,
    service: InboxService = Depends(get_inbox_service),
    pp: PageParams = Depends(page_params),
    direction: str | None = Query(default=None, description="incoming | outgoing"),
    sender_type: str | None = Query(default=None, description="customer | ai | operator | system"),
) -> Page[MessageOut]:
    items, total = await service.list_messages(
        conversation_id, pp=pp, direction=direction, sender_type=sender_type
    )
    return Page(items=[MessageOut.model_validate(m) for m in items], total=total, limit=pp.limit, offset=pp.offset)


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageOut,
)
async def send_message(
    conversation_id: uuid.UUID,
    payload: SendMessageRequest,
    service: InboxService = Depends(get_inbox_service),
    user: User = Depends(require_permission("conversations:create")),
) -> MessageOut:
    """Operator javobi — AI 15 daqiqa pauza qiladi (TZ 9)."""
    message = await service.operator_send(conversation_id, user.id, payload.text)
    return MessageOut.model_validate(message)


@router.post(
    "/conversations/{conversation_id}/read",
    response_model=ConversationOut,
    dependencies=[Depends(require_permission("conversations:view"))],
)
async def mark_read(
    conversation_id: uuid.UUID, service: InboxService = Depends(get_inbox_service)
) -> ConversationOut:
    return ConversationOut.model_validate(await service.mark_read(conversation_id))


@router.post(
    "/conversations/{conversation_id}/transfer",
    response_model=ConversationOut,
)
async def transfer_chat(
    conversation_id: uuid.UUID,
    payload: TransferRequest,
    service: InboxService = Depends(get_inbox_service),
    user: User = Depends(require_permission("conversations:transfer_chat")),
) -> ConversationOut:
    target = payload.operator_id or user.id
    conv = await service.transfer_chat(conversation_id, target, user.id, payload.reason)
    return ConversationOut.model_validate(conv)


@router.post(
    "/conversations/{conversation_id}/assign",
    response_model=ConversationOut,
    dependencies=[Depends(require_permission("conversations:update"))],
)
async def assign(
    conversation_id: uuid.UUID,
    payload: AssignRequest,
    service: InboxService = Depends(get_inbox_service),
) -> ConversationOut:
    return ConversationOut.model_validate(
        await service.assign(conversation_id, payload.operator_id)
    )
