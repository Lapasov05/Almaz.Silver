"""Agent xotirasi (TZ 7.3) — qisqa muddat (oxirgi N xabar) + uzoq muddat (mijoz profili)."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai.guardrail import sanitize_user_input
from app.modules.ai.llm.base import LlmMessage
from app.modules.inbox.models import Conversation, Customer
from app.modules.inbox.repository import InboxRepository


async def build_messages(
    db: AsyncSession,
    conversation: Conversation,
    customer: Customer,
    system_prompt: str,
    memory_limit: int,
) -> list[LlmMessage]:
    """LLM'ga uzatiladigan xabarlar ro'yxatini yig'adi (system + profil + tarix)."""
    messages: list[LlmMessage] = [LlmMessage(role="system", content=system_prompt)]

    # Uzoq muddat: mijoz profili (takroriy so'ramaslik uchun)
    profile = [f"kanal: {conversation.channel}", f"til: {customer.language}"]
    if customer.full_name:
        profile.append(f"ism: {customer.full_name}")
    if customer.username:
        profile.append(f"username: @{customer.username}")
    messages.append(LlmMessage(role="system", content="Mijoz profili — " + ", ".join(profile)))

    # Qisqa muddat: oxirgi N xabar (xronologik)
    history = await InboxRepository(db).list_recent_messages(conversation.id, memory_limit)
    for m in history:
        if m.sender_type == "customer":
            messages.append(LlmMessage(role="user", content=sanitize_user_input(m.content)))
        elif m.sender_type in ("ai", "operator") and m.content:
            messages.append(LlmMessage(role="assistant", content=m.content))
        # system xabarlar (transfer va h.k.) LLM'ga uzatilmaydi
    return messages
