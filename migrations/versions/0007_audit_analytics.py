"""phase6 — audit_log, notification + order.created_by_ai (KPI)

Revision ID: 0007_audit
Revises: 0006_payments
Create Date: 2026-07-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_audit"
down_revision: Union[str, None] = "0006_payments"
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
    # --- audit_log (TZ 6.2/15) ---
    op.create_table(
        "audit_log",
        _id_column(),
        sa.Column("actor_id", _UUID, nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", _UUID, nullable=True),
        sa.Column("before", postgresql.JSONB(), nullable=True),
        sa.Column("after", postgresql.JSONB(), nullable=True),
        sa.Column("ip", sa.String(64), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["actor_id"], ["user.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_audit_log_actor_id", "audit_log", ["actor_id"])
    op.create_index("ix_audit_log_action", "audit_log", ["action"])
    op.create_index("ix_audit_log_entity_type", "audit_log", ["entity_type"])

    # --- notification (TZ 4/12) ---
    op.create_table(
        "notification",
        _id_column(),
        sa.Column("type", sa.String(48), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("target", sa.String(128), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(12), server_default="pending", nullable=False),
        sa.Column("entity_type", sa.String(48), nullable=True),
        sa.Column("entity_id", _UUID, nullable=True),
        *_timestamps(),
    )

    # --- order.created_by_ai (TZ 1 KPI 3) ---
    op.add_column(
        "order",
        sa.Column("created_by_ai", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("order", "created_by_ai")
    op.drop_table("notification")
    op.drop_table("audit_log")
