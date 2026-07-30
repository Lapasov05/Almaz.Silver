"""product: engraving_max_chars — gravyurkaga sig'adigan belgi limiti (har uzukka mos)

Revision ID: 0022_engraving_max_chars
Revises: 0021_warranty_resize
Create Date: 2026-07-30

Ba'zi uzuklarga 3 ta belgi (masalan "A&B"), ba'zilariga to'liq ism (masalan "Abdug'ani & Falonchioy")
sig'adi. Har mahsulotда o'z limiti; NULL bo'lsa global settings.engraving_max_chars ishlaydi.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0022_engraving_max_chars"
down_revision: Union[str, None] = "0021_warranty_resize"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("product", sa.Column("engraving_max_chars", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("product", "engraving_max_chars")
