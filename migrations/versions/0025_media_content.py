"""product_media: caption + status + scheduled_at + engagement (like/view/comment) — kontent boshqaruvi

Revision ID: 0025_media_content
Revises: 0024_order_notes
Create Date: 2026-07-31

Instagram kontent (media)ni rejalashtirish (status/scheduled_at) va samaradorlikni (engagement) ko'rish uchun.
status: draft | scheduled | published (default published — mavjud media e'lon qilingan hisoblanadi).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0025_media_content"
down_revision: Union[str, None] = "0024_order_notes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("product_media", sa.Column("caption", sa.Text(), nullable=True))
    op.add_column("product_media", sa.Column("status", sa.String(20), server_default="published", nullable=False))
    op.add_column("product_media", sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("product_media", sa.Column("like_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("product_media", sa.Column("view_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("product_media", sa.Column("comment_count", sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    for col in ("comment_count", "view_count", "like_count", "scheduled_at", "status", "caption"):
        op.drop_column("product_media", col)
