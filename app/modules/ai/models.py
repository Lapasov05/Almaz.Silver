"""ai ORM modellari — knowledge_base (RAG manbasi, TZ 6.2 / 7.6).

Promptlar versiyalash `settings.prompt_version` orqali (alohida jadval shart emas).
"""
import enum

from pgvector.sqlalchemy import Vector
from sqlalchemy import Computed, String, Text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import Base, TimestampMixin, UUIDMixin


class KnowledgeType(str, enum.Enum):
    faq = "faq"
    policy = "policy"
    delivery = "delivery"
    payment = "payment"
    company = "company"
    guarantee = "guarantee"
    instruction = "instruction"


# to_tsvector manbasi: title + content ('simple' — o'zbekcha uchun xavfsiz)
_KB_SEARCH_EXPR = (
    "to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(content, ''))"
)


class KnowledgeBase(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_base"

    type: Mapped[KnowledgeType] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # TZ 6.3: GIN (tsvector) — Faza 3'da tayyor; embedding (hnsw) generatsiyasi kalit bilan
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed(_KB_SEARCH_EXPR, persisted=True), nullable=True
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
