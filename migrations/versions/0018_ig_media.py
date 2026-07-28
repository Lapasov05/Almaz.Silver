"""product_media: media_type + story_ref + expires_at + is_active (Instagram story/post)

Revision ID: 0018_ig_media
Revises: 0017_combos
Create Date: 2026-07-28

Mijoz IG post/story linkini tashlasa yoki story'ga javob bersa, AI mahsulotni topadi.
- media_type: image | post | reel | story
- story_ref: story media_id (webhook reply_to.story.id bilan mos) — unique
- expires_at: story 24 soat (post/reel = NULL)
- is_active: yoqilgan/o'chirilgan
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018_ig_media"
down_revision: Union[str, None] = "0017_combos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("product_media", sa.Column("media_type", sa.String(20), server_default="image", nullable=False))
    op.add_column("product_media", sa.Column("story_ref", sa.String(128), nullable=True))
    op.add_column("product_media", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("product_media", sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False))
    op.create_unique_constraint("uq_product_media_story_ref", "product_media", ["story_ref"])
    op.create_index("ix_product_media_media_type", "product_media", ["media_type"])


def downgrade() -> None:
    op.drop_index("ix_product_media_media_type", table_name="product_media")
    op.drop_constraint("uq_product_media_story_ref", "product_media", type_="unique")
    op.drop_column("product_media", "is_active")
    op.drop_column("product_media", "expires_at")
    op.drop_column("product_media", "story_ref")
    op.drop_column("product_media", "media_type")
