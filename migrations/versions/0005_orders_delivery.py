"""phase4 orders+delivery — order, order_item, order_status_history, delivery, checkout_token

Revision ID: 0005_orders
Revises: 0004_knowledge
Create Date: 2026-07-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_orders"
down_revision: Union[str, None] = "0004_knowledge"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID = postgresql.UUID(as_uuid=True)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def _id_column() -> sa.Column:
    return sa.Column("id", _UUID, server_default=sa.text("gen_random_uuid()"), primary_key=True)


def upgrade() -> None:
    # --- order ---
    op.create_table(
        "order",
        _id_column(),
        sa.Column("order_no", sa.String(32), nullable=False),
        sa.Column("customer_id", _UUID, nullable=False),
        sa.Column("assigned_operator_id", _UUID, nullable=True),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("items_total", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("delivery_fee", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("grand_total", sa.Numeric(12, 2), server_default="0", nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["customer_id"], ["customer.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assigned_operator_id"], ["user.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("order_no", name="uq_order_no"),
    )
    op.create_index("ix_order_no", "order", ["order_no"])
    op.create_index("ix_order_customer_id", "order", ["customer_id"])
    op.create_index("ix_order_status", "order", ["status"])

    # --- order_item ---
    op.create_table(
        "order_item",
        _id_column(),
        sa.Column("order_id", _UUID, nullable=False),
        sa.Column("variant_id", _UUID, nullable=False),
        sa.Column("quantity", sa.Integer(), server_default="1", nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("ring_size", sa.String(10), nullable=True),
        sa.Column("bonus_snapshot", postgresql.JSONB(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["order_id"], ["order.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["variant_id"], ["variant.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_order_item_order_id", "order_item", ["order_id"])

    # --- order_status_history ---
    op.create_table(
        "order_status_history",
        _id_column(),
        sa.Column("order_id", _UUID, nullable=False),
        sa.Column("from_status", sa.String(20), nullable=True),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("changed_by", _UUID, nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["order_id"], ["order.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["changed_by"], ["user.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_order_status_history_order_id", "order_status_history", ["order_id"])

    # --- delivery (order_id UNIQUE) ---
    op.create_table(
        "delivery",
        _id_column(),
        sa.Column("order_id", _UUID, nullable=False),
        sa.Column("zone", sa.String(20), nullable=True),
        sa.Column("provider", sa.String(20), nullable=True),
        sa.Column("fee", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("address_text", sa.Text(), nullable=True),
        sa.Column("lat", sa.Numeric(9, 6), nullable=True),
        sa.Column("lng", sa.Numeric(9, 6), nullable=True),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["order_id"], ["order.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("order_id", name="uq_delivery_order"),
    )

    # --- checkout_token ---
    op.create_table(
        "checkout_token",
        _id_column(),
        sa.Column("order_id", _UUID, nullable=False),
        sa.Column("delivery_id", _UUID, nullable=True),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["order_id"], ["order.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["delivery_id"], ["delivery.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("token_hash", name="uq_checkout_token_hash"),
    )
    op.create_index("ix_checkout_token_order_id", "checkout_token", ["order_id"])
    op.create_index("ix_checkout_token_hash", "checkout_token", ["token_hash"])


def downgrade() -> None:
    op.drop_table("checkout_token")
    op.drop_table("delivery")
    op.drop_table("order_status_history")
    op.drop_table("order_item")
    op.drop_table("order")
