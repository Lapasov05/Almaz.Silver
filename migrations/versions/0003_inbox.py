"""phase2 inbox — customer, conversation, message + indekslar

Revision ID: 0003_inbox
Revises: 0002_catalog
Create Date: 2026-07-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_inbox"
down_revision: Union[str, None] = "0002_catalog"
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
    # --- customer (UNIQUE channel+external_id) ---
    op.create_table(
        "customer",
        _id_column(),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("external_id", sa.String(128), nullable=False),
        sa.Column("username", sa.String(255), nullable=True),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(32), nullable=True),
        sa.Column("language", sa.String(8), server_default="uz", nullable=False),
        sa.Column("source", sa.String(64), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("channel", "external_id", name="uq_customer_channel_external"),
    )

    # --- conversation ---
    op.create_table(
        "conversation",
        _id_column(),
        sa.Column("customer_id", _UUID, nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("ai_state", sa.String(30), server_default="greeting", nullable=False),
        sa.Column("status", sa.String(20), server_default="open", nullable=False),
        sa.Column("assigned_operator_id", _UUID, nullable=True),
        sa.Column("ai_paused_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unread_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_message", sa.Text(), nullable=True),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["customer_id"], ["customer.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assigned_operator_id"], ["user.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_conversation_customer_id", "conversation", ["customer_id"])
    # TZ 6.3: conversation(status, last_activity_at)
    op.create_index(
        "ix_conversation_status_activity", "conversation", ["status", "last_activity_at"]
    )

    # --- message ---
    op.create_table(
        "message",
        _id_column(),
        sa.Column("conversation_id", _UUID, nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("sender_type", sa.String(10), nullable=False),
        sa.Column("sender_user_id", _UUID, nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("attachments", postgresql.JSONB(), nullable=True),
        sa.Column("tool_call", postgresql.JSONB(), nullable=True),
        sa.Column("delivery_status", sa.String(12), server_default="pending", nullable=False),
        sa.Column("is_read", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("external_id", sa.String(128), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversation.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_user_id"], ["user.id"], ondelete="SET NULL"),
    )
    # TZ 6.3: message(conversation_id, created_at)
    op.create_index(
        "ix_message_conversation_created", "message", ["conversation_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_table("message")
    op.drop_table("conversation")
    op.drop_table("customer")
