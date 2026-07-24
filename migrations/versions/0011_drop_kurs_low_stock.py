"""kurs/weight_grams olib tashlash + product.low_stock_threshold

Revision ID: 0011_lowstock
Revises: 0010_kurs
Create Date: 2026-07-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011_lowstock"
down_revision: Union[str, None] = "0010_kurs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Sklad: mahsulot darajasidagi «kam qolgan» chegarasi (bo'sh -> global sozlama)
    op.add_column("product", sa.Column("low_stock_threshold", sa.Integer(), nullable=True))
    # Og'irlik kalkulyatori olib tashlandi
    op.drop_column("product", "weight_grams")
    op.drop_index("ix_kurs_category_id", table_name="kurs")
    op.drop_table("kurs")


def downgrade() -> None:
    op.create_table(
        "kurs",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("category_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("value", sa.Numeric(12, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("note", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["category.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_kurs_category_id", "kurs", ["category_id"])
    op.add_column("product", sa.Column("weight_grams", sa.Numeric(8, 3), nullable=True))
    op.drop_column("product", "low_stock_threshold")
