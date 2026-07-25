"""category.requires_ring_size — faqat Uzuklarда o'lcham (qolganlari universal)

Revision ID: 0013_req_size
Revises: 0012_ai_enabled
Create Date: 2026-07-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013_req_size"
down_revision: Union[str, None] = "0012_ai_enabled"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "category",
        sa.Column("requires_ring_size", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    # Mavjud «Uzuklar» kategoriyalarini o'lchamli deb belgilaymiz (nom bo'yicha, uz/ru)
    op.execute(
        "UPDATE category SET requires_ring_size = true "
        "WHERE lower(name_uz) LIKE '%uzuk%' OR lower(coalesce(name_ru,'')) LIKE '%кольц%'"
    )


def downgrade() -> None:
    op.drop_column("category", "requires_ring_size")
