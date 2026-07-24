"""kurs (gramm narxi, kategoriyaga ulangan) — category.gram_price o'rniga

Revision ID: 0010_kurs
Revises: 0009_catalog_i18n
Create Date: 2026-07-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_kurs"
down_revision: Union[str, None] = "0009_catalog_i18n"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "kurs",
        sa.Column("id", _UUID, server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("category_id", _UUID, nullable=False),
        sa.Column("value", sa.Numeric(12, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("note", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["category.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_kurs_category_id", "kurs", ["category_id"])

    # Mavjud category.gram_price -> kurs yozuvi (ko'chirish)
    op.execute(
        "INSERT INTO kurs (category_id, value, is_active, note) "
        "SELECT id, gram_price, true, 'migratsiya 0009->0010' FROM category WHERE gram_price IS NOT NULL"
    )
    op.drop_column("category", "gram_price")


def downgrade() -> None:
    op.add_column("category", sa.Column("gram_price", sa.Numeric(12, 2), nullable=True))
    op.execute(
        "UPDATE category c SET gram_price = k.value FROM ("
        "  SELECT DISTINCT ON (category_id) category_id, value FROM kurs "
        "  WHERE is_active = true ORDER BY category_id, created_at DESC"
        ") k WHERE k.category_id = c.id"
    )
    op.drop_table("kurs")
