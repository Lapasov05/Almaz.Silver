"""phase3 ai — knowledge_base (RAG) + tsvector GIN + pgvector hnsw

Revision ID: 0004_knowledge
Revises: 0003_inbox
Create Date: 2026-07-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0004_knowledge"
down_revision: Union[str, None] = "0003_inbox"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID = postgresql.UUID(as_uuid=True)

# models.py bilan bir xil generatsiya ifodasi
_KB_SEARCH_EXPR = (
    "to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(content, ''))"
)


def upgrade() -> None:
    op.create_table(
        "knowledge_base",
        sa.Column("id", _UUID, server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(_KB_SEARCH_EXPR, persisted=True),
            nullable=True,
        ),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_knowledge_type", "knowledge_base", ["type"])
    # TZ 6.3: RAG uchun GIN (tsvector) + hnsw (embedding)
    op.create_index(
        "ix_knowledge_search_vector", "knowledge_base", ["search_vector"], postgresql_using="gin"
    )
    op.create_index(
        "ix_knowledge_embedding",
        "knowledge_base",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_table("knowledge_base")
