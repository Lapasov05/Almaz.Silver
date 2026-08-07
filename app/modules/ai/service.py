"""ai Service qatlami — knowledge base CRUD + AgentService (agent kirish nuqtasi)."""
import asyncio
import time
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.core.redis_lock import redis_lock
from app.modules.ai.agent import Agent, AgentOutcome
from app.modules.ai.coalesce import already_answered
from app.modules.ai.llm.base import LLMProvider
from app.modules.ai.llm.factory import get_llm_provider
from app.modules.ai.models import KnowledgeBase
from app.modules.ai.repository import KnowledgeRepository
from app.modules.inbox.repository import InboxRepository

settings = get_settings()

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
        self,
        conversation_id: uuid.UUID,
        *,
        force: bool = False,
        started_at: float | None = None,
    ) -> AgentOutcome:
        provider = await self._resolve_provider()
        return await Agent(self.db, provider).respond(
            conversation_id, force=force, started_at=started_at
        )

    async def handle_incoming_message(self, message_id: uuid.UUID) -> AgentOutcome:
        """Kelgan xabarga javob — mijoz ketma-ket yozsa ham FAQAT BITTA javob ketadi.

        Har kiruvchi xabar alohida Celery task ochadi. Ular parallel ishlasa bir xil javob
        ikki marta yuboriladi. Uch qatlam bilan oldi olinadi:
          1. qisqa kutish — mijoz yozib bo'lsin (xabarlar bitta javobga jamlanadi);
          2. suhbat qulfi — bir vaqtda bitta javob generatsiyasi;
          3. "qayergacha javob berildi" belgisi — qamrab olingan xabarga qayta javob berilmaydi.
        """
        started_at = time.monotonic()
        repo = InboxRepository(self.db)
        message = await repo.get_message(message_id)
        if message is None:
            raise NotFoundError("Xabar topilmadi")
        # rollback obyektni "expire" qiladi — kerakli qiymatlarni oldindan olamiz
        conversation_id = message.conversation_id
        message_created_at = message.created_at

        if settings.ai_burst_wait_seconds > 0:
            await asyncio.sleep(settings.ai_burst_wait_seconds)
            await self.db.rollback()  # kutish davomida kelgan xabarlarni ko'rish uchun yangi snapshot

        async with redis_lock(
            f"ai:respond:{conversation_id}",
            wait_seconds=settings.ai_lock_wait_seconds,
        ) as acquired:
            if not acquired:
                return AgentOutcome(status="skipped", reason="busy")
            await self.db.rollback()  # qulfni kutgan bo'lsak — oldingi javob allaqachon yozilgan
            last_incoming = await repo.get_last_incoming_message(conversation_id)
            if last_incoming is not None and last_incoming.id != message_id:
                # Yangiroq xabar bor — javobni o'sha task beradi (bu xabar ham kontekstga kiradi)
                return AgentOutcome(status="skipped", reason="superseded")
            if await already_answered(conversation_id, message_created_at):
                return AgentOutcome(status="skipped", reason="already_answered")
            return await self.respond(conversation_id, started_at=started_at)
