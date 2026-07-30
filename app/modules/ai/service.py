"""ai Service qatlami — knowledge base CRUD + AgentService (agent kirish nuqtasi)."""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.modules.ai.agent import Agent, AgentOutcome
from app.modules.ai.llm.base import LLMProvider
from app.modules.ai.llm.factory import get_llm_provider
from app.modules.ai.models import KnowledgeBase
from app.modules.ai.repository import KnowledgeRepository
from app.modules.inbox.repository import InboxRepository

# provider berilmaganini (None dan farqli) bildiruvchi sentinel
_UNSET = object()


class KnowledgeService:
    def __init__(self, repo: KnowledgeRepository):
        self.repo = repo

    async def create(self, *, type_: str, title: str, content: str) -> KnowledgeBase:
        kb = KnowledgeBase(type=type_, title=title, content=content)
        await self.repo.add(kb)
        await self.repo.db.commit()
        return await self.repo.get(kb.id)

    async def list_all(self, *, type_=None, q=None, pp=None):
        return await self.repo.list_all(type_=type_, q=q, pp=pp)

    async def get(self, kb_id: uuid.UUID) -> KnowledgeBase:
        kb = await self.repo.get(kb_id)
        if kb is None:
            raise NotFoundError("Knowledge base yozuvi topilmadi")
        return kb

    async def update(self, kb_id: uuid.UUID, data: dict) -> KnowledgeBase:
        kb = await self.get(kb_id)
        for field, value in data.items():
            setattr(kb, field, value)
        await self.repo.db.commit()
        return await self.get(kb_id)

    async def delete(self, kb_id: uuid.UUID) -> None:
        kb = await self.get(kb_id)
        await self.repo.db.delete(kb)
        await self.repo.db.commit()


class AgentService:
    """AI agent kirish nuqtasi — worker/CRM shu orqali agentni ishga tushiradi.

    provider berilmasa, sozlamaga qarab tanlanadi (get_llm_provider); kalit yo'q bo'lsa None.
    """

    def __init__(self, db: AsyncSession, provider: LLMProvider | None | object = _UNSET):
        self.db = db
        self._provider_arg = provider  # _UNSET -> DB'дан olinadi (get_llm_provider)

    async def _resolve_provider(self) -> LLMProvider | None:
        if self._provider_arg is not _UNSET:
            return self._provider_arg  # test/qo'lda berilgan (FakeProvider yoki None)
        return await get_llm_provider(self.db)

    async def respond(
        self, conversation_id: uuid.UUID, *, force: bool = False, trigger_message_id: uuid.UUID | None = None
    ) -> AgentOutcome:
        provider = await self._resolve_provider()
        return await Agent(self.db, provider).respond(
            conversation_id, force=force, trigger_message_id=trigger_message_id
        )

    async def handle_incoming_message(self, message_id: uuid.UUID) -> AgentOutcome:
        message = await InboxRepository(self.db).get_message(message_id)
        if message is None:
            raise NotFoundError("Xabar topilmadi")
        # trigger_message_id — debounce uchun: shu xabardan keyin yangi xabar kelsa, bu javob eskiradi
        return await self.respond(message.conversation_id, trigger_message_id=message_id)
