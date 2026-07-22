"""engraving — uzukka ism yozish xizmati (product flag/narx + order_item matn/narx)

Revision ID: 0008_engraving
Revises: 0007_audit
Create Date: 2026-07-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_engraving"
down_revision: Union[str, None] = "0007_audit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- product: shu mahsulotga ism yozish mumkinmi + ixtiyoriy narx override ---
    op.add_column(
        "product",
        sa.Column("engraving_available", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column("product", sa.Column("engraving_price", sa.Numeric(12, 2), nullable=True))

    # --- order_item: yoziladigan ism + buyurtma vaqtidagi narx snapshot'i ---
    op.add_column("order_item", sa.Column("engraving_text", sa.String(50), nullable=True))
    op.add_column(
        "order_item",
        sa.Column("engraving_price", sa.Numeric(12, 2), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("order_item", "engraving_price")
    op.drop_column("order_item", "engraving_text")
    op.drop_column("product", "engraving_price")
    op.drop_column("product", "engraving_available")
