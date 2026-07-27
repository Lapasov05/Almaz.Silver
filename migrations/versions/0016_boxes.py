"""box (kategoriyaning rangli qutisi) + order_item box maydonlari (snapshot)

Revision ID: 0016_boxes
Revises: 0015_msg_extid
Create Date: 2026-07-27

Har kategoriya o'z rang ro'yxatiga ega (dynamic). Har rang alohida yozuv: o'z narxi
(0=tekin) + o'z zaxirasi (Variant kabi, TZ 10 reservation). Buyurtmada order_item.box_*
snapshot bilan saqlanadi (keyin box o'zgarsa eski buyurtma o'zgarmaydi).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision: str = "0016_boxes"
down_revision: Union[str, None] = "0015_msg_extid"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "box",
        sa.Column("id", PgUUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column(
            "category_id", PgUUID(as_uuid=True),
            sa.ForeignKey("category.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("name_uz", sa.String(100), nullable=False),   # rang nomi
        sa.Column("name_ru", sa.String(100), nullable=True),
        sa.Column("color_hex", sa.String(9), nullable=True),
        sa.Column("price", sa.Numeric(12, 2), server_default="0", nullable=False),  # 0 = tekin
        sa.Column("stock_qty", sa.Integer(), server_default="0", nullable=False),
        sa.Column("reserved_qty", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_box_category_id", "box", ["category_id"])
    op.create_index("ix_box_category_active", "box", ["category_id", "is_active"])

    # order_item ga box maydonlari (o'lcham/gravyurka kabi, snapshot)
    op.add_column("order_item", sa.Column("box_id", PgUUID(as_uuid=True), nullable=True))
    op.add_column("order_item", sa.Column("box_price", sa.Numeric(12, 2), server_default="0", nullable=False))
    op.add_column("order_item", sa.Column("box_label", sa.String(150), nullable=True))
    op.create_foreign_key(
        "fk_order_item_box", "order_item", "box", ["box_id"], ["id"], ondelete="SET NULL"
    )


def downgrade() -> None:
    op.drop_constraint("fk_order_item_box", "order_item", type_="foreignkey")
    op.drop_column("order_item", "box_label")
    op.drop_column("order_item", "box_price")
    op.drop_column("order_item", "box_id")
    op.drop_index("ix_box_category_active", table_name="box")
    op.drop_index("ix_box_category_id", table_name="box")
    op.drop_table("box")
