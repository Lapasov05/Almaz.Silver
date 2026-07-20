"""ai Repository qatlami — knowledge_base CRUD + qidiruv (TZ 7.6 RAG)."""
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai.models import KnowledgeBase


class KnowledgeRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add(self, obj: KnowledgeBase) -> KnowledgeBase:
        self.db.add(obj)
        await self.db.flush()
        return obj

    async def get(self, kb_id: uuid.UUID) -> KnowledgeBase | None:
        return await self.db.get(KnowledgeBase, kb_id)

    async def list_all(self, *, type_: str | None = None) -> list[KnowledgeBase]:
        stmt = select(KnowledgeBase)
        if type_ is not None:
            stmt = stmt.where(KnowledgeBase.type == type_)
        stmt = stmt.order_by(KnowledgeBase.type, KnowledgeBase.title)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def search_text(self, query: str, limit: int = 3) -> list[KnowledgeBase]:
        """tsvector RAG qidiruvi (TZ 6.3 GIN). Embedding (hnsw) — kalit bo'lganda."""
        tsquery = func.websearch_to_tsquery("simple", query)
        rank = func.ts_rank(KnowledgeBase.search_vector, tsquery)
        stmt = (
            select(KnowledgeBase)
            .where(KnowledgeBase.search_vector.op("@@")(tsquery))
            .order_by(rank.desc())
            .limit(limit)
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def exists_title(self, title: str) -> bool:
        res = await self.db.execute(
            select(KnowledgeBase.id).where(KnowledgeBase.title == title).limit(1)
        )
        return res.scalar_one_or_none() is not None
