"""order: notes — operator/admin izohi (PATCH /orders/{id} bilan tahrirlanadi)

Revision ID: 0024_order_notes
Revises: 0023_category_sizes
Create Date: 2026-07-31
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0024_order_notes"
down_revision: Union[str, None] = "0023_category_sizes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("order", sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("order", "notes")
