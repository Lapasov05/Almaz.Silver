"""integrations — integration_config (DB-driven token) + integration_event (xom payload audit)

Revision ID: 0014_integr
Revises: 0013_req_size
Create Date: 2026-07-26
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014_integr"
down_revision: Union[str, None] = "0013_req_size"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID = postgresql.UUID(as_uuid=True)


def _ts():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "integration_config",
        sa.Column("id", _UUID, server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        *_ts(),
        sa.UniqueConstraint("provider", "key", name="uq_integration_provider_key"),
    )
    op.create_index("ix_integration_config_provider", "integration_config", ["provider"])

    op.create_table(
        "integration_event",
        sa.Column("id", _UUID, server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("direction", sa.String(10), server_default="inbound", nullable=False),
        sa.Column("raw", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(16), server_default="received", nullable=False),
        sa.Column("note", sa.String(255), nullable=True),
        *_ts(),
    )
    op.create_index("ix_integration_event_provider", "integration_event", ["provider"])
    op.create_index("ix_integration_event_status", "integration_event", ["status"])


def downgrade() -> None:
    op.drop_table("integration_event")
    op.drop_table("integration_config")
