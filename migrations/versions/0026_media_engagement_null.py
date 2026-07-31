"""product_media: engagement (like/view/comment) NULLABLE — NULL = hali o'lchanmagan (0 emas)

Revision ID: 0026_media_engagement_null
Revises: 0025_media_content
Create Date: 2026-07-31

Frontend "hali o'lchanmagan" (NULL) ni "hech kim ko'rmagan" (0) dan ajrата olishi uchun. IG'dan
engagement hali ulanmagan — barcha mavjud qiymatlar default 0 (o'lchanmagan) => NULL ga o'tkaziladi.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0026_media_engagement_null"
down_revision: Union[str, None] = "0025_media_content"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLS = ("like_count", "view_count", "comment_count")


def upgrade() -> None:
    for col in _COLS:
        op.alter_column("product_media", col, nullable=True, server_default=None)
    # Mavjud qiymatlar (default 0) — o'lchanmagan, NULL ga o'tkazamiz
    op.execute("UPDATE product_media SET like_count=NULL, view_count=NULL, comment_count=NULL")


def downgrade() -> None:
    op.execute(
        "UPDATE product_media SET like_count=COALESCE(like_count,0), "
        "view_count=COALESCE(view_count,0), comment_count=COALESCE(comment_count,0)"
    )
    for col in _COLS:
        op.alter_column("product_media", col, nullable=False, server_default="0")
