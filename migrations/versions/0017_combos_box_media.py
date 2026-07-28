"""combo (product.is_combo + combo_item) + box_media (box galereya)

Revision ID: 0017_combos
Revises: 0016_boxes
Create Date: 2026-07-27

- product.is_combo: mahsulot combo (to'plam) ekanligini bildiradi. Combo o'z narxiga ega,
  lekin o'z zaxirasi yo'q — sotilganda combo_item'dagi komponent variantlar zaxirasi band bo'ladi.
- combo_item: combo tarkibi (combo_product_id -> component_variant_id + quantity).
- box_media: box (rangli quti) galereyasi (bir nechta rasm URL).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision: str = "0017_combos"
down_revision: Union[str, None] = "0016_boxes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _id():
    return sa.Column("id", PgUUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True)


def _ts():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    # product.is_combo
    op.add_column("product", sa.Column("is_combo", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.create_index("ix_product_is_combo", "product", ["is_combo"])

    # combo_item (combo tarkibi)
    op.create_table(
        "combo_item",
        _id(), *_ts(),
        sa.Column("combo_product_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("product.id", ondelete="CASCADE"), nullable=False),
        sa.Column("component_variant_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("variant.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Integer(), server_default="1", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.UniqueConstraint("combo_product_id", "component_variant_id", name="uq_combo_item"),
    )
    op.create_index("ix_combo_item_combo", "combo_item", ["combo_product_id"])

    # box_media (box galereya)
    op.create_table(
        "box_media",
        _id(), *_ts(),
        sa.Column("box_id", PgUUID(as_uuid=True), sa.ForeignKey("box.id", ondelete="CASCADE"), nullable=False),
        sa.Column("image_url", sa.String(500), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_index("ix_box_media_box", "box_media", ["box_id"])


def downgrade() -> None:
    op.drop_index("ix_box_media_box", table_name="box_media")
    op.drop_table("box_media")
    op.drop_index("ix_combo_item_combo", table_name="combo_item")
    op.drop_table("combo_item")
    op.drop_index("ix_product_is_combo", table_name="product")
    op.drop_column("product", "is_combo")
