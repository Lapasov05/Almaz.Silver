"""phase5 payments — payment_card, payment

Revision ID: 0006_payments
Revises: 0005_orders
Create Date: 2026-07-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_payments"
down_revision: Union[str, None] = "0005_orders"
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
    # --- payment_card ---
    op.create_table(
        "payment_card",
        _id_column(),
        sa.Column("holder_name", sa.String(255), nullable=False),
        sa.Column("card_number_masked", sa.String(32), nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        *_timestamps(),
    )

    # --- payment (order_id UNIQUE) ---
    op.create_table(
        "payment",
        _id_column(),
        sa.Column("order_id", _UUID, nullable=False),
        sa.Column("card_id", _UUID, nullable=True),
        sa.Column("status", sa.String(12), server_default="pending", nullable=False),
        sa.Column("receipt_url", sa.String(500), nullable=True),
        sa.Column("payer_name", sa.String(255), nullable=True),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column("reviewed_by", _UUID, nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["order_id"], ["order.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["card_id"], ["payment_card.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["user.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("order_id", name="uq_payment_order"),
    )
    op.create_index("ix_payment_status", "payment", ["status"])


def downgrade() -> None:
    op.drop_table("payment")
    op.drop_table("payment_card")
