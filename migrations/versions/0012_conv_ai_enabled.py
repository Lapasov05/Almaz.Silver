"""conversation.ai_enabled — shu suhbatда AI'ni butunlay o'chirish imkoni

Revision ID: 0012_ai_enabled
Revises: 0011_lowstock
Create Date: 2026-07-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_ai_enabled"
down_revision: Union[str, None] = "0011_lowstock"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversation",
        sa.Column("ai_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("conversation", "ai_enabled")
