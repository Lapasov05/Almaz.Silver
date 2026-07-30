"""product: warranty_months + resize_available + resize_price (kafolat + o'lcham o'zgartirish)

Revision ID: 0021_warranty_resize
Revises: 0020_bts_location
Create Date: 2026-07-30

Garantiya (kafolat): global default settings.warranty_months, mahsulotда override `warranty_months`.
O'lcham o'zgartirish (zargar): uzuk o'lchami to'g'ri kelmasa zargar moslaydi — global settings.resize_price,
mahsulotда `resize_price` override; `resize_available` bilan mahsulot darajasida o'chirsa bo'ladi.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0021_warranty_resize"
down_revision: Union[str, None] = "0020_bts_location"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("product", sa.Column("warranty_months", sa.Integer(), nullable=True))
    op.add_column(
        "product",
        sa.Column("resize_available", sa.Boolean(), server_default="true", nullable=False),
    )
    op.add_column("product", sa.Column("resize_price", sa.Numeric(12, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("product", "resize_price")
    op.drop_column("product", "resize_available")
    op.drop_column("product", "warranty_months")
